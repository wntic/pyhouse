# hex-wiring — the composition root

Topic file of `hex-wiring`. The mechanism-free obligations are `## Rules` in `SKILL.md`; what follows
is the **dishka** binding that satisfies them.

This is the **base** every project extends: the provider classes and the handlers. It binds no store,
no optional adapter and no feature. Each of those — a relational store, a blob store, an HTTP gateway, a
canonicalizer, a key-value store, a token verifier, a tunable value object, a unit of work — ships its
own binding beside what it binds, in the skill that owns it: the relational engine, session factory and
`Foo` repository in `hex-persistence`, the S3 storage, the HTTP gateway and the idna canonicalizer in
`hex-capability-adapter`, the Redis repository in `hex-store-repository`, the token verifier in
`hex-restapi-auth`, the tunable in `hex-domain-model`, the unit-of-work factory in `hex-patterns`. A
project merges the ones it has into the providers below, each line into the provider class of the same
name, in declaration order; a provider class a binding adds (a second subdomain's) joins the
`create_container` list.

```python
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide

from myapp.application.foos import (
    CreateFooHandler,
    DeleteFooHandler,
    GetFooHandler,
    ListFoosHandler,
    UpdateFooHandler,
)
from myapp.domain.foos import FooUniquenessService

__all__ = ["create_container"]


class SettingsProvider(Provider):
    """Settings — process lifetime; everything else may depend on them."""

    scope = Scope.APP


class InfrastructureProvider(Provider):
    """Long-lived handles, each released after its yield, and cross-cutting adapters,
    which the binding beside each adapter adds here."""

    scope = Scope.APP


class FoosProvider(Provider):
    """One provider class per subdomain: repository, then the services that use it,
    then the handlers that use them. `provides=` is what binds the adapter to the port;
    every constructor argument is resolved from its annotation, so nothing is passed here.
    """

    scope = Scope.REQUEST

    # IFooRepository's binding is merged in from the skill of the store Foo lives in —
    # hex-persistence for a relational store, hex-store-repository for a key-value one.
    foo_uniqueness_service = provide(FooUniquenessService)

    create_foo_handler = provide(CreateFooHandler)
    get_foo_handler = provide(GetFooHandler)
    list_foos_handler = provide(ListFoosHandler)
    update_foo_handler = provide(UpdateFooHandler)
    delete_foo_handler = provide(DeleteFooHandler)


def create_container(*overrides: Provider) -> AsyncContainer:
    """The composition root. `overrides` is the test seam and nothing else appends to it
    (`hex-test-integration-setup`)."""
    return make_async_container(
        SettingsProvider(),
        InfrastructureProvider(),
        FoosProvider(),
        *overrides,
    )
```

Every add-on binding has the same parts, each in the place the declaration order gives it: a settings
factory in `SettingsProvider`; in `InfrastructureProvider`, the client it needs — built by a factory that
releases it after its yield when it holds connections — and a capability adapter bound to its port; and
a repository bound to its port in its subdomain's per-operation provider. One adapter satisfying two
ports is bound once, to both (`AnyOf`), so the two ports share the one instance — the S3 binding is the
worked case. An aggregate has one authoritative store (`hex-store-repository` rule 1), so no add-on binds
a second repository for `Foo`; the key-value one binds `Baz`'s.

Add `FastapiProvider()` to that list **only** when a factory takes `fastapi.Request` or
`fastapi.WebSocket` as a parameter; the default composition root above takes neither and stays free of
transport imports.
