# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

Every item proposed up to 121 was decided on 2026-11-18 (D204): 116 closed, 120 folded into 117, the
rest agreed below.

### 123. A fix of a defect already on the mainline asks for a review check
**Proposed.** Tried first in the producer, whose `CLAUDE.md` asks it since 2026-11-22: when a change
fixes a defect that was already on the mainline, the agent asks the person whether
`/pyhouse-universal:change-review` should have caught it from the diff that brought it in, and on a yes
proposes an entry for `.claude/review-checks.md` (D214) — trigger, check, incident — written only once
they agree; a defect that diff could not show earns none. Nothing else reminds anyone: D214 gives the
file a reader and no writer, and a retrospective was closed unbuilt (D219). Proposal once it has worked on a few fixes there:
the obligation in the catalogue, where an agent fixing a defect already is — beside `test-principles`'
*A defect's test*, which every fix already loads, or in the fix form of `delivery-spec` — and
`/pyhouse-universal:adopt` adds one row to its section pointing at it, so `/pyhouse:setup`, which runs
adopt, sets it up; never in `pyhouse` itself, which states no rule (D205), nor in `pyhouse-git`, which
cannot name the review. Open: which owner, since one is about tests and the other only reaches fixes
made through a spec; and whether the producer's line was followed — counted on its next fixes of
defects that reached `main`.

### 124. The release note is written without waiting for the person's approval
**Proposed.** `/release` step 7 item 1 runs `/release-notes` and goes on only once the person approves
the draft, and `/release-notes` holds its note a draft until then (D215). The maintainer has cut about
30 releases here and has never read or changed a release note, so the stop costs a turn on every
release and catches nothing. The reason D215 gives — the note is read before the tag, which cannot be
taken back — does not hold where the tag is local: `/release` pushes nothing unasked (step 7 item 5),
so until the push a note can still be corrected with an amend and a re-tag. Proposal: `/release` writes
the note, shows it in its report and commits it with the version fields without asking; the one
question it still asks is the version (step 6), and the push stays an explicit request.
`/release-notes` run on its own shows the note and leaves the file uncommitted, as now, without
calling it a draft awaiting approval. Open: whether a repository that wants the stop can keep it
through a line in its own rules (step 1 of `/release-notes` already reads them), or whether the
commands drop it for every repository. The `/release-notes` description and `/release`'s "What this
does not do" both say the note is for the person to approve, and change with it.

## Agreed

Nothing is agreed and not yet made. Every item has landed or was closed (D130–D178, D191, D192,
D195–D198, D201–D210, D212–D214, D216, D217, D219).
