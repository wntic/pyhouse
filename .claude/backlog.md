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

### 126. The catalogue is split by subject: Python, delivery, and optionally git and releases
**Proposed** (maintainer, 2026-11-27). Changes are now implemented from specs in projects other than
Python ones (a frontend has been generated from them too), but what delivers a change ships inside a
marketplace named and framed for Python, and `pyhouse-delivery` depends on `pyhouse-universal`. So a
frontend repository that wants the spec and the implementation flow installs eighteen Python skills
with it. The proposal is two or three parts:

- **Python**: `pyhouse-universal` without what does not depend on the stack, the two families (`hex`,
  and `flat`, or `layered` after 125), and the `pyhouse` aggregate with `/pyhouse:setup`.
- **Delivery**: `pyhouse-delivery`, plus `/pyhouse-universal:change-review` and its `change-reviewer`
  agent, which already work in any project on any stack but ship in `pyhouse-universal`. They are most
  of what delivery depends on it for. `pyhouse-secrets` probably goes here too: it already depends on
  nothing and works in any language.
- **Git and releases** (optional): `pyhouse-git`, which already depends on nothing and no plugin
  depends on it.

What has to be untangled first:
- Delivery names `test-principles` (five times in `delivery-spec`, once in `delivery-change-contract`,
  twice in the implementer). Every rule delivery needs from it is either stated without a language in
  delivery or named only as an example, in the way `pyhouse-git` names catalogue skills today.
- The four rules `CLAUDE.md` states in two places (git ↔ `python-versioning` and `/release`) end up in
  two products.
- `/pyhouse:setup`'s dependency list, the three `adopt` commands, and `tools/`: the import checker
  stays with Python, the secrets hook's test goes with the hook, and the skill-loading measurement is
  undecided.
- `DECISIONS.md`, `CHANGELOG.md` and tags: each part gets its own version line and tag, since a tag
  names one released thing (`python-versioning` rule 13).
- `CLAUDE.md`, `kickoff.md`, `README.md` and the indexes.
- Names: "pyhouse" names Python, so the parts that are not Python need names of their own.

Open:
- Separate repositories and marketplaces, or a smaller first step: keep the one marketplace, move the
  review into delivery or into a plugin of its own, and drop delivery's dependency on
  `pyhouse-universal`. That alone lets a frontend repository install delivery, git and secrets without
  any Python. It may be all the need asks for, and the full split can wait until a second language has
  skills of its own.
- Whether git stays separate from delivery, or the two become one language-free part.
- Order: this comes after 125, which lands alone.

Either way it is a break. A plugin that is renamed, moved or loses a dependency changes what an
installed project resolves, so it takes a minor bump below 1.0.0, and the release note says how to
reinstall.

## Agreed

Every earlier item has landed or was closed (D130–D178, D191, D192, D195–D198, D201–D210, D212–D214,
D216, D217, D219, D220).

### 125. The flat family is renamed `layered`
**Agreed** (maintainer, 2026-11-23). "Flat" names no architecture anywhere outside this catalogue, so a
reader meeting `flat-*` has nothing to look up, while the style it covers has an established name:
the layered architecture (Richards, *Software Architecture Patterns* ch. 1 and *Fundamentals of
Software Architecture* ch. 10), packaged by layer (Brown), with transaction scripts above it (Fowler) —
the last two already cited in `flat-layered`. It pairs with `hex` as one named style with another, and
the literature separates the two on the axis this catalogue does: dependencies run down to the data
access in one and in to the domain in the other. This reverses D1, which kept `flat-*` because no one had
asked; the maintainer now has.

The change: `pyhouse-flat` becomes `pyhouse-layered`, every `flat-*` skill takes the `layered-*` prefix,
and `flat-layered` becomes `layered-architecture`, the mirror of `hex-architecture`. "The flat family"
and "a flat service" become "the layered family" and "a layered service" throughout, including the
argument `/pyhouse:setup` and `/pyhouse-universal:adopt` take (`hex | layered`), the prefix table in
`meta-skill-author` and `CONVENTIONS.md`, both indexes and their counts, the top-level `README.md`,
`CLAUDE.md`, `kickoff.md`, `.claude/commands/commit.md`'s scope vocabulary, `QUESTIONS.md`'s test-service
table, and `tools/skill_prompts.json` and `tools/measure_skill_loading.py`. `DECISIONS.md` and
`CHANGELOG.md` are history and keep the old names. Since `hex-architecture` also speaks of layers,
`architecture-choice` says in one sentence what tells the two apart, so "layered" is not read as "has
layers".

It is a break: a project that names a `flat-*` skill, or whose `CLAUDE.md` section `adopt` wrote lists
them, stops resolving them, so every plugin whose files change takes a minor bump below 1.0.0, and the
release note tells such a project to rerun `/pyhouse:setup` or `/pyhouse-universal:adopt`. It lands
alone: the marketplace keeps its name and its seven plugins.
