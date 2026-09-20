# pyhouse

House-style rules for writing Python services, as Claude Code skills.

Forty-two skills covering naming, packaging, versioning, errors and tests — plus two mutually exclusive service
architectures. They are project-neutral: worked examples use `myapp` and `Foo`, never a real service
name. The skills are plain `SKILL.md` files, so Claude Code, opencode and Codex all read them.

## Install

```bash
claude plugin marketplace add wntic/pyhouse
claude plugin install pyhouse-hex@pyhouse       # or pyhouse-flat
claude plugin install pyhouse-git@pyhouse       # /commit, independent of the rest
```

Either family brings `pyhouse-universal` with it. Install `pyhouse-universal` alone for just the
language-level rules, or before you have picked an architecture.

| Plugin | Skills | What it covers |
|---|---|---|
| `pyhouse-universal` | 11 | Naming, typing and logging, packaging and re-exports, what a version promises and what changes it, the error catalogue, the testing constitution, the workspace root when one repository holds several distributions, the architecture chooser, and the reviewer that applies all of it to code that already exists. |
| `pyhouse-hex` | 24 | Ports and adapters: layer boundaries, the composition root, entities and value objects, CQRS handlers, persistence with paired migrations, the REST family, eight test families. |
| `pyhouse-git` | — | A language-independent `/commit`: reviews what is about to be staged, then writes a Conventional Commits message whose type carries the release the change earns. `/install-commit-hook` adds a `commit-msg` hook that refuses a malformed message at commit time. Depends on nothing; install it on its own. |
| `pyhouse-flat` | 7 | Package-by-technical-role for workers, pipelines and ETL: the package layout and its import contract, the package owning a service's data access, trigger choice from loop to durable execution, four test families. |

## Which family?

> **Does this service have business invariants of its own that it must enforce?**

Rules about what is valid living in your codebase — **hexagonal**. Orchestrating external systems,
where correctness is whether the data moved — **flat-layered**. A script run once and deleted, or a
project whose layout Django, Airflow or a package-by-feature convention already fixes — neither.

Run `/choose-architecture` for the cases that are not clean: invariants *and* heavy integration work,
a flat service growing its first rule, a monorepo holding both, and the shapes the catalogue does not
cover.

## Reviewing existing code

The same rules are the review criteria. `/pyhouse-universal:code-review` reads a diff, a commit range or a path and
reports where the code departs from them; it runs in a subagent, so reading the tree and the skills
costs the calling session nothing but the report.

It states no rules of its own. It works out which family the code is in — or that it is in neither,
which is the answer for a Django tree, a library, a CLI or an ML repo, and means most of the
catalogue does not bind — then checks each skill's own precondition before holding the code to its
rules. Every finding names the skill and the rule or hard stop it came from; anything it cannot
attribute is reported as a gap in the catalogue, not as a finding against you.

It reports obligations, never a difference from a template: a finding you would have to change
library to act on is a review of that library, which its own tooling does better.

## How a skill is written

`## Rules` states what must be true in terms that survive changing library. `## Template(s)` carries
one concrete binding, named in its heading. `## Other bindings` names the alternatives. `## Hard stops`
are stops, not advice.

So the rules still hold if you swap the ORM, the DI container or the logger.

## The catalogue

[`plugins/pyhouse-universal/skills/README.md`](plugins/pyhouse-universal/skills/README.md) lists every
skill and what it owns. `meta-skill-author` is the format's own authority.

## Licence

MIT — see [`LICENSE`](LICENSE).

Copying the templates into your own project needs no attribution and puts no obligation on the code
around them. The attribution clause covers redistributing the catalogue itself.
