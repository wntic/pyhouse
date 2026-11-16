# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Agreed

87 waits until there are defects found after a change landed to run it on. Every other item has
landed or was closed (D130–D178, D191, D192, D195–D198, D201).

### 87. A retrospective over released changes
`/retro`: the defects found after a change landed, which check each escaped, and the rule or test that
would close it — the loop D186 was the first output of. Deferred (D192) until such defects exist: in
the repository it would run on, most defects testing will find predate the pipeline, and half its
steps are gone.

## Proposed

### 112. A security review before a service is first exposed to the internet
The maintainer builds web applications and other services that will be reachable by anyone on the
internet, and a service an agent wrote in a short time is an easy target. Wanted: a check of the code
for security before its first deploy. The catalogue has nothing for this — `/pyhouse-universal:change-review`
reviews one change for what it breaks, not a whole codebase for what an attacker can reach, and 111 asks
only whether the linter's security family is selected. A candidate to start from is Cloudflare's
`security-audit-skill` (github.com/cloudflare/security-audit-skill, MIT, read 2026-11-17): six phases —
reconnaissance into an architecture note and a coverage ledger of trust boundaries and input surfaces,
hunting by isolated sub-agents assigned from the ledger, a fresh verifier trying to disprove each
candidate, findings written as confirmed / needs-validation / rejected against a JSON schema, an
independent re-check of each record's source claims, and a report — with attack-class guides (HTTP and
authentication, client-side code, supply chain and CI, cloud and deployment, serialization and queues,
resource exhaustion, data isolation, LLM-backed targets, and more) and Node validators for its outputs.
It is multi-agent by design. Claude Code's own `/security-review` exists and has not been compared. To
do: look for other credible security-review skills and checklists, compare them with Cloudflare's, and
try the best on one real service before its deploy. Open: whether the catalogue ships anything at all
or the maintainer installs a third-party skill beside it — the catalogue's rules state obligations, and
a security audit may be a tool rather than a rule set; if obligations come out of it (an untrusted input
validated at the boundary, secrets never in the repository), which existing skill owns each; and how
many agents a run costs against the two the delivery pipeline settled on.

### 113. How much context the catalogue's listing takes now
The maintainer remembers that the descriptions passed the default listing budget (1% of the context
window, ~10k tokens) and that the budget was raised to 2% (~20k). Measured from the frontmatter on
2026-11-17: 53 skill descriptions are 41,362 characters (~10,300 tokens at four characters a token), 11
command descriptions 2,513, and 2 agent descriptions 1,474 — about 45,000 characters, ~11,300 tokens,
before names and the listing's own formatting. `meta-skill-author`'s "Length" section still says
~38,700, and D178 ~38,300; both are stale. D178 measured the default budget at 30,000 characters, so the
catalogue alone overruns it by half and the least-invoked skills are listed by name only; the
`README.md` tells a user to set `"skillListingBudgetFraction": 0.02` to list them all, and `/pyhouse:setup`
does not set it, since which skill loaded did not depend on it. The maintainer's
`~/.claude/settings.json` does not carry the setting; where it is set, if anywhere, is unchecked. Other
installed plugins share the same budget. To do: measure what a session actually spends — `/context` in a
project with the catalogue and the maintainer's usual plugins installed, at the default and at 0.02 —
and update the stale figures. Open: whether a 2% budget still holds the catalogue with other plugins
beside it; and whether the size matters beyond D178's finding that names carry the routing — the
listing is paid on every session, and D178 did not measure what the agent then wrote.
