# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

None.

## Agreed

Item 4, agreed on 2026-09-28, and items 52–55, agreed on 2026-10-04, remain. Every other agreed item
has landed (D130–D151). Item 54 is first.

### 4. Re-run the short-prompt scenario on the current skills
Last, once everything above has landed. The maintainer runs the short `dns_scanner` prompt on GLM
against the pushed `main`, as before the generality rework; the output is then reviewed the same way
(layout, module size, which skills loaded, defects → rules).

### 52. A pinned external version is looked up, never recalled
No skill says where a version comes from, so an agent writes the one it remembers — often two years
old, unmaintained or carrying known vulnerabilities — for a base image, a compose service, a
dependency floor, the interpreter, a CI action or a pre-commit hook. One universal rule, one owner,
every other skill pointing at it: a version is read from its registry or release page at the time it
is written, and where that is not possible the agent says the version is unverified rather than
guessing silently. The catalogue's own templates pin versions too (image tags in
`hex-test-integration-setup/CONFTEST.md`), and an agent copies them verbatim, so the change
also decides what a template shows in place of a number that will age. Choosing the owner
(`python-toolchain` or `python-packaging`) is the first step.

### 53. A container image skill
A universal skill for building a Python program's image — any runnable service or CLI tool has one, a
library does not. Obligations, stated without the mechanism: a multi-stage build, an install from the
lock file, a non-root user, no secret in any layer, a context that excludes what the image does not
need, and an entrypoint that receives the platform's signals. One binding, Docker, named in the
template heading; others under `## Other bindings`. Compose stays in `python-workspace`. Depends on
item 52 for its base-image pin.

### 54. History refers only to what outlives it
Agents cite the spec or plan a change was written from — its number or name — in commit messages,
branch names and request titles. Specs are working documents: they drift from the code within days
and are deleted, while the history is permanent, so the reference sends a later reader to something
gone or wrong. A rule in `git-commit-message` (it owns what a message says): a message names only what
will still exist and still say the same thing when it is read — a tracker issue, a decisions record,
another commit — and carries what it needs from a working document in its own words. `git-branching`
points at it for the branch name, which a merge commit records. This repository's own commit subjects
cite backlog item numbers, whose entries are removed once done; that practice changes with the rule.
Whether the same obligation reaches code comments (`python-style`) is undecided.

### 55. Performance obligations, placed with their owners
No `performance` skill: a bag of tips would restate rules other skills own. Two groups, each with an
owner. Language-level, a universal skill on async code: no blocking I/O or CPU-bound work inside a
coroutine (today one `## Other bindings` bullet in `hex-capability-adapter`), concurrency always
bounded, a client or pool built once per process rather than per call. Data access, in `persistence`:
no query per item in a loop, filtering and paging in the store rather than in Python, only the columns
and rows used, and every filter of a hot query backed by an index. Only what is expensive to retrofit
and checkable in review belongs; a micro-optimisation without a measurement does not. The maintainer
collects concrete findings from the lead's reviews first, and each becomes a rule.
