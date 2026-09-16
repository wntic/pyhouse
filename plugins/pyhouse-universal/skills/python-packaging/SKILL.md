---
name: python-packaging
description: Use when the question is the mechanics around a module rather than what it is called — `__init__.py`, `__all__`, a re-export, one file or two modules, relative versus absolute imports, a circular import. Owns one class per module, the four-part re-export contract, and building nothing at import time. Naming a module is `naming`.
when_to_use: Adding a public module to a package; a wildcard import; import order; a module-level settings object, engine or client.
---

# Python Packaging

What a thing is called, how its module is packaged, and how another module reaches it. These rules are
**architecture-neutral** — they hold in a layered app, a standalone service, and a shared library alike,
because they are about naming and Python's import system rather than about layers.

What they do *not* decide is which package a module belongs in. That is the architecture's job:
`hex-architecture` for a layered app, `flat-layered` for a package-by-tech service.

## When to use vs. neighbours

- Choosing a name for anything — a package, module, class, function or variable → `naming`, first.
  "Name this module" lands there, not here; this skill only checks the filename against the class
  once the name exists.
- Creating a module or an `__init__.py`, or changing a package's public surface → this skill.
- Any question of relative vs absolute, or how to spell an import → this skill.
- A circular import, or an import pushed into a function body to break one → this skill; the cycle is
  a structural problem and the hard stops below say so.
- Which package a module belongs in → `hex-architecture` or `flat-layered`.
- Annotation forms, logging, comments → `python-style`.
- The exception catalog's contents, and why that one file holds many classes → `exception-catalog`.
- Whether the boundary between two modules or packages should exist at all → `coupling`, first; this skill owns the mechanics once it is drawn.

## Naming — owned by `naming`

**The choice of the name itself lives in the `naming` skill** — the derivation procedure, the tests a
name must pass, the kind-by-kind rules, and the vague-noun families (`CheckResult`, `…Data`,
`…Manager`, `process_…`). Load it before writing an identifier; load it *first* when the code was
ported or generated, because that is where names arrive by inertia.

Two consequences of naming land here, in the packaging mechanics, and are enforced below:

- A module filename must describe its contents and **match its single class in snake_case**
  (`foo_client.py` → `FooClient`). `utils.py` holding `class FooHelper` is wrong twice — the file
  names a category rather than a responsibility, and so does the class.
- A rename is a **separate commit** from any behaviour change, and names that have escaped into
  external contracts — log event names, exception `code` values, registered workflow/activity names,
  database constraint names, published API fields — are not renamed in place at all.

## Modules

- **One class per module file**, and the module name matches the class in snake_case (`foo_client.py` →
  `FooClient`, `entity_registry.py` → `EntityRegistry`).
- **`__all__` goes after the imports and before the class definition**, never at the top of the file.
- A module filename must describe its contents, by the rules in `naming`.

```python
# imports


__all__ = ["FooClient"]


class FooClient:
    pass
```

### The named exceptions to one-class-per-module

Two file *shapes* deliberately hold several classes, because they co-evolve and splitting them would cost
readability with no decoupling gain:

1. **The exception catalog** — one file holding the root error and every subclass, so the catalog stays
   auditable (`exception-catalog`).
2. **A per-resource wire-schema module** — the request/response models describing one resource's
   contract from different angles.

The carve-out is by exact file, not by directory or category. A third entity in `foos/foo.py` is still
wrong; two adapters in one repository module are still wrong; a command and its handler in one file are
still wrong.

Modules holding multiple **functions** — a route module, a module of pure filters — do not engage this
rule at all. It is about classes.

### Nothing is built at import time

**Importing a module binds names.** It does not reach the network or the filesystem, read an environment
variable, or build anything that needs either — a settings object, a client, an engine, a session
factory, a connection pool. Those are built **behind a factory function** the caller calls. Declaring is
not building: a class, a constant, a type alias, or a schema object that only describes a shape may sit
at module level, because none of them needs anything to exist.

```python
# no — runs on import, so importing this module is what fails
settings = Settings()

# yes — the caller decides when, and the failure names the missing value
@lru_cache
def get_settings() -> Settings:
    return Settings()
```

The reason is the import graph, which is why it lives here. A module-level construction runs for every
importer, including ones that never touch the object: a test collector importing a sibling symbol, a
documentation build, a CLI that only wanted one constant. Each of those now needs the full environment
of the thing it did not ask for, and the traceback names the import rather than the missing value. It
also puts a side effect somewhere nothing can order it, since import order is decided by whoever imports
first.

Carve-out 2 below is a concession to modules that genuinely cannot avoid this — an application object a
server loads by path — not a licence for the rest.

## The `__init__.py` re-export contract

This contract is what makes the collapsed import form below legal. It has four parts, and skipping any
one of them breaks either the runtime or the type checker.

- **Always `from .module import *`**, never `from .module import ClassName`.
- **Always `__all__ = module.__all__`** (or `+`-joined across modules), never `__all__ = ["ClassName"]`.
- **Precede the wildcards with one `from . import <module>, …` line** naming every re-exported submodule,
  alphabetically.
- **An `__init__.py` contains only imports and `__all__`.** No class definitions, no constants, no logic.

That third bullet is the one people delete as redundant. It is not. The wildcard binds the submodule at
runtime, but **the type checker does not model that side effect** — without the explicit
`from . import …`, the `__all__ = module.__all__` reference fails type-checking as an undefined name. The
explicit import is what makes the contract check.

A single module:

```python
from . import manager
from .manager import *

__all__ = manager.__all__
```

Several modules — name them all in the `from . import …` line, repeat the wildcard per module, and
concatenate:

```python
from . import command, handler
from .command import *
from .handler import *

__all__ = command.__all__ + handler.__all__
```

**A package re-exports its immediate children — direct modules *and* child subpackages** — except the
carve-outs below. A package with children and an empty `__init__.py` is wrong; re-export them so
`from <pkg> import X` resolves.

Adding a module to a re-exporting package is **four edits**: declare `__all__` in the module, add it to
the `from . import …` line, add its `from .<module> import *`, and append `<module>.__all__` to the
package's own `__all__`. Miss one and the collapsed form breaks at the first call site.

### Carve-outs — where re-export stops

**1 — the distribution root stays minimal.** The top-level `<package>/__init__.py` carries only
`__version__`. Aggregating everything to the root makes `import <package>` transitively pull every
third-party dependency the project has on every use, and destroys any dependency-free import path the
architecture was maintaining. Re-export stops below the root; it does not climb to it.

**2 — a module with import-time side effects is not wildcarded.** If importing the module *does*
something — builds an application object, opens a connection, registers a handler — its package
`__init__` must not pull it in. Re-export only the side-effect-free surface, or leave the `__init__`
empty. The same applies to a package of modules that each export a **colliding** name (several route
modules each exporting `router`): a wildcard would clash, so those are reached by explicit aliased
import at the one place that consumes them.

This carve-out is per module, not per directory. A sibling package whose class names are distinct
re-exports them normally.

**3 — wildcard only class-modules.** `from .x import *` is for a module that declares `__all__` — a class
module. A module whose public name is a bare object rather than a class (a `metadata` instance, a
configured singleton) is **not** wildcarded into its package `__init__`, because the wildcard would bind
a name shadowing the submodule itself. Reach it by explicit relative import: `from ..metadata import
metadata`.

## Imports

### Relative vs absolute

- **Inside a package, relative imports up to two dots** — `from .sibling import X`,
  `from ..parent import Y`.
- **Same package → one dot, never up-and-back-down.** A module importing a sibling in its **own** package
  uses `.sibling`. Routing through the parent back into the same package
  (`from ..pkg.sibling import X` while already inside `pkg/`) resolves but reads as a cross-package
  reach. No tool flags it — the import is valid Python — so it is on the author.
- **Three or more dots → absolute.** `from ...thing import Z` is banned; write
  `from myapp.subpkg.thing import Z`. Once it would be `...`, the absolute path is both shorter and
  clearer.
- **Across package boundaries → absolute**, regardless of dot count. **A layer is a package**, so in a
  layered architecture this is the same rule under a second wording — cross-layer imports absolute,
  within-layer imports relative. One rule, not two.

```python
from .create_foo_command import CreateFooCommand          # same dir — relative
from ..bars.create_bar_command import CreateBarCommand    # one level up — relative
from myapp.domain.foos import IFooRepository              # cross-package — absolute

from .settings import DbSettings                          # same package — one dot
# NOT: from ..postgres.settings import DbSettings         # up-and-back-down into the same package
```

### Collapse same-package imports

Importing several symbols from the same place is **one statement**:

```python
# yes
from myapp.domain.foos import (
    Foo,
    FooListFilter,
    FooKind,
    IFooRepository,
)

# no
from myapp.domain.foos.foo import Foo
from myapp.domain.foos.foo_kind import FooKind
```

- One symbol per line inside the parens, alphabetically sorted, trailing comma on the last entry. A
  one-symbol import stays on a single line.
- Import from the **package**, not from an individual module — which is exactly what the re-export
  contract underwrites. Bypassing `__init__.py` forces every reader to know the file layout.

**"Package" means the one that DIRECTLY contains the defining module — never a grandparent.** Reach a
symbol through **one** `from .module import *` hop. Do not reach it through a grandparent that would
re-export it across a second hop: the intermediate package's `__all__` is a **computed** concatenation
(`a.__all__ + b.__all__`) that the type checker cannot evaluate through a `from .subpkg import *`, so the
name resolves at runtime while the checker reports "module has no attribute".

Concretely: a repository class comes from its `repositories` package —
`from myapp.infrastructure.postgres.repositories import FooRepository` (one hop) — **not** from
`myapp.infrastructure.postgres` (two hops, the middle `__all__` computed). A class sitting *directly*
under a package is one hop from it, so importing it from there is correct.

### Import order inside a module

PEP 8 grouping, one blank line between groups:

1. `__future__` — **banned in this style** (`python-style`); this slot stays empty.
2. Standard library.
3. Third-party.
4. First-party absolute.
5. First-party relative.

The formatter and import sorter handle this automatically. Do not fight them, but know the groupings so
hand-written imports land in the right block.

## Rules

1. Use `naming` for identifier choice and renaming; check module filenames against their class names.
2. Check class counts against **Modules** and its two exact-file exceptions; function-only modules do
   not engage that rule.
3. Put module exports between imports and definitions, using the placement shown in **Modules**.
4. Check each re-exporting `__init__.py` against all four parts of the re-export contract.
5. When adding a public module, complete all four package edits listed under that contract.
6. Apply each re-export carve-out at its documented scope: distribution root, side effects or colliding
   exports, and bare-object modules.
7. Select relative or absolute reach using **Relative vs absolute**, without routing a sibling import
   through its parent. A layer boundary is a package boundary and takes the absolute form.
8. **Build nothing at import time.** Importing a module binds names; anything that reaches the network
   or filesystem, reads the environment, or needs either goes behind a factory the caller calls — so
   importing a module never demands the environment of an object the importer did not ask for.
9. Collapse symbols from the same direct package into the documented sorted import form; keep the
   re-export reach to one hop.
10. Keep imports in the five documented groups; apply `python-style` to the empty future-import slot.
11. Check wildcard use, module aliases and cycle workarounds against the hard stops below.

## Hard stops

- A new module file with two top-level classes → stop, split it. The only exceptions are the exception
  catalog and a per-resource wire-schema module.
- A module filename that does not match its class in snake_case → stop, rename the file.
- `__all__` placed above the imports → stop, it goes after the imports and before the class.
- An `__init__.py` with `from .module import ClassName` instead of the wildcard → stop, use the wildcard
  so the package `__all__` can be `+`-joined.
- An `__init__.py` holding class definitions, constants or logic → stop, imports and `__all__` only.
- An `__init__.py` referencing `module.__all__` with no matching `from . import module` line → stop, add
  the explicit submodule import; the wildcard alone does not bind the name for the type checker.
- A package with children and an empty `__init__.py` → stop, re-export them.
- The distribution root's `__init__.py` wildcarding its subpackages → stop, it carries `__version__` only.
- A module with import-time side effects being wildcarded into its package → stop, importing the package
  would now run it.
- A module-level `settings = Settings()`, client, engine or connection → stop, put it behind a factory;
  as written, every importer pays for it and the failure names the import instead of the missing value.
- Importing an inner module rather than its package (`from pkg.foo.foo import Foo`) → stop, import from
  the package.
- Reaching a symbol through a grandparent package → stop, one hop; the middle `__all__` is computed and
  will not type-check.
- `from x import *` outside an `__init__.py` → stop, a wildcard inside a regular module pollutes the
  namespace and breaks linting.
- A three-or-more-dot relative import → stop, switch to absolute.
- `import myapp.domain.foos as fs` followed by `fs.Foo` → stop, use `from … import`; a module alias hides
  what is actually used.
- An import inside a function body, or a `TYPE_CHECKING` block, used purely to break a cycle → stop, the
  cycle points at a structural problem; fix the structure.
- Any identifier is being chosen, or carried over from ported or generated code → `naming` owns that
  judgment and carries its own hard stops; this skill's stops cover only the packaging mechanics.
