# pyhouse

House-style rules for writing Python services, as Claude Code skills.

Forty-four skills covering naming, packaging, errors and tests — plus two mutually exclusive service
architectures. They are project-neutral: worked examples use `myapp` and `Foo`, never a real service
name. The skills are plain `SKILL.md` files, so Claude Code, opencode and Codex all read them.

## Install

```bash
claude plugin marketplace add wntic/pyhouse
claude plugin install pyhouse-hex@pyhouse       # or pyhouse-flat
```

Either family brings `pyhouse-universal` with it. Install `pyhouse-universal` alone for just the
language-level rules, or before you have picked an architecture.

| Plugin | Skills | What it covers |
|---|---|---|
| `pyhouse-universal` | 9 | Naming, typing and logging, packaging and re-exports, the error catalogue, the testing constitution, the architecture chooser. |
| `pyhouse-hex` | 25 | Ports and adapters: layer boundaries, the composition root, entities and value objects, CQRS handlers, persistence with paired migrations, the REST family, eight test families. |
| `pyhouse-flat` | 10 | Package-by-technical-role for workers, pipelines and ETL: the uv monorepo, the shared schema package, entrypoints, durable workflows, five test families. |

## Which family?

> **Does this service have business invariants of its own that it must enforce?**

Rules about what is valid living in your codebase — **hexagonal**. Orchestrating external systems,
where correctness is whether the data moved — **flat-layered**. A script run once and deleted, or a
project whose layout Django, Airflow or a package-by-feature convention already fixes — neither.

Run `/choose-architecture` for the cases that are not clean: invariants *and* heavy integration work,
a flat service growing its first rule, a monorepo holding both, and the shapes the catalogue does not
cover.

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
