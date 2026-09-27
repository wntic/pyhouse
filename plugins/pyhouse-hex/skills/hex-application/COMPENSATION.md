# hex-application — compensation

Topic file of `hex-application`, read only when a command makes an externally visible write before a
store write that can still fail. The obligations are Compensation, under Rules in `SKILL.md`; what
follows is the create handler's body with that form, in the same stdlib-dataclasses and structlog
binding as the other templates.

## Template — create, compensating an external write

The one `CreateFooCommand` gains the uploaded bytes (`data: bytes`, after `name`) — its file changes;
there is never a second `CreateFooCommand` beside it.

```python
import uuid

import structlog

from myapp.domain.foos import Foo, ICanStoreFoos, IFooRepository

from .create_foo_command import CreateFooCommand

__all__ = ["CreateFooHandler"]

logger = structlog.get_logger()


class CreateFooHandler:
    def __init__(self, repo: IFooRepository, storage: ICanStoreFoos) -> None:
        self._repo = repo
        self._storage = storage

    async def execute(self, cmd: CreateFooCommand) -> uuid.UUID:
        foo = Foo(id=uuid.uuid4(), name=cmd.name, note=cmd.note)
        storage_key = f"foos/{foo.id}"

        await self._storage.upload(storage_key, cmd.data)
        try:
            await self._repo.create(foo)
        except Exception:
            try:
                await self._storage.delete(storage_key)
            except Exception as undo_exc:
                logger.warning("foo_upload_undo_failed", storage_key=storage_key, exc_info=undo_exc)
            raise

        logger.info("foo_created", foo_id=str(foo.id))
        return foo.id
```

The storage key is derived from the entity's id, so the entity carries no field for it. Where the
fallible step is a unit of work (`hex-persistence`'s `UNIT_OF_WORK.md`), its `async with` goes inside
this `try`.
