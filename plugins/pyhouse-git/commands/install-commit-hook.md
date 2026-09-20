---
description: Install the commit-msg hook that rejects a commit message which is not Conventional Commits, either shared with the repository or local to this clone
argument-hint: "[shared | local]"
---

Install `${CLAUDE_PLUGIN_ROOT}/git-hooks/commit-msg` into the current repository so a malformed
commit message is refused at commit time rather than found later.

## 1. Check the ground

- Not a git repository (`git rev-parse --git-dir` fails) → say so and stop.
- **A `commit-msg` hook already exists** at the destination → show it and ask before replacing. Do not
  overwrite a hook someone wrote; if it is this same file, say so and stop rather than reinstalling.
- `core.hooksPath` is already set to something else → name it, and say that installing elsewhere will
  have no effect while that setting stands.

## 2. Choose where it goes

`$ARGUMENTS` picks one; when empty, **recommend shared** and say why in one line.

**shared** — `.githooks/commit-msg`, tracked in the repository, with `core.hooksPath` pointing at it:

```
mkdir -p .githooks
cp "${CLAUDE_PLUGIN_ROOT}/git-hooks/commit-msg" .githooks/commit-msg
chmod +x .githooks/commit-msg
git config core.hooksPath .githooks
```

The hook is reviewed and versioned like anything else, and everyone gets the same one. **Say the
catch plainly: `core.hooksPath` is per-clone configuration, so every contributor runs that last
command once.** A hook nobody enabled protects nobody — if the repository has a setup script or a
task runner, add the line to it and say so.

**local** — `.git/hooks/commit-msg`, this clone only, nothing tracked:

```
cp "${CLAUDE_PLUGIN_ROOT}/git-hooks/commit-msg" .git/hooks/commit-msg
chmod +x .git/hooks/commit-msg
```

Right for trying it out, or for a repository whose convention is not settled. It protects one person.

## 3. Prove it runs

Do not report success on a copy. Run the hook against a message it must reject and one it must
accept, and show both results:

```
printf 'not a conventional subject\n' > /tmp/pyhouse-hook-check
<installed path> /tmp/pyhouse-hook-check ; echo "exit=$?"     # expect a failure and exit=1
printf 'feat: add the thing\n' > /tmp/pyhouse-hook-check
<installed path> /tmp/pyhouse-hook-check ; echo "exit=$?"     # expect silence and exit=0
rm -f /tmp/pyhouse-hook-check
```

An exit status of 0 on the first message means the hook is not being read — usually a missing
executable bit, or a `core.hooksPath` pointing somewhere else.

## 4. Report

Say where it went, whether it is tracked, and what a contributor must run to enable it. Then name the
two ways out, because a hook that cannot be bypassed gets deleted rather than fixed:

- `git commit --no-verify` skips it for one commit.
- `git config --unset core.hooksPath`, or deleting the file, removes it.

## Optional settings

Mention these only if asked, or if the repository obviously wants one:

```
git config pyhouse.commit.types "feat fix docs refactor perf test build ci style chore"
git config pyhouse.commit.maxSubject 72
```

Without a `types` list the hook accepts any lowercase type, which is what the specification allows —
`feat` and `fix` are the only two it mandates. Set the list when a project wants its vocabulary
closed; leave it unset when it does not.

## What this does not cover

The hook validates commits written in this clone. **If the project squash-merges, the message that
reaches the mainline is the merge request's title, which no local hook sees** — that check belongs in
CI or in the forge's own settings. Say so when installing into a repository that squashes, rather
than leaving the impression that the mainline is now guarded.
