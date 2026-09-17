---
name: test-architecture-rule
description: Use when forbidding X in layer Y with a static grep firewall — an architecture test, its path constants, a rule fragment, a bounded allow-list. Owns `tests/unit/test_architecture.py` in a standalone distributable and `tests/test_architecture.py` at the root of a repository of several members. Runtime behaviour belongs in an ordinary test; the constitution is `test-principles`.
---

# Test — Architectural Firewall Rule

Each function greps the source tree for a forbidden pattern and asserts the result is empty. Where the file sits follows the shape of the tree, not the architecture family: one distributable puts it at `tests/unit/test_architecture.py`; a repository holding several members puts it at `tests/test_architecture.py` beside them, because its subject is the repository rather than anything in it. The firewall must stay collectable when the tree is broken.

## When to use vs. neighbours

- A static, absolute "layer Y must not import X" invariant the codebase needs enforced → this skill.
- Shared testing constitution → `test-principles`. That is prose the whole suite obeys; this is one
  grep that reddens a build.
- Runtime domain behavior → `hex-test-domain`, in the `pyhouse-hex` plugin.
- Runtime storage behavior → `flat-test-persistence`, in the `pyhouse-flat` plugin. Greps enforce
  static structure; runtime tests enforce dynamic behavior.
- Hex layer boundaries → `hex-architecture`, in the `pyhouse-hex` plugin.
- Flat repository boundaries → `flat-layered`, in the `pyhouse-flat` plugin.
- A type-correctness rule → `mypy` / `pyright` enforce it; do not duplicate as a grep test.
- A style or formatting rule → `ruff` enforces it; do not duplicate.
- A "should usually" rule with material exceptions → not a firewall candidate; document it in the
  skill that owns the layer instead. Firewalls are absolutes that accumulate exceptions and stop
  paying for themselves.
- An intent-based rule ("do not use `Any` *unless* at a true external boundary") → not a firewall
  candidate; greps either hit or do not, with no intent inspection.

## Template(s) — `grep` through `subprocess`, one plain pytest function per rule

### File scaffold (once per repo)

The standalone form follows — one distributable, one `src/`, one `tests/`. A repository of several
members replaces the path-constant block with the multi-member fragment below; the imports, the
`_grep` helper and every rule in this skill are identical in both.

```python
import subprocess
from pathlib import Path

# parents[2] walks up from tests/unit/test_architecture.py. A firewall placed directly under
# tests/ uses parents[1] instead; that constant is the only line the move changes.
_ROOT = Path(__file__).resolve().parents[2]
_SRC = str(_ROOT / "src" / "myapp")
_TESTS = str(_ROOT / "tests")
_UNIT_TESTS = str(_ROOT / "tests" / "unit")
# One constant per scope a rule names (rule 4). Give the layer or role directories this
# distributable actually has one line each; the two below are illustrative, not required.
_DOMAIN = str(_ROOT / "src" / "myapp" / "domain")
_APP = str(_ROOT / "src" / "myapp" / "application")


def _grep(pattern: str, *paths: str) -> list[str]:
    if not paths:  # a glob that matched nothing must not leave grep reading stdin
        return []
    result = subprocess.run(
        [
            "grep", "-rnE",
            "--include=*.py",
            "--exclude=test_architecture.py",
            pattern,
            *paths,
        ],
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]
```

Patterns run under `-E`: basic `grep`'s `\|` alternation is a GNU extension that BSD `grep` does not
reliably carry, while `-E` behaves the same on both. `grep` exits 1 when it finds nothing, which is the
ordinary case, so the helper must not check the return code — it reads `stdout` and lets an empty result
be an empty list.

### Multi-member path constants

For a repository of several members with the firewall at `tests/test_architecture.py`, replace the
scaffold's constants from `_ROOT` through `_APP` with the block below. The member directory names
are a constant for the same reason rule 9 keeps a role name out of a pattern: a repository that
groups its members differently overrides one tuple and every glob follows.

```python
_ROOT = Path(__file__).resolve().parents[1]

# The directories under which this repository's members live, as it declared them.
_MEMBER_DIRS = ("packages", "services")
# Source trees only: a member's tests/ legitimately names what its src/ may not.
_SRC_DIRS = [str(p) for d in _MEMBER_DIRS for p in _ROOT.glob(f"{d}/*/src")]

# `myschema` is the shared library the other members import, under whatever name this repository
# gave it; here it is the member that owns the database schema, and it is also where the framework
# guard below sits. A repository with no shared library drops these three constants.
_SCHEMA = str(_ROOT / "packages" / "myschema")
_SCHEMA_SRC = str(_ROOT / "packages" / "myschema" / "src")
_SRC_OUTSIDE_SCHEMA = [p for p in _SRC_DIRS if p != _SCHEMA_SRC]

# Tests live beside the member they cover, so a repo-wide test rule sweeps every member's tests/
# tree plus the root one. Splat these into `_grep`: `_grep(pattern, *_TESTS)`.
_TESTS = [str(p) for d in _MEMBER_DIRS for p in _ROOT.glob(f"{d}/*/tests")] + [
    str(_ROOT / "tests")
]
_UNIT_TESTS = [str(p) for d in _MEMBER_DIRS for p in _ROOT.glob(f"{d}/*/tests/unit")]

# A project may declare that exactly one package wraps a given framework and that nothing else
# imports it. Both names below are the ones THIS project declared — fill in your own; they are two
# constants because a project that names the wrapping package for its role rather than for the
# framework changes one without the other. Neither is inferred from a directory name (rule 9).
_FRAMEWORK_IMPORT = "myframework"            # the top-level module the framework is imported as
_FRAMEWORK_WRAPPER_PACKAGE = "myframework"   # the package the declaration allows to import it
# The one module outside that package the declaration exempts — the shared helper that holds the
# framework import so its callers stay framework-free. It is exempted by the rule's allow-list
# below, never by going unswept. A project that declared no such helper drops this constant and the
# filter that reads it.
_FRAMEWORK_GUARD_MODULE = str(
    _ROOT / "packages" / "myschema" / "src" / "myschema" / "myframework.py"
)
# Every member's src/ EXCEPT the package holding the wrapper role. Every member directory is
# swept, and loose top-level modules are kept (no is_dir() filter) — that is what puts the shared
# helper in front of the allow-list instead of leaving it exempt because nothing looked at it.
_SRC_OUTSIDE_FRAMEWORK_WRAPPER = [
    str(p)
    for d in _MEMBER_DIRS
    for p in _ROOT.glob(f"{d}/*/src/*/*")
    if p.name != _FRAMEWORK_WRAPPER_PACKAGE
]
```

### Standard rule (no allow-list)

```python
def test_no_<rule_name>() -> None:
    hits = _grep("<pattern>", <paths>)
    assert hits == [], "<message>:\n" + "\n".join(hits)
```

Concrete, in the standalone form:

```python
def test_domain_has_no_sqlalchemy() -> None:
    hits = _grep(r"import sqlalchemy|from sqlalchemy", _DOMAIN)
    assert hits == [], "sqlalchemy import in domain:\n" + "\n".join(hits)
```

The same rule in the multi-member form, where the scope is every member except the one that owns
the schema:

```python
def test_no_service_defines_a_table() -> None:
    hits = _grep(r"^from sqlalchemy import.*\bTable\b|sqlalchemy\.Table", *_SRC_OUTSIDE_SCHEMA)
    assert hits == [], "a Table defined outside the schema package:\n" + "\n".join(hits)
```

### Rule with an in-test allow-list

The invariant this one pins, stated here so the rule is writable on its own: **where one member
owns the shared database schema, only that member's repository modules may name a table object;
every other member reaches the data through a repository method.** (The flat family states it as a
rule in `flat-persistence`, in the `pyhouse-flat` plugin; the firewall does not need that skill
installed.)

```python
def test_no_service_reaches_the_shared_tables_directly() -> None:
    _repo = str(_ROOT / "packages" / "myschema" / "src" / "myschema" / "repositories")
    all_hits = _grep(r"\bfoos_table\b|\bbars_table\b", *_SRC_OUTSIDE_SCHEMA, _SCHEMA_SRC)
    forbidden = [h for h in all_hits if not h.startswith(_repo)]
    assert forbidden == [], (
        "a shared table object reached directly — go through FooRepository:\n"
        + "\n".join(forbidden)
    )
```

The pattern stays simple; the exception is explicit and visible to whoever reads the failure.

The framework-import rule is the second allow-listed one, and the entry is the module the
declaration exempts. It is not a multi-member rule — a single distributable sweeps `_SRC` with the
wrapper package's directory filtered out, and every line below is unchanged. The pattern is built
from the constant rather than spelled out, so the name the project declared and the name the rule
greps for cannot drift apart:

```python
def test_no_framework_import_outside_the_wrapper_package() -> None:
    all_hits = _grep(rf"\b{_FRAMEWORK_IMPORT}\b", *_SRC_OUTSIDE_FRAMEWORK_WRAPPER)
    forbidden = [h for h in all_hits if not h.startswith(_FRAMEWORK_GUARD_MODULE)]
    assert forbidden == [], (
        "framework import outside the declared framework-wrapper package:\n" + "\n".join(forbidden)
    )
```

Widening the sweep over the member that holds the shared helper and allow-listing that helper are
**one change, not two**. A sweep that stops short of it leaves the helper exempt because nothing
looked at it, and adding the sweep without the allow-list entry turns the firewall red on its own
sanctioned exception.

Standalone example:

```python
def test_no_print_calls_outside_allowed() -> None:
    _main_py = str(_ROOT / "src" / "myapp" / "restapi" / "main.py")
    _cli = str(_ROOT / "src" / "myapp" / "cli")
    all_hits = _grep(r"print\(", _SRC)
    forbidden = [h for h in all_hits if not h.startswith(_main_py) and not h.startswith(_cli)]
    assert forbidden == [], "print() calls found outside allowed locations:\n" + "\n".join(forbidden)
```

The pattern stays simple ("no `print(`"); exceptions are explicit and visible to a future maintainer.

### Adding a new path constant (when a new scope is needed)

Append at the top of the file, next to the existing constants:

```python
_RESTAPI = str(_ROOT / "src" / "myapp" / "restapi")
_INFRA   = str(_ROOT / "src" / "myapp" / "infrastructure")
```

## Other bindings

- **Import-linter contracts**, declared in config and run as their own command. Forbidden
  relationships become layer and forbidden-module contracts instead of patterns, and because it
  resolves real imports there are no word-boundary or docstring false positives. One rule per
  contract, the named allow-list, the failure naming the offending module and the never-ship-it-red
  rule are unchanged; the firewall stops being a test, so collectability moves to the linter's run.
- **A linter's banned-API rule** (`flake8-tidy-imports`' `banned-api` under ruff). Cheapest — it runs
  in a pass the project already has, scoped per directory. It reaches import rules only, so every
  non-import invariant (`print(`, a sleep, a module-level engine) stays here and most projects carry
  both, and the hard stop on restating what the linter enforces decides which file a rule goes in.
- **An `ast` walk over the tree.** Distinguishes an import from the same word in a docstring, and a
  module-level call from one nested in a function. Only `_grep` is replaced — every rule below holds,
  and rule 8's escaping advice becomes a node test instead.

## Rules

Consult `test-principles` for the testing constitution. Where this skill contradicts
`test-principles`, the constitution wins. The *words inside* a rule's name — which layer, which
thing, which verb — are `naming`'s decision; the **patterns those words go into are rule 2 here**.

1. **One test function per rule, with nothing around it.** No fixtures, no parametrization, no async —
   `def test_*() -> None` under the pytest binding. The test name **is** the rule, and the file's test
   list reads as the workspace's structural constitution.
2. **A rule's name states its scope and what is absent, in its family's form.** Do not pluralize, do
   not add qualifiers.
   - **hex — layer-scoped:** `test_<layer>_has_no_<thing>`, e.g. `test_domain_has_no_pydantic`.
   - **flat — service-scoped:** `test_no_service_<verb>_<thing>`, e.g.
     `test_no_service_defines_a_table`.
   - **either family — repo-wide:** `test_no_<thing>`, e.g. `test_no_future_annotations_anywhere`.
   A name that does not say where the rule looks sends a reader to the pattern to find out, and the
   file stops being readable as a constitution.
3. **The failure names every offending location, never a count or a boolean.** Assert the collected
   hits against an empty collection so the runner prints the actual list beside the expected one —
   `assert hits == []` under pytest. `assert not hits` and `assert len(hits) == 0` say the firewall is
   red and nothing about where.
4. **Every scope a rule names is a named constant at the top of the file.** Add a new `_<NAME>`
   constant when a new scope is needed; a path written inside a test drifts silently when the tree
   moves, and the rule keeps passing over a directory that no longer exists.
5. **Run the rule against the current tree before committing.** Confirm zero unexpected hits, and
   never ship a firewall that is already red — narrow it or fix the hits. A rule that arrives red
   teaches everyone to skip it.
6. **Exceptions are allow-listed inside the test, by name, and cap at three.** Filter the result
   against named paths — `startswith(...)` against a path constant under the grep binding — rather
   than weakening the pattern, so the pattern stays readable and the exception is visible to whoever
   reads the failure. The framework-import rule's one entry is `_FRAMEWORK_GUARD_MODULE`, the shared
   framework-guarded helper module. A fourth entry means the rule has too many exceptions to be a
   firewall: split it into something more specific, or demote it to prose.
7. **A rule never imports what it forbids, or anything from the tree it polices.** Importing it
   defeats the firewall, and the file must stay collectable when the tree is broken — a broken import
   turns "the rule failed" into "the rule could not be collected", which reads as green in some
   reports. The schedule/task-queue rule below is the one documented exception, and it is not a
   pattern rule.
8. **A pattern matches the whole token it names and nothing that merely contains it.** Under
   `grep -E` that is raw strings wherever a backslash appears, `\b` at both ends of a bare word, and
   plain `|` for alternation. A pattern that also catches a longer identifier, a comment or a
   docstring makes the rule's own name a lie, and the first false hit is what gets it deleted.
9. **A rule that exempts a package because of the role it holds reads that role from what the
   project declared, never from a directory name.** The worked case is the framework wrapper: a
   project declares that exactly one package wraps a framework and that nothing else imports it, so
   the framework's import name, the wrapping package's name and any exempted module are each a
   constant a project that chose other names overrides — and the pattern is built from the constant,
   so the two cannot drift apart. **One constant per declared name.** A repository whose members each
   chose a different name for the same role widens that constant into its own lookup on the way in;
   the rule as written carries the single declaration, because a per-member override table is a
   second allow-list with no cap (rule 6) and it is unreadable to everyone but the repository that
   needed it. (Both families make such declarations; this rule holds wherever one is made at all.) A
   rule with the name hardcoded is green on a project where it is checking nothing.

### Candidates, by family

The two lists below are the invariants this catalogue has found worth a firewall, one list per
architecture family. Each names the skill that *states* the invariant, in `pyhouse-hex` or
`pyhouse-flat`; the invariant itself is spelled out here, so the list is readable and the rule
writable with neither family plugin installed. Both templates above are complete in this file.

### What is worth a firewall in hex

- No SQLAlchemy or Pydantic imports in domain code — `hex-architecture`.
- No infrastructure dependencies in domain or application code — `hex-architecture`.
- No mocks in tests — `test-principles`.
- No print calls outside the explicit entrypoint allow-list — `python-style`.

### What is worth a firewall in flat

- No tables or statements constructed outside the package that owns the data access — `flat-persistence`.
- No sibling-service imports, and no framework import outside the package whose declared role is
  framework wrapper (plus the shared framework-guarded helper the allow-list names) — `flat-layered`.
- No module-level engine construction — `flat-persistence`.
- No engines in unit tests, mocks, or sleeps in tests — `test-principles`.

### A rule that is not a grep

"Every schedule's task queue is served by some worker" is worth pinning and cannot be grepped
meaningfully. Write it as an ordinary test that imports the schedule script's declarations and the
services' task-queue constants and compares the two sets. It lives in the same file, breaks rule 7's
"no imports" for a documented reason, and is the exception that proves it — if a second such rule
appears, move both into a `tests/test_schedules.py` of their own.

## Inlined typing / import rules

- `subprocess` and `pathlib.Path` only at the file level (already present).
- In a grep rule, never import from `myapp` — importing what you're trying to forbid defeats the firewall.
- Tests are sync `def test_*() -> None`.

## Hard stops

- The pattern produces unintended hits in the current tree → stop, fix them or narrow the pattern before
  the test is committed.
- The rule depends on intent or on runtime state → stop, this is not a grep-firewall rule.
- The allow-list would need a fourth entry → stop, the rule is too leaky; restructure or demote it.
- A fixture, `parametrize` or `async` is being added → stop, one plain `def test_*` per rule.
- A `try/except` or a conditional skip is being wrapped around `_grep` → stop, that breaks the
  unconditional property that makes a firewall worth having.
- The rule restates something the linter or type checker already enforces → stop, two enforcers for one
  rule means two places to change it.
- A "no `Protocol` in services" rule is proposed → stop unless the repository genuinely has none: a
  style that permits a port the moment a second implementation exists turns this into an allow-list
  that outgrows three entries, which rule 6 forbids. It is prose, not a firewall — the flat family
  already carries it as prose in `flat-layered`, in the `pyhouse-flat` plugin.
- A grep rule imports anything from `myapp` → stop, importing the thing you forbid defeats the firewall.
- A rule exempts a package by a hardcoded directory name rather than by the role the repository
  declared → stop, read the name from a constant (rule 9); otherwise the rule is green on every
  repository that named that package something else, and it is checking nothing.
- A sweep is widened over a directory holding a sanctioned exception, without the allow-list entry
  landing in the same change → stop, the firewall goes red on its own exception; land both together.
- Spec inlines a literal path inside a test → stop, use the `_<NAME>` constants at module top; add a new constant if a new scope is needed.
