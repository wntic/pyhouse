---
description: Review skills in this repository through the four lenses in .claude/review/QUESTIONS.md — generality first — verify every finding, and present keep/delete/reduce/move/fix decisions for the maintainer
argument-hint: "[skill dirs, files, a git range, or nothing for the working-tree diff; 'recheck' after applying findings]"
---

Review the skills named by `$ARGUMENTS` with the `catalogue-reviewer` subagent: once per lens, then once
more to verify what the lenses found. Present the result for the maintainer to decide.

**The questions live in `.claude/review/QUESTIONS.md`.** This command only resolves the target, runs
the lenses and the verifier, and merges what comes back. Do not review anything yourself and do not add
criteria here.

## 1. Resolve the target

- Paths → those skill directories or files.
- A git range or ref → the skills that range touches; the reviewers read each touched skill in full.
- Empty → the skills touched by the working-tree diff, then the staged diff. If both are clean, ask.
- `recheck` → go to step 5.

Then decide which lenses the change earns, from its diff:

- **Lens 4 only** — the change alters no obligation: a wording fix, a dead cross-reference, a template
  whose imports did not resolve, a frontmatter repair. These are the `fix` rows of `commit.md` step 4.
- **All four lenses** — anything else: a skill added, a rule added, changed or removed, a template or a
  tree line added or changed. When unsure, all four.

Say which you chose and why, in one line.

## 2. Run the lenses

Start one `catalogue-reviewer` subagent per chosen lens, in parallel (1 generality, 2 placement, 3 copy
outcome, 4 contract), each given the target, the lens number and the diff that defines what the change
touched. For lens 4 also give the scratch venv path for `tools/check_template_imports.py`.

If a subagent type named `catalogue-reviewer` is not available in this session, start general-purpose
subagents instead and tell each to read `.claude/agents/catalogue-reviewer.md` and act as it.

## 3. Verify

Start one more `catalogue-reviewer` in **verify** mode, given every finding the lenses returned, the
target and the same diff. It answers `QUESTIONS.md`, *Verifying a finding*, for each one and returns it
confirmed or refuted, with its severity and whether it is pre-existing. One verifier, not a vote.

## 4. Merge and present

- Only confirmed findings. Say how many the verifier refuted, and list each refuted one in one line with
  its reason, so a wrong refutation can be overruled.
- `Important` first, grouped by skill, then by verdict: `DELETE` and `REDUCE` first, then `MOVE`, then
  `FIX`. `Nit`s after, one line each.
- `Pre-existing` findings in their own section after those: they do not hold this change up.
- Where two lenses disagree on one artifact (lens 1 says delete, lens 4 says fix its heading), the
  lens with the lower number wins; show both.
- End with the total lines the proposals remove versus add.
- Zero confirmed findings is a complete result; say so and stop.
- Last, the outcome line for the branch's merge commit body:
  `Review (<lenses>): <N> findings, <R> refuted, <C> confirmed (<I> important).` The maintainer adds how
  many were applied when the branch lands.

Then stop. Applying the findings is a separate step the maintainer decides on — do not edit skills from
this command.

## 5. Recheck after the findings are applied

Run with `recheck` once the maintainer has applied the findings they chose. This is **one** round, and
there is no second:

- Start a single `catalogue-reviewer` in verify mode, given only the diff of the fixes and the findings
  they answer — not the whole skills, and no lenses.
- It reports, per finding, whether the fix answers it, and anything `Important` the fix diff itself
  introduces. Nothing else: a skill re-read in full finds new things in every round, most of them in the
  text the previous round just wrote.
- Present that, add the recheck to the outcome line, and stop. What is still open goes to the
  maintainer, never into another round.
