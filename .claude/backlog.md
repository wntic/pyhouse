# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Agreed

Item 55 predates the rest and is the only agreed item left; every other has landed or was closed
(D130–D178).

### 55. Performance obligations, placed with their owners
No `performance` skill: a bag of tips would restate rules other skills own. Two groups, each with an
owner. Language-level, a universal skill on async code: no blocking I/O or CPU-bound work inside a
coroutine (today one `## Other bindings` bullet in `hex-capability-adapter`), concurrency always
bounded, a client or pool built once per process rather than per call. Data access, in `persistence`:
no query per item in a loop, filtering and paging in the store rather than in Python, only the columns
and rows used, and every filter of a hot query backed by an index. Only what is expensive to retrofit
and checkable in review belongs; a micro-optimisation without a measurement does not. The maintainer
collects concrete findings from the lead's reviews first, and each becomes a rule.

## Proposed

### 81. hex has no test rule for a returned unit or a redelivery
`at-least-once-delivery` names `flat-test-entrypoint` rules 2 and 6 as the example of testing a delivered
unit: a consumer's handler asserted to return a failed unit unacknowledged and to acknowledge a
successful one after its effect, and a second delivery asserted to change nothing. No `hex-test-*` skill
states either for a hexagonal consumer; none of them mentions a consumer, an acknowledgement or a
redelivery, so a hex service driven by a queue (a `QUESTIONS.md` test service) has no test obligation
for the consumer line in `hex-architecture`, including a redelivered create acknowledged rather than
mapped to a conflict.
