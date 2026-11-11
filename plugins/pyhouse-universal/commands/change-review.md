---
description: Review a change before it lands for what it breaks — contracts other code relies on, failure paths, and tests that would not catch it — in one run, and print every finding with its scenario and severity, and an outcome line for the merge commit. Works in any project and on any stack. Run `recheck` once after the findings are fixed. Not a style audit; conformance to the catalogue is /pyhouse-universal:code-review.
argument-hint: "[a git range or ref, nothing for this branch against its mainline; 'recheck' after fixing] [--tests-at <ref>]"
---

Review the change named by `$ARGUMENTS` with the `change-reviewer` subagent, once in find mode, and print
what it finds.

**The subagent holds the procedure.** This command resolves the target, runs the pass and renders
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

**`--tests-at <ref>`**, beside any target, names a commit inside the change whose tests count as tests
that existed before it — where tests were committed before the code they test, so that an edit to them
is classified rather than read as part of a new file. Pass it to the run.

State the resolved range and its `--shortstat` in one line.

## 2. Find

Start one `change-reviewer` in **find** mode, given the target, the repository root, the plugin root
(`${CLAUDE_PLUGIN_ROOT}`) and the `--tests-at` commit where one was named. There is no second run to
refute its findings: a wrong one is answered by whoever fixes the change, or by the person landing it.

If a subagent type named `change-reviewer` is not available in this session, start a general-purpose
subagent instead and tell it to read `${CLAUDE_PLUGIN_ROOT}/agents/change-reviewer.md` and act as it
in the named mode.

## 3. Render

- The find run's `Read:` and `Tests:` lines.
- Every finding, verbatim in the block find mode wrote, `Important` first, then `Nit`.
- `Pre-existing` findings in their own section after those: they do not hold this change up.
- Last, the outcome line for the merge commit body:
  `Review (contracts, failure paths, tests): <N> findings (<I> important).`
  The person landing the change adds how many were applied.

Add no sentence of your own before, between or after these — no summary, no merged cause, no
assessment.

Zero findings is a complete result: print the `Read:` and `Tests:` lines, `No findings.` and the outcome
line, and stop.

**This command reports; it does not fix.** Do not edit, stage or offer a patch unless asked in a new
message.

## 4. Recheck, once

Run with `recheck` after the findings someone chose to fix are fixed. Ask for, or take from the
conversation, the findings that were fixed and the range that holds the fixes. Start a single
`change-reviewer` in **recheck** mode, given only those findings and that diff. Print, per finding,
whether it is answered, and anything `Important` the fixes introduced; append
`recheck: <A> answered, <O> open` to the outcome line.

There is no second recheck. What is still open goes to the person landing the change, never into
another round: a reviewer asked again always finds more.
