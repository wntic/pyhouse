#!/usr/bin/env python3
"""Import every symbol the catalogue's templates name, and report the ones that do not exist.

A skill is prose until someone pastes its template. This walks every fenced ``python`` block in
every skill and its sibling files, collects the imports, and resolves each name against what is
installed here.

Three outcomes, and the distinction between the last two is the point:

  ok          the module imported and every name resolved
  MISSING     the module imported and a name it is asked for does not exist
  unchecked   the module is not installed, so nothing was verified

`unchecked` is not a pass. It is the report saying which surface still has no evidence behind it.
Placeholder modules — the ones the catalogue deliberately invents — are skipped by name.
"""

from __future__ import annotations

import ast
import importlib
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
FENCE = re.compile(r"```python\n(.*?)```", re.S)

# Modules the catalogue means not to exist: a reader substitutes their own.
PLACEHOLDERS = ("myapp", "myschema", "myrepo", "myframework", "mycommon", "store_sdk", "shared", "tests")


def _placeholder(module: str) -> bool:
    return module.startswith(".") or module.split(".")[0] in PLACEHOLDERS


def _imports(source: str) -> list[tuple[str, tuple[str, ...]]]:
    """Every (module, names) an import statement in this block asks for."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []  # a fragment, not a file — nothing to check
    out: list[tuple[str, tuple[str, ...]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(a.name, ()) for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            out.append((node.module, tuple(a.name for a in node.names)))
    return out


def main() -> int:
    missing: list[str] = []
    unchecked: dict[str, set[str]] = {}
    checked = 0

    for path in sorted(ROOT.glob("plugins/*/skills/*/*.md")):
        rel = path.relative_to(ROOT)
        seen: set[tuple[str, tuple[str, ...]]] = set()
        for block in FENCE.findall(path.read_text(encoding="utf-8")):
            for module, names in _imports(block):
                if _placeholder(module) or (module, names) in seen:
                    continue
                seen.add((module, names))
                try:
                    mod = importlib.import_module(module)
                except ImportError:
                    unchecked.setdefault(module.split(".")[0], set()).add(str(rel))
                    continue
                checked += 1
                for name in names:
                    if hasattr(mod, name):
                        continue
                    # A submodule is not an attribute until something imports it.
                    try:
                        importlib.import_module(f"{module}.{name}")
                    except ImportError:
                        missing.append(f"{rel}: `from {module} import {name}` — {name} does not exist")

    for line in missing:
        print(f"MISSING  {line}")
    if unchecked:
        print(f"\nunchecked — not installed here, so nothing was verified:")
        for pkg, files in sorted(unchecked.items()):
            print(f"  {pkg:<18} named by {len(files)} file(s)")
    print(f"\n{checked} imports resolved, {len(missing)} missing, {len(unchecked)} packages unchecked")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
