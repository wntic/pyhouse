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

Inspect the staged diff with `git diff --staged`, then compose a message following these rules:

**Subject line**
- Imperative mood ("This commit will…" completes the sentence)
- ≤50 chars ideally, hard limit 72
- Capitalize first word, no trailing period
- Specific enough to understand without reading the diff

**Verb choices** — prefer specific over vague:

| Vague | Better |
|---|---|
| `Update X` | `Refactor X`, `Simplify X`, `Optimize X` |
| `Fix X` | `Handle X`, `Prevent X`, `Resolve X` |
| `Change X` | `Replace X`, `Rename X`, `Move X` |
| `Add X` | `Introduce X`, `Expose X`, `Implement X` |

**Body** (include when the cause/decision is non-obvious):
- Blank line after subject
- 72-char wrap
- Explain *why*, not what — context, problem before, trade-offs
- Plain prose, not bullet lists

**Footers** (blank line before):
- `Closes #N`, `Fixes #N`, `Refs #N`
- `BREAKING CHANGE: <description>`

**Atomic commits**: one logical change per commit — if the subject needs "and", split it. A skill and
the index entries it forces are *one* change, not two.

### 5. Commit

```
git commit -m "<message>"
```

Output the commit hash to the user after committing:

```
Commited as <hash> - <N> files, <M> insertions.
```
