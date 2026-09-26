---
name: python-settings
description: Use when a program reads configuration from its environment — writing or extending a settings class, deciding whether a field gets a default, carrying a secret, or deciding where the settings object is built and how its values reach the code that uses them. Owns one settings class per configured component, the non-strict namespace, no default on a required field or a tunable, the secret type and where it is unwrapped, derived values, validation that only normalizes or rejects, construction at the composition root, and what a library reads (nothing, when published). The prefix's name is `naming`; nothing built at import time is `python-packaging`.
when_to_use: Also when asked for a config class, an env var, a `.env` file, a `BaseSettings` subclass, an API key or password field, a timeout or pool-size default, `os.getenv` in a module, or where to call `get_settings()`.
---

# Python — Settings

A program's configuration arrives from its environment, and one kind of class reads it: the settings
class. This skill owns what that class declares, which of its fields may default, how a secret travels
through it, and where the object is built. It holds in any Python program — a service of either
architecture family, a CLI tool, a library — because every one of them either reads configuration or is
handed it.

## When to use vs. neighbours

- What a settings class or its environment prefix is called, the nested-prefix collision, and the stem a
  shared library reads → `naming` (its rule 7 and **One environment prefix per settings class**).
- A settings object, client or engine built at module level → `python-packaging` rule 8, which owns
  building nothing at import time; this skill owns where the factory is called instead.
- A field's annotation, and keeping a secret out of a log line → `python-style`.
- Building settings inside a test, `monkeypatch.setenv`, and dotenv files leaking into a test run →
  `test-principles`.
- Renaming an environment variable that is already deployed → `naming`'s **Renaming**; the name is a
  frozen external contract.
- Where the composition root is and how it binds settings — examples only, each in its family plugin:
  the container (`hex-wiring`, in `pyhouse-hex`) or the process definition (`flat-layered`, in
  `pyhouse-flat`). Where a settings module sits in the package is that family's layout.
- A threshold the domain itself reasons about (a maximum, a retention period) → the settings class still
  reads it; turning it into a domain value is the family's (`hex-domain-model`'s tunable, in `pyhouse-hex`).

## Template — pydantic-settings

The settings module of the component it configures — one component, one class, one factory:

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["FooSettings", "get_foo_settings"]


class FooSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MYAPP_FOO_",
        env_file=".env",  # only where the project keeps a dotenv file for development
        extra="ignore",
    )

    url: str
    api_key: SecretStr
    timeout_seconds: float


def get_foo_settings() -> FooSettings:
    return FooSettings()
```

Each `model_config` key is one rule: `env_prefix` is the component's namespace (rule 2), `env_file` reads
the local dotenv file where one exists and the real environment where it does not (rule 2), and
`extra="ignore"` keeps the namespace non-strict (rule 2). `url` and `api_key` are required and have no
default (rules 4 and 8); `timeout_seconds` is a tunable and has none either (rule 5). `SecretStr` is
this binding's secret type and `.get_secret_value()` its unwrap (rules 7 and 9); a derived value is a
`@property` on the class (rule 10), a validator a `@field_validator` (rule 12). Under a dependency-injection container the
container's provider method is the factory and `get_foo_settings` is not written.

## Other bindings

- **Another settings library** — `environ-config`, `dynaconf`, attrs with converters. The prefix becomes
  that library's own prefix argument, the secret its secret wrapper, the validator its converter or
  validator hook. Every rule below is unchanged.
- **The standard library alone.** A frozen dataclass with a `from_env(environ: Mapping[str, str])`
  classmethod that reads only its own prefixed keys, raises naming the variable when a required one is
  missing, and wraps each secret in a small class whose `__repr__` does not print it; the composition
  root passes `os.environ` in. What the library did for free — the missing-value error, coercion, the
  non-strict namespace — becomes a few lines written once. The rules are identical.

## Rules

1. **One settings class per configured component.** An external system, a store, and the process's own
   knobs are three components and three classes; one class holding several components' fields is
   forbidden. A component with nothing to configure has no class. It declares the fields its consumer
   reads and no others; a field copied from another component's class is dead configuration.
2. **Each class reads its own environment namespace, and the namespace is non-strict.** Every field is
   read under the component's own prefix — its name, and keeping it disjoint from every other prefix, are
   `naming`'s rule 7. A variable inside the namespace that the class does not declare never fails
   startup: the process environment is shared with the deployment and with every other settings class,
   so strictness turns an unrelated variable into an outage. Where the project keeps a local dotenv file
   for development, the class reads it when it is present and the real environment when it is not, so
   one class serves both without a branch. A program run from arbitrary directories — a CLI tool —
   reads no dotenv file, because whichever one sits in the working directory is not its own.
3. **Only a settings class reads the environment.** No other module reads an environment variable; code
   that needs a configured value is handed it.
4. **A required field has no default.** A missing value fails loudly the first time the settings object
   is built, at startup, before any work is done.
5. **A tunable with no single right value carries no default.** A timeout, a pool size, a batch size is
   set from what the deployment observes and can afford; a default is one deployment's tuning frozen into
   a template, and it converts a missing variable into a silent wrong answer instead of a startup failure.
   In a program its users run rather than a deployment configures — a CLI tool — a tunable may carry
   the documented default the tool ships with; a value the user picks per run is an argument (rule 15).
6. **An optional field's default is safe for production.** A value that is genuinely optional and absent
   is `None`, never a placeholder string, and the default of a switch is the side that fails safe.
7. **A value that must not appear in a log, a repr or a traceback carries a type that keeps it out of
   them** — passwords, API keys, signing secrets, connection strings with a password in them. A bare
   string is printed by every default repr in the program, so the type is what makes disclosure
   impossible rather than merely discouraged.
8. **Never default a secret the component requires.** A missing secret crashes the process at startup. A
   credential that is genuinely optional — a store that may run unauthenticated — is `None` when absent.
9. **A secret is unwrapped only at the point of use** — inside the derived value that assembles a
   connection string, or where the client that sends it is constructed, which then holds it privately.
   Never into a log field, an exception's context, or an intermediate string built for anything else.
10. **A value assembled from other fields is computed on the settings object, never reassembled by its
    consumers** — a connection string, a composite URL, a normalized form. One place decides how the
    parts go together, so changing the recipe is one edit rather than a search.
11. **Two components do not share fields by importing one settings class from another.** Each is
    self-contained; copy the field if both genuinely need it.
12. **Field validation only normalizes or rejects.** Normalization accepts an environment-friendly form
    and stores the canonical one (an escaped newline in a multi-line key); rejection refuses a value that
    would cause silent misbehaviour (an algorithm outside an allowlist). Nothing else — no IO, no
    lookups. The message names the variable, because it is read at startup.
13. **Settings are built at the program's composition root and passed down as values.** The composition
    root is the one place a program assembles its objects: a service's container or process
    definition, a CLI command's entry function, a migration environment, the test infrastructure. It
    calls each settings factory once and hands the object, or the values it holds, to what it
    constructs. Never at import time (`python-packaging` rule 8), and never below the root — owning a
    settings class is not permission for a component to build it, and a client, repository or unit of
    work that builds its own settings cannot be given different ones.
14. **A published library reads no environment.** Its importer is the program with a composition root,
    so the library's constructors and functions take plain values and the importer's own settings supply
    them. A library shared inside one repository may declare a settings class under its own stem
    (`naming`); the importing program's root builds it, like any other.
15. **A value chosen per invocation is an argument, not a setting.** Settings hold what a deployment or a
    machine decides; what a caller picks each time it runs a command or calls a function is a
    command-line argument or a parameter.

## Inlined typing / import rules

- Fields are real types, and the settings library coerces the string: `port: int`, `enabled: bool`,
  `timeout_seconds: float` — never a `str` parsed later. Optional is `T | None = None`, never `T = ""`
  (`python-style`).
- Import a validator decorator only when the class defines one — an unused import is a lint failure.
- A type checker in strict mode needs the settings library's plugin, where it ships one, to accept a
  no-argument construction; `python-toolchain` configures it.
- No `from __future__ import annotations` (`python-style`).

## Package wiring

The settings module re-exports its class and factory like any other module (`python-packaging`).

## Hard stops

- `os.environ`, `os.getenv` or a dotenv read outside a settings class → stop, add a field to the
  component's settings class and hand the value in (rule 3).
- A default on a required field or a required secret → stop, remove it; the default is what lets a
  broken deployment start (rules 4 and 8).
- A default on a timeout, a pool size or a batch size in a deployable → stop, make it required (rule 5).
- A placeholder string standing for "not set" → stop, the field is `T | None = None` (rule 6).
- A password, key or token typed as a plain string → stop, give it the secret type (rule 7).
- A secret unwrapped into a log call, an exception's context, or a string built for anything but its
  use → stop, unwrap it only where it is used (rule 9).
- A consumer reassembling a connection string or URL from settings fields → stop, derive it once on the
  settings class (rule 10).
- One class holding two components' fields, or one class importing another to reuse its fields → stop,
  one class per component, fields copied (rules 1 and 11).
- A settings class made strict about undeclared variables in its namespace → stop, an unrelated
  variable then takes the process down (rule 2).
- A validator doing IO, a lookup, or anything but normalizing or rejecting → stop, move that work to the
  code that uses the value (rule 12).
- A settings object built at module level → stop, `python-packaging` rule 8; built inside a client, a
  repository, a handler or a run function → stop, the composition root builds it and passes it down
  (rule 13).
- A published library reading an environment variable → stop, take the value as a parameter (rule 14).
- A value the caller picks per run or per call read from the environment → stop, make it an argument
  or a parameter (rule 15).
- Choosing or checking an environment prefix → stop, use `naming`.
