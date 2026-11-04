---
description: Write the spec for one change with the person who wants it — the questions, the file, and every acceptance criterion checked before any code exists — and mark it ready only once each check has passed
argument-hint: "[a sentence or two about the change, or the path of a draft spec to finish]"
---

Write the spec for one change, by the `delivery-spec` skill, with the person who wants it, and check
its criteria before anyone implements it.

**The skill holds the rules** — the sections, what goes into Contracts, when a spec is several, the
form a fix takes, what a criterion is and how each is checked. This command drives the work. Load the
skill first and work from it; restate none of it here, and do not answer from memory.

## 1. Find what the project already says

- Read the repository's `CLAUDE.md` (and any file it imports) for where specs live, the environment
  criteria run in with its commands, and how long a check may take. Read the specs already there for
  their numbering, language and the wording of their headings, and the decision records, where the
  project keeps them.
- What is not written down, ask once, in one message: the specs directory, the environment and the
  commands that reach it, the time a check may take — the environment only where the skill asks for
  one. Use the answers for this spec; this command does not write them into `CLAUDE.md`.
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

Showing is done in the reply: what a tool printed reaches only you. A draft is shown by its path, what it
delivers and its numbered criteria; a diff the person asks for is quoted in full, and a check's output
in the lines that decide met or not met.

## 4. Check every criterion

Check each criterion the way the skill names for it, and keep the output of each check.

- A check rule 11 holds for the person's yes — ask before running it, naming what it touches. This
  holds for a check run while drafting, too.
- A step the skill makes the person's — ask them to run it and paste what came back.
- A criterion that fails its check: show the output, propose the correction, and change it only once
  the person agrees. Check again only the criteria that changed, once; whatever still fails after that
  goes to the person as it stands.

## 5. Mark it ready, or leave it a draft

Set `Status: ready` once the skill's rule for a ready spec holds. Otherwise it stays a draft, and the
report says which criteria block it.

Report the file's path and one line per criterion: how it was checked, and met or not met. Leave the
file uncommitted. Where the person asks for the commit, it is a change of its own, by the branching the
repository records.
