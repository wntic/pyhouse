---
name: delivery-change-contract
description: Use when implementing a ready spec and about to change something other than the change's own code — a test written before the code, a test that existed before the change, a shared package, a gap the spec left, its criteria, a decision record, or a check that guards the repository such as the architecture test, the linter's configuration or CI. Owns the three modes an artifact takes while a spec is implemented — free, declared, frozen — and which artifact takes which, what a declaration says, the base commits a change is measured from, and catching an edit by a diff from them rather than by forbidding it. What a spec holds and that its criteria change only with the person's consent are `delivery-spec`'s; whether an edit to a test changed what it asserts is decided by the review that reads the diff. - Also when asked whether an implementer may edit a test, correct a criterion, loosen the architecture test, touch code another component shares, or fill in a name the spec does not give.
---

# Delivery — Change contract

While a spec is implemented, every artifact the change touches is in one of three modes: **free** to
change, changed only with a **declaration**, or **frozen** until the person says otherwise. No tool can
stop an edit — a file changes through any command that can write — so the modes are not a ban. They
make sure no edit is silent: whatever is not free is caught by a diff from a fixed commit, and it
reaches the review declared, marked undeclared, or — frozen and not agreed — as a stop.

## When to use vs. neighbours

- What a spec holds, what a criterion is, and that a ready spec's criteria change only with the
  person's consent → `delivery-spec`.
- Whether a test is strong enough, at which level, and a fix's failing test → `test-principles`.
- Whether an edit to a test repaired its form or weakened its meaning →
  `/pyhouse-universal:change-review`, which classifies every such edit from the diff, and is told the
  tests' base so that a test written before the code counts as one that existed.
- The messages of the change's commits → `git-commit-message`, in the `pyhouse-git` plugin, where
  installed.
- How the branch lands and when its history is folded → `git-branching`, in the `pyhouse-git` plugin,
  where installed.

## The modes

| Artifact | Mode |
|---|---|
| Code in the packages the spec's **Where the code goes** names | free |
| Code outside them — another component, a package several components share | declared |
| A test written for this change before its code, its form — a typo, an import, a name the code settled | declared |
| A test written for this change before its code, what it asserts — a case, an expected value, a check removed | frozen |
| A test that existed before the change, any edit | declared |
| A gap the spec leaves — a name, a default, a case it does not decide — filled | declared |
| The spec's meaning — its goal, scope, contracts and behaviour | frozen |
| The acceptance criteria | frozen |
| The project's decision records | frozen |
| The checks that guard the repository — the architecture test, the linter's and type checker's configuration, CI, hooks | frozen |

## Template — a declaration

```markdown
- `<path>` — <the row of the modes table>: <what changed>. <Why, in the terms of the spec or the code
  that required it.>
```

## Rules

### What each mode allows

1. **A free edit needs nothing.** It is the change itself, and the review reads it as such.
2. **A declared edit is made, and declared in the same step that makes it.** The declaration is one
   entry in the form above: the path, the row it falls under, what changed and why. Declarations travel
   with the change to whoever decides whether it lands; the diff shows the edit, the declaration says
   why it was needed.
3. **A frozen artifact is changed only by the person, or with their consent.** Whoever is implementing
   stops, says what they would change and why, and goes on only with the answer. A change the person
   agrees to is declared like any other, with their consent named in the reason; a change to the spec
   is also recorded in the spec, as `delivery-spec` rule 13 asks.
4. **A gap is filled, not guessed silently and not stopped on.** Where the spec does not decide a name,
   a default or a case, it is filled the way the code around it and the decision records already do,
   and declared. A gap whose filling would change a contract other code depends on, or contradicts a
   decision, is the spec's meaning, and frozen.
5. **An artifact the table does not name takes the mode of what it serves.** A fixture or a test helper
   follows the tests it serves; a configuration file a package reads follows that package; a file that
   guards other files follows the checks that guard the repository.
6. **The project names its paths; the modes are this skill's.** Which directory holds the tests, which
   file is the architecture test, where CI lives — the project records them in its agent instructions.
   Where it records none, they are read from the repository, and whatever the declarations go to says
   the paths were not named.

### How an edit is caught

7. **Every edit is measured from a base commit, by a diff anyone can recompute.** The spec's base is the
   commit at which it reads as ready on the change's branch; the tests' base is the commit holding the
   tests written before the code. The diff of every declared and frozen path from its base, and of the
   repository's guarding checks from where the branch left its mainline, is taken before the change is
   reviewed. An edit to a frozen artifact the person did not agree to is a stop; an edit to a declared
   artifact that no declaration names is recorded as undeclared, by path and diff, and goes with the
   declarations to the review.
8. **A base commit stays as written until the change has been measured from it.** No later edit is
   folded into it before the diff and the review have read the change: an edit folded into the commit it
   changes is invisible to both. Once they have, the branch's history may be curated as the repository
   lands branches.
9. **Whoever made an edit does not judge what it did to a test.** An edit to a test is declared as made;
   whether it kept what the test asserts or weakened it is decided by the review, from the diff, by
   someone who wrote neither the test nor the edit — and for a test written before the code, from the
   tests' base, where it already existed. A weakened assertion the person has not agreed to
   holds the change.

## Hard stops

- Asked to write or check the spec itself, or to decide whether it is ready → stop, use
  `delivery-spec`.
- Asked whether the change is correct, or what it breaks → stop, use
  `/pyhouse-universal:change-review`.
