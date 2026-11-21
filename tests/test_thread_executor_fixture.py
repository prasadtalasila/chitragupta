"""`tests/conftest.py::thread_executor` must not let a worker outlive its test.

The pool code under test shuts its executor down with `wait=False` on
purpose: on Ctrl+C the run must not drain the whole backlog first (#501).
A real process pool then has its workers killed by `terminate_workers`;
the thread pool the tests swap in has nothing equivalent, so a job that
had already started kept running after the test returned. Once
`monkeypatch` had restored `config`, that job wrote into the real
`content/`, and `tests/content_guard.py` failed a CI run in which every
test passed (#1226).
"""

import threading
import types

import pytest

from tests.conftest import ThreadPools

# Stands in for `config`: the test patches it, and the late job reports
# which value it saw.
_PROBE = types.SimpleNamespace(value="original")


def _late_job(release: threading.Event, seen: list) -> None:
    """Block until `release`, then record what `_PROBE` says by then."""
    release.wait(5)
    seen.append(_PROBE.value)


def test_join_all_waits_for_a_job_still_running_after_shutdown_wait_false():
    pools = ThreadPools()
    pool = pools(2)
    release = threading.Event()
    seen: list = []
    pool.submit(_late_job, release, seen)
    # What `_drain` does on an interrupt: queued work is cancelled, the
    # running job is not waited for.
    pool.shutdown(wait=False, cancel_futures=True)
    threading.Timer(0.2, release.set).start()

    pools.join_all()

    assert seen == ["original"]


@pytest.fixture
def seen_after_teardown():
    """Requested before `thread_executor`, so pytest tears it down after
    `thread_executor` has joined. Its assertion is about what the late
    job recorded by then, and which value of the patch it saw."""
    seen: list = []
    yield seen
    assert seen == ["patched"], (
        f"the late job ran after monkeypatch was undone, or never ran: saw {seen!r}"
    )


def test_the_fixture_joins_before_monkeypatch_restores_the_patch(
    seen_after_teardown, thread_executor, monkeypatch
):
    monkeypatch.setattr(_PROBE, "value", "patched")
    pool = thread_executor(2)
    release = threading.Event()
    pool.submit(_late_job, release, seen_after_teardown)
    pool.shutdown(wait=False, cancel_futures=True)
    # Released after the test body has returned, so only a teardown
    # that waits for the job lets it record anything in time.
    threading.Timer(0.2, release.set).start()
