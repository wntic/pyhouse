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

### 68. `pyhouse-git` fixes from the 2026-10-11 review
All verified against the current files; four reproduced in a scratch repository (git 2.39.5).
- `commands/commit.md` step 2–3: stage first, then read `git diff --staged -- <files>`; `git diff` on an
  untracked file prints nothing, so a secret in a new file passed the check. On a stop, unstage
  (`git restore --staged`).
- `commands/commit.md` step 5: commit only the resolved paths (`git commit -F - -- <files>`) and name
  anything else already staged; `git commit -F -` committed the whole index.
- `commands/commit.md` step 4: a pointer to `git-branching` rule 4 — a fix to work not yet landed is a
  fixup folded into the commit it fixes, never a `fix` commit `/release` would count.
- `commands/commit.md:38,58-59`: `git log --no-merges`, as `release.md:61-62` already does.
- `commands/commit.md:74-78`: the heredoc skeleton makes scope and body look required; replace with
  the message composed in step 4.
- `commands/release.md:37-39,87-89,103-106`: drop this marketplace repository's own shape (the README
  index over-count, "a repository like a plugin marketplace"); keep the aggregate-version rule.
- `commands/release.md:41`: `git describe --tags --match <release tag pattern>`; without it a later
  deploy tag is taken as the last release.
- `git-commit-message:116-119` (how to find the merge method) moves to `git-branching` rule 2;
  repoint `adopt.md:32` and `commit.md:63-65`.
- `git-branching:54-58`: the fixup/autosquash commands move beside rule 4 as prose, whole, the git 2.44
  sentence included (D121 keeps it).
- `git-branching:62-64`: the squash binding says "every rule but 4 holds" and points at rule 9, instead
  of a list that omits rules 6–8.
- `git-branching:46-47`: no `feat/foo-export`-style examples in the block `/pyhouse-git:adopt` copies
  into a project's `CLAUDE.md`.
- `git-branching:41`, `adopt.md:67-68`: "releases are tags on it" only where releases are tagged.
- `git-hooks/commit-msg:53,61`, `install-commit-hook.md:95-96`: accept a type in any case
  (Conventional Commits item 15); correct the claim that the specification wants lowercase.
- `git-hooks/commit-msg:24-25`: under `-F` git keeps `#` lines, so read the second line from the raw
  file and correct the comment.
- `.claude-plugin/plugin.json:5`: a break is a major, a minor below 1.0.0; name `git-commit-message`
  instead of "that skill".

### 69. `pyhouse-universal` fixes from the 2026-10-11 review
All verified against the current files.
- `architecture-choice:138-142,175-176`: the lists of universal skills that still bind omit
  `persistence`, `coupling` and `python-container-image` and call themselves the whole; say "every
  universal skill whose subject the project has" instead of a list. `:228`: "all five cases" → six.
- `exception-catalog:41-42`: route a client's error translation to rules 8–10 here, the class to the
  family (`flat-layered`, `hex-capability-adapter`) or the project's own layout.
- `exception-catalog:74-98`: drop the hedge "these two show the pattern, not a list to copy" and mark
  each subclass `# only where …`; keep `NotFoundError` and `UpstreamError` (rule 10, the fallback example
  at `:166-169`, `FooNotFoundError` at `:106` and nine family files rely on them).
- `exception-catalog:149`: `{"foo_id": str(foo_id)}`.
- `meta-skill-author:79-82`: "there is no total budget" is false — the listing gets 1% of the context
  window, and past it descriptions drop from the least-invoked skills, the name kept; the catalogue's
  description plus `when_to_use` is ~36,100 characters, ~737 a skill, not ~400. Correct the fact and
  the figure; drop "the only hard number the platform documents". What to do about it is item 70.
- `persistence` rule 8 (`:101-106`): drop the clause on which spellings the key's source merges; keep
  "in Python, never in the store's query language".
- `python-packaging` rule 9 (`:368-370`): an exception for a module directly under the application root,
  which carve-out 1 forbids re-exporting, so `from myapp.exceptions import …` is allowed.
- `python-packaging:40-48`: a drifted copy of `naming`'s Renaming (no env prefixes, queue names,
  revision ids, CLI flags) → a pointer; and `:9` contradicts `:17-19`.
- `python-settings:48`: the `env_file` marker adds "never in a CLI tool" (rule 2), within 120 columns.
- `python-toolchain:54`: the copy-time marker on its own line, apart from the floor's reason.
- `python-versioning:83-94`: the `version.py` template → one sentence.
- `python-versioning:53-54` → `persistence`; `python-workspace:22` in `persistence:216-218`'s form
  (rules `persistence`, files the family's data-access skill or the project's own layout).
- `python-workspace` (`:57,65,114-117`, rule 1): mark `myschema` "only where members share a library";
  compressing `:62-66` is optional.
- `test-architecture-rule:112-125`: tie the `sys.exit` example to `exception-catalog` rule 13.
- `test-architecture-rule` rule 2 (`:160-165`): label the two name forms by meaning ("a scope has no X",
  "X only inside a scope"), not by family.
- Hard stops that route only to a family gain "or the project's own layout": `naming:338-339`,
  `python-packaging:390-391`, `coupling:253-255`, `python-logging:192-193`, `test-principles:389-391`,
  `python-workspace:288-290`.
- `agents/pyhouse-reviewer.md:93-95`: the restated ownership table → a pointer to it.
- `commands/adopt.md` step 2: given no argument, an Opus run on 2026-10-11 still added the "add, move or
  split a package or module" row because the tree looked hexagonal; say outright that without an
  argument naming the family the row is left out, whatever the layout looks like.

### 72. `pyhouse-flat` fixes from the 2026-10-11 review
All verified against the current files. The webhook signature (review item 5), `HTTP.md:117-119` and
Shape 3's "ordering them by the stamp" are item 65's.
- `flat-entrypoint:164`: "A loop or a consumer catches each run's failure … and goes on" hands the
  swallowing `sync_foos_contained` to a consumer, which then acknowledges a failed message and loses it.
  The template is the loop's; a consumer returns the failed unit (rule 15; item 66's skill once landed).
- `flat-entrypoint` rule 12 (`:339-344`): delete the local-state half; move the atomic-file-write half to
  `flat-layered` rule 14 and repoint "(rule 12)" at `:227`.
- `flat-entrypoint:182-194`: the loop template's author comments (`# with the other imports`,
  `# the first lines of _run`, `# in place of …`) land in `__main__.py`; say it in prose or in comments
  true in the reader's file (`meta-skill-author` rule 4).
- `flat-entrypoint:43-52,147-151`: widen the trigger row at `:45` to a CLI-triggered run and point at
  `python-settings` rules 13 and 15 (the CLI's entry function is the composition root, a per-invocation
  value is an argument); no new rule.
- `flat-layered:90-93`, rule 8 (`:329-333`): the engine exemption → a pointer to `flat-entrypoint`.
- `flat-layered` rule 6 (`:315-321`) → a pointer to `python-settings` rule 13.
- `flat-layered` rule 4 (`:307-311`): reduce the second-store half and drop the "(`flat-layered`
  rule 4)" citation in `flat-persistence` rule 5 (`:145-150`) in the same change, or the two point at
  each other.
- `flat-persistence` rule 1 (`:124-127`) → a pointer to `flat-layered` rule 3, number kept
  (`REPOSITORY.md:3,12` cite it).
- `flat-persistence` rule 3 (`:133-140`) → one line on the engine factory; repoint
  `flat-test-integration-setup:178` to `python-packaging` rule 8.
- `flat-persistence/REPOSITORY.md:22,58,62,101-104`, `flat-entrypoint/HTTP.md:24,34,75,86`:
  `StorageWriteRejectedError`, `StorageUnavailableError` and `InvalidPayloadError` state no parent; one
  line of prose each, as `flat-layered:232` does for `QuxRequestFailedError`. No switch to
  `UpstreamError` and no move.
- `flat-project-setup:53`: the development dependencies → `python-toolchain`'s template
  (`pytest-asyncio` is lost today).
- `flat-layered:209`, `flat-persistence/REPOSITORY.md:22`, `flat-entrypoint/HTTP.md:24`: a module in a
  subpackage imports the catalogue as `from myapp.exceptions import …`; `python-packaging` "Relative vs
  absolute" makes a module one level up `from ..exceptions import …`, as the hex templates write it.
  Tests outside the package stay absolute.
- `flat-project-setup:29`: the pytest block's owner is `python-toolchain` (D137), as
  `flat-test-integration-setup:32` says.

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
routes a CLI tool to this skill, still giving no layout for a large command tree; item 72's CLI pointer
in `flat-entrypoint` points here; indexes, counts and the top-level `README.md` gain the skill. Ask the
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
