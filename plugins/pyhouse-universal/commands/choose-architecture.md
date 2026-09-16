---
description: Walk the architecture-choice skill interactively for one service and print the family it belongs to, or that no family applies
argument-hint: "[a sentence or two describing the service]"
---

Load the `architecture-choice` skill and run its decision against `$ARGUMENTS`.

**That skill holds the content** — every question, what each answer implies, the costs, the cases and
the routes. This command only drives the interaction. Do not reproduce any of it here, and do not
answer from memory: read the skill, then work from it.

## Driving it

1. **Start from `$ARGUMENTS`.** If it is empty, ask for a sentence or two about what the service does.
   Nothing more — the skill decides what else it needs.
2. **Try the skill's deciding question against what you were already told.** Often the description
   answers it. Say which sentence answered it and ask the user to confirm or correct, rather than
   asking a question they have already answered.
3. **Otherwise ask it, in the user's own terms** — phrased for their service, not read out as a
   heading. One question per turn.
4. **Stop the moment the skill says the answer is determined.** Usually that is after the first
   question. Ask a further one only while the outcome is genuinely still open, and treat the answers as
   the skill treats them — never as a running total.
5. **Check the skill's non-obvious cases before recommending.** If one of them covers what you were
   told, follow it; that is the answer, and it may be that no family applies — because the project is
   too small, or because its shape is outside the two families entirely.

## Printing the result

Four lines, nothing else:

- **Recommendation** — one family, or neither. When neither, say which kind: too small to need an
  architecture, or a shape the catalogue does not cover.
- **Why** — the answer that settled it, quoted back from what the user said.
- **The price** — what this choice makes expensive, as the skill states it. When no family applies
  there is no price to name — say what the reader gets no templates for, and do not invent one.
- **Next** — what to read, and the plugin to install if it is not present. When the project is too
  small, name what does apply instead and say plainly that no architecture skill is needed. When the
  shape is one the catalogue does not cover, name the shape, say so, and name the universal skills —
  do not offer a layout.

Then stop. Do not scaffold a project, create directories or write files — this command decides and
hands off.

If two of the user's answers contradict each other, say which two and ask once. Do not guess between
them, and do not split the difference.
