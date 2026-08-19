"""Fixture hygiene tests."""

from garimpo.tools.fixture_check import check_fixtures


def test_fixtures_are_anonymized() -> None:
    errors = check_fixtures()
    assert not errors, errors
