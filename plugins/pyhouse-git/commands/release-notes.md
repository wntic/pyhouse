---
description: Draft the release note for a release, or for what is not released yet — what changed for the people who use the project, what a break asks of them, what is deprecated — written from the changes themselves, for the person to approve
argument-hint: "[nothing, a member, or a tag range such as v1.2.0..v1.3.0]"
---

Write a release note: the document a user reads to decide whether to upgrade and what upgrading asks of
them. It is written for that reader by someone who has studied the change — here, the agent running
this — and never assembled from the commit subjects, which record how the work was done rather than
what it changed for anyone using it (`git-commit-message`; for a Python distribution, also
`python-versioning` rule 15, in the `pyhouse-universal` plugin).

**The note is a draft until the person approves it.** Write it, show it, and change nothing else.

## 1. Read the repository's own rules first

Where it keeps release notes and in what form — an existing changelog under any name or format
(`CHANGELOG.md`, `CHANGES.rst`, `NEWS`), a `RELEASING` or `CONTRIBUTING` file, a section of its agent
instructions, a forge's release pages. **Where it states a rule, the repository's rule wins**; an
existing note's headings, order, tone and link references are followed as they are.

- **A release tool owns the notes** — its configuration is in the repository: release-please,
  towncrier, changesets, git-cliff → write nothing into its file. Say so, and offer the note as text
  for the tool's input (a fragment, the release request's description) or the release page.
- **Notes are kept only on the forge's release pages** → write no file; show the note for the person to
  publish.
- **Notes are kept nowhere** → the note goes in `CHANGELOG.md` at the repository root, one
  `## <version> — <date>` section per release, in version order with the newest first.

## 2. Find the range

- **`$ARGUMENTS` names a range** → that range, headed by its end's version where the end is a release
  tag, else `Unreleased`.
- **`HEAD` is a release tag** → from the tag before it to that tag.
- **Otherwise** → from the latest release tag to `HEAD`, under `Unreleased` — unless a release commit
  in the range is still waiting for its tag (`/release` step 3), which makes it that release.

Tags are read as the repository spells them (`git describe --tags --abbrev=0`). **Under per-member
tags, each member is a release of its own**: its range starts at that member's previous tag
(`--match '<member>-v*'`), its note goes in that member's changelog where it keeps one, `$ARGUMENTS` may
name the member, and each member's tag at the range's end is a note of its own. **No release tag before
the range's end** → this is the first release: say so in one line and point at the documentation,
rather than listing what the project offers.

A section dated by a release takes its tag's date (`git log -1 --format=%cs <tag>`), never today's; an
`Unreleased` section carries none. **A section for this range already exists** → it is replaced, never
added to: at a release tag, an `Unreleased` section becomes that release's — its entries checked against
the range, its heading, date and link references rewritten for the version.

## 3. Study what changed

Read, for the range:

- **Every commit, body and footers included** — `git log --no-merges --format='%h %s%n%b%n--'` — and
  every `BREAKING CHANGE` footer or `!`, each checked against the diff and accounted for in the note.
- **The change to what users touch**, from the diff itself rather than the messages: the public names
  and signatures, the command-line surface, configuration and environment variables, file and wire
  formats, supported runtimes and dependency floors — whatever the repository's users call or depend
  on. Where one tag releases several members that version independently, say per member what changed.
- **The repository's record of decisions**, where it keeps one, for the reason behind a change a user
  will notice, where the reason tells them something — never how the change was found.
- **Every version number the note names**, read from its manifest at each end of the range
  (`git show <tag>:<manifest>`) — the release's own and, where members version independently, each
  member's — never recalled or inferred from the commits.

## 4. Write it for the user

- **Each entry says what changed for someone using the project, in their terms** — not which file
  moved or which commit did it. One user-visible change is one entry, however many commits it took; a
  change no user can observe is left out, and a change made and undone inside the range is no change.
- **A break says what the user has to do**, step by step, before anything else in the note.
- **A deprecation says what replaces it** and when it goes, if that is known.
- **A new feature is named with what it is for and when to reach for it**; its own documentation
  carries the rest.
- **Nothing a user can observe** → a release's section says so in one line, and an `Unreleased` range
  gets no section — never an entry made from internal work to fill it.
- **Every claim rests on a commit or the diff.** Where the changes leave something unclear — whether a
  change is visible, what replaces a removed name — write it as a question to the person, never a
  guess.

Group entries under the headings the repository already uses; where it has none, under Breaking,
Added, Changed, Deprecated, Removed and Fixed, leaving out any heading with nothing under it.

## 5. Report

Show the note, the range it covers, and every open question. Leave the file uncommitted. Where the
person asks for the commit, it is a documentation change of its own, written as `git-commit-message`
and `git-branching` direct. A copy for the forge's release page is made only when asked.

## What this does not do

**Choose or cut a version** — that is `/release`. **Publish** the note anywhere but where step 1 says.
