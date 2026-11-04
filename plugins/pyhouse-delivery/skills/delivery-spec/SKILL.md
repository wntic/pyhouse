---
name: delivery-spec
description: Use when writing, splitting or checking the spec for one change before it is implemented — a feature or a fix, what it names as contracts, and the acceptance criteria that decide it is done. Owns the spec's sections and which of them exist only where the project has them, the shorter form a fix takes, contracts limited to what other code depends on, the sign that one spec is several, a criterion as an action and the result it must produce run in the environment the project names, the start and logs criteria only where the project runs as a process and its tests plus a call of its public surface for a library, and criteria checked before any code is written and frozen once the spec is ready. Not why a design was chosen — that is the project's own decision record, which a spec points at. - Also when asked for acceptance criteria, a definition of done, how large a spec may be, whether a spec should name internal functions and types, how to write up a bug before fixing it, or why criteria keep failing during implementation.
user-invocable: false
---

# Delivery — Spec

A spec says what one change delivers and how anyone can tell it is done: what the change adds, what
other code will rely on, and the criteria that decide it is finished. It is written before the code,
with the person who wants the change, and it is short enough to review in one sitting. It is not a
second copy of the code, and it does not carry the reasons for a design.

## When to use vs. neighbours

- Why a design was chosen, and what was rejected → the project's decision record; a spec points at
  the section it implements and restates none of it.
- Whether a new service is hexagonal or flat → `architecture-choice`.
- How the tests a spec lists are written — layers, substitution, assert strength, a defect's failing
  test → `test-principles`.
- The commit or merge message of the change → `git-commit-message`, in the `pyhouse-git` plugin, where
  installed.
- What a change breaks, read from its diff once it exists → `/pyhouse-universal:change-review`, not a
  spec.

## Template(s)

A spec is one Markdown file per change, in the directory the project keeps them in. Section headings
may be in the project's language, worded as the project's earlier specs word them; which sections
exist, and their order, are what the template fixes — never an earlier spec's.
A section the template marks as conditional is left out entirely where its condition does not hold —
never kept with "none" under it.

### A feature

```markdown
# <the key the project's specs use>. <What the change delivers, in one line>

Status: draft

## Goal

<One paragraph: what exists once this change is done that does not exist now.>

## Source

<Only where the project keeps decision records: the record and section this spec implements.>

## In scope / out of scope

- In: <…>
- Out: <… — and the spec that takes it, where one does>

## Depends on

<The specs that must be done first, or "nothing".>

## Where the code goes

<The packages or layers this change adds or touches — never its files or the classes in them.>

## Contracts

<Only where the change adds or changes something other code depends on — a table or schema, a
message or payload, a function another component calls, an HTTP or command-line surface, a setting's
or metric's name — each with its exact name and shape.>

## Behaviour and failures

<What invalid input, a repeat or a dependency that fails or answers late leaves behind, and, where
the change holds state, a restart or a partial write — those the change has.>

## Settings and metrics

<Only where the change adds or changes one: its name, its meaning, and whether it is required.>

## Tests

<What is tested, at which level.>

## Acceptance criteria

<Where the project runs as a process: the environment the criteria run in, and any preparation, as
steps.>

1. <Action — a command, a query, a request.> → <The result it must produce — an output line, a
   number, a state.>
```

### A fix

```markdown
# <the key the project's specs use>. Fix: <the symptom, in one line>

Status: draft

## Symptom

<What was observed, where, and how to reproduce it.>

## Cause

<The code that produces it, and why.>

## Regression test

<The test `test-principles` *A defect's test* asks for; where no test can reach the defect, the check
that would have caught it.>

## Acceptance criteria

<Where the project runs as a process: the environment the criterion runs in, and any preparation, as
steps.>

1. <The action that showed the symptom.> → <The result it produces once the symptom is gone.>
```

## Rules

### What a spec holds

1. **One spec is one change a person can review in one sitting.** It is measured by a sign, not a
   line count: where the work has to be cut into parts implemented one after another, each part is its
   own spec, with its own criteria, ordered by **Depends on**.
2. **A fix takes the short form; anything else takes the full one.** A fix states the symptom, its
   cause, the regression test `test-principles` asks for and one criterion showing the symptom gone.
   A change that adds behaviour, a surface or a schema is a feature, however small, and takes every
   section whose condition holds.
3. **A spec states what, never why.** Where the project keeps decision records, the reasons live there
   and the spec names the section it implements. Where a spec and a decision disagree, the decision
   wins and the spec is corrected — by the person, not by whoever is implementing it.
4. **Contracts hold only what other code depends on** — a table or schema, a message or payload, a
   function another component calls, an HTTP or command-line surface, a setting's or metric's name —
   with exact names and shapes. A name used inside one component is left out: the implementation lays
   it down, and a spec that fixes internal names and types becomes a second copy of the code that
   drifts from it with every change. The test for each entry: would anything outside the component
   that implements it — other code, a stored row, a dashboard, an operator's command — break if its
   name or shape changed? If not, it is internal. So is a function placed in a shared package that only
   this change calls, and so is the order of steps inside the component's work: **Behaviour and
   failures** says what those steps leave behind, not how they run. An earlier spec that names
   internals is no precedent.
5. **Behaviour and failures name the paths the tests must cover** — what invalid input, a repeat or a
   failing dependency leaves behind, and, where the change holds state, a restart or a partial write —
   so they are decided before the code and not discovered in it.

### What a criterion is

6. **A criterion is one numbered action and the result it must produce.** The action is something
   anyone can run — a command, a query, a request — and the result something they can see: an output
   line, a number, a state. Whoever checks it answers met or not met and shows the output. "The code
   matches the contracts", "errors are handled", "the tests cover X" are not criteria: no one can
   answer them without rereading the spec.
7. **A criterion runs in the environment the project names, within the time the project allows a
   check.** It names that environment, where the project has one, and the preparation it needs. What
   takes longer — a long wait, an outage that is costly to provoke — goes into **Tests**, or into a
   note after the criteria that holds nothing up. A check the project's own gate already runs is not
   repeated as a criterion.
8. **A step the person must take is written as theirs.** Anything an agent may not do — handling a
   secret, deleting from an environment the person has not said is the agent's to change, an action
   needing an account it does not hold —
   is written into the criterion as the person's step, with the command they run.
9. **Criteria prove what tests cannot.** Tests prove logic, failure paths and edge cases; criteria prove
   the running system. A feature's criteria, where the project runs as a process, cover its start, the
   main path on real input, at most one failure that is cheap to provoke, and one or two signals that
   show it working — and include one standing criterion: no error-level event in its logs for the time
   the criteria take, other than the one a provoked failure is stated to produce. Where the project is a
   library, with no process to start, a call of its public surface is its criterion, its tests run in
   the gate, and neither the start nor the logs criterion applies.
10. **A criterion that waits on another spec says so** and moves into that spec's criteria — or, where
    that spec is not yet written, into this spec's **Out** line — instead of being left here unmet.

### Checked before code, frozen after

11. **Every criterion is checked while the spec is written, before any code exists.** Against the
    decision records by reading them; an assumption about a real external system by a real request to
    it; each preparation step by running it in the named environment; a command about something not yet
    built by matching every name it uses against **Contracts**; one whose action already runs on today's
    code by running it and seeing today's result — the symptom, or the behaviour being replaced — never
    by editing the result it states. A criterion that fails its check is corrected with the person,
    then checked again. A check that writes to an environment, the one the criteria run in included,
    or costs money, or calls a real external system, runs only once the person agrees, told what it
    touches; whether an environment is anyone else's is theirs to say.
12. **A spec is ready only once every criterion has passed its check.** Its status says so, and until
    then it is a draft that no implementation starts from.
13. **A ready spec's criteria and meaning change only with the person's consent.** A criterion that
    turns out unrunnable, or contradicts a decision, goes back to the person; whoever is implementing
    the spec never rewrites it to match what was built. A change the person agrees to is recorded in the
    spec, with its reason.

## Hard stops

- Asked to record why a design was chosen, or which alternatives were rejected → stop; that is the
  project's decision record, and the spec points at it.
- Asked to write the code, the tests or the commit for a spec → stop, this skill writes only the spec;
  tests are `test-principles`.
