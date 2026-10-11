# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

## Agreed

Items 55, 61 and 62 remain. Every other agreed item has landed or was closed (D130–D162).

### 55. Performance obligations, placed with their owners
No `performance` skill: a bag of tips would restate rules other skills own. Two groups, each with an
owner. Language-level, a universal skill on async code: no blocking I/O or CPU-bound work inside a
coroutine (today one `## Other bindings` bullet in `hex-capability-adapter`), concurrency always
bounded, a client or pool built once per process rather than per call. Data access, in `persistence`:
no query per item in a loop, filtering and paging in the store rather than in Python, only the columns
and rows used, and every filter of a hot query backed by an index. Only what is expensive to retrofit
and checkable in review belongs; a micro-optimisation without a measurement does not. The maintainer
collects concrete findings from the lead's reviews first, and each becomes a rule.

### 61. Drop the clearable-field case from the hex partial update
Agreed on 2026-10-11; partly reverses D143. The catalogue holds an agent to the architecture, not to
every case of a service's logic: an agent that needs a field it can clear will work that out itself.
`sets_note` came from consistency between skills (item 40), never from a defect seen in generated code,
and most services have no such field. Remove from `hex-application`, `hex-restapi-schema`,
`hex-restapi-endpoint` and `hex-test-application-handler` the `sets_note` flag, the presence read from
`model_fields_set`, Command DTO rule 4 and the prose pointing at it, and the `test_update_clears_…`
checklist line with its template; the update shows `None` as "leave unchanged" only. `Foo.note` stays as
the field a partial-update test leaves untouched (D108). Removing a rule is a break
(`feat(pyhouse-hex)!`, a minor below 1.0.0); record it as a D-entry that names D143 as partly reversed.

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
