# hex-restapi-auth — applying auth to a route

Topic file of `hex-restapi-auth`. `SKILL.md` builds the auth layer — the identity, the port, the
verifier adapter, the two dependencies, the error branch and the wiring — once per project. This file
is the half consulted **every time a route is written**: which dependency the operation takes, how the
identity is bound, and which codes the route must then advertise. The obligations are rules 1–13 in
`SKILL.md`; this is the FastAPI binding of the ones about route shape and advertisement.


### Decision rule

| Operation | Dependency on the route | Binding name |
|---|---|---|
| Read by any authenticated caller, handler does not need `caller_id` | `Depends(get_current_user)` | `_: CurrentUser` |
| Read where the handler needs `caller_id` (an auth-scoped list) | `Depends(get_current_user)` | `user: CurrentUser` |
| Mutation requiring role rank ≥ `<Role>` | `Depends(require_role(Role.<MIN_RANK>))` | `user: CurrentUser` |
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

**All auth-derived fields come from `CurrentUser`, never from the request.** In a multi-tenant app the
token also carries the tenant: stamp it from the bound user (`tenant_id=user.tenant_id`), exactly
like `caller_id=user.id`, and bind `user` rather than `_`. A tenant id must never be read from the path,
query or body — that would let a client choose another tenant's scope. The DTO carries the field
(`hex-application`); the route stamps it.

```python
# read — no caller_id needed
async def list_foos(
    handler: FromDishka[ListFoosHandler],
    limit: Annotated[int, Query(ge=1, le=_MAX_PAGE_SIZE)] = _DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
    _: CurrentUser = Depends(get_current_user),
) -> FooListResponse: ...

# mutation — caller_id flows into the command
async def create_foo(
    body: FooCreateRequest,
    handler: FromDishka[CreateFooHandler],
    get_handler: FromDishka[GetFooHandler],
    user: CurrentUser = Depends(require_role(Role.<MIN_RANK>)),
) -> FooResponse:
    new_id = await handler.execute(
        CreateFooCommand(caller_id=user.id, name=body.name, bar_id=body.bar_id)
    )
    ...
```

Both are `hex-restapi-endpoint`'s templates with the auth parameter added last: the handlers arrive as
`FromDishka[...]` parameters through the router's route class, and `_MAX_PAGE_SIZE` /
`_DEFAULT_PAGE_SIZE` are that router's own module constants — the bounds are the app's decision, not
auth's.

### Deriving the authenticated form of a route

`hex-restapi-endpoint`'s primary templates are auth-free. An authenticated route adds exactly four
things to one of them, and nothing else:

1. the auth-dependency parameter, **last** in the signature;
2. the `from myapp.domain.auth import CurrentUser, Role` and `from ..dependencies import
   get_current_user, require_role` imports in the router file, and `Depends` on its `fastapi` import —
   conditional imports, present only when the app declares auth **and** this resource has ≥ 1
   authenticated route;
3. the `401` (and `403` when role-gated) codes in `error_responses(...)`;
4. the `caller_id=user.id` argument to the command or query, where the DTO carries it
   (`hex-application` — the actor field is itself conditional).

A public route inside an app that *does* have auth drops the same four. The auth dependency is never a
frozen role; it is the slot this skill fills.

### Coordinated advertisement — the join between the dependency and the codes

The advertised codes **follow from the chosen dependency**. Getting them out of step is the failure this
half exists to prevent — the app-wide invariant that compares the decorator against the OpenAPI spec
fails on exactly that mismatch.

- `Depends(get_current_user)` → the set includes `401`.
- `Depends(require_role(...))` → the set includes `401` **and** `403`.
- No auth dependency → the set includes neither.

`hex-restapi-endpoint` owns the per-operation code sets for a route with no auth dependency, and the
rule that the input-validation status is advertised on every route carrying any validated input — both
in its sibling `CONTRACTS.md`. **Read the base set for the operation there, then add the auth codes
above and nothing else**: `401` where the dependency only authenticates, `401` **and** `403` where it
gates on rank. The base set is not restated here, so there is no second copy of it to drift.

Which of the two a given operation gets follows from the decision rule at the top of this file, not from
the operation's shape: a read that any authenticated caller may make takes `get_current_user` and so
adds `401` alone; a mutation gated on a role rank takes `require_role(...)` and so adds `401` and `403`.

`401` and `403` are auth codes, not universal. A **public** route, or any route in an app with no auth,
**drops both**. This is load-bearing rather than cosmetic: `error_responses(...)` validates against the
known set, and an auth-less app has no `UnauthorizedError` class, so a stray `401` raises `ValueError`.
