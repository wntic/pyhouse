# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

`pyhouse` is a **Claude Code plugin marketplace**, not a Python project. It contains no Python source,
no build system, no test suite and no dependencies — only Markdown skills plus three plugin manifests.
The "code" is 42 `SKILL.md` files that tell an agent how to write Python services; the Python in them
is template content, never executed here.

Because there is nothing to build, verification is reading: the contracts below are the only things
that can be broken, and they are broken silently.

## Commands

```bash
claude plugin marketplace add wntic/pyhouse        # or `add .` to test this checkout locally
claude plugin install pyhouse-hex@pyhouse          # or pyhouse-flat / pyhouse-universal
```

`/commit` (in `.claude/commands/`) is the repo's own commit flow: it runs a house-style review before
staging and refuses to commit code that breaks a Hard stop. It delegates the family detection to a
`/style-review` command that is **not** in this repo — it comes from the user's own config, so the
step degrades to a manual review if that command is absent.

## Layout

```
.claude-plugin/marketplace.json          lists the three plugins
plugins/pyhouse-universal/               10 skills (9 universal + meta-skill-author), /choose-architecture
plugins/pyhouse-hex/                     25 hex-* skills
plugins/pyhouse-flat/                    7 flat-* skills
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

**Three plugins, one-way dependency.** The prefix decides the plugin: unprefixed and `meta-*` →
`pyhouse-universal`; `hex-*` → `pyhouse-hex`; `flat-*` → `pyhouse-flat`. Family plugins depend on
`pyhouse-universal`, so a `hex-*`/`flat-*` skill may reference a universal skill freely. A universal
skill may name a family skill only as an *example* and must still read correctly with that plugin
absent — `pyhouse-universal` has to be installable alone. Hex↔flat references are expected to dangle
(the families are mutually exclusive) and must therefore name the plugin: "`flat-layered`, in the
`pyhouse-flat` plugin". A cross-family reference that carries a rule the referrer *needs* is a defect.

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

**One instance already unwound, and one still to go.** Two skills in the flat family existed only
because the originating source used a particular durable-execution engine. They are gone: their
obligations are now stack-independent rules in `flat-entrypoint` and `flat-test-run-function`, and
that engine's spelling of them sits in `flat-entrypoint/DURABLE.md` as one binding named in its own
headings. That is what unwinding a technology-shaped skill looks like — the rules stay, the vendor
becomes a template. Do not re-set the precedent by adding another.

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
