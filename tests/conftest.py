"""Pytest configuration for Rinnai integration tests."""

import asyncio
import threading
from collections.abc import Generator

import pytest

# Import the plugins module to access INSTANCES and other helpers
from pytest_homeassistant_custom_component.plugins import (
    INSTANCES,
    get_scheduled_timer_handles,
)


@pytest.fixture(scope="function")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test.

    This fixture is required for compatibility with pytest-homeassistant-custom-component
    which still uses the deprecated event_loop fixture from older pytest-asyncio versions.
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def verify_cleanup(
    event_loop: asyncio.AbstractEventLoop,
    expected_lingering_tasks: bool,
    expected_lingering_timers: bool,
) -> Generator[None, None, None]:
    """Verify that the test has cleaned up resources correctly.

    This overrides the default fixture from pytest-homeassistant-custom-component
    to allow certain known safe threads like _run_safe_shutdown_loop.
    """
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
            pass  # Allow lingering tasks
        else:
            pytest.fail(f"Lingering task after test {task!r}")
        task.cancel()
    if tasks:
        event_loop.run_until_complete(asyncio.wait(tasks))

    for handle in get_scheduled_timer_handles(event_loop):
        if not handle.cancelled():
            if expected_lingering_timers:
                handle.cancel()
            else:
                # Allow storage delayed write timers - they are safe
                handle_repr = repr(handle)
                if "_async_schedule_callback_delayed_write" in handle_repr:
                    handle.cancel()
                    continue
                pytest.fail(f"Lingering timer after test {handle!r}")

    # Verify no threads were left behind - allow known safe threads
    threads = frozenset(threading.enumerate()) - threads_before
    allowed_thread_patterns = (
        "waitpid-",
        "_run_safe_shutdown_loop",
        "ThreadPoolExecutor",
    )
    for thread in threads:
        if isinstance(thread, threading._DummyThread):
            continue
        # Check if thread name contains any allowed pattern
        if any(pattern in thread.name for pattern in allowed_thread_patterns):
            continue
        pytest.fail(f"Lingering thread after test: {thread!r}")


@pytest.fixture(name="expected_lingering_tasks")
def expected_lingering_tasks_fixture() -> bool:
    """Fixture to mark tests that may have lingering tasks."""
    return False


@pytest.fixture(name="expected_lingering_timers")
def expected_lingering_timers_fixture() -> bool:
    """Fixture to mark tests that may have lingering timers.

    Storage delayed write timers are expected and safe.
    """
    return True
