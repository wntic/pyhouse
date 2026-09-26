---
name: python-toolchain
description: Use when laying down or changing the configuration every Python distribution carries once in `pyproject.toml` — the src layout, the linter's rule selection and its written function-size and complexity thresholds, the few sanctioned lint suppressions, strict type checking, the line length, development dependencies grouped by role, and whether a dependency this project consumes may carry a version floor. Holds alike for a service of either architecture family, a CLI tool and a library. The interpreter floor and the type-ignore policy are `python-style`'s; which runtime libraries a service's roles bring and its migration bootstrap belong to the architecture family's setup skill; the version this distribution itself declares is `python-versioning`.
when_to_use: Also when asked to configure ruff or mypy, why a complexity or too-many-arguments rule fired, whether a `noqa` is allowed, which line length to use, how to start a new package, library or CLI tool, where dev dependencies go, or whether to pin or floor a dependency.
---

# Python Toolchain — layout, lint, type-check and dependency declarations

The configuration a Python distribution carries **once**, whatever it is and whatever its internal
layout: where the package sits, what the linter and the type checker enforce, and how dependencies are
declared. None of it recurs per feature. **Which** libraries a program depends on is not here — a
service's roles decide that, under its architecture family's setup skill; a library or a CLI tool with
no family needs only this skill.

## When to use vs. neighbours

- The interpreter floor, its house value and the three settings that name it → `python-style`; this
  skill writes them where it says.
- An inline type-ignore, a `cast`, annotation coverage of tests → `python-style`, which owns the
  type-suppression policy; this skill owns only the per-package missing-stub override in the config.
- The wildcard re-export in `__init__.py` and what a package root exports → `python-packaging`.
- The version this distribution declares, and what a raised dependency floor costs a library's
  consumers → `python-versioning`.
- Which runtime and development libraries a service's roles bring, the floors its family's templates
  rely on, and the migration bootstrap → the family's setup skill (`flat-project-setup`, in the
  `pyhouse-flat` plugin, or `hex-project-setup`, in `pyhouse-hex`).
- The test runner's own configuration block → `test-principles` states what it must hold; the fixtures
  it loads are the family's integration-setup skill's.
- Several distributions in one repository → `python-workspace`, which writes these values once at the
  root; what they are is still this skill's.
- How large a module may grow → the architecture's one-responsibility rule, held in review; the linter
  has no module-length rule.

## Template — ruff, mypy, hatchling (pyproject.toml)

`uv init --package --build-backend hatch myapp` lays the src layout — plain `uv init` lays a single
module that matches nothing here. Then `uv add <lib>` for a runtime dependency and `uv add --dev <lib>`
for a development one; `uv lock` writes the pins.

```toml
[project]
name = "myapp"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = []

[dependency-groups]
dev = [
    "mypy",
    "pytest",
    "ruff",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 120
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "B006", "B904", "C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915", "PLR0917"]

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.ruff.lint.pylint]
max-args = 7
max-positional-args = 5
max-branches = 12
max-returns = 6
max-statements = 50

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F403", "F405"]
"migrations/**/versions/*.py" = ["PLR0915"]  # only with migrations

[tool.mypy]
python_version = "3.13"
strict = true
files = ["src", "tests"]
explicit_package_bases = true
mypy_path = ["src", "."]
plugins = ["pydantic.mypy"]  # only with pydantic
```

The test runner's `[tool.pytest.ini_options]` block follows in the same file. At a workspace root the
same tables are written once; mypy's `files` and `mypy_path` name the member directories instead of
`src`. A library, and a service that runs a single process, remove the `main` stub and script `uv init`
generates; a CLI tool, and a service with several processes, declare one console script per command or
process in `[project.scripts]`.

`E` and `F` are the error and pyflakes families, `I` import sorting; `B904` is raise-without-from and
`B006` the mutable default argument; `F403` and `F405` are the two wildcard-import warnings. `C901` is
cyclomatic complexity; `PLR0911`, `PLR0912`, `PLR0913`, `PLR0915` and `PLR0917` are too many returns,
branches, arguments, statements and positional arguments.

Ruff runs with no paths, so it covers every Python file in the tree, `migrations/` included; mypy is
given `src` and `tests` and stops there. `tests/` is not a package, so a `conftest.py` at two levels
would be two modules with one name — `explicit_package_bases` with `src` and the tree root on
`mypy_path` makes mypy derive each module's name from its path instead.

The pydantic plugin is not optional where pydantic is used: without it strict mode reports every
no-argument settings construction — `FooSettings()` — as a call missing its required fields. A package
the project carries that ships no stubs and no `py.typed` marker adds one block, dev dependencies
included when the suite imports them:

```toml
[[tool.mypy.overrides]]
module = ["<package>", "<package>.*"]
ignore_missing_imports = true
```

**The line length.** `120` is the width this catalogue's templates are written to; `88` is the
formatter's default, which every tool and shared config already agrees on. On an empty tree nothing
needs reformatting, and the wider limit spares signatures and single-line comments from being cut
instead of wrapped; on an established tree the reformat is real, which argues for the number already
there. Either is compliant once written; the setting drives the formatter as well as the lint rule.

## Other bindings

- **Another package manager or build backend.** poetry or pdm replace the commands and the lock file;
  `uv_build` or setuptools replace hatchling. The src layout, names-only dependencies with floors only
  at a named break, and a development group installed by default — PEP 735 `[dependency-groups]`, or the
  tool's own table where it reads no other, never a deprecated one — are unchanged.
- **Another linter or type checker.** flake8 with its plugins, or pyright in strict mode: the rule codes
  and keys change; the parity of `src` and `tests`, the narrow selection that still refuses an unchained
  `raise` in `except` and a mutable default, every size and complexity threshold written down, one
  written line length and the closed list of suppressions do not.

## Rules

1. **The src layout, from the first commit.** The package lives under `src/<package>/`, tests under
   `tests/` beside it, for a service, a CLI tool and a library alike. A single-module or flat tree has
   to be moved before the second module, and the import path it tests is not the one an installed
   distribution has.
2. **One configuration, in `pyproject.toml`, and lint and type-check hold `src` and `tests` at
   parity**, so a defect never hides in whichever surface the other skips. Lint also covers any tree
   outside both, migrations included; the type checker stops at `src` and `tests`. What keeps `tests`
   green under strict checking is `python-style`'s full annotation coverage.
3. **The correctness selection is narrow**: the error and pyflakes families, import sorting, and two
   bugbear rules — a `raise` inside `except` that neither chains the cause nor says `from None`, and a
   mutable default argument — not the whole bugbear family.
4. **Function size and complexity are bounded by the linter, with every threshold written down.**
   Cyclomatic complexity stops at 10, McCabe's own published ceiling; branches at 12, return statements
   at 6 and statements at 50, pylint's long-standing defaults. Arguments are capped twice: positional
   ones at 5, and all of them at 7, because a keyword-only argument names itself at every call site. The
   numbers are written even where they equal the tool's default, because an unwritten threshold moves
   when the tool's default does. A function that trips a bound is split, never suppressed.
5. **A lint suppression is sanctioned only where a skill names it.** One is sanctioned everywhere — the
   wildcard ignore on `__init__.py` (`python-packaging`). Where a family's migration bootstrap is laid,
   its setup skill sanctions at most two more — for generated revisions and for registration-only
   imports — and names them. No other `noqa`, inline or per file, in `src`, `tests` or anywhere else.
6. **Type checking is strict, with the validation library's plugin where the project uses one that
   ships it.** A package with no type information gets one per-package override in the configuration;
   every other type suppression follows `python-style`'s policy.
7. **The line length is written down once, and the number is the project's.** Settled at setup; a later
   change reformats the tree and travels as its own commit, never inside a feature change.
8. **The interpreter floor is written in the three settings `python-style` names, all naming one
   interpreter**, and its value is `python-style`'s — for a deployable and for a distributed package
   alike.
9. **Dependencies are declared by name; a version floor marks a known break and says which.** The lock
   file is the only home for a pin. A floor sits at the release where an API the code relies on arrived
   or changed, with that API named beside it — never at a version remembered as recent, which is a
   guess dressed as a constraint — and a floor whose API the code no longer calls is removed with it.
   **A distributed package's floors are its consumers' contract**: they bound what every consumer's
   resolver may choose, so they sit at the oldest release that works and never pin exactly, and raising
   one is a change consumers see, released under `python-versioning`.
10. **Dependencies are grouped by role.** What the running code imports is a runtime dependency and
    arrives with the code that imports it; what only developing it needs — the test runner, the linter,
    the type checker — goes in the group the package manager installs by default, never a deprecated
    tool-specific table. A distributed package's optional integration is an extra its consumers opt
    into, not a runtime dependency all of them install. A package nothing imports is removed.

## Hard stops

- The project is being laid down as a single module or a flat tree with no `src/` → stop, use the src
  layout.
- A dependency is pinned in `pyproject.toml`, or given a floor with no named break → stop, names only;
  the lock file pins, and a floor names the API it relies on.
- A floor is being written from a recollection of what version is "recent" → stop, a floor states a
  known break or it does not exist.
- A development tool is declared as a runtime dependency, or in a deprecated tool-specific table →
  stop, it goes in the default development group.
- `tests` is excluded from the type checker or the linter, or checked less strictly than `src` → stop,
  they are held at parity.
- A size or complexity rule is being dropped from the selection, its threshold raised or left unwritten,
  or a function exempted with `noqa` to get it through → stop, split the function; the bound is the
  point.
- A `noqa` or a per-file ignore no skill sanctions → stop, fix the code (rule 5).
- A missing-stub error silenced anywhere but a per-package override in the configuration → stop, write
  the override; any other type suppression → `python-style`.
- `line-length` left unwritten, or restated in a second file → stop, write it once.
- `line-length` changed inside a feature change on an established tree → stop, it reformats the tree;
  make it its own commit.
- `requires-python`, `target-version` and `python_version` disagree → stop, `python-style`; all three
  name the project's oldest supported interpreter.
- Asked which runtime libraries a service needs → stop, that is its roles', under the family's setup
  skill; this skill says only how they are declared.
