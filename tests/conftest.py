"""Fixtures for pytest.

This file patches pytest-socket on Windows to allow socket usage required
by the Windows proactor event loop.
"""
from __future__ import annotations

import socket
import sys

# Store the real socket class BEFORE any imports that might load pytest-socket
_real_socket_class = socket.socket


def _noop(*args, **kwargs):
    """No-op function to replace pytest_socket functions."""
    pass


# Monkey-patch pytest_socket BEFORE it's used
if sys.platform == "win32":
    import pytest_socket

    # Replace the disable/enable functions with no-ops
    pytest_socket.disable_socket = _noop
    pytest_socket.socket_allow_hosts = _noop
    pytest_socket.enable_socket = _noop


import pytest  # noqa: E402


def _enable_socket():
    """Restore real socket if it was patched by pytest-socket."""
    socket.socket = _real_socket_class


# Pytest hooks - use hookwrapper to run AFTER other plugins
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    """Run after pytest_homeassistant_custom_component's pytest_runtest_setup.

    This re-enables sockets after pytest-socket disables them.
    Windows proactor event loop requires socket.socketpair() for internal IPC.
    """
    # Let other plugins run first (including pytest_homeassistant_custom_component)
    yield
    # Now restore socket after pytest_socket.disable_socket() was called
    if sys.platform == "win32":
        _enable_socket()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    """Ensure socket stays enabled during test execution."""
    if sys.platform == "win32":
        _enable_socket()
    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item, nextitem):
    """Ensure socket stays enabled during teardown."""
    if sys.platform == "win32":
        _enable_socket()
    yield


@pytest.fixture(autouse=True)
def socket_enabled():
    """Allow socket connections for tests on Windows."""
    if sys.platform == "win32":
        _enable_socket()
    yield
    if sys.platform == "win32":
        _enable_socket()

