---
description: Review a diff, a commit range, a path or a tree for conformance to the pyhouse catalogue — the architecture family's rules plus the universal ones — and print only what departs from a rule a skill actually states. Not a correctness review; it hunts no bugs and defers formatting and type-correctness to the project's own tools.
argument-hint: "[paths, a git range, or nothing for the working-tree diff]"
---

Run the `pyhouse-reviewer` subagent against `$ARGUMENTS` and print what it returns.

**The subagent holds the procedure and the skills hold the rules.** This command only resolves what
is being reviewed and renders the result. Do not review anything yourself, do not restate a rule
here, and do not answer from memory.

## What this is not

It reports conformance to the catalogue, so it finds no bugs, no races and no vulnerabilities, and it
reports no formatting or type-correctness issue — those belong to the project's own checkers and to a
correctness review. Say so in one line if the user appears to have expected those; a clean report here
is not a statement that the code is correct.

## Resolving the target

1. **Paths or a directory** → review those files.
2. **A git range or a ref** (`HEAD~3..`, `main...`, a SHA) → review that diff.
3. **Empty** → the working-tree diff; if that is clean, the staged diff. If both are clean, ask what
   to review and offer the last commit or a path. Do not default to the whole tree — a tree review
   is a different, much larger job, and worth confirming before it starts.

Pass the subagent the resolved target, the repository root, and the plugin root
(`${CLAUDE_PLUGIN_ROOT}`) so it can reach the catalogue if a skill fails to load by name.

## Rendering

Print the subagent's report as it comes back — the three header lines, the findings, the gaps.
It is already ordered. Do not re-rank it, summarise it, or add a closing assessment.

Two things are yours to add, each at most one line:

- If the header says a family plugin is not installed, name the plugin to install.
- If the header says the firewall is present but was not run, name the command that runs it.

Then stop. **This command reports; it does not fix.** Do not edit a file, stage anything or offer a
patch unless the user asks for one in a new message — a finding the reader has not read yet is not a
change they have agreed to.

If the subagent returns no findings, print its header and `No findings.` and add nothing. Silence
with a stated scope is the result, not a failure to find something.
