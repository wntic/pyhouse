---
name: python-process-stop
description: Use when a Python process that outlives one run — a polling loop, a queue or stream consumer, a long-running worker, a server that installs no signal handling of its own — is asked to stop by the platform, a container runtime, a service manager or Ctrl-C, and the question is what it does then. Owns the stop request installed first at the entry point for both the termination and the interrupt signal, work taken only while no stop is requested, a wait for work or for the next interval that a stop ends at once, the run in flight finished rather than cut and given no deadline of the process's own, the longest run fitting the platform's grace period, a requested stop leaving through the same release as any other exit, and a clean exit with one event rather than a traceback. A process that does one run and exits, and one whose server installs its own signal handling, install nothing. Delivering the signal into a container is `python-container-image`.
when_to_use: Also when asked for graceful shutdown, draining a consumer, handling SIGTERM or SIGINT, why a worker exits with a KeyboardInterrupt traceback, why a deploy cuts a message mid-processing, or how long a stop may take.
---

# Python Process Stop — what a long-lived process does when asked to stop

What a process that outlives one run does between the moment it is asked to stop and the moment it
exits: stop taking work, finish what it holds, leave through its usual release, exit cleanly. It holds
for a loop, a consumer and any other worker of either architecture family, in a container or under a
service manager. How the signal reaches the process is the image's; what a run does is the run's.

## When to use vs. neighbours

- Making the platform's stop signal reach the process inside a container — exec form, the image's stop
  signal → `python-container-image`.
- A process whose server installs its own signal handling and drains its requests — uvicorn's command
  is one → the server owns the signal; the program releases what it built in the server's shutdown
  hook (`hex-restapi-app`, in the `pyhouse-hex` plugin, is one) and installs nothing from here. A server
  that installs none — `grpc.aio` is one — is a long-lived process like any other.
- A process that does one run and exits → nothing here; its run is its unit, and a run cut short is a
  failed run, which the next start makes whole.
- How a unit is acknowledged, returned, redelivered or dead-lettered → the family's trigger rules
  (`flat-entrypoint`, in the `pyhouse-flat` plugin, or the entrypoint layer of `hex-architecture`, in
  `pyhouse-hex`).
- What the entry point builds and how it is released → the family's composition root (`flat-entrypoint`
  rule 14, or `hex-wiring` rule 5).
- The interval a loop waits between runs, as a setting → `python-settings` rule 5.
- The event a stop logs, and where logging is configured → `python-logging`.

## Template — asyncio

The entry point's async body, written inside the `try` or `async with` that releases what the entry
point builds; `run_once` is the one contained run the process repeats, `interval_seconds` its settings'
interval, and `log` the module's logger (`python-logging`):

```python
import asyncio
import contextlib
import signal


async def _run() -> None:
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stopping.set)
    # build what the process needs here, inside the block that releases it
    while not stopping.is_set():
        await run_once()
        # a consumer waits here on its next unit and this event together; a stop ends only that wait
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stopping.wait(), interval_seconds)
    log.info("process_stopped")
```

Both signals set one event, so the process stops the same way under a platform that sends the
termination signal, a container image that declares the interrupt one and a developer's Ctrl-C, and
`asyncio.run`'s own interrupt handling — a `KeyboardInterrupt` traceback and exit status 130 — never
runs. The handlers go in before anything is built, so a stop during start-up is a stop too. The loop
checks the event only between runs, so a run in flight finishes; the wait between runs is a wait on the
event, so a stop requested during it ends it at once. `_run` then returns through the block that
releases what was built, and the process exits with status 0.

## Other bindings

- **A synchronous loop.** A `threading.Event` set by handlers registered with `signal.signal` in the
  main thread, and `event.wait(interval_seconds)` in place of the wait on the asyncio event; nothing in
  `## Rules` changes.
- **Windows.** Its event loop installs no signal handlers; a handler registered with `signal.signal`
  sets the event through `loop.call_soon_threadsafe(stopping.set)`, for the interrupt signal, the one a
  console delivers there.
- **A consumer SDK, or a server that installs no signal handling of its own.** Its own stop call, made
  once the stop request is set, replaces the loop above: it must stop taking units or requests before
  it returns, and the one in flight still finishes.

## Rules

1. **The stop request is installed once, first, at the process's entry point, for both the termination
   and the interrupt signal, and does nothing but record the request.** It is installed before the
   process builds anything, so a stop during start-up is a clean stop. Nothing below the entry point
   installs a handler — a library that installs one takes the signal from the program that imports it.
   The two signals are handled alike, so whichever one the platform, the image or a terminal sends, the
   process stops the same way.
2. **No new work is taken once a stop is requested.** The process checks the request before taking
   each unit; a unit fetched after the request is a unit the process then has to hand back.
3. **A wait is interruptible; a run is not.** A wait for the next interval or the next unit ends the
   moment a stop is requested — a receive that blocks until a unit arrives is such a wait, so a loop that
   checks the request only between blocking receives does not see a stop until the next unit comes. A
   run in flight finishes and settles its unit as the family's trigger rules require, rather than being
   cancelled half-way.
4. **The longest run fits the platform's grace period, and the process sets no deadline of its own.**
   The platform kills a process that has not exited when its grace period ends, and a run killed mid-way
   is lost and redone. A run that can take longer is split into units that each fit, or writes durable
   progress as it goes, so being killed costs at most the unit in flight. A timer the process sets to
   cancel the run in flight is the cut rule 3 forbids.
5. **A requested stop leaves through the same release as any other exit.** The loop ending returns into
   the entry point's existing release — the composition root's close — never a second release of its
   own, and a failure takes the same path.
6. **A requested stop is a clean exit.** It logs one event (`python-logging`), never a traceback, and
   exits with status 0; a failure exits non-zero. The status is what tells whatever restarts the
   process a deploy from a crash.

## Hard stops

- Asked to make the signal reach a containerized process at all — exec form, the image's stop signal →
  stop, use `python-container-image`.
- Asked what a consumer does with a unit whose run failed, how many times it is redelivered, or where
  it goes after the limit → stop, use the family's trigger rules (`flat-entrypoint`, in the
  `pyhouse-flat` plugin, or the entrypoint layer of `hex-architecture`, in `pyhouse-hex`); this skill
  only stops the process.
