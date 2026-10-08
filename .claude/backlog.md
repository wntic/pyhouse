# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

### 57. Code refers only to what outlives it
`git-commit-message` rule 10 keeps a spec or plan out of the history. The same reference appears in
code — a comment or docstring citing "spec 012" or a requirement ID taken from one, a test named for
it — and fails the same way once the spec is deleted. Decide whether `python-style`, which owns
comments, states it.

### 58. What a long-lived process does on the stop signal
`python-container-image` makes the platform's stop signal reach the process; no skill says
what the process does then. `flat-entrypoint` covers progress and cancellation only under an earned
engine (rule 7), and a loop or a queue consumer has no rule: stop taking new work, finish or hand back
the unit in flight within the platform's grace period, release what the process definition built, and
exit with a status that tells a clean stop from a failure. Decide whether it is one rule in each
family's entrypoint skill or a language-level one in a universal skill that both point at, and whether
a process an HTTP server runs is already covered by the server and its lifespan.

## Agreed

Items 55 and 56, agreed on 2026-10-04, remain. Every other agreed item has landed (D130–D154).

### 55. Performance obligations, placed with their owners
No `performance` skill: a bag of tips would restate rules other skills own. Two groups, each with an
owner. Language-level, a universal skill on async code: no blocking I/O or CPU-bound work inside a
coroutine (today one `## Other bindings` bullet in `hex-capability-adapter`), concurrency always
bounded, a client or pool built once per process rather than per call. Data access, in `persistence`:
no query per item in a loop, filtering and paging in the store rather than in Python, only the columns
and rows used, and every filter of a hot query backed by an index. Only what is expensive to retrofit
and checkable in review belongs; a micro-optimisation without a measurement does not. The maintainer
collects concrete findings from the lead's reviews first, and each becomes a rule.

### 56. A decisions-record skill
`git-commit-message` rule 10 sends a decision meant to bind later changes to wherever the repository
keeps decisions, and lets the body be the record where it keeps none. A skill says how a repository
keeps them, once it decides to: an architecture decision record — one numbered, dated entry per
decision with its context, the choice, its consequences and how to reverse it, never edited after it
is accepted, only superseded by a later one. `DECISIONS.md` in this repository is one. Language-
independent, so its plugin is decided first: `pyhouse-git` is the only one installed in a repository
of any language, but a decisions record is not about git.
