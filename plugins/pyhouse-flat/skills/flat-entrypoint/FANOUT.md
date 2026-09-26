# flat-entrypoint — a fan-out over independent units

Topic file of `flat-entrypoint`. The obligations are rules 11 and 13 and their hard stops in `SKILL.md`;
what follows is the **asyncio** binding that satisfies them, for the worked example's run functions.
Testing it is `flat-test-run-function`.

## The run function — asyncio

`src/myapp/ingest/foo_refresh.py` — one upstream record per unit, a bounded number in flight:

```python
import asyncio
from collections.abc import Sequence
from datetime import UTC, datetime

import structlog

from myapp.exceptions import MyappError
from myapp.ingest.foo_ingest import to_foo
from myapp.postgres import FooRepository
from myapp.schemas import IngestResult
from myapp.services.foo_api import FooClient

__all__ = ["refresh_foos"]

logger = structlog.get_logger()


async def refresh_foos(
    client: FooClient, repository: FooRepository, foo_ids: Sequence[str], *, concurrency: int
) -> IngestResult:
    slots = asyncio.Semaphore(concurrency)
    failed: list[str] = []

    async def refresh_one(foo_id: str) -> int:
        async with slots:
            try:
                foo = to_foo(await client.fetch(foo_id), datetime.now(UTC))
                if foo is None:
                    return 0
                await repository.record_batch([foo])
                # a unit with a progress marker writes it here, after its own rows (rule 11)
            except Exception:
                logger.exception("foo_refresh_failed", foo_id=foo_id)
                failed.append(foo_id)
                return 0
            return 1

    kept = sum(await asyncio.gather(*(refresh_one(foo_id) for foo_id in foo_ids)))
    if failed:
        raise MyappError("some foos could not be refreshed", {"failed": sorted(failed)})
    return IngestResult(fetched=len(foo_ids), kept=kept)
```

**The unit's whole body — fetch, write, marker — sits inside its own `try`** (rule 13), so a failure
anywhere in one unit is recorded against that unit and never reaches the others. That is also what
makes the plain `gather` safe here: no unit raises, so none is cancelled or left unawaited. The run
raises only after every unit has finished, naming each failed one, so the guard sees one failure that
lists them all. `concurrency` has no default (`flat-layered` rule 10); the process definition passes it.

## Other bindings

- **A task group in place of `gather`.** `asyncio.TaskGroup` cancels its siblings on the first failure,
  so it fits only when every unit keeps the same `try` around its whole body; what must survive the
  swap is that no unit's failure escapes its own containment before every unit has finished.
