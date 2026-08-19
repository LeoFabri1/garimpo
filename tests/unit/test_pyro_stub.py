"""Pyro backend raises clear NotImplementedError."""

import pytest

from garimpo.ingest.clients.pyro_client import PyroClient


def test_pyro_not_implemented() -> None:
    with pytest.raises(NotImplementedError, match="pyrotgfork"):
        PyroClient()
