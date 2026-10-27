"""Tests for the Rinnai local TCP client."""

from __future__ import annotations

import asyncio
import json

import pytest

from custom_components.rinnai import local
from custom_components.rinnai.local import RinnaiLocalClient

BANNER = b"monitor\nhelp for help\n"
SYSINFO = {"sysinfo": {"serial-number": "ABC123", "fw": "238"}}
LIST_RESPONSE = (
    b"list\n"
    b"                  domestic_temperature:  135 (0x87) {93m}\n"
    b"                     operation_enabled:  true {2h}\n"
)


class _FakeReader:
    """Replays a scripted console session.

    Banner chunks are readable immediately; reply chunks only after the
    client has written its command. Each chunk is a (delay, data) pair; a
    ConnectionResetError instance as data raises it instead.
    """

    def __init__(self, writer, banner, reply, eof) -> None:
        self._writer = writer
        self._banner = list(banner)
        self._reply = list(reply)
        self._eof = eof

    async def read(self, _n: int) -> bytes:
        if self._banner:
            delay, data = self._banner.pop(0)
        else:
            await self._writer.written.wait()
            if not self._reply:
                if self._eof:
                    return b""
                await asyncio.sleep(3600)  # Idle, like a connection left open
            delay, data = self._reply.pop(0)
        await asyncio.sleep(delay)
        if isinstance(data, Exception):
            raise data
        return data


class _FakeWriter:
    def __init__(self, reset_on_close: bool) -> None:
        self.written = asyncio.Event()
        self.data = b""
        self._reset_on_close = reset_on_close

    def write(self, data: bytes) -> None:
        self.data += data
        self.written.set()

    async def drain(self) -> None:
        return

    def close(self) -> None:
        return

    async def wait_closed(self) -> None:
        if self._reset_on_close:
            raise ConnectionResetError("Connection reset by peer")


@pytest.fixture(autouse=True)
def _fast_timeouts(monkeypatch):
    """Shrink console timeouts so tests run quickly."""
    monkeypatch.setattr(local, "BANNER_TIMEOUT", 0.2)
    monkeypatch.setattr(local, "BANNER_IDLE_TIMEOUT", 0.05)
    monkeypatch.setattr(local, "RESPONSE_TIMEOUT", 0.5)
    monkeypatch.setattr(local, "RESPONSE_IDLE_TIMEOUT", 0.2)
    monkeypatch.setattr(local, "MAX_RESPONSE_SECONDS", 2.0)


def _patch_console(
    monkeypatch,
    reply,
    banner=((0, BANNER),),
    eof=False,
    reset_on_close=False,
):
    """Route asyncio.open_connection to a scripted fake console."""
    writer = _FakeWriter(reset_on_close)
    reader = _FakeReader(writer, banner, reply, eof)

    async def _open_connection(host, port):
        return reader, writer

    monkeypatch.setattr(local.asyncio, "open_connection", _open_connection)
    return writer


def _sysinfo_line(prefix: str = "") -> bytes:
    return f"{prefix}{json.dumps(SYSINFO)}\n".encode()


@pytest.mark.asyncio
async def test_get_sysinfo_success(monkeypatch):
    """A prompt reply with a banner returns the sysinfo dict."""
    writer = _patch_console(monkeypatch, [(0, _sysinfo_line())])

    assert await RinnaiLocalClient("1.2.3.4").get_sysinfo() == SYSINFO
    assert writer.data == b"sysinfo\n"


@pytest.mark.asyncio
async def test_get_sysinfo_slow_reply(monkeypatch):
    """A reply slower than the idle timeout is still read (#169)."""
    _patch_console(monkeypatch, [(0.35, _sysinfo_line())])

    assert await RinnaiLocalClient("1.2.3.4").get_sysinfo() == SYSINFO


@pytest.mark.asyncio
async def test_get_sysinfo_reply_split_with_gap(monkeypatch):
    """A reply split across chunks with a short gap is reassembled."""
    line = _sysinfo_line()
    _patch_console(monkeypatch, [(0, line[:10]), (0.1, line[10:])])

    assert await RinnaiLocalClient("1.2.3.4").get_sysinfo() == SYSINFO


@pytest.mark.asyncio
async def test_get_sysinfo_without_banner(monkeypatch):
    """A console that sends no banner still works."""
    _patch_console(monkeypatch, [(0, _sysinfo_line())], banner=())

    assert await RinnaiLocalClient("1.2.3.4").get_sysinfo() == SYSINFO


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reply",
    [
        _sysinfo_line("#? "),
        (json.dumps(SYSINFO, indent=2) + "\n").encode(),
    ],
    ids=["prompt-prefix", "pretty-printed"],
)
async def test_get_sysinfo_json_formats(monkeypatch, reply):
    """Sysinfo JSON is found behind a prompt or across multiple lines."""
    _patch_console(monkeypatch, [(0, reply)])

    assert await RinnaiLocalClient("1.2.3.4").get_sysinfo() == SYSINFO


@pytest.mark.asyncio
async def test_get_sysinfo_no_reply(monkeypatch, caplog):
    """No reply returns None and logs why."""
    _patch_console(monkeypatch, [])

    assert await RinnaiLocalClient("1.2.3.4").get_sysinfo() is None
    assert "No response to 'sysinfo'" in caplog.text


@pytest.mark.asyncio
async def test_get_sysinfo_no_json(monkeypatch, caplog):
    """A reply without JSON returns None and logs why."""
    _patch_console(monkeypatch, [(0, b"unknown command\n")])

    assert await RinnaiLocalClient("1.2.3.4").get_sysinfo() is None
    assert "No sysinfo JSON found" in caplog.text


@pytest.mark.asyncio
async def test_reset_after_reply_keeps_data(monkeypatch):
    """A reset after the reply keeps the data already received."""
    _patch_console(
        monkeypatch,
        [(0, _sysinfo_line()), (0, ConnectionResetError("reset"))],
        reset_on_close=True,
    )

    assert await RinnaiLocalClient("1.2.3.4").get_sysinfo() == SYSINFO


@pytest.mark.asyncio
async def test_reset_before_reply_returns_none(monkeypatch, caplog):
    """A reset before any reply is reported as a socket error."""
    _patch_console(monkeypatch, [(0, ConnectionResetError("reset"))])

    assert await RinnaiLocalClient("1.2.3.4").get_sysinfo() is None
    assert "Socket error" in caplog.text


@pytest.mark.asyncio
async def test_connect_timeout(monkeypatch, caplog):
    """A connection timeout returns None and logs it."""

    async def _hang(host, port):
        await asyncio.sleep(3600)

    monkeypatch.setattr(local.asyncio, "open_connection", _hang)
    client = RinnaiLocalClient("1.2.3.4")

    assert await client._send_command("sysinfo", timeout=0.05) is None
    assert "Timeout connecting" in caplog.text


@pytest.mark.asyncio
async def test_get_status_success(monkeypatch):
    """The list reply is parsed into properties."""
    _patch_console(monkeypatch, [(0, LIST_RESPONSE)], eof=True)

    status = await RinnaiLocalClient("1.2.3.4").get_status()

    assert status == {"domestic_temperature": 135, "operation_enabled": True}


@pytest.mark.asyncio
async def test_get_status_without_properties_is_failure(monkeypatch, caplog):
    """A list reply with no properties is a failure, not empty data."""
    _patch_console(monkeypatch, [(0, b"list\n")], eof=True)

    assert await RinnaiLocalClient("1.2.3.4").get_status() is None
    assert "No properties found" in caplog.text


@pytest.mark.asyncio
async def test_test_connection(monkeypatch):
    """test_connection reflects whether sysinfo could be read."""
    _patch_console(monkeypatch, [(0, _sysinfo_line())])
    assert await RinnaiLocalClient("1.2.3.4").test_connection() is True

    _patch_console(monkeypatch, [])
    assert await RinnaiLocalClient("1.2.3.4").test_connection() is False
