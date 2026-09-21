"""Attach coupon / purchase URL onto a parsed Offer."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation

from garimpo.models.offer import Coupon, Offer

_URL = re.compile(r"https?://[^\s<>\"'\]]+", re.IGNORECASE)

_COUPON_CODE = re.compile(
    r"(?:cupom|coupon|c[oó]digo)(?:\s+de\s+desconto)?[^\S\n]*[:=\-]?\s*([A-Za-z0-9_-]{3,24})\b",
    re.IGNORECASE,
)
# "Cupom para MELI+: OFFMELIMAIS", "Cupom no APP: 300PAYDAY" — a qualifier
# between the word and the colon.
_COUPON_CODE_AFTER_COLON = re.compile(
    r"cupo(?:m|ns)\b[^\n:]{1,25}:[^\S\n]*([A-Za-z0-9_-]{3,24})\b", re.IGNORECASE
)
# Words that follow "cupom" in prose and would otherwise be read as a code.
_NOT_A_CODE = frozenset({"HTTP", "HTTPS", "OFF", "PIX", "AQUI", "DESTA", "DESSA", "PARA"})

_DISCOUNT_ABS = re.compile(
    r"cupo(?:m|ns)\s+(?:de\s+)?"
    r"(?:R\$\s*(\d{1,4}(?:[.,]\d{2})?)|(\d{1,4})\s+(?:reais\s+)?off\b)",
    re.IGNORECASE,
)
_DISCOUNT_PCT = re.compile(r"cupo(?:m|ns)\s+(?:de\s+)?(\d{1,2})\s*%", re.IGNORECASE)

# What the text next to a link says it is. Order of checks: footer, coupon,
# purchase — a "grupo de ofertas" footer is never the product.
_FOOTER_LABEL = re.compile(r"telegram|whats\s*app|instagram|grupo|canal", re.IGNORECASE)
_FOOTER_HOST = re.compile(
    r"https?://(?:www\.)?(?:t\.me|telegram\.me|chat\.whatsapp\.com|wa\.me|whatsapp\.com|instagram\.com)/",
    re.IGNORECASE,
)
# A specific post ("Ainda disponível… t.me/canal/170418") leads back to the
# original offer; a bare t.me/canal in the footer does not.
_CHANNEL_POST = re.compile(r"https?://(?:t|telegram)\.me/\w+/\d+", re.IGNORECASE)
# Redeem-a-coupon link. A bare "Cupom QUEROOFERTA" line above a link does not
# qualify: it names a code, it does not point at the link.
_COUPON_LABEL = re.compile(
    r"resgat|\bcupons\b|\bpegue\b|cupom[^\n]*\b(?:off|aqui)\b", re.IGNORECASE
)
_PURCHASE_LABEL = re.compile(r"compr[ae]|link\s+(?:do\s+)?produto|adquir|acesse|🛒", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class _Link:
    url: str
    kind: str  # purchase | coupon | post | footer | plain


def _classify_links(text: str) -> list[_Link]:
    """Each URL, labelled by the text on its line — or, for a link alone on its
    line, by the line above it. Channels write "Compre aqui:" and "Resgate o
    cupom:" either inline or as a heading one line up."""
    links: list[_Link] = []
    previous = ""
    for line in text.splitlines():
        matches = list(_URL.finditer(line))
        if not matches:
            if line.strip():
                previous = line
            continue
        cursor = 0
        for match in matches:
            label = line[cursor : match.start()]
            if not label.strip() and cursor == 0 and not _URL.search(previous):
                label = previous
            url = match.group(0).rstrip(").,;!?")
            if _CHANNEL_POST.match(url):
                kind = "post"
            elif _FOOTER_HOST.match(url) or _FOOTER_LABEL.search(label):
                kind = "footer"
            elif _COUPON_LABEL.search(label):
                kind = "coupon"
            elif _PURCHASE_LABEL.search(label):
                kind = "purchase"
            else:
                kind = "plain"
            links.append(_Link(url, kind))
            cursor = match.end()
        previous = line
    return links


def extract_purchase_url(text: str) -> str | None:
    """Link to buy the product. Not the first link: on Shopee deals the first
    one is "Resgate o cupom", and the product comes after it. A link to the
    channel's own post is the last resort, for "back in stock" reposts."""
    links = _classify_links(text)
    for kind in ("purchase", "plain", "coupon", "post"):
        for link in links:
            if link.kind == kind:
                return link.url
    return None


# "Resgate o cupom no anúncio": the coupon is on the product page itself.
_COUPON_ON_PAGE = re.compile(r"cupom\s+(?:no|do|na)\s+(?:an[uú]ncio|p[aá]gina)", re.IGNORECASE)


def _coupon_url(text: str) -> str | None:
    url = next((link.url for link in _classify_links(text) if link.kind == "coupon"), None)
    if url is None and _COUPON_ON_PAGE.search(text):
        url = extract_purchase_url(text)
    return url


def extract_coupon_code(text: str) -> str | None:
    matches = sorted(
        [*_COUPON_CODE.finditer(text), *_COUPON_CODE_AFTER_COLON.finditer(text)],
        key=lambda m: m.start(1),
    )
    for match in matches:
        raw = match.group(1)
        code = raw.upper()
        if code in _NOT_A_CODE or not any(c.isalpha() for c in code):
            continue
        # Codes are posted uppercase; a lowercase word after "cupom" is prose
        # ("cupom de", "cupom exclusivo", "código do produto"). Mixed case
        # still counts when it carries a digit ("Nova10").
        if raw != code and not any(c.isdigit() for c in raw):
            continue
        return code
    return None


def _amount(raw: str) -> Decimal | None:
    try:
        return Decimal(raw.replace(".", "").replace(",", "."))
    except InvalidOperation:
        return None


def extract_coupon(text: str) -> Coupon | None:
    code = extract_coupon_code(text)
    abs_match = _DISCOUNT_ABS.search(text)
    pct_match = _DISCOUNT_PCT.search(text)
    discount_abs = _amount(abs_match.group(1) or abs_match.group(2)) if abs_match else None
    discount_pct = _amount(pct_match.group(1)) if pct_match else None
    url = _coupon_url(text)
    if not (code or discount_abs or discount_pct or url):
        return None
    return Coupon(code=code, discount_abs=discount_abs, discount_pct=discount_pct, url=url)


def extract_first_url(text: str) -> str | None:
    """Back-compat name — prefer extract_purchase_url."""
    return extract_purchase_url(text)


def enrich_offer(offer: Offer | None, text: str) -> Offer | None:
    """Attach coupon and purchase URL from the raw message text."""
    if offer is None:
        return None
    coupon = offer.coupon if offer.coupon and offer.coupon.code else extract_coupon(text)
    url = offer.url or extract_purchase_url(text)
    if coupon == offer.coupon and url == offer.url:
        return offer
    return replace(offer, coupon=coupon, url=url)
