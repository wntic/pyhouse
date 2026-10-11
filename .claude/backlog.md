# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Agreed

Item 55 predates the rest; every earlier agreed item has landed or was closed (D130–D164). Items 63–72
come from the full review of 2026-10-11 after adversarial verification; 76–80 from the maintainer's own
questions the same day (78 folded into 70).

### 55. Performance obligations, placed with their owners
No `performance` skill: a bag of tips would restate rules other skills own. Two groups, each with an
owner. Language-level, a universal skill on async code: no blocking I/O or CPU-bound work inside a
coroutine (today one `## Other bindings` bullet in `hex-capability-adapter`), concurrency always
bounded, a client or pool built once per process rather than per call. Data access, in `persistence`:
no query per item in a loop, filtering and paging in the store rather than in Python, only the columns
and rows used, and every filter of a hot query backed by an index. Only what is expensive to retrofit
and checkable in review belongs; a micro-optimisation without a measurement does not. The maintainer
collects concrete findings from the lead's reviews first, and each becomes a rule.

### 66. A universal skill owns at-least-once delivery
The obligations of a unit a broker or a third-party sender delivers are scattered and worded apart:
`flat-entrypoint` rule 15 (bounded redelivery, dead letter, an idempotent effect) and rule 9 (the HTTP
case, the sender's signature), `hex-architecture:146-147` (acknowledge after the handler; a create takes
its identity from the message), `exception-catalog` rule 15 (a failure after a committed write, delivered
by something that retries it), `persistence` rule 16 (an older write never replaces a newer one). Hex has
no bounded redelivery or dead letter at all; flat states them only in its entrypoint skill, which is how
the review found its containment function handed to a consumer that then acknowledges a failed message
("Главное" item 4); a hex create handler copied into a consumer points at nothing and duplicates on
every redelivery (item 3b). Both families have consumers, so D145's condition is met.
A new universal skill, rules only and no template (a broker's redrive policy is deployment
configuration, not code); its name derived by `naming` (working name `message-delivery`). About five
rules: a unit is acknowledged only once its effect is committed, and a failed one is returned; redelivery
is bounded, then the unit goes to a dead letter the operator can read, both declared in the broker's
configuration, never a counter in the process; a redelivery changes nothing — identity and values come
from the message, never the clock or a mint per delivery; ordering points at `persistence` rule 16,
which stays there as the store's side; a third party's delivery is verified against the raw body it
signed before the body is parsed. The families keep the spelling — the consumer wrapper and HTTP route
in `flat-entrypoint`, the inbound adapter in `hex-architecture` — and point at the skill instead of
restating it. The outbox and its relay stay in hex (D145). Item 65 has landed; update both
indexes, the counts, `kickoff.md` if the skill list there changes, and the ownership table in
`meta-skill-author`.

### 76. `python-versioning` rule 13 states the tag and the aggregate number
Rule 13 says members version independently and lockstep is right only where one artifact ships them
all, but the tag scheme and the aggregate number are written only in `/release` (`pyhouse-git`,
`release.md:37-39`, `:104`) and this repository's `CLAUDE.md` — a project with `pyhouse-universal`
alone never sees them. Add one or two sentences to rule 13: a tag names exactly one released thing —
`<member>-v<version>` per member where members are released separately, one `v<version>` naming an
aggregate number where one artifact ships every member; the aggregate moves whenever a member does, by a
minor if any member moved by a minor or more, by a patch if every member that moved only patched. No
section and no template — the mechanics stay in `/release`. This is a fourth rule stated in both
`pyhouse-git` and `pyhouse-universal`, worded to agree: add it to the list in `CLAUDE.md` "Four plugins,
one-way dependency", which names three today.

### 77. "No comments" reaches every file the project writes by hand
`python-style` "Comments" (`:269-290`) binds source, migrations and tests; nothing binds the
`pyproject.toml`, Dockerfiles, compose files, CI workflows, hook configurations and scripts an agent
writes, and they fill with comments. The rule stays owned by `python-style`, not split across the files'
owners. Three changes:
- `python-style` "Comments": one bullet — the source form holds in every file the project writes by
  hand, configuration and scripts included; comments a tool generated (`alembic.ini` after
  `alembic init`) are not the project's writing and the rule does not reach them.
- One pointer line to it in `python-toolchain` (where it names Dockerfiles, compose, CI and hook
  configurations) and in `python-container-image`, since those fire when such a file is written and
  `python-style`'s description does not.
- `python-workspace:79,82,85`: the three `# …python-toolchain's tables, whole, written here once`-style
  lines inside the root `pyproject.toml` block are notes to the copier that would land verbatim; move
  them to prose under the block. `python-container-image`'s `# only where …` optional-line marker stays.

### 79. The templates move from httpx to httpx2
httpx is stalled: last stable 0.28.1 on 2024-12-06, only `1.0.devN` since, the 1.0 PR (#3796) open, issues
and discussions closed on 2026-02-27; its transport httpcore last released 1.0.9 on 2025-04-24 with open
defects in exactly what the templates use — a long-lived pooled `AsyncClient` and cancellation (httpcore
#1093, #1110; httpx #3782, #3728). httpx2 (Pydantic's fork, 2.13.1 on 2026-09-23) is the drop-in
continuation: the import is renamed, httpcore vendored as `httpcore2`. Not aiohttp: httpx serves two roles
here — the outbound client and the in-process FastAPI test client over `ASGITransport`
(`hex-test-restapi-endpoint`, `hex-test-app-invariants`, `hex-test-restapi-auth`) — and aiohttp has no
ASGI transport, so httpx would stay anyway, and its client API is not drop-in. At implementation, check:
- httpx2 keeps `ASGITransport` and `MockTransport`.
- Whether `respx` supports httpx2 by then (draft PR #317 on 0.23.1). If not, the stubs move to
  `pytest-httpx2` or to the built-in `MockTransport`, which `flat-test-service-client` already uses and
  which needs no stubbing library.
- The rename across the 15 files: the setup skills' floors, `test-principles`' `respx` wording, the
  package list `CLAUDE.md` gives `tools/check_template_imports.py`.
The rules do not change; `## Other bindings` gains aiohttp with aioresponses.

### 80. A universal skill for a CLI tool
Working name `cli-entrypoint`, final name from `naming`. Mostly rules; the universal skills already hold
for a CLI and stay the owners — the entry function as composition root and per-invocation values as
arguments (`python-settings` 13, 15), dotenv and tunable defaults (2, 9), result on stdout and logs on
stderr (`python-logging`), one console script per command (`python-toolchain:113`), the interpreter
floor (`python-style:82`), nothing built at import (`python-packaging` 8). What it owns, none of it
written anywhere today:
1. A command is thin — it parses, calls an ordinary typed function and renders the result; no logic in
   the command.
2. The exit code is mapped once at the boundary — 0 on success, each catalogue error its own non-zero
   code in one place, as `exception-catalog` has a transport's status mapped at its boundary; an
   unexpected exception is never hidden behind a bare 1.
3. A multi-command tool: one module per command, commands never import each other.
4. A CLI is tested in process through the library's runner, asserting the exit code and stdout as
   literals, never through a subprocess.
5. A CLI as one more entrypoint of a hex or flat service — the families point here, never restate it.
Binding: **typer** — built on click, arguments declared by annotations, in line with the catalogue's
typing rules and with FastAPI already in the hex templates. One template, the module holding the
`typer.Typer()` app and its commands, with `pretty_exceptions_enable=False` so error output stays
predictable (rule 2 says why). `## Other bindings`: click, argparse. Then `architecture-choice:164`
routes a CLI tool to this skill, still giving no layout for a large command tree; the CLI pointer in
`flat-entrypoint`'s trigger table (now at `python-settings` rules 13 and 15) points here too; indexes, counts and the top-level `README.md` gain the skill. Ask the
maintainer for a real CLI to check the rules against before writing.

### 70. Descriptions stay as they are; `when_to_use` folds into `description`
Measured on 2026-10-11 (Opus, `claude -p`, a scratch hex project, the checkout's universal + hex + git
loaded with `--plugin-dir`, user settings excluded). The listing budget is 30,000 characters (Opus and
Sonnet alike); the catalogue's 41 skills take ~29,500 of the 38,145 listed, and 14 of 23 `hex-*` skills
were listed by name alone (`hex-restapi-endpoint`, `hex-store-repository`, `hex-wiring`, every
`hex-test-*`, …). `skillListingBudgetFraction` in a project's `.claude/settings.json` takes effect. Over
39 runs — three prompts naming the artifact, five not naming it ("publishing a Foo must check its Bar is
active", "only admins may create a Foo", "fail the build if the domain imports SQLAlchemy", "keep each
Foo's attachment in S3", "cover the create-Foo handler"), default budget against 0.02, three repeats for
the second set — the skill loaded never differed between the conditions: names carry the routing. The
adopt section widened what was loaded (`hex-architecture` first, then universal skills) at 1.5–4× the
turns. Not measured: what the agent then wrote, and models other than Opus. So:
- Descriptions are not shortened.
- `when_to_use` leaves the catalogue: Claude Code only appends it to `description`, under the same cap and
  budget, and claude.ai and the Skills API reject the key. In the 21 skills that carry it, its text moves
  to the end of `description` as it is listed today (` - Also fires on …`), keeping `Use when …` first,
  one paragraph, no bare `: `, within 1,536 characters. Then `meta-skill-author` (`:52`, `:60`, `:79`,
  `:107`) drops the field, the README (`:49`, `:194`, `:212`) and `CLAUDE.md:233` drop the pair wording,
  and a `DECISIONS.md` entry reverses D120.
- The README gains a short note: the catalogue takes most of Claude Code's skill-listing budget, so with
  many plugins installed some skills are listed without a description; `skillListingBudgetFraction` in
  the project's `.claude/settings.json` raises it. `/pyhouse-universal:adopt` does not write it.
