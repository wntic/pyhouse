---
name: hex-store-repository
description: Use when an aggregate is persisted on a nonrelational store — key-value, document or wide-column (redis, mongo, dynamo) — reached through an injected SDK client, or a derived index is kept beside the authoritative store. Produces the repository adapter satisfying the narrower port such a store answers, the store's settings class, its container token and namespace keys, record mapping, and SDK-error translation. Not a relational `Table` and its migration (`hex-persistence`), and not a single-action `ICan<Verb>` port (`hex-capability-adapter`).
paths: ["**/infrastructure/**"]
---

# Hex — Store Repository

Produces one repository class that adapts a domain repository protocol to a client-style datastore — any store reached through an injected SDK client rather than the shared relational bootstrap. That sentence is the whole selection rule: **the store profile, not the vendor, decides that this skill applies.** The adapter does not inherit from the protocol — structural subtyping at the DI injection site is the contract.

**A new vendor is a store-profile row plus its package — never a fork of this skill** (Rule 12). The pattern is fixed here (client injection, container token from settings, record↔entity mapping, boundary translation via `exception-catalog`); the vendor rides in through three things and nothing else: the injected client type, the store's settings class, and the SDK semantics that store documents. Key-value, document and wide-column stores are all one profile under that rule, and so is an index kept beside the authoritative store, which is why one skill serves them.

## When to use vs. neighbours

- The aggregate's store is the relational bootstrap store (SQLAlchemy/Postgres) → `hex-persistence`.
- The protocol file (`i_foo_repository.py`) → `hex-domain-ports`.
- A single-action `ICan<Verb>` port (not an aggregate's collection) → `hex-capability-adapter`.
- The obligations a settings class meets (env namespace, secrets, construction only at a composition root) → `hex-wiring`; the store's own settings class is shown here, beside the adapter that reads it.
- The DI provider that constructs this repository → `hex-wiring`.
- Which store profile a datastore is, and the client factory that profile names → `hex-conventions`.
- The catalogue exception an SDK error is translated into → `exception-catalog`.
- An in-memory test stand-in for handler unit tests → `hex-test-application-handler`.
- The integration contract test that drives this adapter against the real store →
  `hex-test-repository-contract`.

## Template — redis-py, key-value form

One vendor is worked end to end so the shape is concrete; a document store (mongo, dynamo, a
key-value cache) differs only in the SDK's call names and its exception root. A key-value store answers
only reads by key, so this adapter satisfies `IFooArchive` — create, fetch by id, delete — rather than
the full `IFooRepository` (`hex-domain-ports`), and lives in `redis/repositories/foo_archive.py`
(`hex-conventions`' protocol-derived stem).

```python
import json
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

from myapp.domain.exceptions import NotFoundError, UpstreamError
from myapp.domain.foos import Foo

from ..settings import RedisSettings

__all__ = ["FooRepository"]


class FooRepository:
    def __init__(self, client: Redis, settings: RedisSettings) -> None:
        self._client = client
        self._prefix = settings.foos_key_prefix

    def _key(self, id: UUID) -> str:
        return f"{self._prefix}:{id}"

    def _record_to_entity(self, record: dict[str, str]) -> Foo:
        return Foo(id=UUID(record["id"]), name=record["name"], bar_id=UUID(record["bar_id"]))

    async def create(self, foo: Foo) -> None:
        record = {"id": str(foo.id), "name": foo.name, "bar_id": str(foo.bar_id)}
        try:
            await self._client.set(self._key(foo.id), json.dumps(record))
        except RedisError as exc:
            raise UpstreamError(
                "store write failed",
                {"key": self._key(foo.id), "reason": exc.__class__.__name__},
            ) from exc

    async def get_by_id(self, id: UUID) -> Foo:
        try:
            raw = await self._client.get(self._key(id))
        except RedisError as exc:
            raise UpstreamError(
                "store read failed",
                {"key": self._key(id), "reason": exc.__class__.__name__},
            ) from exc
        if raw is None:
            raise NotFoundError("Foo not found", {"id": str(id)})
        return self._record_to_entity(json.loads(raw))

    async def delete(self, id: UUID) -> None:
        try:
            removed = await self._client.delete(self._key(id))
        except RedisError as exc:
            raise UpstreamError(
                "store delete failed",
                {"key": self._key(id), "reason": exc.__class__.__name__},
            ) from exc
        if removed == 0:
            raise NotFoundError("Foo not found", {"id": str(id)})
```

The settings class the adapter and the store's connection factory (`hex-conventions` block B) read, in
`infrastructure/redis/settings.py`. It follows `hex-wiring`'s settings rules; the URL is a secret
because it carries the password, and the key prefix is the adapter's container token.

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["RedisSettings"]

class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MYAPP_REDIS_",
        env_file=".env",
        extra="ignore",
    )

    url: SecretStr
    foos_key_prefix: str
```

## Other bindings

The key-value form is the one worked binding; every other client-style store is the same two files with
different SDK names. What changes, and what does not:

- **Document / wide-column stores** (mongo, dynamo, cassandra) — the key-value form, with the container
  token being a collection or table name instead of a key prefix, and the record a native document
  rather than a JSON string. Mapping helpers, translation and thinness are unchanged.
- **A search index — vector or full-text** (a vector store, OpenSearch) — a derived projection of the aggregate,
  never its authoritative store (Rule 1), so it satisfies a narrower port of its own shaped by what the
  index answers (`hex-domain-ports`) — typically an upsert, a query returning scored pairs (Rule 3) and a
  delete by the field the projection is keyed on. Client injection, the container token from settings,
  the entity rebuilt from the stored payload (Rule 8), translation and ownership are unchanged. An index
  inside the relational database (`pgvector`) is reached through the shared engine, so it is
  `hex-persistence`.
- **Object stores** (`s3`, gcs, azure blob) — a bucket is a container token like any other, but a blob
  is usually a single-action capability rather than an aggregate's collection, so check
  `hex-capability-adapter` first.

Each of these is one store-profile row and one `infrastructure/<kind>/` package. None of them is a
second copy of this skill.

## Rules

### File layout

```
src/myapp/infrastructure/<store-kind>/   # the profile's kind token — infra groups by tech
├── __init__.py
├── connection.py          # create_<store>_client(settings) — the datastore's factory, not this skill
├── settings.py            # the store's settings class — shown in the template above
└── repositories/
    ├── __init__.py        # package wiring — python-packaging
    └── foo_archive.py     # this skill writes this file — the stem is the port's (`hex-conventions`)
```

### Form

1. **Names and module structure** follow `naming` and `python-packaging`; technology placement follows `hex-architecture` and `hex-conventions`. An aggregate has exactly one **authoritative** store — the one its writes go to — unlike a capability port that several vendors may implement. A second store may hold a derived projection of the same aggregate (an index over `Foo`, see `## Other bindings`), which is why the repository file stem is protocol-derived for client stores; see `hex-conventions`. Two stores both accepting writes for one aggregate is the thing this forbids.
2. **No explicit `(IFooRepository)` inheritance.** Structural subtyping.
3. **Method signatures match the protocol exactly**, including async mode, keyword-only markers, and compound return shapes (a `tuple[tuple[Foo, float], ...]` of scored pairs is returned as pairs — never flattened to bare entities with the second element discarded).

### Client & settings

4. **Inject the SDK client and the settings class.** Both come from `containers.py`; the client is built once by the datastore's `create_<store>_client(settings)` factory and bound at process lifetime (`hex-wiring`). Never construct a client inline in a method, and never swap the injected client type for a different flavor of the SDK.
5. **Stash only what the methods need** — typically the store's *container token* (collection / key-prefix / index / bucket name) read from settings in `__init__`.

### Records ↔ entities

6. **Private, pure mapping helpers** (`_record_to_entity` / `_entity_to_record`): no IO; logging follows `python-style`. IDs serialize as strings unless the SDK is UUID-native. **Annotate the SDK's own record type on the parameter and narrow with `isinstance` or `typing.cast`** — never `object` plus a row of `# type: ignore[attr-defined]`. An inline ignore in an adapter body is a hard stop in `hex-project-setup` and is "never sanctioned" in `hex-capability-adapter`; an adapter is the one place the vendor type is allowed, so there is nothing to silence.
7. **The record shape is a design decision, not a transcription.** What becomes the key, what goes into the payload, what the store indexes — the client-store analogue of "column types are judgment" in `hex-persistence`. The aggregate's access patterns and the store's semantics guide it.
8. **An entity is reconstructed from its own stored data.** Never substitute query-side values for stored ones (e.g. an entity rebuilt from a record is built from the record's fields, never patched with the key or the arguments the caller looked it up by); when the read path doesn't consume a stored field, omit it explicitly rather than faking it.

### Exception translation

9. **Boundary exception translation**, including SDKs without a single exception root, follows `exception-catalog`.
10. **Error selection** follows `exception-catalog`. An absent record on `get_by_id` is **not** an SDK error — detect it (a `None`, an empty result, a zero count) and fail.
11. **Exception context** follows `exception-catalog`; the templates show the store-specific inputs.

### Vendor & semantics

12. **Vendor semantics come from the SDK, not from this skill.** Query API, filter DSL, batching, consistency options — read them from the SDK's own documentation. A **new vendor is a store-profile row plus its package — never a fork of this skill** (the same way `hex-capability-adapter` binds aioboto3, httpx and idna in one skill).
13. **No provisioning.** The repository never creates collections, indexes, buckets, or schemas — provisioning is a deployment/bootstrap concern.
14. **Ordering is explicit.** A `list`, `scan` or query that promises an order must produce it deliberately (an explicit sort key, the store's documented result order) — never rely on insertion accident.
15. **No retries, no caching, no domain reasoning.** Same thinness contract as every adapter (see `hex-capability-adapter`'s adapters-are-thin rules). Logging follows `python-style`.

### Testing neighbours

- An in-memory test stand-in for handler unit tests → `hex-test-application-handler`.
- The integration contract test that drives this adapter against the real store → `hex-test-repository-contract`.

## Inlined typing / import rules

- Domain imports absolute (`from myapp.domain.foos import Foo`); the sibling settings module relative (`from ..settings import RedisSettings`). **Never import the protocol the adapter satisfies** — structural subtyping needs no import (Rule 2); importing it is a dead F401.
- SDK types stay inside the adapter; method signatures use domain types or primitives only.
- Raw SDK payloads may be `dict[str, Any]` / `object` at the immediate boundary — convert to the domain type in the mapping helper, never return them.
- No `from __future__ import annotations`. Full annotations on every method.

## Package wiring

For `repositories/__init__.py`, follow `python-packaging`; package placement follows `hex-architecture`.

## Hard stops

- The aggregate's store is the relational bootstrap store — reached through a shared engine rather than an injected client → stop, use `hex-persistence`.
- Asked for SQL, SQLAlchemy, or a `Table` for this aggregate → stop, use `hex-persistence`.
- The repository is asked to create or migrate the collection/index/bucket → stop, provisioning is not the repository's concern.
- Asked for atomicity across this store and another (two stores in one transaction) → stop, use `hex-patterns` for handler compensation; there is no cross-store transaction.
- The repository is asked to log → stop, use `python-style`.
- The port is a single-action capability (`ICan<Verb>`), not an aggregate's collection → stop, use `hex-capability-adapter`.
