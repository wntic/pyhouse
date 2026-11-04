---
description: Review a change before it lands for what it breaks — contracts other code relies on, failure paths, and tests that would not catch it — then verify every finding in a separate run and print only what survives, with an outcome line for the merge commit. Works in any project and on any stack. Run `recheck` once after the findings are fixed. Not a style audit; conformance to the catalogue is /pyhouse-universal:code-review.
argument-hint: "[a git range or ref, nothing for this branch against its mainline; 'recheck' after fixing]"
---

Review the change named by `$ARGUMENTS` with the `change-reviewer` subagent: once in find mode, then
once in verify mode on what the first run found. Print what survives.

**The subagent holds the procedure.** This command resolves the target, runs the two passes and renders
the result. Do not review anything yourself, do not add a lens here, and do not re-rank or soften what
comes back.

## 1. Resolve the target

This reviews a change, so the target is always a diff.

1. **A git range or a ref** (`main...HEAD`, `HEAD~3..`, a SHA) → that diff.
2. **Empty** → the current branch against the commit where it left its mainline. The mainline is the
   one the repository's agent instructions name in their branching section; where none is named, the
   remote's default branch, else `main`, else `master`. If the branch has uncommitted changes as well,
   say in one line that they are not part of the review.
   If the branch *is* the mainline or has no commits of its own, the target is the uncommitted change:
   `git diff HEAD`, staged and unstaged together, plus every untracked file `git status --porcelain`
   lists, which no diff shows — name those files to the subagent. If there is nothing at all, ask what
   to review.
3. **Paths or a whole tree** → not a change. Say so and offer `/pyhouse-universal:code-review`, which
   audits files.
4. **`recheck`** → step 4.

State the resolved range and its `--shortstat` in one line.

## 2. Find, then verify

Start one `change-reviewer` in **find** mode, given the target, the repository root and the plugin root
(`${CLAUDE_PLUGIN_ROOT}`).

Then start one more `change-reviewer` in **verify** mode — a fresh run, not a continuation of the
first — given every finding and the `Tests:` line verbatim, the same target and roots. One verifier, not
a vote. Skip verify only when the find run returned no finding and its `Tests:` line says no existing
test was edited.

If a subagent type named `change-reviewer` is not available in this session, start general-purpose
subagents instead and tell each to read `${CLAUDE_PLUGIN_ROOT}/agents/change-reviewer.md` and act as
it in the named mode.

## 3. Render

- The find run's `Read:` and `Tests:` lines.
- **Confirmed findings only**, verbatim in the block find mode wrote, with the severity and pre-existing
  mark the verifier set, `Important` first, then `Nit`; the verifier's note under a finding when it
  named a recorded decision. Findings the verifier added come with them, in its words.
- `Pre-existing` confirmed findings in their own section after those: they do not hold this change up.
- The refuted findings, one line each with the verifier's reason, so a wrong refutation can be
  overruled.
- Last, the outcome line for the merge commit body:
  `Review (contracts, failure paths, tests): <N> findings, <R> refuted, <C> confirmed (<I> important).`
  `N` counts the find run's findings and any the verifier added; a duplicate the verifier merged
  counts as refuted. The person landing the change adds how many were applied.

Add no sentence of your own before, between or after these — no summary, no merged cause, no
assessment.

Zero confirmed findings is a complete result: print the `Read:` and `Tests:` lines, `No findings.` and the outcome
line, and stop.

**This command reports; it does not fix.** Do not edit, stage or offer a patch unless asked in a new
message.

## 4. Recheck, once

Run with `recheck` after the findings someone chose to fix are fixed. Ask for, or take from the
conversation, the confirmed findings and the range that holds the fixes. Start a single
`change-reviewer` in **recheck** mode, given only those findings and that diff. Print, per finding,
whether it is answered, and anything `Important` the fixes introduced; append
`recheck: <A> answered, <O> open` to the outcome line.

There is no second recheck. What is still open goes to the person landing the change, never into
another round: a reviewer asked again always finds more.
