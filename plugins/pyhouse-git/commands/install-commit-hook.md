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
- **`core.hooksPath` is already set** (`git config --get core.hooksPath`) → name it, and do not change
  it: another tool or a teammate owns that setting, and repointing it silently disables every hook
  already there. Offer to install into that directory instead. Where a hook manager owns it and
  regenerates its files (husky, for one), a copy placed there is overwritten — add the hook through the
  manager's own configuration, calling this file, and say so.

## 2. Choose where it goes

`$ARGUMENTS` picks one; when empty, **recommend shared** and say why in one line.

**shared** — `.githooks/commit-msg`, tracked in the repository, with `core.hooksPath` pointing at it.
Only where `core.hooksPath` is unset; otherwise install into the directory it already names (step 1):

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

**local** — the clone's own hooks directory, this clone only, nothing tracked. Ask git where that is
rather than assuming `.git/hooks`: in a linked worktree or a submodule `.git` is a file, not a
directory, and where `core.hooksPath` is set the answer is that directory:

```
hooks=$(git rev-parse --git-path hooks)
mkdir -p "$hooks"
cp "${CLAUDE_PLUGIN_ROOT}/git-hooks/commit-msg" "$hooks/commit-msg"
chmod +x "$hooks/commit-msg"
```

Right for trying it out, or for a repository whose convention is not settled. It protects one person.

## 3. Prove it runs

Do not report success on a copy. Have **git** run the hook — not the file run by hand, which proves
the file and not that git finds it — against a message it must accept and one it must reject, and show
both results. `git hook run` (git 2.36 and later) runs it exactly as a commit would:

```
check=$(mktemp)
printf 'feat: add the thing\n' > "$check"
git hook run commit-msg -- "$check" ; echo "exit=$?"     # expect silence and exit=0
printf 'not a conventional subject\n' > "$check"
git hook run commit-msg -- "$check" ; echo "exit=$?"     # expect the hook's refusal and exit=1
rm -f "$check"
```

The accepted message comes first because it separates the two failures: a non-zero exit on it, with
`cannot find a hook named commit-msg`, means git is not reaching the file — it is not executable (git
says it was ignored), or `core.hooksPath` points somewhere else. Before git 2.36, run the file at the
path git resolves, `"$(git rev-parse --git-path hooks)/commit-msg" "$check"`: it proves the location
git reads, and a missing executable bit shows as exit 126, not as a pass.

## 4. Report

Say where it went, whether it is tracked, and what a contributor must run to enable it. Then name the
two ways out, because a hook that cannot be bypassed gets deleted rather than fixed:

- `git commit --no-verify` skips it for one commit.
- Deleting the file removes it — and `git config --unset core.hooksPath` as well, only where this
  install is what set it.

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
