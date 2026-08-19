"""Credential validation without network."""

import pytest

from garimpo.auth.errors import LoginConfigError
from garimpo.auth.login import validate_credentials


def test_api_id_must_be_numeric() -> None:
    with pytest.raises(LoginConfigError):
        validate_credentials("abc", "a" * 32)


def test_api_hash_must_be_32_hex() -> None:
    with pytest.raises(LoginConfigError):
        validate_credentials("12345", "short")
    with pytest.raises(LoginConfigError):
        validate_credentials("12345", "g" * 32)


def test_valid_credentials() -> None:
    api_id, api_hash = validate_credentials("12345", "a" * 32)
    assert api_id == 12345
    assert api_hash == "a" * 32
