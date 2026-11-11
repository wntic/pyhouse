---
description: Write the spec for one change with the person who wants it — the questions, the file, and every statement it makes about today's system checked before any code exists — and mark it ready only once the person has accepted it and each check has passed
argument-hint: "[a sentence or two about the change, or the path of a draft spec to finish]"
---

Write the spec for one change, by the `delivery-spec` skill, with the person who wants it, and check
what it says about today's system before anyone implements it.

**The skill holds the rules** — the sections, what goes into Contracts, when a spec is several, the
form a fix takes, what is checked before code and what is frozen once the spec is ready. This command
drives the work. Load the skill first and work from it; restate none of it here, and do not answer from
memory.

## 1. Find what the project already says

- Read the repository's `CLAUDE.md` (and any file it imports) for where specs live. Read the specs
  already there for their numbering, language and the wording of their headings, and the decision
  records, where the project keeps them.
- Where the specs directory is not written down, ask once. Use the answer for this spec; this command
  does not write it into `CLAUDE.md`.
- `$ARGUMENTS` naming an existing draft → read it and continue from step 3 in that file, with what it
  lacks.

## 2. Ask about the change

- Start from `$ARGUMENTS`; empty → ask for a sentence or two about the change. Decide from it whether
  it is a fix or a feature, say which, and let the person correct it.
- Read the code the change touches before asking anything the repository answers: where it goes, who
  calls what it changes, what already exists. Ask the person only for what the code and the records
  cannot tell — intent, scope, what is out, how a failure should behave. One question per turn, each in
  the person's terms.
- When the work needs cutting into parts done one after another, say so and propose the specs it
  splits into before writing any of them; write the one the person picks.

## 3. Write the draft

Write the file in the specs directory, named the way the specs already there are, with
`Status: draft`. Show it to the person and take their corrections before checking anything.

Showing is done in the reply: what a tool printed reaches only you. A draft is shown by its path, its
goal and scope, its contracts and its behaviour list; a diff the person asks for is quoted in full, and
a check's output in the lines that decide it.

## 4. Check what the spec says about today's system

Check each statement the way the skill names, and keep the output of each check.

- A check the skill holds for the person's yes — ask before running it, naming what it touches.
- A step the skill makes the person's that a check needs — ask them to run it and paste what came
  back. A step for after the change lands is not run now; it stays in the spec.
- A statement that fails its check: show the output, propose the correction, and change it only once
  the person agrees. Check again only the statements that changed, once; whatever still fails after
  that goes to the person as it stands.

## 5. Mark it ready, or leave it a draft

Ask the person to accept the spec as it now stands. Set `Status: ready` once the skill's rule for a
ready spec holds. Otherwise it stays a draft, and the report says what blocks it.

Report the file's path and one line per statement checked: how it was checked, and whether it held.
Leave the file uncommitted. Where the person asks for the commit, it is a change of its own, by the
branching the repository records.
