"""Pyro backend construction and message mapping (no network)."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from garimpo.ingest.base import SourceRef
from garimpo.ingest.clients.pyro_client import (
    PyroClient,
    _session_name_and_workdir,
    message_to_raw,
)


def test_session_path_split() -> None:
    name, workdir = _session_name_and_workdir("data/session.session")
    assert name == "session"
    assert workdir == "data"


def test_message_to_raw_maps_fields() -> None:
    src = SourceRef(tg_id=-1001, username="promobit_hardware", parser="promobit")
    message = SimpleNamespace(
        id=42,
        text="RTX 5070 Ti R$ 5799",
        caption=None,
        media=None,
        date=datetime(2026, 1, 2, tzinfo=UTC),
        chat=SimpleNamespace(id=-1001, username="Promobit_Hardware"),
    )
    raw = message_to_raw(message, src)
    assert raw.tg_msg_id == 42
    assert raw.source_id == -1001
    assert raw.text == "RTX 5070 Ti R$ 5799"
    assert raw.parser_hint == "promobit"
    assert raw.source_username == "promobit_hardware"
    assert not raw.has_media


def test_message_to_raw_uses_caption_when_no_text() -> None:
    message = SimpleNamespace(
        id=1,
        text=None,
        caption="RX 9070 XT R$ 5499",
        media=object(),
        date=datetime.now(UTC),
        chat=SimpleNamespace(id=9, username=None),
    )
    raw = message_to_raw(message, SourceRef(tg_id=9, parser="gatry"))
    assert raw.text == "RX 9070 XT R$ 5499"
    assert raw.has_media


def test_pyro_client_constructs_without_network() -> None:
    # The mapping tests above need no backend, but constructing the client does.
    # Skip instead of fail so `uv sync --extra telethon` (what docs/login.md
    # tells users to run) leaves a green suite.
    pytest.importorskip("pyrogram", reason="pyro extra not installed")
    client = PyroClient(
        session="data/pyro_test.session",
        api_id=12345,
        api_hash="0123456789abcdef0123456789abcdef",
    )
    assert client.raw is not None
