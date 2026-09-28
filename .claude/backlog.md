# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

### 35. A side effect after the store write has no rule
Found by item 19's review (lens 3). `hex-application` Compensation rule 1 puts a notification after
`repo.create` with nothing after it, and command handler rule 5 forbids a `try/except`, so a partner
timeout answers 502 for a stored foo (the client's retry then conflicts), a queue redelivery conflicts
forever, or an agent spawns an unobserved task. Proposed rule, mechanism left open: a side effect after
the store write never reports a committed command as failed and is never dropped unrecorded — the
handler stops its failure and logs it once, after the success event, or hands it to something that
retries it.

## Agreed

Decided by the maintainer on 2026-09-28, every open item at once. Order of work: 34, 19, 11 and 31
first, in parallel, since they touch disjoint files; then 14 (after 11 and 31, which touch
`flat-persistence`) and 24 (after 34, which touches `hex-restapi-app`); then 26; 4 last. Review
findings are applied where a test service backs them; a contested one — lenses disagreeing, a whole
file or skill deleted, a rule reversed — goes to the maintainer.

### 34. Hex templates keep the structured logger, and name it where they do not yet
Unlike `flat-entrypoint` before D129, every hex log line carries an obligation: `hex-application`
command handler rule 6 (the handler logs the command's success), the warning a failed undo earns under
compensation, and the central error handler logging a failure once. Nothing is removed. The binding is
already named in `hex-application`'s template heading; name it in `hex-restapi-app`'s template heading
and at `hex-persistence/UNIT_OF_WORK.md`'s handler template, which uses it without saying so.

### 11. Webhook redelivery and ordering get a word, not a template
- No new test. `flat-test-run-function` rule 3 already pins the second run of "any run a trigger may
  retry", and rule 5 keeps the body out of a wrapper test. Rule 3 names a delivery the sender may repeat
  among its examples.
- `flat-persistence` rule 12 gains one sentence: where an older write can arrive after a newer one, the
  update is guarded by the row's ordering stamp, so the older never overwrites the newer. `HTTP.md`'s
  pointer then names that rule. No template: most services do not have the case.

### 31. A routine is a sentence; a block laid once as written stays
The criterion for command blocks: one a project runs once, as written — the `alembic init` bootstrap in
the setup skills, `git-branching`'s one-time `gh api` block (D121) — stays; a routine repeated per change
or per release becomes a sentence beside its rule.
- `flat-persistence/SETUP.md`: the `alembic revision --autogenerate` / `alembic upgrade head` block → a
  sentence.
- `python-versioning/SKILL.md`: the `git tag -a` / `git push` block → a sentence (an annotated tag
  carrying the `v`).
- `meta-skill-author` (~line 378): "shapes add and remove nothing" is reworded — a shape adds no section,
  and the one section a skill may omit is `Template(s)`, when it has nothing to copy.

### 14. A universal `persistence` skill owns every store-generic obligation
A new universal skill (working name `persistence`; reference shape, no template) owns what holds in any
Python project with a store, whatever its family:
- from both families: one declared transaction owner per callable, a multi-statement write as one
  transaction, driver-error translation at the data-access edge with the offending field and the full
  constraint name in the context, constraint names generated from one convention, the pure row mapping
  that gives a naive timestamp its offset, migrations as an expand/contract deploy step with a
  reversing downgrade, a repository that never logs;
- from `hex-persistence` alone: column types chosen by meaning, timestamps stored with their offset, a
  closed value set as a constraint over text, indexing what is filtered, joined and sorted on;
- from `flat-persistence` alone: conflicts resolved explicitly with the matched key never updated,
  deduplication by the store's own write-time or merge-time mechanism, a cursor read over a total order;
- from `hex-conventions` (item 21): that a table name is derived by one rule declared once.

The id policy stays in the families (hex mints `uuid4` with no dependency, flat a time-ordered id).
Each family skill keeps only its own shape — flat: one package per store, batched Core writes, no
protocol; hex: port-satisfying adapters, entity mapping, the paired revision, the unit of work — and
points at the owner. The ownership table in `meta-skill-author`, both indexes and every count move with
it. `hex-persistence/REPOSITORY.md` says in one sentence at the constructor why `FooRepository` takes
the session factory and `FooSessionRepository` a session (`:68`, `:152`). The test-side echo is item 26.

### 21. No conventions skill for the flat family
`hex-conventions`' registry exists because hex has fixed layers and many artifacts per aggregate; flat
has no fixed tree by design, and its package-naming decisions are `flat-layered`'s "The package names".
The one derivation with no flat owner, the table name, is store-generic and moves to item 14's skill.
Closed by the change that does 14.

### 24. Audit the four `hex-restapi-*` skills and their tests
Run `/review-skills` on `hex-restapi-app`, `hex-restapi-auth`, `hex-restapi-endpoint`,
`hex-restapi-schema`, `hex-test-restapi-auth` and `hex-test-restapi-endpoint`, generality first, and
apply the findings. `TRANSFER.md` is code taken from one application — an import/export CSV pair, a
10 MiB ceiling, a mixed multipart + JSON route; lens 1 decides whether it is reduced to rules or
deleted. Absorbs item 5: `TRANSFER.md`'s `ImportFoosHandler`/`ExportFoosHandler` go with it.

### 26. Audit the test skills the same way
After 14, 19 and 24 have landed, run `/review-skills` over every `hex-test-*` and `flat-test-*` skill,
in two batches, and apply the findings. Known echoes: the unit-of-work and session fakes (14), the
repository-contract and persistence tests against the new universal owner (14), the restapi tests (24),
the template comments (D123, D128). `hex-test-restapi-auth` and `hex-test-application-handler/FAKES.md`
are the densest in domain nouns.

### 4. Re-run the short-prompt scenario on the current skills
Last, once everything above has landed. The maintainer runs the short `dns_scanner` prompt on GLM
against the pushed `main`, as before the generality rework; the output is then reviewed the same way
(layout, module size, which skills loaded, defects → rules).
