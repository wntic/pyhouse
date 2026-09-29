---
description: Start a session on this repository with its purpose, the lessons that shape every change, the current state and the open work already in view
---

Get oriented before doing anything else. Read, in this order:

1. `CLAUDE.md` — what the repository is, its invariants, branching, releasing and review.
2. `.claude/review/QUESTIONS.md` — the criteria every change to a skill is reviewed by.
3. `.claude/backlog.md` — edits already agreed or proposed and not yet made.
4. `git log --oneline -15` and `git status` — what landed last and whether anything is in flight.

Then reply with three to five lines: where the repository stands, what is open in the backlog, and
anything in flight. Ask what to work on. Change nothing until the maintainer answers.

## Why this catalogue exists

The maintainer's team is backend developers and data scientists. Everyone writes code with AI agents,
mostly through short prompts with no skills loaded, and the result is the same every time: a service
that is one or two modules of a thousand lines, comments everywhere, a package layout ignored even
where one was asked for. The maintainer, a backend engineer, then spends days rewriting it.

The catalogue is the fix: skills an agent loads so that the code it writes is clean from the start —
the right layout, small modules, one owner per concern. It serves the data scientists and the
maintainer alike: someone who can write the code still wants to prompt in two sentences and get the
structure right. The same skills are the criteria an agent reviews code against.

Two architecture families exist because two kinds of service exist: hexagonal for a service with
business rules of its own, flat for workers, ingest, ETL and glue with no rules to protect. The
universal plugin holds what binds any Python project, including a library or a CLI tool.

## The lessons every change is made under

- **An agent copies templates and skeletons verbatim** — names, comments, constants, package sets.
  A line in a template is a line in every project that uses it.
- **Generic over sample.** Much of the catalogue was first written from one real application, and
  review rounds kept passing it because they checked the skills against their own format rules and
  against that application. Most services of the family must have a line for it to belong in a
  template; everything else is one sentence of prose or nothing.
- **A defect becomes a rule, not a template.** A failure seen in one generated service is stated as an
  obligation without the mechanism. Reviews only ever added until deletion became a finding.
- **Language-level concerns live in universal skills**; a family skill uses them and defines no
  family-wide instance. What is optional is shown as optional.
- **Judge by outcome.** The real test is what an agent builds from a short prompt with the skills
  installed — not whether the skills conform to their own format.

## How work is done here

Each change goes on its own branch and lands with a merge commit, as `CLAUDE.md` records. Every change
to a skill is reviewed with `/review-skills` before it is committed; every agent that writes or reviews
skills is given `QUESTIONS.md`. Commit after each verified step; a fix to a commit the branch already
carries is a fixup, folded into it before the branch lands. Merging to `main`, pushing and cutting
a release are the maintainer's call unless they said otherwise in this session.

## Keeping this command true

When the purpose, the families, the review setup or the way work is done changes, update this file in
the same change. Open work goes in `.claude/backlog.md`, not here.
