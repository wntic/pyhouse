# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Agreed

87 waits until there are defects found after a change landed to run it on. Every other item has
landed or was closed (D130–D178, D191, D192, D195–D198).

### 87. A retrospective over released changes
`/retro`: the defects found after a change landed, which check each escaped, and the rule or test that
would close it — the loop D186 was the first output of. Deferred (D192) until such defects exist: in
the repository it would run on, most defects testing will find predate the pipeline, and half its
steps are gone.

## Proposed

### 107. The tests' base keeps what already works
`delivery-implementer` build step 5 commits the names and the tests together as the tests' base, and
step 3 lets a test fail on the not-implemented marker. Under a merge-commit strategy that commit lands
on the mainline. Where the change reworks behaviour that already exists, the implementer has stubbed
the working body out so the new tests fail on the marker: seen in an adopted repository, where a `test:`
commit replaced a working list endpoint and its handler with `raise NotImplementedError` and the next
`feat!` commit restored them, leaving one mainline commit with a live endpoint broken. Nothing records
that as an accepted cost. Proposal: the marker goes only on a name that does not exist yet; a test of
changed behaviour fails on an assertion against today's code, which the existing body already gives.
Open: whether a red tests' base on the mainline is itself acceptable, which D193 and the merge method
left unsaid.
