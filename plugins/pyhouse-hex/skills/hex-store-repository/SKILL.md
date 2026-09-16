---
name: hex-store-repository
description: Use when an aggregate is persisted on a nonrelational store — key-value, document, search-index or vector (redis, mongo, qdrant, elasticsearch) — reached through an injected SDK client. Produces the repository adapter, its container token and namespace keys from settings, record mapping, and SDK-error translation. Not a relational `Table` and its migration (`hex-persistence`), and not a single-action `ICan<Verb>` port (`hex-capability-adapter`).
paths: ["**/infrastructure/**"]
---

# Hex — Store Repository

Produces one repository class that adapts a domain repository protocol to a client-style datastore — any store reached through an injected SDK client rather than the shared relational bootstrap. That sentence is the whole selection rule: **the store profile, not the vendor, decides that this skill applies.** The adapter does not inherit from the protocol — structural subtyping at the DI injection site is the contract.

**A new vendor is a store-profile row plus its package — never a fork of this skill** (Rule 12). The pattern is fixed here (client injection, container token from settings, record↔entity mapping, boundary translation via `exception-catalog`); the vendor rides in through three things and nothing else: the injected client type, the store's settings class, and the SDK semantics the spec's notes name. Key-value, document, wide-column, search-index and vector stores are all one profile under that rule, which is why one skill serves them.

## When to use vs. neighbours

- The aggregate's store is the relational bootstrap store (SQLAlchemy/Postgres) → `hex-persistence`.
- The protocol file (`i_foo_repository.py`) → `hex-domain-ports`.
- A single-action `ICan<Verb>` port (not an aggregate's collection) → `hex-capability-adapter`.
- The settings class the store's connection factory consumes → `hex-wiring`.
- The DI provider that constructs this repository → `hex-wiring`.
- Which store profile a datastore is, and the client factory that profile names → `hex-conventions`.
- The catalogue exception an SDK error is translated into → `exception-catalog`.
- An in-memory test stand-in for handler unit tests → `hex-test-application-handler`.
- The integration contract test that drives this adapter against the real store →
  `hex-test-repository-contract`.

## Template(s) — two store profiles, each naming its stack

### Key-value / document form — worked binding: `redis`

One vendor is worked end to end so the shape is concrete; a document store (mongo, dynamo, a
key-value cache) differs only in the SDK's call names and its exception root.

```python
import json
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

from myapp.domain.exceptions import NotFoundError, UpstreamError
# The adapter uses structural subtyping at the DI site (Rule 2); imports follow
# python-packaging.
from myapp.domain.foos import Foo

from ..settings import FoosStoreSettings

__all__ = ["FooRepository"]


class FooRepository:
    def __init__(self, client: Redis, settings: FoosStoreSettings) -> None:
        self._client = client
        self._prefix = settings.key_prefix   # the store's container token (Rule 5)

    def _key(self, foo_id: UUID) -> str:
        return f"{self._prefix}:{foo_id}"

    def _record_to_entity(self, record: dict[str, object]) -> Foo:
        return Foo(id=UUID(str(record["id"])), name=str(record["name"]))

    async def add(self, foo: Foo) -> None:
        record = {"id": str(foo.id), "name": foo.name}
        try:
            await self._client.set(self._key(foo.id), json.dumps(record))
        except RedisError as exc:
            raise UpstreamError(
                "store write failed",
                {"key": self._key(foo.id), "reason": exc.__class__.__name__},
            ) from exc

    async def get_by_id(self, foo_id: UUID) -> Foo:
        try:
            raw = await self._client.get(self._key(foo_id))
        except RedisError as exc:
            raise UpstreamError(
                "store read failed",
                {"key": self._key(foo_id), "reason": exc.__class__.__name__},
            ) from exc
        if raw is None:
            raise NotFoundError("Foo not found", {"id": str(foo_id)})
        return self._record_to_entity(json.loads(raw))

    async def delete(self, foo_id: UUID) -> None:
        try:
            removed = await self._client.delete(self._key(foo_id))
        except RedisError as exc:
            raise UpstreamError(
                "store delete failed",
                {"key": self._key(foo_id), "reason": exc.__class__.__name__},
            ) from exc
        if removed == 0:
            raise NotFoundError("Foo not found", {"id": str(foo_id)})
```

### Collection-shaped form — placeholder client, worked on a scored-search store

The second form is deliberately **not** a second vendor. `store_sdk` below stands for whatever client
library this datastore's store profile names (`hex-conventions` block B) — a vector store such as
qdrant, weaviate or pinecone, a search index such as elasticsearch or opensearch, a document store's
collection API. Substituting the real SDK's type names is the whole of the port; everything else on the
page holds unchanged.

```python
from uuid import UUID

from store_sdk import AsyncStoreClient
from store_sdk.models import (
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    Record,
    ScoredRecord,
)

from myapp.domain.exceptions import UpstreamError
from myapp.domain.foos import Foo

from ..settings import FoosVectorSettings

__all__ = ["FooRepository"]


class FooRepository:
    def __init__(self, client: AsyncStoreClient, settings: FoosVectorSettings) -> None:
        self._client = client
        self._collection = settings.collection

    async def add_many(self, foos: tuple[Foo, ...]) -> None:
        points = [
            Record(
                id=str(foo.id),
                vector=foo.vector,
                payload={"bar_id": str(foo.bar_id), "text": foo.text},
            )
            for foo in foos
        ]
        try:
            await self._client.upsert(collection_name=self._collection, points=points)
        # Many store SDKs expose no single exception root; boundary translation
        # follows exception-catalog (Rule 9).
        except Exception as exc:
            raise UpstreamError(
                "vector upsert failed",
                {"collection": self._collection, "reason": exc.__class__.__name__},
            ) from exc

    async def search(
        self, query_vector: list[float], k: int
    ) -> tuple[tuple[Foo, float], ...]:
        try:
            response = await self._client.query_points(
                collection_name=self._collection,
                query=query_vector,
                limit=k,
                with_payload=True,
                with_vectors=True,  # each entity carries its OWN vector, never the query's
            )
        except Exception as exc:
            raise UpstreamError(
                "vector search failed",
                {"collection": self._collection, "reason": exc.__class__.__name__},
            ) from exc
        # The store computed a similarity score per hit — return it alongside the entity
        # (the protocol's pair shape exists precisely so the score is not discarded).
        return tuple(
            (self._point_to_entity(point), point.score) for point in response.points
        )

    async def delete_by_bar(self, bar_id: UUID) -> None:
        selector = FilterSelector(
            filter=Filter(
                must=[FieldCondition(key="bar_id", match=MatchValue(value=str(bar_id)))]
            )
        )
        try:
            await self._client.delete(
                collection_name=self._collection, points_selector=selector
            )
        except Exception as exc:
            raise UpstreamError(
                "vector delete failed",
                {
                    "collection": self._collection,
                    "bar_id": str(bar_id),
                    "reason": exc.__class__.__name__,
                },
            ) from exc

    def _point_to_entity(self, point: ScoredRecord) -> Foo:
        payload = point.payload or {}
        vector = point.vector if isinstance(point.vector, list) else []
        return Foo(
            id=UUID(str(point.id)),
            bar_id=UUID(str(payload["bar_id"])),
            text=str(payload["text"]),
            vector=[float(v) for v in vector],
        )
```

## Other bindings

One form is worked per profile above; every other store is the same two files with different SDK names.
What changes, and what does not:

- **Document / wide-column stores** (mongo, dynamo, cassandra) — the key-value form, with the container
  token being a collection or table name instead of a key prefix, and the record a native document
  rather than a JSON string. Mapping helpers, translation and thinness are unchanged.
- **Search indices** (elasticsearch, opensearch) — the collection-shaped form. The scored-pair return
  shape in Rule 3 is the same one; only the query DSL differs.
- **Vector stores** (qdrant, weaviate, pinecone, milvus) — the collection-shaped form as written; the
  vector is a stored field of the entity, which is what Rule 8 is about.
- **Object stores** (`s3`, gcs, azure blob) — a bucket is a container token like any other, but a blob
  is usually a single-action capability rather than an aggregate's collection, so check
  `hex-capability-adapter` first.
- **`pgvector` and other relational extensions** — relational, not this profile: the store is reached
  through the shared engine, so it is `hex-persistence` even though the workload is vector search.

Each of these is one store-profile row and one `infrastructure/<kind>/` package. None of them is a
second copy of this skill.

## Rules

### File layout

```
src/myapp/infrastructure/<store-kind>/   # the profile's kind token — infra groups by tech
├── __init__.py
├── connection.py          # create_<store>_client(settings) — the datastore's factory, not this skill
├── settings.py            # hex-wiring
└── repositories/
    ├── __init__.py        # package wiring — python-packaging
    └── foo_repository.py  # this skill writes this file
```

### Form

1. **Names and module structure** follow `naming` and `python-packaging`; technology placement follows `hex-architecture` and `hex-conventions`. An aggregate has exactly one **authoritative** store — the one its writes go to — unlike a capability port that several vendors may implement. A second store may hold a derived projection of the same aggregate (a vector index over `Foo`, say), which is why the repository file stem is protocol-derived for client stores; see `hex-conventions`. Two stores both accepting writes for one aggregate is the thing this forbids.
2. **No explicit `(IFooRepository)` inheritance.** Structural subtyping.
3. **Method signatures match the protocol exactly**, including async mode, keyword-only markers, and compound return shapes (a `tuple[tuple[Foo, float], ...]` of scored hits is returned as pairs — never flattened to bare entities with the score discarded).

### Client & settings

4. **Inject the SDK client and the settings class.** Both come from `containers.py`; the client is built once by the datastore's `create_<store>_client(settings)` factory and bound at process lifetime (`hex-wiring`). Never construct a client inline in a method, and never swap the injected client type for a different flavor of the SDK.
5. **Stash only what the methods need** — typically the store's *container token* (collection / key-prefix / index / bucket name) read from settings in `__init__`.

### Records ↔ entities

6. **Private, pure mapping helpers** (`_record_to_entity` / `_point_to_entity` / `_entity_to_record`): no IO; logging follows `python-style`. IDs serialize as strings unless the SDK is UUID-native. **Annotate the SDK's own record type on the parameter and narrow with `isinstance` or `typing.cast`** — never `object` plus a row of `# type: ignore[attr-defined]`. An inline ignore in an adapter body is a hard stop in `hex-project-setup` and is "never sanctioned" in `hex-capability-adapter`; an adapter is the one place the vendor type is allowed, so there is nothing to silence.
7. **The record shape is a design decision, not a transcription.** What becomes the key, what goes into the payload, what the store indexes — the client-store analogue of "column types are judgment" in `hex-persistence`. The spec's notes guide it.
8. **An entity is reconstructed from its own stored data.** Never substitute query-side values for stored ones (e.g. a search result's vector is the point's own, not the query's); when the read path doesn't consume a stored field, omit it explicitly rather than faking it.

### Exception translation

9. **Boundary exception translation**, including SDKs without a single exception root, follows `exception-catalog`.
10. **Error selection** follows `exception-catalog`. An absent record on `get_by_id` is **not** an SDK error — detect it (a `None`, an empty result, a zero count) and fail.
11. **Exception context** follows `exception-catalog`; the templates show the store-specific inputs.

### Vendor & semantics

12. **Vendor semantics come from the SDK, not from this skill.** Query API, filter DSL, batching, consistency options — read them from the SDK's own documentation. A **new vendor is a store-profile row plus its package — never a fork of this skill** (the same way `hex-capability-adapter` serves boto3, httpx, PyJWT, and openai with one skill).
13. **No provisioning.** The repository never creates collections, indexes, buckets, or schemas — provisioning is a deployment/bootstrap concern.
14. **Ordering is explicit.** A `list`/`search` that promises an order must produce it deliberately (the store's score order, an explicit sort key) — never rely on insertion accident.
15. **No retries, no caching, no domain reasoning.** Same thinness contract as every adapter (see `hex-capability-adapter`'s adapters-are-thin rules). Logging follows `python-style`.

### Testing neighbours

- An in-memory test stand-in for handler unit tests → `hex-test-application-handler`.
- The integration contract test that drives this adapter against the real store → `hex-test-repository-contract`.

## Inlined typing / import rules

- Domain imports absolute (`from myapp.domain.foos import Foo`); the sibling settings module relative (`from ..settings import FoosStoreSettings`). **Never import the protocol the adapter satisfies** — structural subtyping needs no import (Rule 2); importing it is a dead F401.
- SDK types stay inside the adapter; method signatures use domain types or primitives only.
- Raw SDK payloads may be `dict[str, Any]` / `object` at the immediate boundary — convert to the domain type in the mapping helper, never return them.
- No `from __future__ import annotations`. Full annotations on every method.

## Package wiring

For `repositories/__init__.py`, follow `python-packaging`; package placement follows `hex-architecture`.

## Hard stops

- The aggregate's store is the relational bootstrap store — reached through a shared engine rather than an injected client → stop, use `hex-persistence`.
- Spec asks for SQL, SQLAlchemy, or a `Table` for this aggregate → stop, use `hex-persistence`.
- Spec asks the repository to create or migrate the collection/index/bucket → stop, provisioning is not the repository's concern.
- Spec asks for atomicity across this store and another (two stores in one transaction) → stop, use `hex-patterns` for handler compensation; there is no cross-store transaction.
- Spec asks the repository to log → stop, use `python-style`.
- The port is a single-action capability (`ICan<Verb>`), not an aggregate's collection → stop, use `hex-capability-adapter`.
