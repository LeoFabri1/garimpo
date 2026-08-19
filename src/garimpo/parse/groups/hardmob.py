"""Hardmob forum-style (BBCode leftovers, Preço: bare amounts)."""

from __future__ import annotations

from garimpo.catalog.index import ModelIndex
from garimpo.models.offer import Offer
from garimpo.models.raw import RawMessage
from garimpo.parse.generic import GenericParser
from garimpo.parse.groups.common import ensure_currency_markers, strip_bbcode, with_coupon
from garimpo.parse.text import normalize_text


class HardmobParser(GenericParser):
    name = "hardmob"

    def __init__(self, index: ModelIndex) -> None:
        super().__init__(index)

    def parse(self, msg: RawMessage) -> Offer | None:
        if not msg.text:
            return None
        cleaned = ensure_currency_markers(strip_bbcode(normalize_text(msg.text)))
        proxy = RawMessage(
            source_id=msg.source_id,
            tg_msg_id=msg.tg_msg_id,
            text=cleaned,
            has_media=msg.has_media,
            received_at=msg.received_at,
            source_username=msg.source_username,
            parser_hint=self.name,
        )
        return with_coupon(super().parse(proxy), msg.text)
