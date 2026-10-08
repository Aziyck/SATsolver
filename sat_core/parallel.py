"""
Parallel benchmark runs (opt-in with "workers" > 1 in the benchmark request).

Process layout while a parallel benchmark runs:

    web server (sat_web)
      +- benchmark job process        run_benchmark -> run_cases_in_pool
           +- worker 1 .. worker N    _solve_case: one whole case at a time

The unit of work is a case: a worker encodes the case once and runs every
solver on that CNF, exactly like the sequential loop (run_case), so all
solvers still see the same formula. Workers return the case's rows and log
lines; the job process forwards them as the usual events, so the server and
the browser do not know whether a benchmark ran in parallel.

Workers rebuild the plan from the normalized request instead of receiving
the (possibly large) plan object; parse_request is deterministic, so every
process sees the same cases.

Cancel and skip reach the workers through shared objects:
- cancel: one multiprocessing Event; every running solver stops at its next
  check.
- skip: a shared counter. A worker remembers the counter's value when it
  starts a case, and "skip requested" means the counter has moved since. So
  Skip affects exactly the cases running at that moment, and no later ones.

Timings are wall-clock per run, as in sequential mode. With several workers
the runs compete for CPU, caches and memory bandwidth, so absolute times are
noisier; keep workers at 1 when the timings themselves are the result.
"""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
import multiprocessing
import os
import threading
from typing import Any, Callable

from sat_core.runtime import EVENT_LOG, RunToken, cancel_requested, emit, skip_requested


# Cases queued per worker. Keeping the queue short means a cancel does not
# leave hundreds of submitted cases to drain.
QUEUE_PER_WORKER = 2

# State of a worker process, set once by _init_worker.
_PLAN = None
_CANCEL = None
_SKIP_GENERATION = None


class CaseToken(RunToken):
    """
    Cancellation token for one case inside a worker.

    Cancel comes from the shared event (and timeouts work as usual through
    child tokens); skip is "the shared counter moved since this case started".
    """

    def __init__(self, cancel_event, skip_generation) -> None:
        super().__init__(cancel_event)
        self._generation = skip_generation
        self._seen = skip_generation.value

    def skip_requested(self) -> bool:
        return self._generation.value != self._seen

    def clear_skip(self) -> None:
        self._seen = self._generation.value


def exit_when_parent_dies(interval: float = 1.0) -> None:
    """
    Start a daemon thread that ends this process if its parent disappears.

    A worker whose parent was killed would otherwise keep computing with
    nobody to report to. Works on every platform (it watches the parent's
    process handle through multiprocessing).
    """

    parent = multiprocessing.parent_process()
    if parent is None:
        return

    def watch() -> None:
        while True:
            parent.join(interval)
            if not parent.is_alive():
                os._exit(1)

    threading.Thread(target=watch, daemon=True, name="parent-watchdog").start()


def _init_worker(request: dict[str, Any], cancel_event, skip_generation) -> None:
    global _PLAN, _CANCEL, _SKIP_GENERATION
    from sat_core.benchmark import parse_request

    _PLAN = parse_request(request)
    _CANCEL = cancel_event
    _SKIP_GENERATION = skip_generation
    exit_when_parent_dies()


def _solve_case(case_index: int, label: str):
    """Worker task: run one case, return (finished, rows, log messages)."""
    from sat_core.benchmark import run_case

    case = _PLAN.cases[case_index]
    if case.label != label:
        raise RuntimeError(f"worker plan differs from the job's plan at case {case_index + 1}")
    rows = []
    events = []
    finished = run_case(_PLAN, case, rows.append, events.append, CaseToken(_CANCEL, _SKIP_GENERATION))
    logs = [event.message for event in events if event.type == EVENT_LOG]
    return finished, rows, logs


def run_cases_in_pool(plan, add: Callable, event_callback=None, cancel_token: RunToken | None = None) -> bool:
    """
    Run the plan's cases on plan.workers processes. Returns False if cancelled.

    add(row) is called in the job process for every row, in completion
    order; rows carry their final index, so the order does not matter.
    """

    context = multiprocessing.get_context("spawn")
    cancel_event = context.Event()
    skip_generation = context.Value("q", 0)
    stop_mirror = threading.Event()

    def mirror() -> None:
        # Forward Stop and Skip from the job's token (set by the web server)
        # to the shared objects the workers watch.
        while not stop_mirror.wait(0.1):
            if cancel_requested(cancel_token):
                cancel_event.set()
            if skip_requested(cancel_token):
                with skip_generation.get_lock():
                    skip_generation.value += 1
                cancel_token.clear_skip()

    mirror_thread = threading.Thread(target=mirror, daemon=True, name="benchmark-mirror")
    mirror_thread.start()

    workers = min(plan.workers, len(plan.cases))
    emit(event_callback, EVENT_LOG, f"Starting {workers} worker processes")
    cases = plan.cases
    next_case = 0
    finished = True
    try:
        with ProcessPoolExecutor(
            max_workers=workers,
            mp_context=context,
            initializer=_init_worker,
            initargs=(plan.normalized, cancel_event, skip_generation),
        ) as pool:
            pending = set()

            def submit_more() -> None:
                nonlocal next_case
                while next_case < len(cases) and len(pending) < workers * QUEUE_PER_WORKER:
                    case = cases[next_case]
                    pending.add(pool.submit(_solve_case, case.index, case.label))
                    next_case += 1

            submit_more()
            while pending:
                done, still_running = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
                pending.clear()
                pending.update(still_running)
                for future in done:
                    try:
                        case_finished, rows, logs = future.result()
                    except BaseException:
                        # A worker failed (or died): stop the others quickly
                        # instead of waiting for their cases, then report it.
                        cancel_event.set()
                        raise
                    for message in logs:
                        emit(event_callback, EVENT_LOG, message)
                    for row in rows:
                        add(row)
                    if not case_finished:
                        finished = False
                if cancel_requested(cancel_token):
                    cancel_event.set()
                if cancel_event.is_set():
                    finished = False
                    # Queued cases never start; running ones stop at their
                    # next check and are collected by the loop.
                    for future in list(pending):
                        if future.cancel():
                            pending.discard(future)
                else:
                    submit_more()
    finally:
        stop_mirror.set()
        mirror_thread.join(1.0)
    return finished
