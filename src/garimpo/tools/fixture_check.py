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


# Encurtador aponta para destino que não dá para inspecionar aqui, e num canal
# de oferta ele quase sempre carrega o código de afiliado do dono. `t.me` real
# republica o canal de alguém.
_OPAQUE_LINK = re.compile(
    r"https?://("
    r"meli\.la|"
    r"s\.shopee\.com\.br|"
    r"magazinevoce\.com\.br|"
    r"amzn\.to|"
    r"bit\.ly|"
    r"cutt\.ly|"
    r"t\.me"
    r")/\S+",
    re.IGNORECASE,
)


def check_test_sources(tests_root: Path) -> list[str]:
    """Os mesmos padrões, no código dos testes.

    Uma regressão escrita a partir de mensagem real leva junto o link real —
    foi assim que um `meli.la` do canal entrou em tests/unit/test_text.py e
    passou por este check, que só olhava fixtures `.txt`. Telefone e handle
    ficam de fora aqui: em Python dariam falso positivo em qualquer
    `@pytest.mark` e em qualquer número.
    """
    errors: list[str] = []
    for path in sorted(tests_root.rglob("*.py")):
        rel = path.as_posix()
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            # Só linhas com URL. Aplicar _AFFILIATE ao arquivo inteiro acusava
            # a palavra "afiliado" escrita num comentário explicando por que o
            # link foi trocado — o check delatando a própria documentação.
            if "http" not in line:
                continue
            if _AFFILIATE.search(line):
                errors.append(f"{rel}:{lineno}: possible affiliate URL/pattern")
            for match in _OPAQUE_LINK.finditer(line):
                errors.append(
                    f"{rel}:{lineno}: opaque/real link {match.group(0)!r} — use example.com"
                )
    return errors


def check_fixtures(root: Path | None = None) -> list[str]:
    base = root or Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "messages"
    errors: list[str] = []
    tests_root = base.parent.parent if root is None else None
    if tests_root is not None and tests_root.is_dir():
        errors.extend(check_test_sources(tests_root))
    if not base.is_dir():
        return [*errors, f"missing fixtures dir: {base}"]
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
