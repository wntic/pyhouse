---
description: Write into this repository's agent instructions which pyhouse skill governs each kind of Python work, so agents load the skills rather than merely having them installed; settles no architecture family
argument-hint: "[nothing, or the architecture family the code already follows]"
---

Name, in the file the repository's agents read their instructions from, the skill an agent loads before
each kind of Python work. Run once per repository, new or existing; running it again updates the
section it wrote.

**The skills hold the rules.** This command writes only where to find them; it states none of them, and
it chooses no architecture family.

## 1. Find the instructions file

- The file agents read is the one the repository already has: `CLAUDE.md` at the root (or
  `.claude/CLAUDE.md`), else `AGENTS.md`. Where `CLAUDE.md` imports `@AGENTS.md`, or both exist and
  neither imports the other, write `AGENTS.md` — and in the second case propose adding `@AGENTS.md` to
  `CLAUDE.md` rather than writing the section twice. Where there is neither, create `CLAUDE.md`.
- A section headed `## Python house style` that this command wrote before → update it in place.
- A new section goes at the end of the file. Nothing else in the file changes.

## 2. Write the section

```markdown
## Python house style

The pyhouse skills are installed for this repository and are not background reading: before each kind
of work below, load the skill named for it and do the work the way it says. A skill loaded earlier in
the session still counts. Where this file states a convention of its own, it wins over a skill.

| Before you… | Load |
|---|---|
| start a new service | `pyhouse-universal:architecture-choice`, then the layout skill of the family it picks |
| write or change Python code | every pyhouse skill whose description matches the code you are writing |
```

The family is not chosen here. Only where `$ARGUMENTS` names the family the code already follows, add
the row "add, move or split a package or module | `pyhouse-hex:hex-architecture`" (or
`pyhouse-flat:flat-layered`). Where the repository is a library or a CLI tool, the first row is left
out. Where the file is `AGENTS.md`, skills are named bare — `architecture-choice` — since the
plugin-qualified form is Claude Code's.

## 3. Report

Say which file was written. Leave it uncommitted. Where the person asks for the commit, it is one change
of its own — on a branch, where the repository records branching. Where the `pyhouse-git` plugin is
installed and the file has no section on branches and commits, name `/pyhouse-git:adopt`, which writes
that one.
