# hex-restapi-auth — applying auth to a route

Topic file of `hex-restapi-auth`. `SKILL.md` builds the auth layer — the identity, the port, the
verifier adapter, the two dependencies, the error branch and the wiring — once per project. This file
is the half consulted **every time a route is written**: which dependency the operation takes, how the
identity is bound, and which codes the route must then advertise. The obligations are rules 1–12 in
`SKILL.md`; this is the FastAPI binding of the ones about route shape and advertisement.


### Decision rule

| Operation | Dependency on the route | Binding name |
|---|---|---|
| Any authenticated caller may perform it; the handler does not need `caller_id` | `Depends(get_current_user)` | `_: CurrentUser` |
| Any authenticated caller; the handler needs `caller_id` (an actor stamped, an auth-scoped list) | `Depends(get_current_user)` | `user: CurrentUser` |
| Requires role rank ≥ `<Role>` — only in an app whose identity carries a role | `Depends(require_role(Role.<MIN_RANK>))` | `user: CurrentUser` |
| Public route (health, info), **or any route in an app with no auth** | none | n/a |

**Pick the lowest privilege the operation actually requires.** If a list endpoint shows different rows
depending on role, filter the rows in the handler using `caller_id`; do not promote the dependency to a
higher role.

### `_` vs `user` — the binding name is significant

- **`_: CurrentUser = Depends(get_current_user)`** when the value is unused. The underscore makes the
  intent explicit.
- **`user: CurrentUser = Depends(...)`** when the value flows into a command or query as
  `caller_id=user.id`.

Do not bind to `user` and leave it unused — a reviewer reads that as "did the author forget to pass
`caller_id`?".

**All auth-derived fields come from `CurrentUser`, never from the request** — the actor, and a tenant
where the identity carries one, so a route stamping either binds `user`. Which fields a DTO carries and
how the handler scopes by them are `hex-application`'s.

```python
async def list_foos(
    handler: FromDishka[ListFoosHandler],
    limit: Annotated[int, Query(ge=1, le=_MAX_PAGE_SIZE)] = FooListFilter.limit,
    offset: Annotated[int, Query(ge=0)] = 0,
    _: CurrentUser = Depends(get_current_user),
) -> FooListResponse: ...

async def create_foo(
    body: FooCreateRequest,
    handler: FromDishka[CreateFooHandler],
    get_handler: FromDishka[GetFooHandler],
    user: CurrentUser = Depends(get_current_user),
) -> FooResponse:
    new_id = await handler.execute(
        CreateFooCommand(caller_id=user.id, name=body.name, note=body.note)
    )
    ...
```

Both are `hex-restapi-endpoint`'s templates with the auth parameter added last: the read binds `_`,
since it needs no `caller_id`, and the mutation binds `user`, whose id flows into the command.

### Deriving the authenticated form of a route

`hex-restapi-endpoint`'s primary templates are auth-free. An authenticated route adds exactly four
things to one of them, and nothing else:

1. the auth-dependency parameter, **last** in the signature;
2. the `from myapp.domain.auth import CurrentUser` and `from ..dependencies import get_current_user`
   imports in the router file (plus `Role` and `require_role` on a rank-gated route), and `Depends` on its `fastapi` import —
   conditional imports, present only when the app declares auth **and** this resource has ≥ 1
   authenticated route;
3. the `401` (and `403` when role-gated) codes in `error_responses(...)`;
4. the `caller_id=user.id` argument to the command or query, where the DTO carries it
   (`hex-application`).

A public route inside an app that *does* have auth drops the same four. The auth dependency is never a
frozen role; it is the slot this skill fills.

### Coordinated advertisement — the join between the dependency and the codes

The advertised codes **follow from the chosen dependency**. Getting them out of step is the failure this
half exists to prevent, and no test catches it: the decorator and the published document omit a `401`
together.

- `Depends(get_current_user)` → the set includes `401`.
- `Depends(require_role(...))` → the set includes `401` **and** `403`.
- No auth dependency → the set includes neither.

**Read the base set for the operation in `hex-restapi-endpoint`'s `CONTRACTS.md`, then add the auth
codes above and nothing else.** Which dependency an operation takes follows from the decision rule at
the top of this file, not from its shape. In an app with no auth, `STATUS_BY_ERROR` maps nothing to
`401`, so a stray one raises `ValueError` at import.
