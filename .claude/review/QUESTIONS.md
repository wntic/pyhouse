# Reviewing the catalogue — the questions

This file is the criteria a reviewer applies to the skills in this repository. The reviewer agent
(`.claude/agents/catalogue-reviewer.md`) and the command (`/review-skills`) point here; neither
restates it.

## Why these questions exist

The catalogue is carried into projects its authors have never seen, and an agent that loads a skill
**copies its templates and skeletons verbatim** — names, comments, constants, the set of packages. So
every line of code in a skill is a line in every project that uses it.

Earlier review rounds checked skills against the catalogue's own format rules and against one
sample application. Both passed skills that were a copy of that application: a package tree with its
package names, a family-level exception catalogue with its classes, an HTTP status on exceptions in a
family where HTTP is optional. Each round also only **added** — a defect became a new template — and
never removed anything. These questions put generality first and make deletion a finding of the same
weight as a fix.

## The lenses, in priority order

A review answers the lenses in this order. A reviewer short on budget stops early, not late: the
mechanical checks in lens 4 are the least valuable and the most likely to be done anyway.

### Lens 1 — Generality: would most services of this family have this?

Walk every template, skeleton line, example class, constant and default through the **test services**
below. For each one ask:

1. **Would most of these services have this line?** If a minority would, it is not template material:
   it becomes one sentence of prose ("where the service has X, …") or it goes.
2. **Is it one application's shape?** A set of package names, a split between two kinds of job, a
   specific number of error classes, an upstream that pages by cursor — a detail with no reason to be
   *this* rather than something else is a sample leaking through. Placeholders do not fix this:
   `Foo` in place of a real name still carries the sample's shape.
3. **Is something optional shown as always present?** An HTTP status, a second store, a framework, a
   pagination loop, a scheduler. Optional things are shown as optional: the obligation is stated, and
   the template either omits them or marks the one line that exists only when they do.
4. **Would an abstract placeholder confuse more than it helps?** `<work>/`, `<system>/` in a tree gives
   an agent nothing to copy and something to invent. If a skeleton only makes sense with a sample's
   names in it, the skeleton is not worth having — say so and propose deleting it.
5. **Is there a smaller version that still carries the house pattern?** Strip everything a vendor or a
   workload supplies. What remains — injection, translation at the boundary, one transaction owner —
   is the template. If nothing remains, the template is the vendor's manual.

**Test services** — use these, not the sample the skill came from:

| Family | Test services |
|---|---|
| flat | a queue consumer that calls one API and stores nothing · a nightly job that reads one table and writes a report file · a webhook receiver writing to one table · a CLI-triggered export from an object store · a crawler writing to two stores |
| hex | a CRUD REST service with one aggregate · a service driven only by a queue consumer · a gRPC service with two aggregates and no auth · a service with no relational store |
| universal | the above, plus a library with no entrypoint and a CLI tool |

### Lens 2 — Placement: is this in the skill that owns it?

1. **Is this a language-level concern sitting in a family skill?** Exceptions, typing, logging,
   packaging and naming hold in any Python project whatever its architecture; they belong to a
   universal skill. A family skill may *use* them in a template, never define a family-wide instance
   of them (a family exception catalogue is the example).
2. **Is this a family concern sitting in a universal skill?** A universal skill carrying a "flat
   version" and a "hex version" of the same template is carrying family material.
3. **Does it restate a rule another skill owns?** Point at the owner instead — after opening the owner
   and confirming the rule is there.
4. **Does it bind to a transport, a store or a framework in a place that should not know about it?**
   An HTTP status belongs to the HTTP boundary; a driver's error code belongs to the data-access
   package.

### Lens 3 — Copy outcome: what would an agent build from this?

Take a short, naive prompt for one of the test services — two sentences, no layout, no stack — and
read the skill the way a generating agent would: the `SKILL.md` bodies whose `description` matches,
the siblings they explicitly tell it to read, the templates copied as written.

1. **What does the result contain that the service did not need?**
2. **Where does a template contradict a rule?** An agent copies the template and never reaches a rule
   200 lines below it. A rule the template breaks is a template defect.
3. **Which rule would be missed?** A rule that matters and is stated only far from the template it
   governs, or only in a sibling nothing points to.
4. **What would the agent invent where the skill is silent?** The answer is a missing rule — not a
   missing template.

### Lens 4 — Contract: is it well-formed?

The mechanical checks. They matter and they are the easiest, which is why they come last.

1. Frontmatter per `meta-skill-author`: `name` equals the directory, `description` opens `Use when`,
   has no bare `: `, stays within its length limits.
2. Section order and headings; a template heading names its stack; rules are stated without the
   mechanism; each plausible wrong turn has a hard stop.
3. Every cross-reference resolves — skill names, `rule N` citations, sibling files.
4. Plugin direction: a universal skill reads correctly with every family plugin absent; a hex↔flat
   reference names the plugin.
5. Placeholders only; no real application, product, role or tenant names.
6. Every template's imports resolve (`tools/check_template_imports.py`). Templates are checked **one at
   a time**; they are not assembled into one runnable application — that pressure is what turns a set
   of templates into one sample app.

## How a finding is written

Each finding carries:

- **Artifact** — `file:line`, and what it is (template, tree line, example class, rule, prose).
- **Verdict** — `DELETE`, `REDUCE` (to a sentence of prose or a smaller template), `MOVE` (to its
  owner), `FIX`, or `KEEP` when a lens-1 question was asked and the answer was yes.
- **The question it failed** — lens and number.
- **Evidence** — concretely which test service gets what: "a queue consumer with no store gets an
  empty `postgres/` package and a migrations directory".
- **Proposed change** — the replacement text, or "delete".

The report ends with a count of lines the proposals remove versus add. A review that only adds is
suspect; say why if it does.

## What a reviewer does not do

- **Judge by the sample.** The application a skill was written from, or the one a test generation
  produced, is evidence of a failure mode — never the reference for what a service looks like.
- **Fix a defect with a template.** A defect found in one generated service becomes a rule stated
  without the mechanism. A new template is proposed only when every test service would have that file,
  and the proposal says so.
- **Grade against the format rules alone.** A skill can satisfy every rule in `meta-skill-author` and
  still be one application's copy; lens 1 is the review, lens 4 is hygiene.
- **Report cosmetics as progress.** Wrapping, wording and ordering go in one line at the end, if at
  all.
