# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

### 57. Code refers only to what outlives it
`git-commit-message` rule 10 keeps a spec or plan out of the history. The same reference appears in
code — a comment or docstring citing "spec 012" or a requirement ID taken from one, a test named for
it — and fails the same way once the spec is deleted. Decide whether `python-style`, which owns
comments, states it.

## Agreed

Item 4, agreed on 2026-09-28, and items 53, 55 and 56, agreed on 2026-10-04, remain. Every other agreed
item has landed (D130–D153).

### 4. Re-run the short-prompt scenario on the current skills
Last, once everything above has landed. The maintainer runs the short `dns_scanner` prompt on GLM
against the pushed `main`, as before the generality rework; the output is then reviewed the same way
(layout, module size, which skills loaded, defects → rules).

### 53. A container image skill
A universal skill for building a Python program's image — any runnable service or CLI tool has one, a
library does not. Obligations, stated without the mechanism: a multi-stage build, an install from the
lock file, a non-root user, no secret in any layer, a context that excludes what the image does not
need, and an entrypoint that receives the platform's signals. One binding, Docker, named in the
template heading; others under `## Other bindings`. Compose stays in `python-workspace`. Its base image
is pinned by `python-toolchain` rule 12, which it points at rather than restates.

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
