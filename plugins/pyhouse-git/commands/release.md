---
description: Propose the next version from the commits since the last tag — per member, where a repository versions several independently — and only on an explicit yes write the one release commit and tag it
argument-hint: "[nothing, or a version to release as instead of the proposed one]"
---

Propose a release from the history, and cut it only when the person running this says so.

**This command decides nothing on its own.** The `git-commit-message` skill makes every commit's type
a record of which release that change earned, so the next number is arithmetic on the history, and
the arithmetic is all this command does unasked. *Whether* to release is not in the history. It is
the person's call every time, and a release is irreversible once its tag is pushed. Never run this
because a task looks finished: an agent may suggest a release and never cut one.

## 1. Read the repository's own release rules first

Look for how this repository says it releases — a `## Releasing` section in `CLAUDE.md`, a
`RELEASING` or `CONTRIBUTING` file, a release tool's configuration. Wherever it states a rule this
command also has a default for — how a break is numbered below 1.0.0, what an aggregate version
follows, how a tag is spelled — **the repository's rule wins.** Say which rules you followed and where
you fell back on a default below.

## 2. Stop on any of these

- **Uncommitted changes** → stop. The release commit must contain the release and nothing else.
- **Not on the branch releases are cut from** → stop and ask which one.
- **Behind the remote** after `git fetch` → stop. A release cut from a stale branch omits what landed.
- **`git fetch` fails** → stop and say so. An unreachable remote is not an up-to-date one; go on only if
  the person says to, and say in the proposal that the remote was not checked.
- **The tag the proposal would create already exists** → stop. A tag is immutable; the correction is
  the next number, never a moved tag.

## 3. Find the range

`git describe --tags --abbrev=0` names the last release. **No tag at all is a first release**: propose
nothing and ask what it should be — below 1.0.0 while nothing depends on this, 1.0.0 only if a
compatibility promise is being made from the start.

`git log --no-merges --format='%h %s' <tag>..HEAD` is the range; git writes merge commits itself and
the convention skips them. An empty range → nothing to release; say so and stop.

## 4. Classify every commit

By `git-commit-message`'s type table: `feat` → minor, `fix` → patch, a `!` or a `BREAKING CHANGE:`
footer → the break position, any other type → none. **Read the footer, not only the subject** — a break
stated only in the body is still a break, and it is the one classification that must not be missed.

**A commit you cannot classify** — not in Conventional Commits form, or a type the repository has not
mapped — is listed as unclassified with its subject. Never guess its weight: an under-counted break
ships as a compatible release and breaks everyone who upgrades. While any remain, the proposal is not
complete, so ask the person to classify each one before going on.

## 5. Attribute to members, where there are several

A repository whose members version independently has one version field per member — a manifest in
each member's directory: `pyproject.toml`, `package.json`, `Cargo.toml`, a plugin manifest. Attribute
each commit to every member whose directory it touches. A commit touching no member — documentation at
the root, CI, tooling — moves no number. A repository with one version is the case with one member.

Path attribution over-counts in one known way: a commit that touched a member only to update an index
or a listing it ships moves that member. Show the attribution in the proposal so the person can strike
it.

**A version derived from tags** — a build that reads the number from the VCS rather than from a field —
has no field to edit. The release is then the tag alone; say so, and skip the edit in step 7.

## 6. Propose, then stop

Per member: the strongest classification among its commits, applied **once** to its current number.
Three `feat` commits are one minor bump, not three.

**Below 1.0.0, a break bumps the minor, never the major.** Reaching 1.0.0 is the act of making a
compatibility promise, and no commit type can make that decision for anyone — so this command never
proposes 1.0.0 on its own. A `feat` bumps the minor and a `fix` the patch. Say which of these applied.

**An aggregate version** — a marketplace, a meta-package, anything whose number follows what it
contains — moves when what it offers changes: by a minor if any member moved by a minor or a major, by
a patch if every member that moved did so by a patch. It always moves when a member does, because a
repository's tag usually names it and a tag is never reused.

```
Last release:  <tag>   <N> commits since, <M> unclassified

<member>       <current> -> <next>    <why, e.g. feat: <sha> <subject>>
<member>       <current>              unchanged
<aggregate>    <current> -> <next>    follows <member>'s minor

Tag:           <next tag>
```

Under each bump, list the commits that justify it and nothing else. **Then ask for confirmation.**
Accept a different version if the person gives one — they may know of a break the types do not show,
which is the case the types exist to prevent and cannot always catch.

## 7. Cut it — only after an explicit yes

1. Edit exactly the version fields the proposal named. Nothing else goes into this commit.
2. Commit it as `chore(release): <tag>`. `chore`, because a release commit records no change of its own
   and must not propose another version — it is the one commit `git-commit-message` rule 2 lets touch
   the version.
3. Tag that commit, annotated, spelled the way the repository's existing tags are: `git tag -a <tag>`.
   The annotation names the version and each member's bump.
4. Show `git show --stat HEAD` and the tag. **Do not push** unless the person asked for the push in so
   many words: once the tag leaves this machine it cannot be taken back.

## What this does not do

**Write a release note.** A consumer reads one to decide whether to upgrade, and a commit log does not
answer that question, so a note generated from these subjects is the wrong document with the right
name. The tag annotation is not a release note. If the repository keeps release notes, say so and leave
them to the author.

**Publish.** Building an artifact and uploading it to an index is the repository's pipeline, usually
run by CI on the pushed tag.

**Decide what a version promises.** What counts as breaking for a Python distribution, and when one
should reach 1.0.0, are `python-versioning`'s, in the `pyhouse-universal` plugin; this command reads the
types it is given and trusts them.
