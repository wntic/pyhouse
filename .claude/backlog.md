# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Agreed

Item 55 predates the rest; every earlier agreed item has landed or was closed (D130–D164). Items 63–72
come from the full review of 2026-10-11 after adversarial verification; 76–80 from the maintainer's own
questions the same day (78 folded into 70).

### 55. Performance obligations, placed with their owners
No `performance` skill: a bag of tips would restate rules other skills own. Two groups, each with an
owner. Language-level, a universal skill on async code: no blocking I/O or CPU-bound work inside a
coroutine (today one `## Other bindings` bullet in `hex-capability-adapter`), concurrency always
bounded, a client or pool built once per process rather than per call. Data access, in `persistence`:
no query per item in a loop, filtering and paging in the store rather than in Python, only the columns
and rows used, and every filter of a hot query backed by an index. Only what is expensive to retrofit
and checkable in review belongs; a micro-optimisation without a measurement does not. The maintainer
collects concrete findings from the lead's reviews first, and each becomes a rule.

### 70. Descriptions stay as they are; `when_to_use` folds into `description`
Measured on 2026-10-11 (Opus, `claude -p`, a scratch hex project, the checkout's universal + hex + git
loaded with `--plugin-dir`, user settings excluded). The listing budget is 30,000 characters (Opus and
Sonnet alike); the catalogue's 41 skills take ~29,500 of the 38,145 listed, and 14 of 23 `hex-*` skills
were listed by name alone (`hex-restapi-endpoint`, `hex-store-repository`, `hex-wiring`, every
`hex-test-*`, …). `skillListingBudgetFraction` in a project's `.claude/settings.json` takes effect. Over
39 runs — three prompts naming the artifact, five not naming it ("publishing a Foo must check its Bar is
active", "only admins may create a Foo", "fail the build if the domain imports SQLAlchemy", "keep each
Foo's attachment in S3", "cover the create-Foo handler"), default budget against 0.02, three repeats for
the second set — the skill loaded never differed between the conditions: names carry the routing. The
adopt section widened what was loaded (`hex-architecture` first, then universal skills) at 1.5–4× the
turns. Not measured: what the agent then wrote, and models other than Opus. So:
- Descriptions are not shortened.
- `when_to_use` leaves the catalogue: Claude Code only appends it to `description`, under the same cap and
  budget, and claude.ai and the Skills API reject the key. In the 21 skills that carry it, its text moves
  to the end of `description` as it is listed today (` - Also fires on …`), keeping `Use when …` first,
  one paragraph, no bare `: `, within 1,536 characters. Then `meta-skill-author` (`:52`, `:60`, `:79`,
  `:107`) drops the field, the README (`:49`, `:194`, `:212`) and `CLAUDE.md:233` drop the pair wording,
  and a `DECISIONS.md` entry reverses D120.
- The README gains a short note: the catalogue takes most of Claude Code's skill-listing budget, so with
  many plugins installed some skills are listed without a description; `skillListingBudgetFraction` in
  the project's `.claude/settings.json` raises it. `/pyhouse-universal:adopt` does not write it.

## Proposed

### 81. hex has no test rule for a returned unit or a redelivery
`at-least-once-delivery` names `flat-test-entrypoint` rules 2 and 6 as the example of testing a delivered
unit: a consumer's handler asserted to return a failed unit unacknowledged and to acknowledge a
successful one after its effect, and a second delivery asserted to change nothing. No `hex-test-*` skill
states either for a hexagonal consumer; none of them mentions a consumer, an acknowledgement or a
redelivery, so a hex service driven by a queue (a `QUESTIONS.md` test service) has no test obligation
for the consumer line in `hex-architecture`, including a redelivered create acknowledged rather than
mapped to a conflict.
