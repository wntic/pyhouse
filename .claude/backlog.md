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
`python-container-image` (item 53) makes the platform's stop signal reach the process; no skill says
what the process does then. `flat-entrypoint` covers progress and cancellation only under an earned
engine (rule 7), and a loop or a queue consumer has no rule: stop taking new work, finish or hand back
the unit in flight within the platform's grace period, release what the process definition built, and
exit with a status that tells a clean stop from a failure. Decide whether it is one rule in each
family's entrypoint skill or a language-level one in a universal skill that both point at, and whether
a process an HTTP server runs is already covered by the server and its lifespan.

## Agreed

Items 53, 55 and 56, agreed on 2026-10-04, remain. Every other agreed item has landed (D130–D153).

### 53. A container image skill
`python-container-image`, in `pyhouse-universal`, for a program that ships as an image — a service
usually does; a CLI tool distributed as a package and a library do not, and the skill does not apply to
them. Obligations, stated as outcomes rather than the mechanism: the runtime image carries nothing only
the build needs (compiler, package manager cache, development dependencies); exactly what the lock file
pins is installed, and the build fails where the lock has drifted from `pyproject.toml`; the process
runs as a non-root user; no secret reaches any layer, a build-time one included; the build context
excludes what the image does not need; the program's output reaches the platform's log unbuffered; and
the platform's stop signal reaches the Python process. One image serves every environment, its
configuration read at start-up — a pointer to `python-settings`, not a restatement. The base image's
interpreter matches `requires-python`, and its tag, like the package manager's, is pinned by
`python-toolchain` rule 12, which it points at. One binding, Docker and uv, named in the template
heading — a `Dockerfile` and its ignore file for one distribution at the repository root, with the one
line a workspace member changes marked; Podman or Buildah, buildpacks, a distroless base and pip
without uv under `## Other bindings`. Compose stays in `python-workspace`, which names where a member's
`Dockerfile` sits. Not stated: running migrations, and a health check, which most of the test services
lack and the platform usually declares. What the process does once the signal arrives is item 58.

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
