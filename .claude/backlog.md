# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

### 57. Code refers only to what outlives it
`git-commit-message` rule 10 keeps a spec or plan out of the history. The same reference appears in
code — a comment or docstring citing "spec 012" or a requirement ID taken from one, a test named for
it — and fails the same way once the spec is deleted. Decide whether `python-style`, which owns
comments, states it.

### 59. Adopting the catalogue in a project, so agents keep to it
A project that installs the plugins still gets code and history that ignore them. A `CLAUDE.md` line
saying "follow pyhouse" is not enough in practice: agents skip the skills, and even with the line in
place they branch and commit without `pyhouse-git` — the wrong branch name, a message off the type
table. Decide what a project adds, once, so the skills are used rather than merely installed, for a
new repository and an existing one alike. Candidate directions, not yet weighed against each other:
- a command that adopts the catalogue in a project — settles the family (`architecture-choice`), and
  writes what the repository must carry: the branch-name pattern and merge method `git-branching` rule 2
  records, the commit-msg hook `/install-commit-hook` installs, and a short `CLAUDE.md` section;
- what that section says, so an agent acts on it — naming the skill to load for each kind of task
  (writing code, a commit, a branch, a release) rather than the catalogue as a whole, since a general
  instruction is the one already shown not to hold;
- enforcement that does not depend on the agent remembering — a hook that refuses a branch name off
  the recorded pattern the way the commit-msg hook refuses a message, or one that reminds the agent
  which skill applies when it is about to commit, branch or write a module;
- an adoption section in the top-level `README.md`.
Before choosing, find out which of these actually changes what an agent does: run the same short
prompts in a project with and without each, as the catalogue's purpose asks for.

## Agreed

Items 55 and 56, agreed on 2026-10-04, remain. Every other agreed item has landed (D130–D156).

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
