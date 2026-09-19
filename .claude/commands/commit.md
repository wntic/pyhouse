---
description: Check the catalogue contract, stage, and commit specified files or previously introduced changes
---

> This repo holds no Python — the "code" is `SKILL.md` files and plugin manifests. There is nothing to
> lint, so step 2 checks the contracts that break silently instead. The commit message rules are
> unchanged.

## Argument interpretation

`$ARGUMENTS` can be:
- File paths / directories (e.g. `plugins/pyhouse-hex/skills/hex-wiring/`) — commit exactly those
- A description like `changes that you introduced` — resolve to the files you edited in this session

If `$ARGUMENTS` is empty, fall back to whatever is already staged.

## Steps

### 1. Resolve target files

If arguments are file paths: use them directly.
If arguments describe prior changes: recall which files you created or modified in this conversation and use those.

### 2. Check the catalogue contract

Run these against the resolved files. Any failure stops the commit and is reported to the user.

**Every skill touched:**

```
for d in <resolved skill dirs>; do
  n=$(basename $d); got=$(grep -m1 '^name:' $d/SKILL.md | sed 's/name: *//')
  [ "$n" != "$got" ] && echo "name/dir mismatch: $n != $got"
done
grep -h '^description:' <resolved SKILL.md files> | grep ': .*: '   # bare ": " breaks the YAML parse
```

`name` must equal the directory name, `description` must open `Use when …` and contain no bare
colon-plus-space, and a `paths:` glob must be prefixed `**/` and absent on universal skills.

**If a skill was added, renamed or rescoped**, confirm all four are in step — the counts go stale first:

```
for p in plugins/*/; do echo "$p $(ls $p/skills | grep -v README | wc -l)"; done
```

- `plugins/pyhouse-universal/skills/README.md` — entry and the count in its heading
- `plugins/pyhouse-universal/skills/meta-skill-author/CONVENTIONS.md` — `## Index` line, heading count, packaging table
- top-level `README.md` — the plugin table
- the skill's own `description`, which both indexes must agree with

**Read the diff for contract breaks** — no tool catches these:

- A real project, service, tenant, bucket, queue or product name where a placeholder belongs
  (`Foo`/`Bar`/`myapp`/`myschema`/`myrepo`/`foo_parser`), in any spelling including env-var prefixes
- A rule in `## Rules` that says nothing once the library name is removed — it belongs in the template
- A second full template for an alternative stack — that is `## Other bindings` bullets or a sibling skill
- A `## Template` heading that does not name its stack
- A hard stop softened into advice ("think carefully before X" is not a stop)
- A universal skill *requiring* a `hex-*`/`flat-*` skill, or a cross-family reference carrying a rule
  the referrer needs
- A skill, section or rule that exists only because some source material happened to use a technology

If any of these is broken, stop and ask before continuing — do not commit content the catalogue's own
rules reject.

### 3. Stage files

```
git add <resolved files>
```

### 4. Write the commit message

Inspect the staged diff with `git diff --staged`, then compose a **Conventional Commits 1.0.0**
message — https://www.conventionalcommits.org/en/v1.0.0/.

```
<type>[(scope)][!]: <description>

[body]

[footers]
```

**Type** — the type states the kind of change, so the description does not have to. It also decides
the next release under `## Releasing` in `CLAUDE.md`, which is why picking it is not cosmetic:

| Type | Use for | Release |
|---|---|---|
| `feat` | a new skill, command or agent; an existing skill's scope widened | minor |
| `fix` | a correction that changes no obligation — a dead cross-reference, a template whose imports do not resolve, a broken frontmatter parse | patch |
| `docs` | `README.md`, `CLAUDE.md`, `DECISIONS.md`, or an index entry changed on its own | none |
| `refactor` | a skill restructured without changing what it obliges — a split into sibling files, a section reordered | none |
| `chore` | manifests, versions, tooling, repository housekeeping | none |
| `test` | `tools/` and anything that checks the catalogue | none |

A skill and the index entries it forces are **one** commit, so it takes the skill's type — `feat`,
not `docs`. `docs` is for a documentation change that stands alone.

**Scope** — a noun naming the part of the catalogue affected. Prefer the skill's own name; fall back
to the plugin, or `catalogue` for something genuinely cross-cutting.

```
feat(python-versioning):    fix(hex-wiring):    docs(catalogue):    chore(universal):
```

**Breaking changes** — a skill removed or renamed, a rule reversed, a plugin's prefix set changed.
Anything that breaks a project already carrying the catalogue. Mark it **both** ways when the
description alone will not carry it: `!` before the colon, and a `BREAKING CHANGE:` footer saying what
breaks and what to do instead. `BREAKING CHANGE` is the one token that must be uppercase.

**Description**
- Lowercase, imperative, no trailing period — "This commit will…" completes the sentence
- Specific enough to understand without reading the diff; the type already says what kind of change it is, so do not repeat it (`feat(x): add …`, never `feat(x): add a new feature that adds …`)
- Whole subject line ≤72 characters including type and scope

**Body** (include when the cause or decision is non-obvious)
- Blank line after the description
- 72-char wrap
- Explain *why*, not what — context, the problem before, trade-offs
- Plain prose, not bullet lists

**Footers** — one blank line after the body. A token uses `-` for spaces:
- `Closes #N`, `Fixes #N`, `Refs #N`
- `BREAKING CHANGE: <description>`
- `Co-Authored-By: <name> <email>`

**Atomic commits**: one logical change per commit — if the description needs "and", split it. A skill
and the index entries it forces are *one* change, not two.

### 5. Commit

```
git commit -m "<message>"
```

Output the commit hash to the user after committing:

```
Committed as <hash> - <N> files, <M> insertions.
```
