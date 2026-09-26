---
description: Review skills in this repository through the four lenses in .claude/review/QUESTIONS.md — generality first — and present keep/delete/reduce/move/fix decisions for the maintainer
argument-hint: "[skill dirs, files, a git range, or nothing for the working-tree diff]"
---

Review the skills named by `$ARGUMENTS` with the `catalogue-reviewer` subagent, once per lens, and
present the result for the maintainer to decide.

**The questions live in `.claude/review/QUESTIONS.md`.** This command only resolves the target, runs
the lenses and merges what comes back. Do not review anything yourself and do not add criteria here.

## 1. Resolve the target

- Paths → those skill directories or files.
- A git range or ref → the skills that range touches; the reviewers read each touched skill in full.
- Empty → the skills touched by the working-tree diff, then the staged diff. If both are clean, ask.

## 2. Run the lenses

Start four `catalogue-reviewer` subagents in parallel, one per lens (1 generality, 2 placement, 3 copy
outcome, 4 contract), each given the target and the lens number. For lens 4 also give the scratch venv
path for `tools/check_template_imports.py`.

If a subagent type named `catalogue-reviewer` is not available in this session, start general-purpose
subagents instead and tell each to read `.claude/agents/catalogue-reviewer.md` and act as it.

## 3. Merge and present

- Group findings by skill, then by verdict: `DELETE` and `REDUCE` first, then `MOVE`, then `FIX`.
- Where two lenses disagree on one artifact (lens 1 says delete, lens 4 says fix its heading), the
  lens with the lower number wins; show both.
- Drop findings with no test-service evidence, and say how many were dropped.
- End with the total lines the proposals remove versus add.

Then stop. Applying the findings is a separate step the maintainer decides on — do not edit skills from
this command.
