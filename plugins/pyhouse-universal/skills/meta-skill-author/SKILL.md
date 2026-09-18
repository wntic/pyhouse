---
name: meta-skill-author
description: Use when creating a skill or reviewing its format. Defines the catalogue frontmatter and its real length limits, the two-layer principle/binding anatomy, the five-question portability gate, section order, skill shapes, naming, rule ownership, and which plugin a skill belongs to.
---

# Meta — Skill Author

A skill is **narrow**: it covers one artifact, or one set of artifacts that always arrive together.
Skills are read as reference knowledge; the job is to show how the right file gets written. Uniformity
matters more than expressiveness — a reader who has applied one skill should be able to apply any other.

This catalogue is distributed on the Claude Code marketplace, so a skill is written for someone whose
stack is not yours: state the obligation mechanism-free, then bind it to exactly one concrete stack.

This skill produces one new `SKILL.md`. It does **not** edit other skills (that is an audit task) or
design the change format.

**Read the sibling `CONVENTIONS.md` in this skill's own directory before writing anything.** It carries
the catalogue's shared placeholder vocabulary (`Foo`, `Bar`, `myapp`, `myschema` and the names derived
from them), the banned vocabulary, the index of what each existing skill covers, the three-plugin
packaging layout, and the two standing catalogue decisions — what is deliberately out of scope, and why
repositories are not split read/write. Only this file is loaded automatically; the sibling is not, so
open it rather than working from this summary of it.

## When to use vs. neighbours

- Adding a brand-new skill → this skill.
- Editing an existing skill to fix a rule or a template → not this skill; edit the file directly.
- Sweeping cross-references after a rename → not this skill; that is an audit task.
- Deciding which plugin a skill ships in → the packaging table in the sibling `CONVENTIONS.md`.
- Documenting a process rather than an artifact → still this skill; the format adapts (no `Template(s)`
  section, every other section still applies).

## File location

```
skills/<skill-name>/SKILL.md
```

The directory name **is** the skill name. One `SKILL.md` per directory, plus sibling files when the skill
needs them — this skill's own `CONVENTIONS.md` is one. A theme large enough that its body would exceed
~500 lines takes sibling topic files alongside `SKILL.md`, which then becomes navigation — but reach for
that only when the body genuinely does not fit, because only `SKILL.md` is loaded when a skill is
preloaded, so a sibling file is reached by an explicit instruction to read it.

## Frontmatter

Two fields are required. Two more are valid, documented and used deliberately.

```yaml
---
name: <skill-name>
description: Use when <trigger>. <What it owns, second.>
when_to_use: <optional — additional trigger phrasings, Claude Code only>
paths: <optional — activation globs, Claude Code only>
---
```

- **`name`** — the skill's name. Keep it identical to the directory name.
- **`description`** — what the skill covers and when to apply it. This is what gets matched to decide
  whether to load the skill, and it is the **only** field every client reads.
- **`when_to_use`** — a valid, documented Claude Code field carrying additional invocation context.
  Optional. It supplements `description`; it never replaces part of it.
- **`paths`** — a valid, documented Claude Code field carrying glob patterns that limit when a skill
  auto-activates. Optional, and not restricted to test skills. It **narrows** auto-activation, so a
  too-tight glob makes a skill unfindable in a project whose layout differs slightly. Glob the layer
  directory (`**/domain/**`, `**/tests/**`), never a file name, and prefix with `**/` so the skill
  still fires inside a workspace member. A **universal** skill carries no `paths` at all — it binds
  anywhere, and a glob would suppress it — and neither does a skill that must fire on a greenfield
  project, where the directories it would match do not exist yet (`architecture-choice` is the case).

`allowed-tools`, `metadata`, `license` and `compatibility` are also valid; this catalogue has no use for
them yet. Two further fields exist and are deliberately **not** used: `user-invocable: false` hides a
skill from the `/` menu, and `disable-model-invocation: true` blocks automatic loading. The second has a
trap — it *also* prevents the skill from being preloaded, so a skill carrying it can only ever be
invoked by hand.

### Length

- **`description` has no documented maximum.** Plan to **1,024 characters** as a safe ceiling.
- **`description` + `when_to_use` truncate at 1,536 characters combined** in the skill listing. This is
  the only hard number the platform documents.
- **There is no total budget across the catalogue.** 41 skills at ~400 characters is ~4,100 tokens,
  about 2% of a 200k window. Length is spent where it buys disambiguation, not minimised.
- Truncation is from the end, so **the trigger leads**. A description that does not fit is rewritten as
  complete sentences to fit, never cut mid-sentence.

### `description` must be self-sufficient

opencode and Codex read `description` and nothing else. A `description` therefore has to distinguish its
skill from every sibling on its own. `when_to_use` carries *additional trigger phrasings* for Claude
Code — never a fact that appears nowhere else, and never the clause that makes the skill identifiable.

### Description rules

- **Open with `Use when …` — the single opening formula.** Put the trigger first and what the skill owns
  second. The first clause decides whether the skill is loaded, so it carries the trigger: what artifact,
  what situation.
- **Never a bare `: ` inside an unquoted description.** A colon-plus-space breaks the YAML parse and
  the skill loads with empty metadata: `/name` still works, it just never fires on its own. Use an
  em dash.
- **Carry the negative routing that separates this skill from its nearest sibling, and only that.**
  A skill that never fires never reaches its own `When to use vs. neighbours`, so the one or two
  "not X — that is `<other-skill>`" clauses a dispatcher needs belong here. The *rest* of the
  neighbour map stays in the body: a `description` that carries all of it is spending length where
  it buys the least.
- One paragraph, no bullets, no line breaks. It should read as a sentence.
- No application-specific names (no `Material`, no `Order`). Use the placeholder vocabulary from the
  sibling `CONVENTIONS.md`.

### Publishing caveat

Claude Code accepts and ignores unknown frontmatter keys. **claude.ai and the Skills API do not**: they
accept only `name`, `description`, `license`, `compatibility`, `metadata` and `allowed-tools`, and
**fail hard** on anything else. A skill published on that channel must have `paths` and `when_to_use`
stripped first. Marketplace distribution — a GitHub repo plus `plugin.json`, which is this catalogue's
channel — is unaffected, so both fields are safe here.

## Body — the canonical sections

Every skill has these sections, in this order, with these exact headings — templates have one
allowance, stated in rule 1. Four sections are required; three (`Other bindings`, `Inlined typing /
import rules`, `Package wiring`) are optional, included only when load-bearing.

```markdown
# <Title> — usually `<Prefix> — <Concept>` or `<Concept>` alone

<One short opening paragraph: what the skill covers and its hardest boundary.>

## When to use vs. neighbours

<One line per genuine neighbour, as many as the skill has: "X → `skill-name`." Goal: a reader who
misclassified the work sees its real home immediately. This is also where the negative routing lives
that the description deliberately leaves out.>

## Template(s)

<One or more literal file templates with placeholder names, from the sibling CONVENTIONS.md. Show the
entire file content, not a fragment. The heading NAMES THE STACK the template binds. When the skill
covers several kinds (standalone vs UoW-managed repository, list vs cursor pagination), give one
template per kind under `### <kind>` subheadings.>

## Other bindings

<Optional. 1–3 bullets per named alternative, each saying what changes and what does not. Never a
second full template.>

## Rules

<Numbered list of the obligations specific to this artifact, stated mechanism-free. Don't restate
cross-cutting rules (typing, imports, packaging) — reference the cross-cutting skill instead. Each rule
is one short paragraph or one bold-led bullet.>

## Inlined typing / import rules

<Optional but common. A 3–6 bullet slice of the cross-cutting rules most load-bearing for THIS
artifact, so the reader need not pull the full cross-cutting skill when only a few rules apply.>

## Package wiring

<Optional. When the artifact requires updating an `__init__.py` re-export, point to
`python-packaging` in one line. Do not restate the rules.>

## Hard stops

<Bullet list of "asked for X → stop, use `<other-skill>` (or fix the request)". One line each. These
are how a reader self-detects "I'm in the wrong skill".>
```

## The two layers — principle and binding

One skill serves several stacks by keeping two layers apart.

**Layer 1 — the principle.** What the reader is obliged to achieve. It survives a change of library,
driver or framework. It lives in `## Rules`.

**Layer 2 — the binding.** One concrete stack, shown in full, so the reader has something to copy. It
lives in `## Template(s)`, and alternatives are *named* in `## Other bindings` without being written
out.

### `## Rules` states obligations, not mechanisms

The test for every rule: **would it survive swapping the library?**

- Survives: "Translate the driver's integrity error into a catalogue exception at the repository
  boundary."
- Does not: "Catch `IntegrityError`."

A rule may *name* a library as an example of the obligation — "…`IntegrityError` under SQLAlchemy" — but
the obligation must be legible with the example removed. A rule that collapses into nothing when the
library name is deleted belongs in the template, not in `## Rules`.

### `## Template(s)` headings name their stack

`## Template — SQLAlchemy Core`, not `## Template`. `## Template — FastAPI router`, not `## Template`.
A reader must know in one glance which binding they are looking at, because the binding they are looking
at may not be theirs. A bare `## Template(s)` is only correct where the template binds no stack at all —
stdlib-only code, or a directory layout.

### `## Other bindings` names alternatives without writing them

- **1–3 bullets per alternative**, each saying **what changes and what does not**. "Under the ORM,
  mapped classes replace the table objects and the session replaces the connection; the repository
  protocol, the exception translation and the transaction ownership rule are unchanged."
- **Never a second full template.** Two full templates in one skill is what makes a skill
  unmaintainable — every rule change then has to land twice, and one copy rots.
- If an alternative genuinely needs its own templates, **it is a sibling skill, not a bullet.**
- Omit the section when the skill has no real alternative. An empty `## Other bindings` is noise.

### `## When to use vs. neighbours` has no bullet cap

**One line per genuine neighbour, as many as the skill has.** There is no 3–5 limit; any such cap is
withdrawn. **Dropping a real routing edge to hit a count is a defect**, not tidiness — a reader who
lands in the wrong skill and finds no route out does the work in the wrong place.

## The portability gate

A skill ships to projects the author has never seen, so it is written against five questions and
re-read against them before every edit. The swap test above answers question 3 only — a skill can pass
it while saturated with one project's directory roles and workload assumptions.

1. **Provenance** — does anything name or imply one particular application: its domain, services,
   tables, queues, env prefixes, role names, or vocabulary invented for it?
2. **Repository shape** — does it assume a layout beyond the one artifact it describes — a monorepo, a
   workspace, sibling packages, a shared library — or carry `paths` globs matching one project's
   directory names?
3. **Technology** — is any library, framework, vendor or protocol required rather than illustrated?
   Would every rule and every hard stop still fire if it were swapped?
4. **Workload** — does it assume what the program is: that it has a database, an HTTP surface, a
   scheduler, a queue, a long-running process, more than one deployable?
5. **Residue** — strip everything the first four flag. Is there a rule left that a reader could
   actually violate, and is it the rule the skill claims to own?

### Hedging is not placeholdering

The failure these questions catch is a **disclaimer standing in for a placeholder**. "One app's
model", "rename these to suit", "illustrative only" above a concrete example lets the example
survive, and readers copy examples, not disclaimers. The proof case in this catalogue was one skill
pair carrying two source projects' role ladders and tenant names at once, each labelled "one app's
model" — when two projects each donate a ladder and both get a disclaimer, the disclaimer is doing a
placeholder's work. **The fix for a hedge is a placeholder or a deletion, never a better hedge.**

## Rules

1. **Match the section order exactly — with one allowance for templates, and one for Reference
   bodies.** Section headings are how a reader decides what to read, so renaming or reordering breaks
   navigation. `## Template(s)` is the canonical heading, and the heading names the stack it binds (see
   above); the allowance touches that section alone and takes two forms.
   **Grouped by topic** — a skill covering **several artifacts** may group its templates by topic
   instead of collecting them under one `## Template(s)`: topical `##` sections with the templates as
   `###` subheadings inside. What makes that form legal is a single condition: **the heading names the
   artifact** (`## The Table`, `## The container`, `## Upload templates`), never the subject of a
   discussion (`## Notes`, `## Background`). An artifact name answers "is this the section I need?" as
   well as `Template(s)` does; a topic name does not.
   **Singular or named** — a heading that carries **one** template may name the form and the stack under
   it (`## Template — SQLAlchemy Core`, `## Template — async, SDK-client form`, `## Skeleton — router
   file`). It is the same section under a name that fits what sits below it: the plural stays canonical,
   and a skill showing several forms of one artifact may either collect them under `## Template(s)` with
   `### <kind>` subheadings or head each form by its name.
   **Reference bodies may carry topical `##` sections.** A Reference skill produces no file and so has
   no template section to hang its subject matter on; its body may use topical `##` headings that name
   *the subject matter* (`## Naming a protocol`, `## The three dimensions`), never a discussion
   label (`## Notes`, `## Summary`, `## Background`). The required sections keep their exact headings
   and their relative order around them.
   Every other section keeps its exact heading and its place in the order, and a Reference skill still
   omits the template section — neither changes.
   These allowances rest on evidence of success rather than a test of failure: skills already written in
   the topical form were loaded and applied, and no template went unfound. If a template is ever missed
   because it sat under a topical, singular or named heading, that form is withdrawn and the single
   `## Template(s)` becomes the only heading.
2. **State the obligation, then bind it once.** `## Rules` is mechanism-free; `## Template(s)` carries
   exactly one stack; `## Other bindings` names the rest in bullets. A skill that teaches two stacks in
   full is two skills, or one skill and a sibling.
3. **Keep the body concise.** Once a skill is loaded its body stays in context for the rest of the
   session, so every line is a recurring cost. State what to do rather than narrating how or why. A
   body past ~500 lines is the signal to split into sibling topic files.
4. **Templates are literal, not prose.** Show the entire file to be written. Use the placeholders the
   sibling `CONVENTIONS.md` defines — `Foo`, `Bar`, `myapp`, `myschema`, `myrepo`, `myframework` — and
   read that file for the full set rather than guessing at it.
5. **One artifact kind per skill, or one set that always arrives together.** Two unrelated artifact
   types means two skills. Producing 2–3 tightly-coupled files (command + handler; protocol + adapter)
   is fine, and so is one skill covering several artifacts a single change always adds at once.
6. **Cross-cutting rules are referenced, not restated.** Point to the cross-cutting skill rather than
   copying its rules. See the ownership table below. An inlined slice of 3–6 bullets is acceptable when
   load-bearing.
7. **Hard stops are explicit.** Every plausible wrong-skill case becomes a hard stop with a redirect.
   This is how a reader recovers from misclassification without overreaching. A hard stop keeps its
   *reason*; softening "X → stop, use `Y`" into advice deletes the rule.
8. **Use placeholder vocabulary.** `Foo` for the primary aggregate, `Bar` for the secondary, `myapp` for
   a distribution's own root package, `myschema` for a library several distributions share, `myrepo`
   for the repository root, `myframework` for a framework a rule is about wrapping. Never name a real
   aggregate, role, tenant, bucket or service from the application at hand. The banned vocabulary is
   in the sibling `CONVENTIONS.md`.
9. **No author-side notes in the body.** Lines like "do not duplicate these rules here" address the
   author, not the reader, and they cost context on every load. Put them in the commit message.
10. **A skill must not know what invokes it.** No mention of who calls it, what it reports back, or what
    inputs some caller must supply — those belong to layers outside the skill. The purity test: would a
    new developer read this as onboarding documentation? If they would trip over a line, that line is a
    leaked layer — cut it.
11. **Names carry their style.** Anything bound to a style carries that style's prefix. An unprefixed
    name means "applies in any style".

```
<universal>              naming, coupling, python-style, ...
meta-<artifact>          meta-skill-author
hex-<artifact>           hex-domain-model, hex-application, ...
hex-restapi-<artifact>   hex-restapi-endpoint, ...
hex-test-<artifact>      hex-test-application-handler, ...
flat-<artifact>          flat-entrypoint, flat-persistence, ...
flat-test-<artifact>     flat-test-run-function, ...
```

`flat-layered` keeps its name — it is the style anchor, not an artifact skill.

12. **Run a template's imports before the skill ships.** A reader pastes a template, so every symbol it
    names has to exist in the library version the template binds — import them and see the names
    resolve. Nothing else catches this: the checks confirm a skill parses and that the skills it names
    exist, never that the code inside it runs. A symbol that does not exist is not a typo, it is a
    template nobody ran.
13. **An empirical claim names what was measured, or it comes out.** "Measured", "in practice", "this
    has been hit" are what make a rule credible, so a rule using them states the observation a reader
    could repeat — what was run, against what, and what came back. Otherwise drop the evidence
    language and let the rule stand as the obligation it is. A fabricated measurement is worse than no
    evidence: it is what stops the next reader checking.

## Ownership — reference, never restate

A rule lives in exactly one skill. Every other skill points at it.

| Rule | Owner |
|---|---|
| What anything is called, incl. the `I` prefix on protocols | `naming` |
| Typing, logging, comments | `python-style` |
| The interpreter floor, and the three settings that name it | `python-style` |
| One class per module, `__all__`, `__init__.py` re-exports, imports | `python-packaging` |
| The error catalogue and boundary translation | `exception-catalog` |
| Where a boundary goes, split vs merge | `coupling` |
| Testing constitution | `test-principles` |
| Choosing between the hex and flat families | `architecture-choice` |

**Every owner in this table is a universal skill**, so every rule it assigns is present in a
`pyhouse-universal`-only install. A rule only one family has is owned inside that family and does not
get a row — transport authentication is `hex-restapi-auth`'s, in the `pyhouse-hex` plugin — because a
row is a requirement, and a universal file may name a family skill only as an example.

**Before replacing a restatement with a reference, open the owner and confirm the rule is there.** A
pointer to a rule the owner does not state is a silent deletion, and it is invisible: both files read as
if the rule exists.

An inlined slice of 3–6 bullets under `## Inlined typing / import rules` is the one allowed exception,
and only when those bullets are load-bearing for the artifact at hand.

## Skill shapes (a navigational aid, not a requirement)

Every skill falls into one of four shapes. The section format is universal — shapes add and remove
nothing; they signal which sections will be load-bearing rather than ceremonial. Identify the shape
before writing, so the content matches skills already in the same shape.

### Producer — the default

Creates one or more new files. Emphasis: `Template(s)` carries full literal file content with
placeholders, under a heading naming its stack; `Package wiring` appears when a new module needs
registering in an `__init__.py`.

Examples: `hex-domain-model`, `hex-application`, `hex-persistence`, `hex-restapi-endpoint`,
`hex-test-domain`.

### Modifier

Extends an existing file rather than creating one. Emphasis: `Template(s)` shows what gets inserted — a
class body, a function, a decorator argument — not a whole file; `Package wiring` is usually absent
because the file already lives in a package.

Examples: `hex-wiring` (modifies the composition root), `hex-patterns` (shapes a handler body),
`test-architecture-rule` (appends a test function).

### Bootstrap

Produces a fixed set of files, once per project. Emphasis: `Template(s)` carries several full file
templates under `###` subheadings, one per file; `When to use vs. neighbours` says plainly that it is
one-shot and names what other skills depend on it having run.

Examples: `hex-restapi-app`, `hex-test-integration-setup`, `hex-test-app-invariants`.

### Reference

Produces no file — documents conventions other skills consult. Keeps `When to use vs. neighbours`,
`Rules` and `Hard stops`; omits `Template(s)`, `Other bindings` and `Package wiring`; may organise its
body under topical `##` headings that name the subject matter (rule 1).

Examples: `hex-conventions`, `hex-architecture`, `python-style`, `test-principles`, this skill.

### Picking a shape

| Question | If yes |
|---|---|
| Does it create a brand-new file each time? | **Producer** |
| Does it only extend a file that already exists? | **Modifier** |
| Does it produce a fixed set of files, once per project? | **Bootstrap** |
| Does it produce no file at all — just rules others follow? | **Reference** |

A skill that fits no shape cleanly probably mixes concerns; split it.

## Universal rules, whatever the shape

- No `## Revision` footer and no author history block — that is author metadata paid for on every load.
  Use git history.
- No section describing what the skill returns or who invokes it (rule 10).
- Hard stops use the canonical phrasing: "X → stop, use `<other-skill>`" or "X → stop, <action>".
- A reference skill omits `Template(s)`, `Other bindings` and `Package wiring`; everything else keeps
  all four required sections, under the allowances of rule 1.
- A universal (unprefixed) skill may name a `hex-*` or `flat-*` skill as an example, but may not
  *require* one — the `pyhouse-universal` plugin must be installable alone. See the packaging table in
  the sibling `CONVENTIONS.md`.

## Common pitfalls

- **Two skills wearing one name.** A description that reads "apply when X *or* Y" is two skills. Split.
- **A description that does not disambiguate.** "Apply when working with foos" is too vague. Compare
  "Apply when adding or modifying a repository adapter for an aggregate on a relational store", which
  excludes the other foo-touching work by construction.
- **A description that leans on `when_to_use`.** The other clients never see that field. If the skill is
  only distinguishable with it, the `description` is unfinished.
- **A description carrying the whole neighbour map.** Keep the one or two clauses that separate it
  from its nearest sibling; move the rest to `When to use vs. neighbours`, where a reader who is
  already in the wrong skill will see them.
- **A rule that names a mechanism instead of an obligation.** "Catch `IntegrityError`" is a template
  line wearing a rule's clothes. Restate it as what must be achieved.
- **A second full template for the alternative stack.** That is a sibling skill, or three bullets under
  `## Other bindings`. It is never a second template.
- **A `## Template` heading that does not say which stack.** The reader cannot tell whether it applies
  to them without reading the whole block.
- **Templates that document the rule instead of showing the file.** More comments than code means the
  rule is being explained. Move the explanation to `Rules` and tighten the template.
- **Hard stops that are not stops.** "Think carefully before X" is not a hard stop. The form is
  "X → stop, use Y".
- **A leaked layer.** Writing what the skill hands back to something else, or a table of inputs some
  caller must supply, is rule 10 being broken.

## After writing the file

The catalogue has two indexes — the one in the sibling `CONVENTIONS.md` and the catalogue index at
`skills/README.md`. Both are **derived from the skills' own frontmatter**, `name` plus `description`,
by the repo's index generator. They are output, not source: a skill's coverage is stated once, in its
own frontmatter.

1. **Run the index generator and commit its output with the skill.** Do not hand-edit either index —
   a line typed straight into one of them is a third statement of what the skill covers, and it is the
   one that goes stale first.
2. If the generated entry reads badly, fix the `description` and regenerate. An index cannot say
   something the frontmatter does not.
3. Confirm which plugin the skill ships in, using the packaging table in `CONVENTIONS.md` — the prefix
   decides it, and the generator groups the entry by that prefix.

## Hard stops

- A `description` that cannot be told apart from its siblings without `when_to_use` → stop, rewrite the
  `description` until it stands alone.
- A fact that exists only in `when_to_use` → stop, move it into `description` or the body;
  `when_to_use` carries extra trigger phrasings, nothing else.
- `description` past ~1,024 characters, or `description` + `when_to_use` past 1,536 → stop, rewrite as
  complete sentences that fit. Never truncate mid-sentence.
- A rule in `## Rules` that says nothing once the library name is removed → stop, it belongs in the
  template.
- A second full template for an alternative stack → stop, make it `## Other bindings` bullets or a
  sibling skill.
- `## When to use vs. neighbours` trimmed to a bullet count, dropping a real routing edge → stop,
  restore the edge.
- Asked for a skill whose whole content is a handful of rules already stated by an existing skill →
  stop; that is an edit to the existing skill, not a new one.
- Asked for a skill whose description overlaps an existing one's by more than half → stop, same reason.
- Asked for a skill built around a frontmatter field outside `name`, `description`, `when_to_use` and
  `paths` → stop, put the information in the body.
- Publishing to claude.ai or the Skills API with `paths` or `when_to_use` still present → stop, strip
  them first; that channel fails hard on unknown keys.
- Templates use application-specific names (`Order`, `Material`, `Invoice`) → stop, replace with
  `Foo`/`Bar`.
- A template imports a symbol nobody ran → stop, import it and confirm the name resolves in the version
  the template binds; a name that does not exist ships as working code.
- A rule leans on "measured", "in practice" or "this has been hit" without saying what was observed →
  stop, state the observation so a reader can repeat it, or delete the evidence language.
- A skill fails any of the five portability questions → stop, replace what the question flagged with a
  placeholder or delete it; a disclaimer above the example is not a fix.
- Nothing survives question 5 once the project-bound material is stripped → stop, there is no skill
  here — the material was a case study, not a subject.
