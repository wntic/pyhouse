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

**The message rules are shipped, not restated here.** Read
`plugins/pyhouse-git/skills/git-commit-message/SKILL.md` — the skill this repository publishes — for
the Conventional Commits template, the scope rule, the breaking-change form, and the description, body,
footer and trailer rules. That file is the authority and it is in this tree, so it cannot dangle.

What this repository adds is **which type its own artifacts take**, since "a capability that was not
there before" needs saying in terms of a catalogue of Markdown:

| Type | Here it means | Release |
|---|---|---|
| `feat` | a new skill, command or agent; an existing skill's scope widened | minor |
| `fix` | a correction that changes no obligation — a dead cross-reference, a template whose imports do not resolve, a broken frontmatter parse | patch |
| `docs` | `README.md`, `CLAUDE.md`, `DECISIONS.md` or an index entry changed on its own | none |
| `refactor` | a skill restructured without changing what it obliges — a split into sibling files | none |
| `chore` | manifests, versions, repository housekeeping | none |
| `test` | `tools/` and anything that checks the catalogue | none |

`BREAKING CHANGE` here means a skill removed or renamed, a rule reversed, or a plugin's prefix set
changed — anything that breaks a project already carrying the catalogue.

**Scope** is the skill's own name where one skill is the subject, else the plugin, else `catalogue`.

```
feat(python-versioning):    fix(hex-wiring):    docs(catalogue):    chore(universal):
```

A skill and the index entries it forces are **one** commit and take the skill's type — `feat`, never
`docs`. `docs` is for a documentation change that stands alone.

**No trailers.** This repository uses none: no `Co-Authored-By`, no generator lines, no
`Signed-off-by`. The shipped skill's rule 8 adds a trailer only where the repository already carries
one or the author asked for it, and this repository carries none.

### 5. Commit

Pass the message through a quoted heredoc, never `-m "<message>"`: inside double quotes the shell
expands the backticks and `$` a body here routinely carries:

```
git commit -F - <<'EOF'
<type>(<scope>): <description>

<body>
EOF
```

Output the commit hash to the user after committing:

```
Committed as <hash> - <N> files, <M> insertions.
```
