"""Ingest package."""

from garimpo.ingest.base import MTProtoClient, SourceRef
from garimpo.ingest.clients.fake_client import FakeMTProtoClient

__all__ = ["FakeMTProtoClient", "MTProtoClient", "SourceRef"]
