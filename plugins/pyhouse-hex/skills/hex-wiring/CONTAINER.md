# hex-wiring — the composition root

Topic file of `hex-wiring`. The mechanism-free obligations are `## Rules` in `SKILL.md`; what follows
is the **dishka** binding that satisfies them.

This is the **base** every project extends: the provider classes and the handlers. It binds no
optional adapter and no feature, and resolves once the subdomain's repository port is bound by its
store's add-on. Each of those — a relational store, an HTTP gateway, a key-value
store, a token verifier, a tunable value object, a unit of work — ships its own binding beside what it
binds, in the skill that owns it: the relational engine, session factory and `Foo` repository in
`hex-persistence`, the HTTP gateway in `hex-capability-adapter`, the Redis repository in `hex-store-repository`, the token verifier in
`hex-restapi-auth`, the tunable in `hex-domain-model`, the unit-of-work factory in `hex-persistence`. A
project merges the ones it has into the providers below, each line into the provider class of the same
name, in declaration order; a provider class a binding adds (a second subdomain's) joins the
`create_container` list.

`SettingsProvider` holds every settings binding, at process lifetime, and everything else may depend on them.
`InfrastructureProvider` holds the long-lived handles, each released after its yield, and the
cross-cutting adapters, which the binding beside each adapter adds. There is one per-operation provider
class per subdomain — `FoosProvider` here — declaring the repository, then the services that use it,
then the handlers that use them, one `provide` line per handler; `IFooRepository`'s line is merged in
from the skill of the store `Foo` lives in (`hex-persistence` for a relational store,
`hex-store-repository` for a key-value one). `provides=` is what binds an adapter to its port, and every
constructor argument is resolved from its annotation — except for an adapter with a client of its own,
whose factory builds the client, hands it in and binds the adapter by its return type
(`hex-capability-adapter`). The `overrides` of
`create_container` are the test seam and nothing else appends to them (`hex-test-integration-setup`).

```python
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide

from myapp.application.foos import CreateFooHandler

__all__ = ["create_container", "resolve_settings"]


class SettingsProvider(Provider):
    scope = Scope.APP


class InfrastructureProvider(Provider):
    scope = Scope.APP


class FoosProvider(Provider):
    scope = Scope.REQUEST

    create_foo_handler = provide(CreateFooHandler)


def create_container(*overrides: Provider) -> AsyncContainer:
    return make_async_container(
        SettingsProvider(),
        InfrastructureProvider(),
        FoosProvider(),
        *overrides,
    )


async def resolve_settings(container: AsyncContainer) -> None:
    for factory in SettingsProvider().factories:
        await container.get(factory.provides.type_hint)
```

`resolve_settings` is the startup check `SKILL.md` requires, and each entrypoint calls it once before
it serves or takes work; `create_container` never does. It resolves each type `SettingsProvider`
declares, read off the provider itself so there is no second list, and the process lifetime keeps what
it built for every later operation.

Every add-on binding has the same parts, each in the place the declaration order gives it: a settings
factory in `SettingsProvider`; in `InfrastructureProvider`, the client it needs — built by a factory that
releases it after its yield when it holds connections — and a capability adapter bound to its port, by
that same factory where the client is the adapter's own; and
a repository bound to its port in its subdomain's per-operation provider. One adapter satisfying two
ports is bound once, to both (`AnyOf`), so the two ports share the one instance. An aggregate has one
authoritative store (`hex-store-repository` rule 1), so no add-on binds a second repository for `Foo`;
the key-value one binds `Baz`'s.

Add `FastapiProvider()` to that list **only** when a factory takes `fastapi.Request` or
`fastapi.WebSocket` as a parameter; the default composition root above takes neither and stays free of
transport imports.
