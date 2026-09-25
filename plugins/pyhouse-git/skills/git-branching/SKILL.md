---
name: git-branching
description: Use when starting a branch, deciding how a change reaches the mainline, cleaning a branch's history before it lands, or choosing whether a repository needs more than one long-lived branch — in a repository of any language. Owns the one mainline releases are cut from, recording the branching and merge method once per repository, the short-lived one-change branch, folding a fix to unlanded work into the commit it fixes, never rewriting history someone else may have built on, and when a released version earns a maintenance branch. What each commit's message says is `git-commit-message`; computing and cutting the release is `/release`.
when_to_use: Also when asked about GitHub Flow, GitFlow or trunk-based development, a develop or release branch, squash versus merge commit versus rebase merging, force-pushing, rebasing a branch, fixup commits, cleaning up work-in-progress commits, branch names, deleting a merged branch, or hotfixing a released version.
---

# Git — Branching

How a change travels from a branch to the mainline, and what the history looks like when it arrives.
This skill assumes no language, forge or team size, and it names no strategy as the right one: it
states what holds under every strategy, binds the lightest one below, and says what a heavier one
has to earn.

**Precondition — who runs a version other than the latest.** Most rules hold for any repository.
One depends on the answer:

| Does anything… | If no, this does not apply |
|---|---|
| run, or depend on, a released version other than the latest | rule 8 — nothing needs a fix on an old line, so every fix ships as the next number |

## When to use vs. neighbours

- What a commit's message says, its type, and where the convention has to hold under each merge
  method → `git-commit-message`. This skill picks the merge method; that one says what the choice
  obliges each message to be.
- Working out the next version from the history and cutting the release commit and tag → `/release`.
- What a version number promises, and the tag's own form → `python-versioning`, in the
  `pyhouse-universal` plugin.
- Refusing a malformed message at commit time → `/install-commit-hook`. It checks a message's shape,
  not which branch it lands on.

## Template — short-lived branches off one mainline, every commit kept, on GitHub

What the repository records, where contributors read — a `CONTRIBUTING` file, an agent instructions
file:

```markdown
## Branching

- `main` is the mainline. It always builds and passes; releases are tags on it.
- Every change reaches `main` through a pull request whose checks pass.
- A pull request lands with a merge commit, keeping every commit. Squash and rebase merging are off.
- A branch carries one change, starts from current `main`, and is deleted once it lands.
```

The forge enforcing it, once:

```bash
gh api -X PATCH repos/{owner}/{repo} \
  -F allow_merge_commit=true -F allow_squash_merge=false -F allow_rebase_merge=false \
  -F delete_branch_on_merge=true
```

One change, from branch to mainline:

```bash
git switch main && git pull --ff-only
git switch -c feat/foo-export

# commit each logical change by git-commit-message; a fix to a commit on this branch is a fixup
git commit --fixup=<sha-it-fixes>

# before the request lands: fold the fixups and replay onto current main
git fetch origin
GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash origin/main
git push --force-with-lease -u origin feat/foo-export

gh pr create --fill
gh pr merge --merge --delete-branch     # deletes both copies of the branch, returns to main
git pull --ff-only
```

`GIT_SEQUENCE_EDITOR=:` accepts the folded plan without opening an editor. Before git 2.44,
`--autosquash` without `-i` is silently ignored and the fixups land as they are.

## Other bindings

- **Squash merging.** The request's title becomes the one message that lands, so no branch commit
  needs curating — and the title is what has to be conventional, checked in CI or by the forge, since
  no local hook sees it. Rules 1, 2, 3 and 5 are unchanged; rule 4 moves from the branch to the title.
- **Committing straight to the mainline** (trunk-based, no requests). Workable where one person owns
  the repository and the checks run before each push. Rule 1's gate moves from the request to the
  push; rule 5 then has no branch to protect but the mainline.
- **GitFlow** — a long-lived integration branch beside the mainline, plus release and hotfix branches.
  Earned when a release has to stabilise while other work continues, or several released lines are
  maintained at once; it is rule 7's exception, taken deliberately and recorded under rule 2.

## Rules

1. **One branch is the mainline, and every change that lands on it leaves it releasable.** Releases are
   cut from it and nowhere else, so a change too large for one short branch lands in steps that each
   pass, or behind a switch that keeps it inert. Where no environment stands between the mainline and
   production, the checks a change passes before landing are the only gate, and nothing skips them.
2. **The strategy is chosen once per repository and recorded where contributors read.** How a change
   reaches the mainline, and the merge method a request lands with, are one decision — not a choice
   per request, because `git-commit-message` puts the convention's check in a different place under
   each method. Enforce it in the forge's settings where the forge allows it. Changing it later is a
   recorded decision too.
3. **A branch carries one logical change, starts from the current mainline, and lives until that change
   lands.** A long-lived branch drifts from what it will merge into, and its conflicts arrive all at
   once, late. Name it for the change, in the pattern the repository already uses.
4. **Before a branch lands under a keep-every-commit method, its history is made true.** A fix to a
   change that has not landed yet is folded into the commit it fixes, never committed as a `fix` of its
   own — that records a defect no release ever carried. Work-in-progress commits are folded or
   reworded. This is the curation a squash would otherwise do, done where the author still knows what
   each commit was.
5. **History someone else may have built on is never rewritten.** The mainline, and any branch another
   person or process has fetched, are never rebased, amended or force-pushed. A branch only its author
   has used may be, until it lands — with a force that refuses to overwrite commits the author has not
   seen.
6. **A branch is deleted once it has landed, and only by whoever created it.** A branch whose commits
   are not on the mainline is someone's unfinished work; deleting it destroys that work with no record
   it existed.
7. **The mainline is the only long-lived branch until another one earns its place.** A second
   integration line, a release-stabilisation branch or a per-environment branch each doubles where a
   change has to land. One earns its place only by a need rule 1 cannot meet — a release stabilising
   while other work continues, or an old line still maintained.
8. **A released version is fixed on the mainline and shipped as the next number, unless something
   still runs that version and cannot take the latest.** Only then is a maintenance branch cut from
   its tag, the fix landed there and on the mainline, and the maintenance release tagged from that
   branch. Precondition: something runs or depends on a version other than the latest.

## Hard stops

- A commit is going straight onto the mainline in a repository whose changes land through requests →
  stop, branch from the mainline and open a request.
- The mainline, or a branch someone else has fetched, is about to be rebased, amended or force-pushed →
  stop; its history is someone else's base. Correct it with a new commit.
- A force-push of your own branch that would overwrite what you have not seen → stop, use a lease
  (`--force-with-lease`), never a bare force.
- A request is about to land by a method other than the one the repository recorded → stop, land it the
  recorded way; a method chosen per request splits where the message convention is checked.
- A `fix` commit corrects a commit on the same unlanded branch → stop, make it a fixup of that commit
  and fold it before landing.
- A `fixup!` or `squash!` commit is about to land on the mainline → stop, fold it first.
- A branch is about to be deleted whose commits are not on the mainline, or that you did not create →
  stop, ask its owner.
- A long-lived branch is being added beside the mainline with no release to stabilise and no old line
  to maintain → stop; that is GitFlow's cost without the need that pays for it.
- Asked what a commit message or its type should be → stop, use `git-commit-message`.
- Asked what the next version is, or to cut a release → stop, use `/release`.
