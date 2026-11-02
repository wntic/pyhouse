---
description: Set this repository up for the pyhouse catalogue in one run — the Python skill table and the branching section in its CLAUDE.md, the agent's authorship line turned off, and the commit-msg hook — by running each pyhouse plugin's own commands in turn
argument-hint: "[nothing, or hex | flat — the architecture family the code already follows]"
---

Run, in order, the commands that set a repository up for the catalogue, so a person installs one plugin
and runs one command. Run once per repository, new or existing; running it again updates what the
earlier run wrote, because every command it runs does.

**This command states no rule and writes no file itself.** Each step is another plugin's command,
invoked by its name and followed as that command says — its questions, its checks, its stops. Do not
reproduce any of them here or do their work from memory: load the command and run it. Where one is
not available, say which plugin is missing and stop.

## 1. Check the ground

- Not a git repository (`git rev-parse --git-dir` fails) → say so and stop. Every later step but one
  needs it, and setting up half a repository leaves it in a state no single command describes.
- No `CLAUDE.md` at the root and no `.claude/CLAUDE.md`, and the repository already holds code →
  offer `/init` first, so the sections below land in a file that describes the project. Where the
  person declines, or the repository is empty, go on: the adopt commands create the file.

## 2. Settle the family

`$ARGUMENTS` naming `hex` or `flat` settles it. Otherwise ask, in one question, which applies:

- the code already follows one family — which;
- a new service whose family is not settled → run `/pyhouse-universal:choose-architecture` and take its
  answer, including "neither";
- a library, a CLI tool, or a project the catalogue's families do not cover → no family.

A tree that looks hexagonal or flat is not a settled family: never infer it from the layout. An
unanswered question means no family — step 3 then leaves the family's row out, and the person can run
`/pyhouse-universal:adopt` again with it later.

## 3. Name the Python skills

Run `/pyhouse-universal:adopt` with the family settled in step 2 as its argument, or with none. It
writes the `## Python house style` section.

Its report names `/pyhouse-git:adopt` where the branching section is missing; that is step 4, so do not
treat it as a question for the person.

## 4. Record branching and commits

Run `/pyhouse-git:adopt`. It writes the `## Branches and commits` section and turns off the agent's
authorship line in `.claude/settings.json`. It asks the person to confirm the mainline, the merge
method and the branch-name pattern before it writes them — that confirmation is the repository's
decision and is never answered on the person's behalf.

Its last step offers the hook; that is step 5, so do not ask twice.

## 5. Install the commit-msg hook

Run `/pyhouse-git:install-commit-hook`, passing `shared` unless the person asked for `local`. It
checks for hooks and a `core.hooksPath` already in place and asks before touching either.

## 6. Report

One list: each file written or changed and by which step, each value recorded and where it came from,
the family recorded or that none was, and what every other contributor must run once to enable the
hook. Name any step skipped and why.

Leave everything uncommitted. Where the person asks for the commit, it is one change of its own, on a
branch named by the pattern step 4 recorded — or the first commit, in a repository that has none.

The skill-listing budget (`skillListingBudgetFraction` in `.claude/settings.json`) is not written:
raising it lists every description, but which skill loads was measured not to depend on it. Mention it
only if the person asks why some skills are listed by name alone.
