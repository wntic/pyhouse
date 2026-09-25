---
description: Stage the named files and commit them with a Conventional Commits 1.0.0 message whose type states what the change earns — a feature, a fix, or a break
argument-hint: "[paths, or a description of the changes to commit]"
---

Commit `$ARGUMENTS` with a message following **Conventional Commits 1.0.0** —
https://www.conventionalcommits.org/en/v1.0.0/.

## 1. Resolve what is being committed

`$ARGUMENTS` is one of:

- **Paths or directories** — commit exactly those.
- **A description of prior work** ("the changes you just made") — resolve it to the files changed in
  this conversation, and list them back before staging.
- **Empty** — commit what is already staged. If nothing is staged, show `git status` and ask; do not
  stage the whole tree on a guess.

## 2. Read the diff before writing anything

Run `git diff` on the resolved files (`git diff --staged` for an empty argument). Two things to stop
for, both of which a commit makes expensive to undo:

- **A secret** — a credential, token, private key, or a local environment file that holds them →
  stop and say so. Do not commit it.
- **An unrelated change riding along** — a stray debug line, a reformatted file nobody asked for →
  name it and ask whether it belongs in this commit or a separate one.

**An empty repository** — `git rev-parse --verify HEAD` fails, and every `git log` below with it →
this is the first commit. It necessarily lands on the mainline, because it is what creates it
(`git-branching` exempts it), and there is no history to read: skip the branch and convention checks
and the practice reading in step 4, and say so.

**Check the branch.** On the mainline, in a repository whose changes land through requests → say so
and offer to branch first; a commit made there bypasses the checks every other change passes
(`git-branching`).

**Check the existing convention.** Run `git log --oneline -15`. If that history is *not* in
Conventional Commits form, say so and ask before introducing it — a repository with one convention is
better than a repository with two, and this is the commit that would split it.

## 3. Stage

```
git add <resolved files>
```

## 4. Compose the message

Write the message by the **`git-commit-message`** skill. It ships in this plugin and owns the
convention — the message shape, the type and the release it records, scope, breaking changes, the
description, body, footers and trailers, and where the convention has to hold under each merge
strategy. Load it if it is not already in context. This command does not restate it, so that there is
one copy to keep right.

The skill defers two things to the repository, and this command finds both out before writing:

- **Its existing practice.** Read `git log --oneline -20` for the scopes and casing in use, and
  `git log -5` for whether bodies and trailers appear. The skill follows what is there.
- **Its merge strategy**, when this commit will land on a branch. The skill's rule 9 says how to read
  it where nothing records it, and when to ask — it puts the convention on the request title under one
  strategy and on every commit under the other, so the answer changes what is being written.

## 5. Commit

Pass the message on standard input through a quoted heredoc, never `-m "<message>"`: inside double
quotes the shell expands `$` and backticks, both common in a body, and a multi-line message is easy to
mangle. The quoted delimiter makes every character literal:

```
git commit -F - <<'EOF'
<type>(<scope>): <description>

<body>
EOF
```

Then report the hash, the subject, and the files and line counts:

```
<hash>  <subject>
<N> files, +<added> -<removed>
```

Do not push, tag, or create a branch unless asked.
