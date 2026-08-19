"""Reject anonymization failures in fixture messages."""

from __future__ import annotations

import re
from pathlib import Path

_AFFILIATE = re.compile(
    r"("
    r"amzn\.to|"
    r"tag=|"
    r"partner[_-]?id=|"
    r"afiliad|"
    r"awin1\.com|"
    r"lomadee|"
    r"s\.click\.|"
    r"bit\.ly/|"
    r"tinyurl\.com|"
    r"magalu\.com\.br/a-|"
    r"shopee\.com\.br/[^\s]*utm_"
    r")",
    re.IGNORECASE,
)

_PHONE = re.compile(r"\b(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?\d{4,5}[-\s]?\d{4}\b")
_HANDLE = re.compile(r"(?<!\w)@[A-Za-z][A-Za-z0-9_]{3,}\b")


def check_fixtures(root: Path | None = None) -> list[str]:
    base = root or Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "messages"
    errors: list[str] = []
    if not base.is_dir():
        return [f"missing fixtures dir: {base}"]
    for path in sorted(base.rglob("*.txt")):
        text = path.read_text(encoding="utf-8")
        rel = path.as_posix()
        if _AFFILIATE.search(text):
            errors.append(f"{rel}: possible affiliate URL/pattern")
        if _PHONE.search(text):
            errors.append(f"{rel}: possible phone number")
        # Allow @channel mentions only if clearly placeholders; reject personal handles
        for match in _HANDLE.finditer(text):
            handle = match.group(0).lower()
            if handle not in {"@exemplo", "@channel", "@grupo"}:
                errors.append(f"{rel}: telegram handle {match.group(0)!r}")
    return errors
