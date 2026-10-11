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

## 2. Check where it lands

**An empty repository** — `git rev-parse --verify HEAD` fails, and every `git log` below with it →
this is the first commit. It necessarily lands on the mainline, because it is what creates it
(`git-branching` exempts it), and there is no history to read: skip the branch and convention checks
and the practice reading in step 4, and say so.

**Check the branch.** On the mainline, in a repository whose changes land through requests → say so
and offer to branch first, named as `git-branching` rule 3 says; a commit made there bypasses the checks every other change passes
(`git-branching` rules 1 and 3).

**Check the existing convention.** Run `git log --no-merges --oneline -15`. If that history is *not* in
Conventional Commits form, say so and ask before introducing it — a repository with one convention is
better than a repository with two, and this is the commit that would split it.

## 3. Stage, then read the staged diff

Stage the resolved files with `git add -- <resolved files>`, then read exactly what will be committed
with `git diff --staged -- <resolved files>` (`git diff --staged` for an empty argument). Stage first:
`git diff` shows nothing for a file git does not track yet, so a new file would pass unread. Two things
to stop for, both of which a commit makes expensive to undo:

- **A secret** — a credential, token, private key, or a local environment file that holds them →
  stop and say so. Do not commit it.
- **An unrelated change riding along** — a stray debug line, a reformatted file nobody asked for →
  name it and ask whether it belongs in this commit or a separate one.

On a stop, unstage what this step staged, so nothing is left half-committed:
`git restore --staged -- <resolved files>`, or `git rm --cached -r -q -- <resolved files>` in an empty
repository, where there is no `HEAD` to restore from. Both leave the working tree as it was. Both
return a path to `HEAD`, which would discard staging the person did before this command ran, so a
named file that already had staged changes then is left as it is, and the report says so.

## 4. Compose the message

Write the message by the **`git-commit-message`** skill. It ships in this plugin and owns the
convention — the message shape, the type and the release it records, scope, breaking changes, the
description, body, footers and trailers, and where the convention has to hold under each merge
strategy. Load it if it is not already in context. This command does not restate it, so that there is
one copy to keep right.

The skill defers two things to the repository, and this command finds both out before writing:

- **Its existing practice.** Read `git log --no-merges --oneline -20` for the scopes and casing in use,
  and `git log --no-merges -5` and the contributing guide for whether bodies and footers appear and
  whether a sign-off is required. The skill follows what is there — except a line saying which tool,
  model or agent wrote the change, which it never adds whatever the history carries, and a sign-off,
  which it asks the author for (rule 8).
- **Its merge strategy**, when this commit will land on a branch. `git-branching` rule 2 says how to
  find it where nothing records it, and when to ask; the message skill's rule 9 puts the convention on
  the request title under one strategy and on every commit under the other, so the answer changes what
  is being written.

**A fix to work that has not landed yet** — under a method that keeps every commit, it is a fixup
folded into the commit it corrects, as `git-branching` rule 4 says.

## 5. Commit

Commit the resolved paths and nothing else, by naming them after `--`: `git commit -F -` alone
commits the whole index, including whatever was staged before this command ran. A rename is named by
both its old and its new path. For an empty argument the staged index is what was asked for, and no
paths are named. Anything else still staged stays staged and out of this commit; name it in the
report. Named paths are committed as they stand in the working tree, so nothing may change between
the step 3 review and the commit; where something did, read the staged diff again.

**While a merge is in progress** (`git rev-parse -q --verify MERGE_HEAD` succeeds), git refuses a
commit of named paths: check that the index holds only the merge's resolution, then commit the whole
index and name no paths.

Pass the message on standard input through a quoted heredoc, never `-m "<message>"`: inside double
quotes the shell expands `$` and backticks, both common in a body, and a multi-line message is easy to
mangle. The quoted delimiter makes every character literal:

```
git commit -F - -- <resolved files> <<'EOF'
<the message composed in step 4>
EOF
```

Then report the hash, the subject, and the files and line counts:

```
<hash>  <subject>
<N> files, +<added> -<removed>
```

Do not push, tag, or create a branch unless asked.
