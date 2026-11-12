---
description: Implement one ready spec end to end — an implementer that writes the tests from the spec before the code, then the code, and checks its own work by the project's gate and, where the change shows only in a running process, a live check; a review of what the change breaks; and one round of fixes — and hand over the body of the merge commit for the person to land it
argument-hint: "<the path or key of a spec whose status is ready>"
---

Implement the spec `$ARGUMENTS` names, by the `delivery-spec` and `delivery-change-contract` skills,
through the `delivery-implementer` agent and the `/pyhouse-universal:change-review` command.

**The skills hold the rules** — what the spec promises, what is frozen while it is implemented, how an
edit to it is caught. The agent holds how each step is done, and checks its own work — the gate and
the live check are its, not this command's. This command runs the steps in order,
carries what one step returns to the next, and asks the person what only they can decide. Load both
skills first; restate neither, and write no code yourself.

**Where this runs.** In a session, a question for the person is asked in the reply and the step waits
for the answer. Run by another agent, the question is returned to whoever started it, with the step it
stopped at, and nothing proceeds past it. Either way, an agent that returns a question is continued with
the answer, keeping what it has done — through `SendMessage` where the session has it, otherwise started
again with its report and the answer — and never answered on the person's behalf. Questions that arrive
together are asked in one message.

**Starting the agent.** It is started as a subagent of its own type for each of its two steps, given the
spec's path, the repository root, the plugin root (`${CLAUDE_PLUGIN_ROOT}`), its step, the frozen paths
and the gate command step 1 settled — saying which the project did not name — the consent step 1 got
for the live check and what it covers, what earlier steps returned, and the person's answers so far.
Where the type is not available in this session, start a general-purpose subagent and tell it to read
`${CLAUDE_PLUGIN_ROOT}/agents/delivery-implementer.md` and act as it.

## 1. Read the spec and what the project says

- `$ARGUMENTS` empty, or naming no spec → ask which one. A spec whose status is not ready → stop:
  it is finished with `/pyhouse-delivery:spec` first.
- Read the repository's agent instructions (`CLAUDE.md` and any file it imports) for: the section that
  names which skills govern which work; how branches are named and land; the command that runs the
  project's gate — its tests, and its linter, type checker and architecture test where it has them, in
  one; the paths of what `delivery-change-contract` freezes; and what the project says about its
  environments and shared services.
- What is not written down, ask once, in one message, with a candidate read from the repository for
  each — the tests directory, and the architecture test, the linter's configuration and the CI
  directory where they exist, the gate command — and, in the same message, the branch's name where the
  instructions name no pattern, or whether the current branch is this change's where it is not the
  mainline. Use the answers for this change; this command does not write them into the instructions
  file. The reply at the end says which paths were not named.
- A change due a live check — a spec with **How to see it working**, or a fix whose **Regression test**
  names a check no test makes — needs its consent before the build, by `delivery-change-contract` rule
  9. Work out from what the project says about its environments, and from its compose or task files and
  entrypoints, what starting the fewest services that show the change would start, stop, recreate or
  otherwise touch — write to, call, or read a secret from — and which of it the instructions do not
  name as the change's to use. Ask for that in the same one message, as rule 9 asks, or say in the
  reply that nothing needs it. Where the check needs a credential the project neither keeps for its
  checks nor lets the change create, the person's script for it goes in the same message.

## 2. Branch and the spec's base

- On the mainline → create the change's branch the way the instructions name branches, or by the name
  step 1 was given. On another branch the person said is this change's → stay on it. One they said is
  not → with a clean working tree, create the change's branch from the mainline as above; otherwise
  stop: what is on it is the person's.
- The spec uncommitted, or changed since it was committed → commit it as the branch's first commit, by
  the repository's commit convention. That commit, or the branch point where the spec was already
  committed as ready, is the **spec's base**.

## 3. Build

Start `delivery-implementer` in **build** step. For a feature it writes the tests from the spec, sees
each fail, commits them as the **tests' base**, then writes the code; for a fix, the regression test
seen failing on today's code, then the fix. Then it checks its own work: the gate in full, and the live
check where the change shows only in a running process or a fix's defect no test reaches. Its questions
go to the person as **Where this runs** says; a run they refused or did not answer is
`delivery-change-contract` rule 9's.

Read its report before going on. It must show the run before the code, each new test failing on an
assertion, on the not-implemented marker or — for a fix — on the symptom the spec names; the
repository's guarding checks passing on the tests; the gate's last full run passing, on the step's last
commit; and the live check, where one was due. What the report does not show goes back to the agent
once; what it still does not show goes in the reply at the end. A gate that still fails — a step the
agent ended at its limit of gate or live-check runs included — stops the change and goes to the person
with its output. A fix whose defect no test reaches has no tests' base; the steps below go without one.

## 4. The diff of what is frozen

Take the diffs `delivery-change-contract` names, from each base. An edit to a frozen artifact the
person did not agree to → stop and ask, showing the diff.

## 5. Review

Run `/pyhouse-universal:change-review` through the Skill tool, on the branch against the commit where it
left its mainline, with `--tests-at <the tests' base>` where there is one, so the tests written before
the code are judged as tests that existed. Keep what it prints — the findings, its `Tests:` line and the
outcome line. A meaning edit to a test after its base that the person has not agreed to is a stop, as
step 4: it goes to the person with the diff, never to step 6.

## 6. One round of fixes

Collect the `Important` findings not marked pre-existing. A pre-existing finding goes to the hand-over
as **open**.

- Nothing collected → step 7.
- Otherwise start `delivery-implementer` in **fix** step once, with exactly that list, and read its
  report for the gate and the live check as step 3 does. Take step 4's diffs over the fix commits, as
  step 4 does, and run `/pyhouse-universal:change-review recheck` on the fix diff.

There is no second round. Whatever is still open goes to the person as it stands: a step asked again
always finds more.

## 7. Hand over

Write the merge commit's body and show it in the reply — the person reads the reply, never a tool's
output:

```
<what changed for the user or the operator and why, one paragraph — the decision record it implements
where the spec names one; for a fix, its cause>
<each decision the spec did not make, one line, only where it changes behaviour>
<each step the spec makes the person's and not yet done, marked before or after landing — the script
`delivery-spec` asks for; no line where there is none>

<the review's outcome line, with how many were applied>
- <each finding not fixed — its first line> — wrong: <why> | intended: <the decision> | not worth
  fixing: <why> | open
```

A fixed finding is not listed: the diff shows it. The answer to each finding is the person's where they
gave one, or the implementer's **wrong**; a finding nobody answered is **open**, never given an answer
on the person's behalf. Where the change goes up as a merge or pull request, its description is a copy of
this body. A spec is a working document unless the repository says otherwise, so a message that cites it
sends a later reader to something rewritten or gone.

After the body, in the reply only and never in a commit:

- the gate — its command and result, for each full run the agent's reports show;
- the live check, where one ran — what was started, what was done, what was seen, whether it was
  stopped, and anything seen outside what the spec asked;
- a skill the instructions name for this work that the agent did not load, where that happened;
- the paths that were not named;
- every question still open.

**This command does not land the change.** It does not merge, push or open a request; landing is the
person's call, by the branching the repository records.
