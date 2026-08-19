"""Catalog loading and alias index."""

from garimpo.catalog.index import ModelIndex, ResolveResult
from garimpo.catalog.loader import load_gpu_catalog, load_stores

__all__ = [
    "ModelIndex",
    "ResolveResult",
    "load_gpu_catalog",
    "load_stores",
]
