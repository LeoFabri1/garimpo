"""Telemetry stays silent when disabled."""

import pytest

from garimpo.telemetry import TelemetryPoint, maybe_send


@pytest.mark.asyncio
async def test_telemetry_off_sends_nothing() -> None:
    from datetime import UTC, datetime

    n = await maybe_send(
        [
            TelemetryPoint(
                "rtx_5070_ti", 100.0, "kabum", datetime.now(UTC)
            )
        ],
        enabled=False,
        endpoint="https://example.invalid/telemetry",
    )
    assert n == 0
