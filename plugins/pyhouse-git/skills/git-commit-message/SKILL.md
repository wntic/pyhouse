---
name: git-commit-message
description: Use when writing a commit message, or deciding what type, scope or breaking-change marker a change takes — whether through a command or typed by hand, in a repository of any language. Owns the Conventional Commits 1.0.0 message shape, the rule that the type records which release the change earns and is chosen by what the change is rather than how large it was, why a commit that is not a release never touches the version, how a break is marked so a tool reading the history finds it, and where the convention has to hold under a squash or a merge-commit strategy. Staging and committing is `/commit`; refusing a malformed message at commit time is `/install-commit-hook`; computing and cutting the release is `/release`.
when_to_use: Also when asked for a commit message, a conventional commit, whether a change is feat or fix, how to mark a breaking change, what a squash-merge request title should say, or whether a feature commit should bump the version.
---

# Git — Commit Message

A commit message is the one record of a change that every later reader has: the reviewer, the person
running `git log` a year on, and the tool that works out the next release. This skill is what that
message has to say and where it says it. It assumes no language, package manager or forge, and it
states no staging or committing procedure — that is `/commit`'s.

The obligation underneath survives any convention: **a message records what kind of change it is, in a
position a tool can read, because that kind decides the release.** Conventional Commits 1.0.0 is the
binding below; every rule above it holds under another.

## When to use vs. neighbours

- Staging files, reading the diff and committing in one step → `/commit`, which composes its message
  by this skill.
- Refusing a malformed message at commit time instead of trusting everyone to remember →
  `/install-commit-hook`, which installs a `commit-msg` hook that checks the parts of this skill a
  machine can check: the shape, the blank line before a body, the uppercase break token and the subject
  length.
- Which merge method a repository uses, how a branch's history is cleaned before it lands, and what
  may never be rewritten → `git-branching`. Rule 9 below is what that choice obliges each message to be.
- Working out the next version from the types since the last tag, and cutting the one release commit
  that rule 2 lets touch it → `/release`, which proposes and cuts only on an explicit yes.
- What a version number promises, and what counts as breaking for a Python distribution →
  `python-versioning`, in the `pyhouse-universal` plugin. This skill records which release a change
  earns; that one decides what the number means.
- A release note a consumer reads before upgrading → written for that reader, never generated from
  these messages. The history says what changed; a release note says whether to upgrade.

## Template — Conventional Commits 1.0.0

```
<type>[(<scope>)][!]: <description>

[body]

[footers]
```

| Type | For | Release |
|---|---|---|
| `feat` | a capability that was not there before | minor |
| `fix` | a defect corrected | patch |
| `docs`, `refactor`, `perf`, `test`, `build`, `ci`, `style`, `chore` | everything else, by what it is | none |

`feat` and `fix` are the two the specification mandates and the two that carry a release; the others
are conventional, and a repository may use more. A break carries the major whatever its type:

```
feat(foo-client)!: return every page where only the first was returned

BREAKING CHANGE: fetch_foos now returns every page. A caller that relied on one
page should pass limit=1, or call fetch_first_foo for the single-page form.
```

## Other bindings

- **A changelog-fragment workflow**, where each change adds a small file naming its kind and a release
  tool assembles them. The kind moves out of the message into the fragment; the obligation — one
  machine-readable kind per change, deciding the release — is unchanged, and the message is then free
  to be plain prose.
- **A repository with its own type vocabulary**, wider or narrower than the table. The specification
  permits it. What cannot change is that only the release-bearing kinds carry a release, so a new type
  maps either onto one of the three rows or explicitly onto none.

## Rules

1. **The type records what kind of change this is, and is chosen by what the change is, never by how
   large it was.** A one-line change that adds a capability is `feat`; a rewrite of a thousand lines
   that changes no behaviour is `refactor`. The type is the field a tool derives the release from, so a
   mistyped commit proposes the wrong version.
2. **A commit that is not a release does not touch the version.** The type is the record; the release
   reads every type since the last tag and takes the strongest, once. Bumping as each change lands
   carries the number past anything released and leaves versions no tag ever carried.
3. **A break is marked where a tool finds it, and says what breaks and what to do instead.** `!` before
   the colon, and a `BREAKING CHANGE:` footer — the one token that must be uppercase. `!` alone is
   enough only when the description already says what broke. The footer is written for the caller who
   has to change something: what stopped working, and its replacement.
4. **The description can be understood without the diff, and does not repeat the type.** Imperative
   mood, no trailing period, specific enough that someone scanning `git log --oneline` knows what
   happened.
5. **A body explains why, when the diff does not.** The problem before the change, then the trade-off
   taken, in prose rather than a list, one blank line after the description. A change that explains
   itself gets no body.
6. **One logical change per commit.** A description that needs "and" is two commits — unless the parts
   cannot build or pass apart, in which case they are genuinely one.
7. **Scope, casing and subject length follow what the repository already does.** Read the history
   before the first message written there. Invent no scope vocabulary in one commit; where the
   repository uses none, omit the scope. Where it has no settled casing, lowercase. Keep the subject
   line, type and scope included, within 72 characters unless the repository sets another limit.
8. **Add no trailer by habit.** An authorship line, a sign-off or a tool advertisement goes in only when
   the repository already carries it or the author asked for it in this commit. A trailer asserting
   authorship or sign-off makes a claim the author did not make.
9. **The convention holds wherever the surviving message is written.** Under a squash merge the
   request's title replaces every commit on the branch, so the title is what must be conventional, and
   one request is one logical change. Under a merge commit every branch commit lands, so each must be.
   Either is fine and both at once is not: the check then has to sit in two places, and usually sits in
   one. Pick one, state it where contributors read, and enforce it there — `git-branching` rule 2.

## Hard stops

- A type is being chosen by how large or important the change feels → stop, classify it by what it is.
- A commit that is not a release edits the version → stop, the release derives the number from the
  types since the last tag; this commit records a kind, it does not bump.
- A change that breaks a caller is being committed without a break marker → stop, the release computed
  from the history will be a minor or a patch that breaks everyone who upgrades.
- A `BREAKING CHANGE` footer names what broke and not what to do instead → stop, the reader of that
  footer is the caller who has to change something.
- The description needs "and" → stop, split the commit.
- A trailer is being added by habit → stop, drop it unless the repository or the author asked for it.
- A squash-merging repository's request title is not conventional → stop, the title is the message that
  survives; fix it before merging.
- A scope is being invented in the first commit that uses it → stop, use the repository's vocabulary or
  none.
