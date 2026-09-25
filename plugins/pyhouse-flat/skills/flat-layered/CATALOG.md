# flat-layered — the exception catalog the family's templates raise

Topic file of `flat-layered`. The catalog's shape, its translation rules and where a caught error is
rendered are `exception-catalog`'s; what follows is the one instance every flat template raises from and
every flat test asserts on, and **the one place their codes and statuses are stated**.

## The catalog — stdlib exceptions

`src/myapp/exceptions.py`:

```python
__all__ = [
    "FooAlreadyRecordedError",
    "FooClientError",
    "FooNotFoundError",
    "MyappError",
    "StorageUnavailableError",
    "StorageWriteRejectedError",
    "ValidationError",
]


class MyappError(Exception):
    code: str = "MYAPP_ERROR"
    http_status: int = 500

    def __init__(self, message: str, context: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.context: dict[str, object] = context if context is not None else {}


class FooAlreadyRecordedError(MyappError):
    code = "FOO_ALREADY_RECORDED"
    http_status = 409


class FooClientError(MyappError):
    code = "FOO_CLIENT_ERROR"
    http_status = 502


class FooNotFoundError(MyappError):
    code = "FOO_NOT_FOUND"
    http_status = 404


class StorageUnavailableError(MyappError):
    code = "STORAGE_UNAVAILABLE"
    http_status = 503


class StorageWriteRejectedError(MyappError):
    code = "STORAGE_WRITE_REJECTED"


class ValidationError(MyappError):
    code = "VALIDATION_ERROR"
    http_status = 422
```

| Class | Status | Raised by |
|---|---|---|
| `FooClientError` | 502 | the client, on a transport, status or parse failure (`SKILL.md`, the client template) |
| `FooNotFoundError` | 404 | the storage class's read, when no row matches (`flat-persistence`) |
| `FooAlreadyRecordedError` | 409 | the storage class's refusing write, on the reference's unique constraint |
| `StorageWriteRejectedError` | 500, the root's | the storage translator, for any other refusal of the data — a defect of this service |
| `StorageUnavailableError` | 503 | the storage translator's fallback — a failed connection, transaction or read |
| `ValidationError` | 422 | the HTTP wrapper, for a request the framework rejected (`flat-entrypoint`) |

`http_status` is there because the HTTP shape renders it. A service with no HTTP trigger drops the root's
annotation and every subclass's `http_status` line, and keeps the codes (`exception-catalog`).
