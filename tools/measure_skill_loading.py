#!/usr/bin/env python3
"""Measure which catalogue skills an agent loads under a short prompt, and whether it loads them before
it writes anything.

Each prompt in `tools/skill_prompts.json`, at each strictness level, runs through `claude -p` in a fresh
git repository in a temporary directory: empty for a new service, or a copy of a project under
`tools/skill_fixtures/`. Only this checkout's plugins are loaded (`--plugin-dir`), and user settings are
excluded, so neither the maintainer's own configuration nor an installed release takes part. The stream
of tool calls is kept as it came and read without a model: which skills the `Skill` tool loaded, which
catalogue files were read directly, and where the first write fell — a `Write`, an `Edit`, or a shell
command that writes a file or scaffolds a project.

By default a run stops at its first write, which is all the trace question needs. `--full` lets it
finish and keeps the files it wrote, for reading what the code looks like; that reading stays a
person's. The prompt set is fixed so runs stay comparable across releases: add a prompt rather than
rewording one.

    python3 tools/measure_skill_loading.py --out .sources/experiments/<date>-<name>
    python3 tools/measure_skill_loading.py --out <dir> --only hex-crud,cli-tool --levels competing --repeat 3
    python3 tools/measure_skill_loading.py --out <dir> --setup          # as /pyhouse:setup leaves a repo
    python3 tools/measure_skill_loading.py --out <dir> --plugins none   # the control: no catalogue
    python3 tools/measure_skill_loading.py --out <dir> --report-only    # rebuild report.md from raw/

Raw streams go to `<out>/raw/`, one summary line per run to `<out>/summary.jsonl`, and the tables to
`<out>/report.md`. Raw output belongs in the sources repository, not in this one.

Every run is a full Opus session drawn on the account running it. The whole set at both levels, 42
runs, emptied a subscription's five-hour usage window in minutes (D210). Start with `--only` and two
or three prompts, `--jobs 1`, and run more only once the maintainer has agreed to that batch.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = ROOT / "plugins"
FIXTURES = ROOT / "tools" / "skill_fixtures"
ADOPT = PLUGINS / "pyhouse-universal" / "commands" / "adopt.md"
SETUP_LISTING_FRACTION = 0.03  # what /pyhouse:setup step 6 writes

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
BASH_WRITE = re.compile(
    r"(?<![0-9&>])>{1,2}\s*(?!&|/dev/null)[\w./~$\"'-]"  # a redirect into a file
    r"|\btee\b"
    r"|\b(?:uv init|poetry new|cookiecutter|copier copy|django-admin startproject)\b"  # a scaffold
)


@dataclass(frozen=True)
class Run:
    prompt: dict
    level: str
    rep: int

    @property
    def run_id(self) -> str:
        return f"{self.prompt['id']}__{self.level}__{self.rep}"


def catalogue_plugins(choice: str) -> list[Path]:
    if choice == "none":
        return []
    if choice == "all":
        return sorted(p for p in PLUGINS.iterdir() if (p / "skills").is_dir())
    paths = [PLUGINS / name.strip() for name in choice.split(",")]
    for path in paths:
        if not (path / ".claude-plugin" / "plugin.json").is_file():
            sys.exit(f"not a plugin of this checkout: {path.name}")
    return paths


def adopt_section(family: str | None, repo: str) -> str:
    """The section /pyhouse-universal:adopt writes, read from the command so it never goes stale."""
    text = ADOPT.read_text()
    block = re.search(r"```markdown\n(.*?)```", text, re.S)
    if block is None:
        sys.exit(f"no section template found in {ADOPT}")
    lines = block.group(1).rstrip("\n").split("\n")
    if repo == "library":
        lines = [line for line in lines if not line.startswith("| start a new service")]
    if family is not None:
        layout = {"hex": "pyhouse-hex:hex-architecture", "flat": "pyhouse-flat:flat-layered"}[family]
        lines.append(f"| add, move or split a package or module | `{layout}` |")
    return "\n".join(lines) + "\n"


def prepare(run: Run, setup: bool, fixtures: dict, listing_fraction: float | None) -> Path:
    work = Path(tempfile.mkdtemp(prefix="skill-run-"))
    fixture = run.prompt.get("fixture")
    if fixture:
        shutil.copytree(FIXTURES / fixture, work, dirs_exist_ok=True)
    fraction = SETUP_LISTING_FRACTION if setup else None
    if listing_fraction is not None:
        fraction = listing_fraction
    if setup:
        family = fixtures.get(fixture, {}).get("family") if fixture else None
        claude_md = work / "CLAUDE.md"
        existing = claude_md.read_text() + "\n" if claude_md.exists() else ""
        claude_md.write_text(existing + adopt_section(family, run.prompt.get("repo", "service")))
    if fraction is not None:
        (work / ".claude").mkdir(exist_ok=True)
        (work / ".claude" / "settings.json").write_text(
            json.dumps({"skillListingBudgetFraction": fraction}, indent=2) + "\n"
        )
    git = ["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid"]
    subprocess.run([*git, "init", "-q", "-b", "main"], cwd=work, check=True)
    if any(p.name != ".git" for p in work.iterdir()):
        subprocess.run([*git, "add", "-A"], cwd=work, check=True)
        subprocess.run([*git, "commit", "-q", "-m", "Initial commit"], cwd=work, check=True)
    return work


def is_write(name: str, tool_input: dict) -> bool:
    if name in WRITE_TOOLS:
        return True
    return name == "Bash" and bool(BASH_WRITE.search(tool_input.get("command", "")))


def execute(run: Run, args: argparse.Namespace, spec: dict, plugins: list[Path], out: Path) -> dict:
    work = prepare(run, args.setup, spec.get("fixtures", {}), args.listing_fraction)
    text = run.prompt["text"] + spec["levels"][run.level]
    cmd = [
        "claude", "-p", text,
        "--model", args.model,
        "--setting-sources", "project,local",
        "--output-format", "stream-json", "--verbose",
        "--no-session-persistence",
        "--max-budget-usd", str(args.max_budget_usd or (10 if args.full else 2)),
        "--permission-mode", "bypassPermissions" if args.allow_bash else "acceptEdits",
    ]
    for plugin in plugins:
        cmd += ["--plugin-dir", str(plugin)]
    raw = out / "raw" / f"{run.run_id}.jsonl"
    stopped = False
    timed_out = threading.Event()
    started = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=work, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)

    def kill() -> None:
        timed_out.set()
        proc.kill()

    timer = threading.Timer(args.timeout, kill)
    timer.start()
    with raw.open("w") as sink:
        for line in proc.stdout:
            sink.write(line)
            if args.full or stopped:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if any(is_write(c["name"], c.get("input", {})) for c in tool_uses(event)):
                stopped = True
                proc.terminate()
    proc.wait()
    timer.cancel()
    stderr = proc.stderr.read()
    meta = {
        "run": run.run_id, "prompt": run.prompt["id"], "level": run.level, "rep": run.rep,
        "stopped_at_first_write": stopped, "timed_out": timed_out.is_set(), "returncode": proc.returncode,
        "seconds": round(time.monotonic() - started, 1), "stderr": stderr[-2000:],
    }
    (out / "raw" / f"{run.run_id}.meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    if args.full:
        shutil.copytree(work, out / "work" / run.run_id, ignore=shutil.ignore_patterns(".git"))
    shutil.rmtree(work, ignore_errors=True)
    summary = summarise(raw, meta)
    print(f"{run.run_id}: {', '.join(summary['skills_before_write']) or '-'}"
          f"{' (timed out)' if timed_out.is_set() else ''}", flush=True)
    return summary


def tool_uses(event: dict) -> list[dict]:
    if event.get("type") != "assistant":
        return []
    content = event.get("message", {}).get("content", [])
    return [c for c in content if isinstance(c, dict) and c.get("type") == "tool_use"]


def catalogue_file(path: str) -> str | None:
    """A file of a catalogue plugin read directly, as `<plugin>/<path inside it>`."""
    match = re.search(r"/plugins/(pyhouse[\w-]*)/(.+)$", path)
    return f"{match.group(1)}/{match.group(2)}" if match else None


def summarise(raw: Path, meta: dict) -> dict:
    skills: list[dict] = []
    reads: list[dict] = []
    first_write = None
    init: dict = {}
    result: dict = {}
    denied = 0
    usage: Counter = Counter()
    messages: set = set()
    for line in raw.read_text().splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "system" and event.get("subtype") == "init":
            init = event
        elif event.get("type") == "system" and event.get("subtype") == "permission_denied":
            denied += 1
        elif event.get("type") == "result":
            result = event
        elif event.get("type") == "assistant" and (message := event.get("message", {})).get("id") not in messages:
            messages.add(message.get("id"))
            usage.update({k: v for k, v in (message.get("usage") or {}).items() if isinstance(v, int)})
        sub = event.get("parent_tool_use_id") is not None
        for use in tool_uses(event):
            name, tool_input = use["name"], use.get("input", {})
            before = first_write is None
            if name == "Skill":
                skills.append({"skill": tool_input.get("skill", "?"), "before_write": before, "subagent": sub})
            elif name == "Read" and (found := catalogue_file(tool_input.get("file_path", ""))):
                reads.append({"file": found, "before_write": before, "subagent": sub})
            if first_write is None and is_write(name, tool_input):
                target = tool_input.get("file_path") or tool_input.get("notebook_path") or tool_input.get("command", "")
                first_write = {"tool": name, "target": target[:200], "subagent": sub}
    listed = [s for s in init.get("skills", []) if s.startswith("pyhouse")]
    return {
        **{k: v for k, v in meta.items() if k != "stderr"},
        "model": init.get("model"),
        "plugins": [p["name"] for p in init.get("plugins", []) if p.get("path") != "builtin"],
        "catalogue_skills_listed": len(listed),
        "skills": skills,
        "skills_before_write": [s["skill"] for s in skills if s["before_write"]],
        "skills_after_write": [s["skill"] for s in skills if not s["before_write"]],
        "catalogue_reads": reads,
        "first_write": first_write,
        "permission_denied": denied,
        "turns": result.get("num_turns") or len(messages),
        "input_tokens": usage["input_tokens"] + usage["cache_creation_input_tokens"]
        + usage["cache_read_input_tokens"],
        "cost_usd": result.get("total_cost_usd"),
        "result": result.get("subtype") or ("stopped" if meta["stopped_at_first_write"] else "none"),
    }


def short(skill: str) -> str:
    return skill.split(":", 1)[-1]


def write_report(out: Path, summaries: list[dict], manifest: dict) -> None:
    summaries = sorted(summaries, key=lambda s: (s["prompt"], s["level"], s["rep"]))
    lines = [f"# Skill loading — {manifest['started']}", ""]
    lines += [f"- {key}: `{value}`" for key, value in manifest.items() if key != "started"]
    cost = sum(s["cost_usd"] or 0 for s in summaries)
    tokens = sum(s.get("input_tokens") or 0 for s in summaries)
    lines += [f"- runs: {len(summaries)}; input tokens, cache included: {tokens:,}; reported cost: ${cost:.2f}"
              " (a run stopped at its first write reports no cost)", ""]
    lines += ["## Runs", "",
              "| run | loaded before the first write | after | catalogue files read | first write |",
              "|---|---|---|---|---|"]
    for s in summaries:
        before = ", ".join(short(x) for x in s["skills_before_write"]) or "—"
        after = ", ".join(short(x) for x in s["skills_after_write"]) or "—"
        read = ", ".join(r["file"].split("/skills/", 1)[-1] for r in s["catalogue_reads"]) or "—"
        fw = s["first_write"]
        first = f"{fw['tool']} `{Path(fw['target']).name if fw['tool'] != 'Bash' else fw['target'][:40]}`" if fw else "none"
        if s.get("timed_out"):
            first += " (timed out)"
        lines.append(f"| {s['run']} | {before} | {after} | {read} | {first} |")
    lines += ["", "## Each skill, over runs", "",
              "Runs that loaded the skill before the first write / at any point, out of all runs.", "",
              "| skill | before | any |", "|---|---|---|"]
    before_count: Counter = Counter()
    any_count: Counter = Counter()
    for s in summaries:
        before_count.update(set(s["skills_before_write"]))
        any_count.update({x["skill"] for x in s["skills"]})
    for skill in sorted(any_count, key=lambda k: (-before_count[k], -any_count[k], k)):
        lines.append(f"| {skill} | {before_count[skill]} | {any_count[skill]} |")
    lines += ["", "## Each prompt and level", "",
              "Runs that loaded any catalogue skill before the first write, out of the runs.", "",
              "| prompt | level | runs | any catalogue skill before writing |", "|---|---|---|---|"]
    groups: dict = defaultdict(list)
    for s in summaries:
        groups[(s["prompt"], s["level"])].append(s)
    for (prompt, level), runs in sorted(groups.items()):
        hit = sum(any(x.startswith("pyhouse") for x in r["skills_before_write"]) for r in runs)
        lines.append(f"| {prompt} | {level} | {len(runs)} | {hit} |")
    (out / "report.md").write_text("\n".join(lines) + "\n")


def checkout_state() -> str:
    sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                         text=True).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain", "plugins"], cwd=ROOT, capture_output=True,
                           text=True).stdout.strip()
    return sha + (" with uncommitted plugin changes" if dirty else "")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", required=True, type=Path, help="directory for raw streams and the report")
    parser.add_argument("--prompts", type=Path, default=ROOT / "tools" / "skill_prompts.json")
    parser.add_argument("--only", help="comma-separated prompt ids")
    parser.add_argument("--levels", help="comma-separated levels; default every level in the prompt file")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--model", default="opus")
    parser.add_argument("--plugins", default="all", help="all, none, or comma-separated plugin directories")
    parser.add_argument("--setup", action="store_true",
                        help="the adopt section in CLAUDE.md and the listing budget /pyhouse:setup writes")
    parser.add_argument("--listing-fraction", type=float, help="skillListingBudgetFraction for the run")
    parser.add_argument("--full", action="store_true", help="let each run finish and keep what it wrote")
    parser.add_argument("--allow-bash", action="store_true",
                        help="bypassPermissions instead of acceptEdits, so the agent can run what it wrote")
    parser.add_argument("--max-budget-usd", type=float, help="per run; default 2, or 10 with --full")
    parser.add_argument("--timeout", type=int, default=900, help="seconds per run")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--report-only", action="store_true", help="rebuild the report from <out>/raw")
    args = parser.parse_args()

    out: Path = args.out.resolve()
    if args.report_only:
        manifest = json.loads((out / "manifest.json").read_text())
        summaries = [summarise(meta.with_name(meta.name.replace(".meta.json", ".jsonl")),
                               json.loads(meta.read_text()))
                     for meta in sorted((out / "raw").glob("*.meta.json"))]
        write_report(out, summaries, manifest)
        print(out / "report.md")
        return

    spec = json.loads(args.prompts.read_text())
    levels = args.levels.split(",") if args.levels else list(spec["levels"])
    unknown = set(levels) - set(spec["levels"])
    if unknown:
        sys.exit(f"unknown levels: {', '.join(sorted(unknown))}")
    prompts = spec["prompts"]
    if args.only:
        wanted = set(args.only.split(","))
        prompts = [p for p in prompts if p["id"] in wanted]
        if missing := wanted - {p["id"] for p in prompts}:
            sys.exit(f"unknown prompts: {', '.join(sorted(missing))}")
    plugins = catalogue_plugins(args.plugins)
    runs = [Run(p, level, rep) for p in prompts for level in levels for rep in range(args.repeat)]

    (out / "raw").mkdir(parents=True, exist_ok=True)
    clashes = [r.run_id for r in runs if (out / "raw" / f"{r.run_id}.jsonl").exists()]
    if clashes:
        sys.exit(f"{out} already holds {len(clashes)} of these runs; use a new --out")
    version = subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip()
    manifest = {
        "started": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "checkout": checkout_state(),
        "claude": version,
        "model": args.model,
        "plugins": ",".join(p.name for p in plugins) or "none",
        "setup": args.setup,
        "listing_fraction": args.listing_fraction if args.listing_fraction is not None
        else (SETUP_LISTING_FRACTION if args.setup else "default"),
        "mode": "full" if args.full else "stop at first write",
        "permission_mode": "bypassPermissions" if args.allow_bash else "acceptEdits",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"{len(runs)} runs, {args.jobs} at a time, into {out}", flush=True)

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        summaries = list(pool.map(lambda r: execute(r, args, spec, plugins, out), runs))
    with (out / "summary.jsonl").open("a") as sink:
        for s in summaries:
            sink.write(json.dumps(s) + "\n")
    write_report(out, summaries, manifest)
    print(out / "report.md")


if __name__ == "__main__":
    main()
