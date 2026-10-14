# Changelog

## 0.25.0 — 2026-10-14

Plugin versions in this release: `pyhouse-universal` 0.22.0 (from 0.21.1), `pyhouse-hex` 0.15.0 (from
0.14.1); `pyhouse-flat` 0.13.1 and `pyhouse-git` 0.8.1 are unchanged. Nothing is removed or reversed.

### Changed

- **What an outbox relay owes is now a universal rule, `at-least-once-delivery` rule 6.** Until now it
  was a paragraph in `hex-persistence`, so a flat service, or a project without `pyhouse-hex`, had no
  rule for its relay and a review had nothing to check it against. The obligations are the same in
  every family: each recorded effect is delivered at least once under the record's own id, marked
  delivered only once the receiver has acknowledged it, and kept in no particular order unless the
  relay holds a key's later records back behind a failed one. Two points are now stated outright:
  - *The receiver's acknowledgement is awaited.* The receiver is whoever the relay hands the effect
    to — a broker confirming the publish, an endpoint answering success. A client that has only
    accepted the send into its buffer has not acknowledged anything. If your relay marks a row
    delivered as soon as the send call returns, check it.
  - *The id travels as the receiver's idempotency key wherever it accepts one.* A receiver that accepts
    no key may see an effect twice; that is the cost of at least once, and nothing on the sending side
    removes it.
- **`at-least-once-delivery` now fires on the sending side as well.** It loads when a program relays an
  effect it recorded with a committed write, and its hard stops no longer send that work elsewhere.
  Whether an effect after a write needs recording at all is still `exception-catalog`'s decision.
  Publishing straight after the write with nothing recorded, where losing the effect costs something,
  stops there. An operation idempotent under redelivery may still fail whole instead. A relay that polls
  its own outbox table is a sender under rule 6, not a reader of a source with no delivery state.
- **`hex-persistence`'s unit-of-work file now covers the unit of work alone.** Its templates are
  unchanged, and the relay's paragraph is replaced by a pointer to rule 6. `hex-application` and
  `hex-architecture` point to the same rule.

## 0.24.1 — 2026-10-12

Plugin versions in this release: `pyhouse-universal` 0.21.1 (from 0.21.0), `pyhouse-hex` 0.14.1 (from
0.14.0), `pyhouse-flat` 0.13.1 (from 0.13.0); `pyhouse-git` 0.8.1 is unchanged. No obligation changes.

### Changed

- **The HTTP test templates stub with httpx2's own `MockTransport`, not respx.** respx does not
  intercept httpx2 by itself, and the `pytest-httpx2` layer it needed lets requests reach the real
  network when the plugin is not loaded. Every test template already builds the `httpx2.AsyncClient`
  it hands to the code under test, so the stub is now that client's transport: a handler records each
  request and answers from a queue the test fills, and an unqueued request fails the test even under a
  caller that catches every exception. Nothing leaves the process, and no stubbing library is needed.
  - *A project already on respx:* nothing is required; it stays listed under *Other bindings*, through
    `pytest-httpx2` with routes answered by `.respond(...)`.
  - *A new project:* drop `respx` and `pytest-httpx2` from the development dependencies.
  - *A credential refresh test:* the login requests go through the same stub, so their answers are
    queued in the order the flow sends them.
- **httpx2 takes a floor, `httpx2>=2`.** 2.0 is its first release with the client API; the only earlier
  one is an empty placeholder. Starlette's `testclient` now imports httpx2 and deprecates httpx, so a
  FastAPI service carries httpx2 either way.
- **`test-principles` *Intercepting HTTP* is worded for either kind of stub.** A stub covers every
  request from before the first one: a transport stub covers the client it is handed, a patching
  library is active for the whole test. A sequence test pins every request's method and URL from the
  stub's record, and no test requires every queued answer to be used.

## 0.24.0 — 2026-10-11

Plugin versions in this release: `pyhouse-universal` 0.21.0 (from 0.20.0), `pyhouse-hex` 0.14.0 (from
0.13.0); `pyhouse-flat` 0.13.0 and `pyhouse-git` 0.8.1 are unchanged. Nothing is removed or reversed.

### Added

- **`at-least-once-delivery` says which delivery guarantee its rules bind.** At least once is what they
  bind, and a client default that acknowledges before the effect — a task queue acknowledging before the
  task runs, offsets committed on a timer — gives less; rule 1 is what corrects it. At most once is a
  choice only where losing a unit costs nothing, made and recorded as that choice, and rules 4 and 5
  still bind it. A broker's exactly-once holds inside the broker and removes no rule: an effect applied
  once is at-least-once delivery with an idempotent effect. If your consumer relies on a client's
  default acknowledgement, check it against rule 1.
- **A hex service driven by a queue now tests its redelivered create.** `hex-test-application-handler`
  gains a coverage group for a handler a consumer calls: the same command handled twice returns the
  unit's id, raises nothing and leaves one entity, and the create test asserts the command's id. Its fake
  repository's `create` does nothing when the id is already stored, checked before any natural key, as
  the real insert does. `hex-test-repository-contract` pins that a second entity under the first's id
  changes nothing while a natural-key conflict still raises. A review will ask for these tests on a hex
  consumer; a service whose creates come only from requests is unaffected.

## 0.23.0 — 2026-10-11

Plugin versions in this release: `pyhouse-universal` 0.20.0 (from 0.19.0), `pyhouse-hex` 0.13.0 (from
0.12.0), `pyhouse-flat` 0.13.0 (from 0.12.0), `pyhouse-git` 0.8.1 (from 0.8.0). No skill is removed or
renamed and no rule is reversed, so code that followed 0.22.0 keeps working. Three things are still
worth doing when you upgrade:

- **If a flat consumer copied the containment template, fix it.** That template caught a run's
  failure, logged it and went on. In a queue or stream consumer, that acknowledges a failed message and
  loses it. The template now belongs to the loop alone. A consumer returns a failed unit for
  redelivery (`flat-entrypoint` rule 15, `at-least-once-delivery` rule 1).
- **Run `/install-commit-hook` again** to pick up the new `commit-msg` hook. It copies the hook into
  your repository, so an installed copy keeps the old behaviour until you replace it.
- **Update any citation of a `hex-application` rule number.** Command handler rules 3–8 are now 1–6,
  and query handler rules 3–7 are now 1–5. Rules 1–2 of each now form a single *DTOs and the handler
  surface* subsection. The rules say what they said before. Only the numbers moved.

### Added

- **`at-least-once-delivery`** (`pyhouse-universal`) states what a program owes a unit of work that
  another party delivers until it is acknowledged, whether from a queue or stream consumer or from a
  webhook receiver. A unit is acknowledged only once its effect is committed, and a failed one is
  returned. Redelivery is bounded and ends in a dead letter an operator can read, and the count is
  never held in the process. A redelivery changes nothing. Arrival order is never taken as the
  record's order. A third party's signature is checked over the raw body before the body is parsed.
  Use it for any consumer or webhook in any architecture. The rules used to be stated only in the flat
  family. One new obligation reaches hex services: a create driven by a delivered unit does nothing on
  a conflict on its own id, and every other unique constraint still refuses (`hex-persistence`
  `REPOSITORY.md` rule 8). A review will now ask for this on a hex consumer.
- **`python-cli`** (`pyhouse-universal`) covers a command-line interface: a CLI tool, or a command
  added to a service of either family. Each command stays thin over one typed function. Exit codes are
  mapped once at the boundary, and only success exits zero. An unexpected exception keeps its
  traceback. Commands never import one another. The command line is the tool's published surface. The
  CLI is tested in process through the library's runner. The template is bound to typer, with click
  and argparse under *Other bindings*. A CLI tool now declares one console script naming its app
  instead of one per command (`python-toolchain`, `flat-project-setup`). `architecture-choice`
  explains how to tell a CLI tool from a service that a command triggers.
- **`persistence` rule 3: one authoritative store per record.** A cache or an index on another store
  may hold a copy that can be lost and rebuilt. Two copies that both accept writes are not allowed.
  This used to be stated only for hex aggregates, and it now holds in a flat service too.
- **`persistence` rule 20 states where a migration chain is rooted.** A new chain starts at its first
  real revision. A baseline exists only over a schema that already exists. It is frozen by hand, and
  the stores that already have that schema are stamped with it. `flat-project-setup` and
  `hex-project-setup` each used to state this in their own words, and the two had drifted. They now
  keep only the Alembic spelling and point here.

### Changed

- **The HTTP templates use `httpx2` in place of `httpx`, and the stubs use respx through
  `pytest-httpx2`.** httpx has had no stable release since 0.28.1. httpx2 continues it under a renamed
  import and keeps every name the templates use. No rule changes.
  - *A project on httpx:* nothing is required. httpx stays under *Other bindings*. respx intercepts
    httpx without the plugin.
  - *A new project:* install `httpx2`, and add `pytest-httpx2` beside `respx` as development
    dependencies (`flat-project-setup`, `hex-project-setup`). respx itself still pulls in httpx, but
    only for tests.
  - *Stubs:* routes are answered with `.respond(...)`, because respx refuses an `httpx2.Response`.
  - *Hex tests:* they take the plugin's `httpx2_mock` fixture.
  - *Flat tests:* `flat-test-service-client`'s conftest enters `respx.mock(..., using="httpcore2")` and
    loads the plugin by name in `pytest_plugins`. That keeps it working when plugin autoloading is off.
  - *If your CI sets `PYTEST_DISABLE_PLUGIN_AUTOLOAD`:* the hex form fails as a missing `httpx2_mock`
    fixture rather than reaching the network. Load the plugin explicitly, for example with
    `-p pytest_httpx2`.
- **The flat templates no longer carry an ordering stamp or a webhook payload.** `Foo` carries its key
  and data only. The `as_of` column, the guarded upsert, the stamp-based out-of-order test,
  `FooChangePayload` and its `changed_at` are gone. The webhook route takes `FooPayload`.
  - The obligations are unchanged and are still rules: a redelivery changes nothing, and an older write
    never replaces a newer one (`persistence` rule 16).
  - Where your source stamps its records, the guard is still required, and `flat-test-persistence`
    still asks for its out-of-order test.
  - If your project copied the stamp, keep it. It is what rule 16 asks for there.
- **`when_to_use` is folded into `description`.** Each of the twenty skills that carried it has the
  text appended to its `description` with the same ` - ` join Claude Code's listing uses, so every
  skill lists exactly as before. `meta-skill-author` no longer has skill authors write the field.
  `description` alone may run to 1,536 characters. A skill of your own that still has `when_to_use` is
  read as before.
- **The README explains the skill-listing budget.** The catalogue takes most of Claude Code's budget,
  so some skills are listed by name only. Set `skillListingBudgetFraction` in the project's
  `.claude/settings.json` to raise it: the default is `0.01`, and `0.02` lists the whole catalogue.
  `/pyhouse-universal:adopt` does not write this setting for you.
- **`python-style`'s comment rule covers every file the project writes by hand.** That includes
  `pyproject.toml`, Dockerfiles, compose files, CI workflows, hook configurations and scripts, and a
  review will now flag comments in them. Comments a tool generated, such as in `alembic.ini` after
  `alembic init`, are exempt.
- **`python-versioning` rule 13 says which tag names a release and how an aggregate version moves.**
  This was previously written only in `/release`.
- **The `commit-msg` hook checks the message git will actually store.**
  - It follows `commit.cleanup`, and checks whether an editor ran.
  - Under `-m` and `-F`, a `#` line straight after the subject is now kept and rejected. It used to
    pass.
  - A type is accepted in any case (`Feat`, `FEAT`), and so is a configured `types` list.
  - A `--cleanup` flag or a `core.commentChar` other than `#` is invisible to the hook. Set
    `commit.cleanup` instead.
- **`/commit` stages first and commits only the paths you named.** It reads the staged diff, so a
  secret in a new, untracked file is now caught. It unstages its own staging when it stops. It commits
  with the paths after `--`, so anything you had already staged stays staged and out of the commit,
  and the report names it.
- **`/release` and `/release-notes` find the last release by its tag pattern.** A deploy or
  environment tag pushed after a release no longer becomes the start of the range.
- **How to find a repository's merge method moved from `git-commit-message` rule 9 to `git-branching`
  rule 2.** The fixup and autosquash commands now sit beside `git-branching` rule 4.

### Fixed

- **`hex-application`:** `caller_id` is the first field of every command, and of a query only when the
  caller scopes it. `hex-restapi-auth`'s route table now agrees.
- **`hex-restapi-auth`:** the JWKS key cache moved out of the adapter and into the client it is built
  on.
- **Hex settings:** every hex settings class that carries a secret hides its input in validation
  errors.
- **`hex-conventions`:** the store profiles no longer describe a generator that does not exist, or a
  fallback to a stub that crashes at startup.
- **`python-packaging` rule 9:** it no longer forbids the import its own carve-out 1 requires.
- **`architecture-choice`:** its lists of the universal skills that still bind no longer leave out
  `persistence`, `coupling` and `python-container-image`.
- **Hard stops:** those that routed only to a family now also name the project's own layout, for a
  project with no family plugin.
- **`/pyhouse-universal:adopt`:** it leaves the package row out whenever no argument names the family.

## 0.22.0 — 2026-10-11

Plugin versions in this release: `pyhouse-universal` 0.19.0 (from 0.18.0), `pyhouse-hex` 0.12.0 (from
0.11.1), `pyhouse-flat` 0.12.0 (from 0.11.0), `pyhouse-git` 0.8.0 (from 0.7.0). Every plugin carries a
break; below 1.0.0 each takes a minor. The catalogue is now written for Claude Code alone.

### Breaking

- **`flat-test-run-function` is renamed `flat-test-entrypoint`.** It is the test counterpart of
  `flat-entrypoint`, as `flat-test-persistence` is of `flat-persistence`; what it says is unchanged.
  Wherever your project names the skill — an instructions file, a command, a review setup — write the
  new name.
- **The adopt commands write `CLAUDE.md` only.** `/pyhouse-universal:adopt` and `/pyhouse-git:adopt`
  no longer write `AGENTS.md` or name skills without their plugin prefix. A section they wrote into an
  `AGENTS.md` that `CLAUDE.md` imports is still found and updated in place, so nothing is needed there.
  If your `AGENTS.md` is imported by nothing, move the section into `CLAUDE.md` before running either
  command again — Claude Code never read it there.
- **A hex partial update no longer carries a field's presence apart from its value.** `hex-application`,
  `hex-restapi-schema`, `hex-restapi-endpoint` and `hex-test-application-handler` drop the `sets_note`
  flag, the presence read from the request body and the test that clears a field: in the templates,
  `None` on an update means "leave unchanged", and nothing more. Code that already distinguishes an
  absent field from a cleared one is not wrong and needs no change; a review simply stops asking for it.

### Changed

- **`meta-skill-author`: `description` no longer has to identify a skill without `when_to_use`.**
  Claude Code reads the two together, so a skill author may put a trigger in either. `Use when …`, the
  trigger first, no bare `: ` and the 1,536-character combined limit still hold.

## 0.21.0 — 2026-10-10

Plugin versions in this release: `pyhouse-git` 0.7.0 (from 0.6.0). `pyhouse-universal` (0.18.0),
`pyhouse-hex` (0.11.1) and `pyhouse-flat` (0.11.0) are unchanged. Nothing in this release breaks a
project already carrying the catalogue.

### Added

- **`/pyhouse-git:release-notes`** — drafts the release note a user reads before upgrading: what
  changed for them, what a break asks of them, what is deprecated. Run it after `/release` has cut the
  tag. It reads the commits with their bodies, the diff of what users touch and the decisions record,
  takes every version number from the manifests, and writes a draft for you to approve into the
  changelog the repository keeps — `CHANGELOG.md` where it keeps none. Where a release tool such as
  release-please or git-cliff owns the notes, it writes no file and hands you the text instead.

### Changed

- **`/pyhouse-git:release` and `git-commit-message` route a release note to the new command**, instead
  of only saying to write one by hand.
- **`/pyhouse-git:adopt` adds a release-note row** to the table it writes, where the repository keeps
  release notes and no tool writes them.

## 0.20.0 — 2026-10-09

Plugin versions in this release: `pyhouse-universal` 0.18.0 (from 0.17.0), `pyhouse-git` 0.6.0 (from
0.5.0). `pyhouse-hex` (0.11.1) and `pyhouse-flat` (0.11.0) are unchanged. Nothing in this release
breaks a project already carrying the catalogue.

### Added

- **`/pyhouse-universal:adopt`** — installing the plugins makes the skills available but does not make
  an agent use them. Run this once in a repository, new or existing, and it writes a short
  `## Python house style` section into the file its agents read (`CLAUDE.md`, or `AGENTS.md` where that
  is the one the repository keeps), naming the skill to load before each kind of Python work. It
  chooses no architecture family; pass the family the code already follows if you want its layout
  skill named too. Running it again updates the section rather than adding a second one.
- **`/pyhouse-git:adopt`** — the same for branching and committing. It works out the repository's
  mainline, merge method and branch-name pattern, asks you to confirm them, and records them in a
  `## Branches and commits` section with the skill to load before branching, committing and
  releasing, plus a line forbidding an agent's authorship trailer. For Claude Code it also sets
  `attribution` to empty in the project's `.claude/settings.json`, so the `Co-Authored-By` and
  "Generated with" lines stop at the source. It offers `/pyhouse-git:install-commit-hook` where no hook
  checks messages yet.

  Both commands leave what they write uncommitted for you to review and commit.

### Changed

- **`python-style`: a comment or docstring cites only what outlives it.** No spec, plan, design draft
  or task list, and no requirement or task number taken from one — even when that document is
  committed beside the code. An issue in the tracker, an entry in a decisions record or a published
  standard may still be cited. Code written with the skill stops citing working documents, and a
  review against it may now report such comments in existing code. It agrees with
  `git-commit-message` rule 10, which already held commit history to the same test.

## 0.19.0 — 2026-10-08

Plugin versions in this release: `pyhouse-universal` 0.17.0 (from 0.16.0), `pyhouse-flat` 0.11.0
(from 0.10.1). `pyhouse-hex` (0.11.1) and `pyhouse-git` (0.5.0) are unchanged. Nothing has to change
when you upgrade.

### Added

- **`python-container-image`** (`pyhouse-universal`) — for a Python program that ships as a container
  image, in either architecture family. Reach for it when you write or change a `Dockerfile` or
  `.dockerignore`, containerize a service, or ask why a container runs as root or takes the whole
  timeout to stop. It covers what goes into the image, who the process runs as, how secrets and the
  build context are kept out, and how the stop signal reaches the process; its template is Docker
  with uv, and a workspace member's build is described beside it. Libraries, and CLI tools installed
  as packages, have no image, so it does not apply to them. `python-workspace` now also says where a
  member's `Dockerfile` goes: in the member's own directory, built with the repository root as its
  context.

### Changed

- **`flat-entrypoint`'s loop now stops when asked** (`pyhouse-flat`). The loop template used to run
  `while True` around a sleep, so only a kill could end it. Now the termination and interrupt signals
  set a stop request, installed before anything is built and checked before each run: a stop cuts the
  wait between runs short, never interrupts a run in flight, and the process logs one event and exits
  0. Rule 16 says the same, so a review against the catalogue will now report a polling loop that
  does not stop this way.
