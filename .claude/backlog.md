# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

## Agreed

Items 55, 60 and 62 remain. Every other agreed item has landed or was closed (D130–D161, D163).

### 55. Performance obligations, placed with their owners
No `performance` skill: a bag of tips would restate rules other skills own. Two groups, each with an
owner. Language-level, a universal skill on async code: no blocking I/O or CPU-bound work inside a
coroutine (today one `## Other bindings` bullet in `hex-capability-adapter`), concurrency always
bounded, a client or pool built once per process rather than per call. Data access, in `persistence`:
no query per item in a loop, filtering and paging in the store rather than in Python, only the columns
and rows used, and every filter of a hot query backed by an index. Only what is expensive to retrofit
and checkable in review belongs; a micro-optimisation without a measurement does not. The maintainer
collects concrete findings from the lead's reviews first, and each becomes a rule.

### 60. Rename `flat-test-run-function` to `flat-test-entrypoint`
Agreed on 2026-10-11. D129 dropped "run function" as a term and left the skill's name "for now"; the
name is the term's last trace. The skill tests what `flat-entrypoint` writes — the work, containment,
the wrapper and an earned engine — so it takes the mirror name, as `flat-persistence` ↔
`flat-test-persistence`. Every reference moves with it: the flat skills, `test-principles`,
`meta-skill-author` and `CONVENTIONS.md`, `skills/README.md`, `CLAUDE.md`. A rename is a break
(`refactor(flat-test-entrypoint)!`, a minor for `pyhouse-flat` below 1.0.0); record it as D162.

### 62. Claude Code only — remove what other agents justified
Agreed on 2026-10-11. The catalogue is for Claude Code alone: the agent-neutral goal came from a
corporate LLM used through opencode, now too rate-limited and too short of context to develop with.
- `CLAUDE.md` and `meta-skill-author` (*`description` must be self-sufficient*): drop the opencode and
  Codex reason and the ban on a fact found only in `when_to_use`, since Claude Code reads both. Keep
  `Use when …`, the trigger first, no bare `: ` and the 1,536-character listing limit. Rewrite no
  skill's frontmatter for it.
- Both adopt commands: drop the `AGENTS.md` branch — the `@AGENTS.md` import, choosing between two
  files, bare skill names — and always write `CLAUDE.md`; drop "No other agent's settings are written"
  from `/pyhouse-git:adopt`. The line against an authorship trailer stays (`git-commit-message` rule 8).
- `README.md`: drop "Claude Code, opencode and Codex all read them" and "or `AGENTS.md`".
Narrowing what the adopt commands support is a break (`!`, a minor for `pyhouse-universal` and
`pyhouse-git` below 1.0.0); record it as a D-entry naming D158 as partly reversed.
