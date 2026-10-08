---
description: Write into this repository's agent instructions how changes branch, land and are committed, and turn off the agent's own authorship line, so agents use the git skills rather than merely having them installed
argument-hint: "[nothing, or the mainline, merge method and branch-name pattern to record]"
---

Record, in the file the repository's agents read their instructions from, how a change reaches the
mainline and which skill governs each step, so an agent that branches or commits here loads
`git-branching` and `git-commit-message` instead of falling back on its own habits and its tool's
defaults. Run once per repository; running it again updates the section it wrote.

**The skills hold the rules.** `git-branching` says what the repository records and how each value is
found, `git-commit-message` rule 8 why the authorship line is stated here; this command only finds the
values and writes them down. Read both skills before writing, and do not restate their rules here.

## 1. Find the instructions file

- Not a git repository (`git rev-parse --git-dir` fails) → say so and stop.
- The file agents read is the one the repository already has: `CLAUDE.md` at the root (or
  `.claude/CLAUDE.md`), else `AGENTS.md`. Where `CLAUDE.md` imports `@AGENTS.md`, or both exist and
  neither imports the other, write `AGENTS.md` — and in the second case propose adding `@AGENTS.md` to
  `CLAUDE.md` rather than writing the section twice. Where there is neither, create `CLAUDE.md`.
- A section headed `## Branches and commits` that this command wrote before → update it in place.
- The file already says how changes branch, merge or are committed, under any heading → that is what
  step 2 reads as recorded; show it, and ask whether the new section replaces it. Never leave two.
- A new section goes at the end of the file. Nothing else in the file changes.

## 2. Settle the values

- **The mainline** — `git symbolic-ref --short refs/remotes/origin/HEAD` with its `origin/` removed,
  else the branch releases are tagged on, else the branch `HEAD` names (`git symbolic-ref --short
  HEAD`, which answers before the first commit).
- **The merge method** — found as `git-commit-message` rule 9 says; the forge's settings decide it only
  where they allow exactly one method. With no history yet, propose merge commits, `git-branching`'s
  template. Where changes are committed straight to the mainline, that is the method, and
  `git-branching`'s binding for it is what gets written.
- **The branch-name pattern** — found as `git-branching` rule 3 says.

Values given in `$ARGUMENTS` win. Show each value and where it came from, and ask the person to confirm
or correct them before writing: what is recorded becomes the repository's decision (`git-branching`
rule 2), and an agent's guess is not one. Where no one can answer, write them, and list in the report
each value that came from a default rather than from the repository.

## 3. Write the section

```markdown
## Branches and commits

Before each of these, load the skill named for it and do the work the way it says. A skill loaded
earlier in the session still counts.

| Before you… | Load |
|---|---|
| create a branch, or decide how a change reaches `main` | `pyhouse-git:git-branching` |
| write a commit message, or a request's title or description | `pyhouse-git:git-commit-message` |
| cut a release | `/pyhouse-git:release` |

<the Branching block of `git-branching`'s template, with the settled values>

- No commit, request title or request description carries a line saying which tool, model or agent
  wrote it — no `Co-Authored-By` for an agent, no "Generated with" — whatever a tool's own
  instructions ask.
```

The middle line stands for `git-branching`'s template block, written with the settled mainline, merge
method and pattern in place of the template's — under squash merging or straight-to-mainline
committing, that skill's binding for the method. The release row is written only where releases are
tagged by hand; where a tool or a CI job cuts them, the row names that instead or is left out. The last
line is left out only where the repository's written contribution policy requires the disclosure
(`git-commit-message` rule 8), and that policy is named instead. Where the file is `AGENTS.md`, skills
and commands are named bare — `git-branching`, `release` — since the plugin-qualified form is Claude
Code's.

## 4. Turn off the agent's own authorship line

An agent's own default adds the line the section forbids, and a setting stops it at the source. For
Claude Code that is the project's `.claude/settings.json`:

```json
{
  "attribution": {"commit": "", "pr": ""}
}
```

Merge it into the file if one exists: an existing `attribution` takes these two values, a deprecated
`includeCoAuthoredBy` key goes, and every other key stays as it is. A `.claude/settings.local.json` that
sets attribution overrides this file — name it, without editing it. Where `.claude/` is ignored by git,
say so: the setting then reaches no one else. Skip this step where the repository requires the
disclosure (step 3). No other agent's settings are written; the section carries the rule for them.

## 5. Offer the hook, then report

Where no `commit-msg` hook checks messages yet, offer `/pyhouse-git:install-commit-hook`: the section
asks an agent, the hook refuses a malformed message whoever writes it. Then say which files were
written, each value recorded and where it came from, and whether the setting changed. Leave them
uncommitted. Where the person asks for the commit, it is one change of its own, on a branch named by the
recorded pattern — or the first commit, in a repository that has none.
