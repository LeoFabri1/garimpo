"""Format alert text for lockscreen-friendly push."""

from __future__ import annotations

from garimpo.models.alert import Level, ScoredOffer


def format_alert(scored: ScoredOffer) -> str:
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
    if offer.coupon and offer.coupon.code:
        meta_bits.append(f"cupom {offer.coupon.code}")
    if meta_bits:
        lines.append(" · ".join(meta_bits))
    lines.append("")
    lines.append(scored.reason)
    if scored.price_per_pt is not None:
        lines.append(f"⚡ R$ {scored.price_per_pt:.1f} por ponto de performance")
    if offer.url:
        lines.append("")
        lines.append(f"🔗 {offer.url}")
    return "\n".join(lines)
