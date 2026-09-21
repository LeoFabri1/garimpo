"""Format alert text for lockscreen-friendly push."""

from __future__ import annotations

from decimal import Decimal

from garimpo.models.alert import Level, ScoredOffer
from garimpo.models.offer import Coupon


def _money(amount: Decimal) -> str:
    return f"{amount:.2f}".rstrip("0").rstrip(".")


def coupon_label(coupon: Coupon | None, *, offer_url: str | None = None) -> str | None:
    """Short label: cupom QUEROOFERTA, cupom R$ 100 OFF, cupom APP10 (10% OFF)."""
    if coupon is None:
        return None
    if coupon.discount_abs is not None:
        discount = f"R$ {_money(coupon.discount_abs)} OFF"
    elif coupon.discount_pct is not None:
        discount = f"{_money(coupon.discount_pct)}% OFF"
    else:
        discount = None
    if coupon.code and discount:
        return f"cupom {coupon.code} ({discount})"
    if coupon.code or discount:
        return f"cupom {coupon.code or discount}"
    if coupon.url:
        return "cupom na página do produto" if coupon.url == offer_url else "cupom no link 🎟️"
    return None


def format_alert(scored: ScoredOffer) -> str:
    # Digest and rate-limit notices ride on a placeholder offer; its
    # "DIGEST — R$ 0 · UNKNOWN" header is noise, the reason is the message.
    if scored.rule_name == "system":
        return scored.reason
    offer = scored.offer
    badge = "🚨" if scored.level == Level.CRITICAL else "📉"
    title = offer.model_key.replace("_", " ").upper()
    if offer.brand:
        title = f"{offer.brand} {title}"
    lines = [
        f"{badge} {title} — R$ {offer.price.amount}",
    ]
    meta_bits: list[str] = []
    if offer.store:
        meta_bits.append(offer.store)
    meta_bits.append(offer.price.method.upper())
    coupon = coupon_label(offer.coupon, offer_url=offer.url)
    if coupon:
        meta_bits.append(coupon)
    if meta_bits:
        lines.append(" · ".join(meta_bits))
    lines.append("")
    lines.append(scored.reason)
    links: list[str] = []
    if offer.url:
        links.append(f"🔗 {offer.url}")
    if offer.coupon and offer.coupon.url and offer.coupon.url != offer.url:
        links.append(f"🎟️ {offer.coupon.url}")
    if links:
        lines.append("")
        lines.extend(links)
    return "\n".join(lines)
