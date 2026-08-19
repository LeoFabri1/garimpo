"""Login errors."""


class LoginAborted(RuntimeError):
    """Raised after too many failed attempts (protect against 22h FloodWait)."""


class LoginConfigError(ValueError):
    """Invalid api_id / api_hash format before hitting the network."""
