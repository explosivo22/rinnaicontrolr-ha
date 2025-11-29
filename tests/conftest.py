"""Pytest configuration for Rinnai integration tests."""
import pytest
import threading
import asyncio
from typing import Generator


# Override the verify_cleanup fixture from pytest-homeassistant-custom-component
# to allow the _run_safe_shutdown_loop thread which is created by HA's executor shutdown
@pytest.fixture(autouse=True)
def verify_cleanup(
    event_loop: asyncio.AbstractEventLoop,
    expected_lingering_tasks: bool,
    expected_lingering_timers: bool,
) -> Generator[None, None, None]:
    """Verify that the test has cleaned up resources correctly.
    
    This overrides the default fixture to allow certain known safe threads.
    """
    from pytest_homeassistant_custom_component.plugins import (
        INSTANCES,
        get_scheduled_timer_handles,
        long_repr_strings,
    )
    from homeassistant.core import HassJob
    import logging

    _LOGGER = logging.getLogger(__name__)

    threads_before = frozenset(threading.enumerate())
    tasks_before = asyncio.all_tasks(event_loop)
    yield

    event_loop.run_until_complete(event_loop.shutdown_default_executor())

    if len(INSTANCES) >= 2:
        count = len(INSTANCES)
        for inst in INSTANCES:
            inst.stop()
        pytest.exit(f"Detected non stopped instances ({count}), aborting test run")

    # Warn and clean-up lingering tasks and timers
    tasks = asyncio.all_tasks(event_loop) - tasks_before
    for task in tasks:
        if expected_lingering_tasks:
            _LOGGER.warning("Lingering task after test %r", task)
        else:
            pytest.fail(f"Lingering task after test {task!r}")
        task.cancel()
    if tasks:
        event_loop.run_until_complete(asyncio.wait(tasks))

    for handle in get_scheduled_timer_handles(event_loop):
        if not handle.cancelled():
            with long_repr_strings():
                if expected_lingering_timers:
                    _LOGGER.warning("Lingering timer after test %r", handle)
                elif handle._args and isinstance(job := handle._args[-1], HassJob):
                    if job.cancel_on_shutdown:
                        continue
                    pytest.fail(f"Lingering timer after job {job!r}")
                else:
                    pytest.fail(f"Lingering timer after test {handle!r}")
                handle.cancel()

    # Verify no threads where left behind - allow known safe threads
    threads = frozenset(threading.enumerate()) - threads_before
    allowed_thread_names = ("waitpid-", "_run_safe_shutdown_loop")
    for thread in threads:
        if isinstance(thread, threading._DummyThread):
            continue
        if any(thread.name.startswith(name) or name in thread.name for name in allowed_thread_names):
            continue
        assert False, f"Lingering thread after test: {thread!r}"


@pytest.fixture(name="expected_lingering_tasks")
def expected_lingering_tasks_fixture():
    """Fixture to mark tests that may have lingering tasks."""
    return False


@pytest.fixture(name="expected_lingering_timers")
def expected_lingering_timers_fixture():
    """Fixture to mark tests that may have lingering timers."""
    return False
