---
description: Implement one ready spec end to end — skeleton, tests written before the code, the code, the project's own gate, a review of what the change breaks, acceptance against the spec's criteria by their tests and on the stand, and one round of fixes — and hand over the body of the merge commit for the person to land it
argument-hint: "<the path or key of a spec whose status is ready>"
---

Implement the spec `$ARGUMENTS` names, by the `delivery-spec` and `delivery-change-contract` skills,
through the step agents `delivery-implementer`, `delivery-tester` and `delivery-prover` and the
`/pyhouse-universal:change-review` command.

**The skills hold the rules** — what the spec promises, which artifact is free, declared or frozen, how
an edit is caught. The agents hold how each step is done. This command runs the steps in order, carries
what one step returns to the next, and asks the person what only they can decide. Load both skills
first; restate neither, and write no code yourself.

**Where this runs.** In a session, a question for the person is asked in the reply and the step waits for
the answer. Run by another agent, the question is returned to whoever started it, with the step it
stopped at, and nothing proceeds past it. Either way, an agent that returns a question is started again,
fresh, with the answer — never answered on the person's behalf.

**Starting a step agent.** Each is started as a subagent of its own type, given the spec's path, the
repository root, the plugin root (`${CLAUDE_PLUGIN_ROOT}`), its mode, the paths and the gate command
step 1 settled — saying which the project did not name — and what earlier steps returned.
Where a type is not available in this session, start a general-purpose subagent and tell it to read
`${CLAUDE_PLUGIN_ROOT}/agents/<name>.md` and act as it.

## 1. Read the spec and what the project says

- `$ARGUMENTS` empty, or naming no spec → ask which one. A spec whose status is not ready → stop:
  it is finished with `/pyhouse-delivery:spec` first.
- Read the repository's agent instructions (`CLAUDE.md` and any file it imports) for: the section that
  names which skills govern which work; how branches are named and land; the command that runs the
  project's gate — its tests, and its linter, type checker and architecture test where it has them, in
  one; the paths for each category of the modes table; and, where the project runs as a process, the
  environment criteria run in.
- What is not written down, ask once, in one message, with a candidate read from the repository for
  each — the tests directory, and the architecture test, the linter's configuration and the CI
  directory where they exist, the gate command — and, in the same message, the branch's name where the
  instructions name no pattern, or whether the current branch is this change's where it is not the
  mainline. Use the answers for this change; this command does not write them into the instructions
  file. Every report from here on says which paths were not named.

## 2. Branch and the spec's base

- On the mainline → create the change's branch the way the instructions name branches, or by the name
  step 1 was given. On another branch the person said is this change's → stay on it. One they said is
  not → with a clean working tree, create the change's branch from the mainline as above; otherwise
  stop: what is on it is the person's.
- The spec uncommitted, or changed since it was committed → commit it as the branch's first commit, by
  the repository's commit convention. That commit, or the branch point where the spec was already
  committed as ready, is the **spec's base**.

## 3. Skeleton

Only for a feature — the skeleton gives the tester its names. A fix adds no surface; it goes to step 4.

Start `delivery-implementer` in **skeleton** mode. It lays every contract the spec names and the internal
names the code needs, with no behaviour, and commits. Keep the files it lists and the skills it loaded.
Where the feature adds no name and changes no contract, it lays nothing, and the tester starts from the
spec's base.

## 4. Tests before the code

- **A feature** → start `delivery-tester` with the spec and the skeleton commit, or the spec's base where
  the skeleton laid nothing. It writes the tests, the test criteria's among them, runs them and the
  repository's checks on them, and commits. A name it
  returns as **Missing** goes to `delivery-implementer` in skeleton mode, once; then the tester is
  started again. Only its **Questions** go to the person. Keep its **Criteria** — which test answers
  which criterion — for step 8.
- **A fix** → start `delivery-implementer` in **regression** mode: the failing test the spec's
  **Regression test** names, seen failing on today's code, committed alone. Where the fix's criterion is
  a test criterion, this test answers it.

Check what was committed before any behaviour exists: run the new tests, and each must fail on an
assertion, on the skeleton's not-implemented marker, or — for a fix — on the symptom the spec names,
such as the error that escaped; never on collection, an import or a missing fixture. A test that
passes, or fails for the wrong reason, goes back to the agent that wrote it once, with the output; what
still does not fail properly goes in the report, and so does a test criterion no test answers. The
commit that holds the tests is the **tests' base**. A fix whose defect no test reaches commits no test
and has no tests' base; the steps below go without one.

## 5. Code

Start `delivery-implementer` in **code** mode with both bases, where there are two. It makes the tests
pass, declares what the modes table asks, runs the tests it wrote or touched, and commits. A question
it returns about a frozen artifact goes to the person (see *Where this runs*).

## 6. The gate and the diff of guarded paths

Run the gate command — the first of its two full runs. Every failure in a full run is a defect, never a
flaky test to run again, even where the test passes alone. A failure here does not stop the steps and
is not retried here: it goes to step 9 with its output, beside the findings and the failed criteria.

Then take the diffs `delivery-change-contract` rule 7 names, from each base, and set every edit they show
against the declarations the agents returned:

- an edit to a frozen artifact the person did not agree to → stop and ask, showing the diff;
- an edit to a declared artifact with no declaration → add it to the declarations as **undeclared**, by
  path and diff, and go on.

## 7. Review

Run `/pyhouse-universal:change-review` through the Skill tool, on the branch against the commit where it
left its mainline, with `--tests-at <the tests' base>` where there is one, so the tests written before
the code are judged as tests that existed. Keep what it prints — the confirmed findings, its `Tests:`
line and every finding on an edit to a test, and the outcome line. A meaning edit to a test that the
person has not agreed to is a stop, as step 6.

## 8. Acceptance

- **The person, once.** Where any stand criterion is to run, ask the person in one message, after the
  review has printed and never before: for each criterion `delivery-spec` rule 11 makes wait for them,
  what it touches and whether it may run; for each step the spec makes theirs, the command to run and
  the output that shows it done — where the step edits what an agent may not read, the script
  `delivery-spec` rule 8 asks for — the one the spec's check used, or one written now where it has
  none; and whether the environment is free for the run.
- Start `delivery-prover` with the spec, the tests' base, step 4's **Criteria** — or, for a fix, the
  regression test it committed — the review's `Tests:` line and its findings on test edits, the
  environment and its commands, the person's outputs, and which waiting criteria they agreed to — one
  they refused, or did not answer, is **not run**. Keep its table, its **Substitutes**, its **Outside
  the criteria** and every environment change it reports.

## 9. One round of fixes

Collect the confirmed `Important` findings, a failed gate from step 6, and the criteria the prover found
**not met**. A criterion it marked **environment** is not a code defect: it goes to the person, never to
the implementer.

- Nothing collected → step 10.
- Otherwise start `delivery-implementer` in **fix** mode once, with exactly that list. Then run the gate
  command — its second and last full run; a failure in it stops the change and goes to the person, with
  its output. Take step 6's diffs over the fix commits and set them against its declarations, as step 6
  does; run `/pyhouse-universal:change-review recheck` on the fix diff, and `delivery-prover` on the
  failed criteria — and on the stand block again where a fix commit changed code the stand runs. The
  person is not asked again unless the environment changed or a criterion to run again waits on an
  agreement they have not given.

There is no second round. Whatever is still open goes to the person as it stands: a step asked again
always finds more.

## 10. Hand over

Write the merge commit's body and show it in the reply — the person reads the reply, never a tool's
output:

```
<the spec's goal, in one line; its path only where the repository says its specs are kept for good>

Review (contracts, failure paths, tests): <the outcome line, with how many were applied>
- <each confirmed finding's first line> — fixed | wrong: <why> | intended: <the decision> | not worth
  fixing: <why> | open

Acceptance:
- <n>. <test | stand> — <met | not met | environment | not run> — <how it was checked, one line>

Declared edits:
- <every declaration, the undeclared ones marked>
```

The answer to each finding is the person's where they gave one; the implementer's fix answers one it
was given as **fixed** or **wrong**; a finding nobody answered is **open**, never given an answer on
the person's behalf. Where the change goes up as a merge or pull request, its description is a copy of
this body. A spec is a working document unless the repository says otherwise, so a message that
cites it sends a later reader to something rewritten or gone.

After the body, in the reply only and never in a commit: the skills each agent says it loaded, set
against the section of the instructions that names them, with any it names that no agent loaded; the
paths that were not named; the prover's **Outside the criteria** and **Environment changes**; and
every question still open.

**This command does not land the change.** It does not merge, push or open a request; landing is the
person's call, by the branching the repository records.
