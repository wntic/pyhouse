# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

`pyhouse` is a **Claude Code plugin marketplace**, not a Python project. It has no build system, no
test suite and no runtime dependencies — only Markdown skills, four plugin manifests, and one
maintainer script. The "code" is 45 `SKILL.md` files — 43 that tell an agent how to write Python
services, and two that tell it how to commit and branch. The Python in them is template content,
not executed as part of anything here.

Most of the contracts below can only be checked by reading, and they are broken silently. One cannot:
whether the symbols a template imports exist. `tools/check_template_imports.py` resolves every import
in every fenced `python` block against an environment with the catalogue's stack installed, and
reports three outcomes — resolved, **missing**, and *unchecked* where a package is absent so nothing
was verified. Run it before shipping a template:

```bash
python3 -m venv .venv && .venv/bin/pip install -q fastapi dishka sqlalchemy greenlet \
  pydantic-settings structlog respx pytest 'testcontainers[postgres,minio]' alembic redis \
  aioboto3 pyjwt uuid6 httpx cryptography idna qdrant-client uvicorn
.venv/bin/python tools/check_template_imports.py
```

It exists because a template once imported two symbols that do not exist in the library it binds, and
every other check in this repository passed over it.

## What it is for

Two uses, and every rule in it is shaped by serving both.

**Writing.** The catalogue is carried into any Python project — greenfield or brownfield, any domain,
any stack, any scale — and used immediately, without adaptation. A rule that holds only on the project
it was extracted from is worthless here however useful it was there.

**Reviewing.** The same rules are the criteria an agent checks code against. This is why the two-layer
split is not stylistic: an **obligation** ("one declared transaction owner per callable", "translate the
driver's error at the boundary") is checkable on any codebase, and a **spelling** ("pass
`join_transaction_mode="create_savepoint"`") is checkable only where the stack happens to match, and is
noise everywhere else. A reviewer carrying a vendor's manual reports that an SDK call is malformed,
which is a review of that SDK and not of this style — and the vendor's own tooling does it better.

Both uses give the same test, which is the one to apply before adding or keeping anything: **would this
still be correct, and still be worth writing, if the project that inspired it had used a different
stack, a different layout and a different domain?** If the honest answer is no, it documents a history
rather than a style.

The corollary for anything that reviews: the rules live in the skills, so a review artifact states
none of its own. It decides which skills apply and applies them.

## Commands

```bash
claude plugin marketplace add wntic/pyhouse        # or `add .` to test this checkout locally
claude plugin install pyhouse-hex@pyhouse          # or pyhouse-flat / pyhouse-universal
```

`/commit` (in `.claude/commands/`) is the repo's own commit flow, and its subject is **this
repository**: step 2 checks the catalogue contract — frontmatter, the placeholder vocabulary, the two
layers, the index counts — because there is no Python here to lint. It calls nothing external.

`/pyhouse-universal:code-review` (shipped in that plugin, not in `.claude/commands/`) is the other direction:
its subject is a **Python project that installs the catalogue**. It resolves a target and hands it to
the `pyhouse-reviewer` subagent, which decides which skills apply and applies them. The two never
overlap — running the review command on this repository finds no architecture family and nothing to
review, which is correct.

## Releasing

The catalogue is subject to `python-versioning` like anything else it ships, and its five version
fields — one per plugin, plus the marketplace — are what that skill calls **members versioning
independently**: each plugin is installed on its own, so each manifest carries its own number, and
they are not expected to match. Read the current numbers from the manifests themselves; this file
does not restate them, because a restated number is the first thing to go stale.

**One bump per plugin per release, never per commit.** A plugin's next number is the strongest change
to it among the commits since the last tag — three `feat` commits in one release are one minor bump,
not three. Bumping as each commit lands inflates the number past what was ever released, and leaves
versions that no tag ever carried.

What moves a plugin's number:

- **Major** — a skill removed or renamed, a rule reversed, or a plugin's prefix set changed. Anything
  that breaks a project already carrying the catalogue.
- **Minor** — a skill added, or an existing one's scope widened. The common case, and what a new skill
  takes: it adds to the surface without changing what is there.
- **Patch** — a correction inside a skill that changes no obligation: a typo, a dead reference, a
  template whose imports did not resolve.

**While a number is below 1.0.0, a major change bumps its minor.** `python-versioning` rule 9: `0.y.z`
withholds the compatibility promise, and reaching 1.0.0 is the act of making it — a decision for the
maintainer, never a consequence of one breaking commit.

The marketplace's own number moves whenever a plugin's does — by a minor when any plugin moved by a
minor or more, by a patch when every plugin that moved only patched — because the tag names it and a
tag is never reused.

**The commit type already decided this.** Commits here are Conventional Commits 1.0.0, whose
`feat` / `fix` / `BREAKING CHANGE` map onto the three rows above, so the next number is read off
the commits since the last tag rather than argued about at release time. `/release` (in
`pyhouse-git`) does that arithmetic and proposes the numbers; cutting one is still the maintainer's
call. The type table and the scope vocabulary are in `.claude/commands/commit.md` step 4; they are
not repeated here.

**Tags are the repository's, not the plugin's.** One artifact ships all four plugins together, so the
tag names the marketplace version — `v0.4.0`, with the `v` on the tag and never in a manifest. A tag
is immutable: a correction is the next number, never a moved tag.

## Branching

Recorded once here, as `git-branching` rule 2 asks of any repository.

- `main` is the mainline. It always passes the catalogue checks; releases are tags on it, cut by
  `/release`.
- Every change is made on a short-lived branch named for it — `feature/…` or `fix/…` — started from
  current `main`.
- A branch lands with a merge commit (`--no-ff`), keeping every commit. Never squash, never
  rebase-merge.
- History on `main` is never rewritten, and a branch is deleted once it has landed.

## Layout

```
.claude-plugin/marketplace.json          lists the four plugins
DECISIONS.md                             why things are the way they are, and how to reverse each
tools/check_template_imports.py          resolves every import in every template (see above)
plugins/pyhouse-universal/               11 skills (10 universal + meta-skill-author),
                                         /choose-architecture, /code-review, agents/pyhouse-reviewer
plugins/pyhouse-hex/                     24 hex-* skills
plugins/pyhouse-flat/                    8 flat-* skills
plugins/pyhouse-git/                     2 git-* skills, /commit, /release,
                                         /install-commit-hook and the commit-msg hook it
                                         installs — no dependency
```

Each plugin's manifest is the single file `plugins/<plugin>/.claude-plugin/plugin.json`; `skills/` and
`commands/` sit at the plugin root, beside that directory, never inside it. A skill is
`skills/<skill-name>/SKILL.md` — **the directory name is the skill name** — plus sibling `.md` files
when the body would otherwise run past ~500 lines (only `SKILL.md` is loaded automatically; a sibling
is reached only by an explicit instruction in the body to read it).

## Before writing or editing a skill

Read `plugins/pyhouse-universal/skills/meta-skill-author/SKILL.md` **and** its sibling
`CONVENTIONS.md`. Together they are the authority for the frontmatter contract, the canonical section
order, the four skill shapes, the placeholder vocabulary and the rule-ownership table. The summary
below exists to tell you what you would break, not to replace them.

## The invariants that are easy to break

**Four plugins, one-way dependency.** The prefix decides the plugin: unprefixed and `meta-*` →
`pyhouse-universal`; `hex-*` → `pyhouse-hex`; `flat-*` → `pyhouse-flat`. Family plugins depend on
`pyhouse-universal`, so a `hex-*`/`flat-*` skill may reference a universal skill freely. A universal
skill may name a family skill only as an *example* and must still read correctly with that plugin
absent — `pyhouse-universal` has to be installable alone. Hex↔flat references are expected to dangle
(the families are mutually exclusive) and must therefore name the plugin: "`flat-layered`, in the
`pyhouse-flat` plugin". A cross-family reference that carries a rule the referrer *needs* is a defect.

`git-*` → `pyhouse-git`, which stands outside that graph: it depends on nothing and nothing depends on
it, because it is installed in repositories of any language. A `git-*` skill may name a catalogue skill
only as an example and must read correctly with it absent. Since neither side can require the other, a
rule both need is stated in both, worded to agree. There are two instances: a commit which is not a
release does not touch the version, stated by `git-commit-message` from the commit's side and by
`python-versioning` from the number's; and below 1.0.0 a break bumps the minor, stated by
`git-commit-message` beside its type table and by `python-versioning` rule 9. Neither is a duplicate
to delete.

**Principle and binding stay separate.** `## Rules` states obligations that survive swapping the
library ("translate the driver's integrity error at the repository boundary"), never mechanisms
("catch `IntegrityError`"). `## Template(s)` carries exactly one stack and its heading names it
(`## Template — SQLAlchemy Core`). Alternatives get 1–3 bullets under `## Other bindings` — never a
second full template; if one is really needed, it is a sibling skill.

**A rule lives in exactly one skill.** The ownership table in `meta-skill-author` assigns naming,
typing/logging, packaging, the error catalogue, boundaries, testing and the architecture choice to
specific owners. Everything else points at the owner. Before replacing a restatement with a pointer,
open the owner and confirm the rule is actually there — a pointer to a rule that was never written is
invisible.

**`description` must stand alone.** opencode and Codex read `description` and nothing else, so it must
disambiguate the skill from its siblings without `when_to_use`. It opens `Use when …`, trigger first,
one paragraph, no bare `: ` (a colon-plus-space breaks the YAML parse and the skill silently stops
auto-firing), no application-specific names. `paths` narrows auto-activation, so it globs a layer
directory prefixed `**/` (`**/domain/**`) and never appears on a universal skill or on
`architecture-choice`, which must fire on a greenfield tree.

**Placeholders only.** `Foo`/`Bar` aggregates, `myapp` a distribution's own package, `myschema` a
shared library several distributions depend on, `myrepo` the repo root, `myframework` a framework a
rule is about *wrapping*. No placeholder asserts a repository shape — one distribution and no
`myschema` is the ordinary case. Real role, tenant, bucket, queue, database or product names are
banned in every spelling including SCREAMING env-var prefixes. Technology names (`postgres`, `redis`,
`jwt`, `s3`, `dishka`) stay concrete on purpose, except one a rule is about wrapping.

## Source material is evidence, never a model to copy

When the user supplies source code, a repository, a config or any other material as the basis for a
new skill or an extension to an existing one, **that material is a case study, not a subject**. Read it
to find the rule it obeys or violates, then write the rule and forget where it came from. Specifically:

- **Do not carry its names across.** Not its aggregates, services, packages, tables, queues, buckets,
  env-var prefixes, roles or tenants, in any spelling. Map every one onto the placeholder vocabulary
  before a line is written; a name with no placeholder to map onto earns a new row in the
  `CONVENTIONS.md` table, not an exception.
- **Do not reference the project.** No "as in the crawler service", no allusion to its team, its
  history or its layout. A reader outside that project must not be able to tell it existed.
- **Do not let its technology set the scope.** That a sample happens to use a given library, broker,
  framework or vendor SDK is a fact about the sample, never a reason for a skill, a section, a rule or
  a hard stop to exist. The obligation comes first; the technology appears only as the one binding
  under `## Template(s)`, named in the heading, with the alternatives acknowledged under
  `## Other bindings`.

The test before adding anything sourced this way: **would this still be worth writing if the material
had used a different stack?** If the answer is no, the skill is documenting someone's dependency
choice. If yes, but the shape changes, write the version that survives the swap.

**The one instance is fully unwound.** Two skills in the flat family existed only because the
originating source used a particular durable-execution engine. They are gone, and so is the engine:
their obligations are stack-independent rules in `flat-entrypoint` and `flat-test-run-function`, each
in a subsection of `## Rules` that applies only once an engine has been earned, with a matching
subsection of `## Hard stops`. The vendor's spelling of them survived for a while as a sibling binding
file and no longer does — it was a vendor manual the model already knows, standing where the rules only
this catalogue can supply have to be, and at 648 lines it was 22% of the plugin. That is what unwinding
a technology-shaped skill looks like at the end — the rules stay and the vendor leaves entirely. Do not
re-set the precedent by adding another.

`python-style` was the other item and is done: the two bullets that named a DI library and a UUID
package in prose are gone, and its validation-constraint rule is stated as an obligation with the
library named once as an example. What it still names is legitimate — a structured logger under a
heading that says so, and a driver exception as the example in a rule that reads without it.

## Two indexes, kept in step by hand

A skill's coverage is stated in its own frontmatter, and two files restate it:

- `plugins/pyhouse-universal/skills/README.md` — the shipped catalogue index (grouped by family, with
  counts in every heading).
- `plugins/pyhouse-universal/skills/meta-skill-author/CONVENTIONS.md` — the `## Index` section, one
  disambiguating line per skill.

`meta-skill-author` describes both as generated output and says to run "the index generator". **No
such generator exists in this repository yet**, so today both are edited by hand. Adding, renaming or
rescoping a skill means updating both, plus the counts in their headings and in the packaging table,
plus the top-level `README.md` — the counts are load-bearing and go stale first.
