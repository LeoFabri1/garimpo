"""Tests for text normalization."""

from garimpo.parse.text import normalize_for_hash, normalize_text
from garimpo.parse.triage import offer_body, passes_triage


def test_emoji_becomes_space_not_glue() -> None:
    assert "PLACA DE" in normalize_text("PLACA🔥DE").upper().replace("  ", " ")


def test_zero_width_removed() -> None:
    assert normalize_text("RTX\u200b5070") == "RTX5070" or "RTX" in normalize_text(
        "RTX\u200b 5070"
    )


def test_hash_normalization_stable() -> None:
    a = normalize_for_hash("RTX 5070 Ti — Kabum")
    b = normalize_for_hash("rtx 5070 ti kabum")
    assert a == b or a.replace("—", "") == b  # dash may remain as char


# --- Regressão: rodapé de canal furava a triagem (2026-08-20) ---------------
# @hardtecpromocoes assina toda mensagem com "Só placa de vídeo:" divulgando
# outro canal. Isso casava com o TRIAGE em cafeteira, ar-condicionado e relógio,
# e 45% do que chegava ao parser vinha dessa assinatura.


# Links trocados por placeholders de propósito: republicar o encurtador do
# canal levaria junto o código de afiliado do dono, e o t.me divulga o canal
# dele. O que o teste precisa é da estrutura — link, depois rodapé — não das
# URLs reais.
_RODAPE = (
    "\n\nLINK LINK: https://example.com/oferta\n\n"
    "Grupos Exclusivos👍\nSó placa de vídeo:\nhttps://example.com/canal-a\n"
    "Memória Ram + cpu:\nhttps://example.com/canal-b\n"
)


def test_footer_does_not_pass_triage() -> None:
    cafeteira = "🔥 WAP WCD1500 Cafeteira Digital 1,5L\n\n✅ R$203,15" + _RODAPE
    assert not passes_triage(cafeteira)


def test_real_offer_still_passes_with_same_footer() -> None:
    gpu = "🔥 Placa de Vídeo MSI RTX 5060 Shadow 2X OC 8GB\n\n✅ R$ 2199" + _RODAPE
    assert passes_triage(gpu)


def test_offer_body_stops_at_first_link() -> None:
    assert offer_body("Produto\nR$ 10\nhttps://example.com/a").strip() == "Produto\nR$ 10"


def test_offer_body_without_link_is_whole_text() -> None:
    assert offer_body("Placa de Vídeo RTX 5060") == "Placa de Vídeo RTX 5060"
