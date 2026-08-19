"""Garimpo — deal prospecting engine for Telegram."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("garimpo")
except PackageNotFoundError:  # source tree without an install
    __version__ = "0.0.0+unknown"

# Reported to Telegram as the client app version. Plausible and honest — a
# fabricated value is what gets sessions flagged.
DEFAULT_APP_VERSION = f"garimpo {__version__}"
