"""Fast triage: discard ~95% of volume with near-zero false negatives."""

from __future__ import annotations

import re
from collections.abc import Iterable

# Keep broad enough for configured categories (gpu / notebook / cpu).
TRIAGE = re.compile(
    r"("
    r"rtx|gtx|radeon|geforce|arc\s?[ab]\d|rx\s?\d{3,4}|"
    r"placa\s+de\s+v[íi]deo|gpu|"
    r"notebook|laptop|ultrabook|"
    r"ryzen|threadripper|core\s*i[3579]|intel\s*i[3579]|\bi[3579]-\d"
    r")",
    re.IGNORECASE,
)

# Opt-in: only for configs that watch the category. Memory deals are frequent
# in these channels; for a GPU-only user they would all become parse_failed
# rows — logged at INFO, never purged, dragging parse_rate down.
CATEGORY_TRIAGE: dict[str, re.Pattern[str]] = {
    "ram": re.compile(r"ddr[45]|mem[oó]ria\s+ram|fury\s+beast", re.IGNORECASE),
}

_URL = re.compile(r"https?://")


def offer_body(text: str) -> str:
    """Trecho da mensagem onde a oferta realmente está: tudo antes do link.

    Canal de oferta escreve produto e preço, depois o link, depois um rodapé
    fixo divulgando os outros canais do dono. O rodapé do @hardtecpromocoes,
    por exemplo, diz "Só placa de vídeo:" — e isso casava com o TRIAGE em
    TODA mensagem, incluindo cafeteira e ar-condicionado. Metade do que
    chegava ao parser vinha dessa assinatura, não do produto.

    Cortar no primeiro link é mais robusto que contar linhas: não depende de
    quantas linhas em branco o canal usa, só do fato estrutural de que o link
    vem depois do produto e antes do rodapé.
    """
    match = _URL.search(text)
    return text[: match.start()] if match else text


def passes_triage(text: str, categories: Iterable[str] = ()) -> bool:
    body = offer_body(text)
    if TRIAGE.search(body) is not None:
        return True
    return any(
        pattern.search(body) is not None
        for category, pattern in CATEGORY_TRIAGE.items()
        if category in categories
    )
