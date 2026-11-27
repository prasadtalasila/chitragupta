import threading
import types

import pytest

from tests.conftest import ThreadPools

_PROBE = types.SimpleNamespace(value="original")


def _late_job(release: threading.Event, seen: list) -> None:
    release.wait(5)
    seen.append(_PROBE.value)


def test_join_all_waits_for_a_job_still_running_after_shutdown_wait_false():
    pools = ThreadPools()
    pool = pools(2)
    release = threading.Event()
    seen: list = []
    pool.submit(_late_job, release, seen)
    pool.shutdown(wait=False, cancel_futures=True)
    threading.Timer(0.2, release.set).start()

    pools.join_all()

    assert seen == ["original"]


@pytest.fixture
def seen_after_teardown():
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
    threading.Timer(0.2, release.set).start()


def test_track_registers_a_pool_built_outside_the_factory():
    from concurrent.futures import ThreadPoolExecutor

    pools = ThreadPools()
    pool = ThreadPoolExecutor(max_workers=2)
    assert pools.track(pool) is pool
    release = threading.Event()
    seen: list = []
    pool.submit(_late_job, release, seen)
    pool.shutdown(wait=False, cancel_futures=True)
    threading.Timer(0.2, release.set).start()

    pools.join_all()

    assert seen == ["original"]


def test_join_all_still_joins_the_other_pools_when_one_shutdown_raises():
    pools = ThreadPools()
    broken = pools(1)

    def refuse(*args, **kwargs):
        raise RuntimeError("shutdown refused")

    broken.shutdown = refuse
    late = pools(2)
    release = threading.Event()
    seen: list = []
    late.submit(_late_job, release, seen)
    late.shutdown(wait=False, cancel_futures=True)
    threading.Timer(0.2, release.set).start()

    with pytest.raises(RuntimeError, match="shutdown refused"):
        pools.join_all()

    assert seen == ["original"]
