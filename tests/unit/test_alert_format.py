"""What reaches the phone: where to buy, and with which coupon."""

from __future__ import annotations

from decimal import Decimal

from garimpo.alert.format import format_alert
from garimpo.models.alert import Level, ScoredOffer
from garimpo.models.offer import Coupon, Offer, Price


def _scored(**offer_kwargs: object) -> ScoredOffer:
    offer = Offer(
        model_key="rtx_5060",
        price=Price(amount=Decimal("2142"), method="pix"),
        store="marketplace_generico",
        **offer_kwargs,  # type: ignore[arg-type]
    )
    return ScoredOffer(
        offer=offer,
        level=Level.NORMAL,
        percentile=0.1,
        baseline=2300.0,
        min_90d=2100.0,
        n_samples=40,
        price_per_pt=None,
        reason="p10 dos últimos 90d",
    )


def test_code_coupon_and_purchase_link() -> None:
    text = format_alert(
        _scored(coupon=Coupon(code="QUEROOFERTA"), url="https://loja.example.com/produto")
    )
    assert "cupom QUEROOFERTA" in text
    assert "🔗 https://loja.example.com/produto" in text


def test_link_only_coupon_shows_discount_and_redeem_link() -> None:
    text = format_alert(
        _scored(
            coupon=Coupon(
                code=None, discount_abs=Decimal("100"), url="https://cupom.example.com/a"
            ),
            url="https://loja.example.com/produto",
        )
    )
    assert "cupom R$ 100 OFF" in text
    assert "🎟️ https://cupom.example.com/a" in text
    # Buy link comes first: it is the one the user taps.
    assert text.index("loja.example.com") < text.index("cupom.example.com")


def test_percent_coupon() -> None:
    text = format_alert(_scored(coupon=Coupon(code="APP10", discount_pct=Decimal("10"))))
    assert "cupom APP10 (10% OFF)" in text


def test_no_coupon_no_coupon_line() -> None:
    text = format_alert(_scored(url="https://loja.example.com/produto"))
    assert "cupom" not in text
    assert "🎟️" not in text


def test_coupon_on_product_page_has_no_second_link() -> None:
    url = "https://loja.example.com/produto"
    text = format_alert(_scored(coupon=Coupon(code=None, url=url), url=url))
    assert "cupom na página do produto" in text
    assert "🎟️" not in text
