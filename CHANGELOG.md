# Changelog

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
