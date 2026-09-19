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

**Check the existing convention.** Run `git log --oneline -15`. If that history is *not* in
Conventional Commits form, say so and ask before introducing it — a repository with one convention is
better than a repository with two, and this is the commit that would split it.

## 3. Stage

```
git add <resolved files>
```

## 4. Compose the message

```
<type>[(scope)][!]: <description>

[body]

[footers]
```

**Type** — what kind of change this is, and what release it earns. This is the load-bearing field: a
tool reading the history derives the next version from it.

| Type | For | Release |
|---|---|---|
| `feat` | a capability that was not there before | minor |
| `fix` | a defect corrected | patch |
| `docs` | documentation only | |
| `refactor` | behaviour unchanged, structure changed | |
| `perf` | faster, behaviour unchanged | |
| `test` | tests only | |
| `build` | build system, dependencies, packaging | |
| `ci` | pipeline configuration | |
| `style` | formatting only, no code change | |
| `chore` | housekeeping that fits nowhere above | |

`feat` and `fix` are the two the specification mandates; the rest are conventional and a project may
use others. Pick by **what the change is**, never by how large it was.

**Scope** — optional, a noun naming the part of the codebase affected, in parentheses:
`fix(parser):`. Use what this repository already uses; where it uses none, omit it rather than
inventing a vocabulary in one commit.

**Breaking changes** — anything that makes a caller who followed the documented surface stop working.
Mark with `!` before the colon, and add a `BREAKING CHANGE:` footer naming what breaks and what to do
instead. `!` alone is enough only when the description itself says what broke. `BREAKING CHANGE` is
the one token that must be uppercase.

```
feat(api)!: return a list where a single object was returned

BREAKING CHANGE: `get_items` now returns a list. Callers reading `.id` directly
should read `[0].id`, or use `get_item` for the single-object form.
```

**Description** — imperative, no trailing period, specific enough to be understood without the diff.
The type already says what kind of change it is, so do not repeat it. Keep the whole subject line
within 72 characters, type and scope included. Match the repository's existing casing; where there is
none, lowercase.

**Body** — include it when *why* is not obvious from the diff. Blank line after the description,
wrapped at 72, plain prose rather than a bullet list, explaining the problem before and the trade-off
taken. Skip it entirely for a change that speaks for itself.

**Footers** — one blank line after the body. A token uses `-` in place of spaces:
`Closes #N`, `Refs #N`, `BREAKING CHANGE: …`, `Reviewed-by: …`.

**Add no trailer of your own.** `Co-Authored-By`, a generator or tool advertisement, `Signed-off-by` —
none of these go in unless this repository already uses them or the author asked for them in this
commit. Check `git log` rather than assuming: a trailer added by habit is noise in every future
`git log`, and one asserting authorship or sign-off makes a claim the author did not make.

**One logical change per commit.** If the description needs "and", it is two commits — unless the
parts cannot compile or pass apart, in which case they are genuinely one.

## 5. Commit

```
git commit -m "<message>"
```

Then report the hash, the subject, and the files and line counts:

```
<hash>  <subject>
<N> files, +<added> -<removed>
```

Do not push, tag, or create a branch unless asked.
