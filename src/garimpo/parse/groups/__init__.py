"""Parser registry: source.parser → implementation (DESIGN §9.6)."""

from __future__ import annotations

from garimpo.catalog.index import ModelIndex
from garimpo.models.offer import Offer
from garimpo.models.raw import RawMessage
from garimpo.parse.generic import GenericParser
from garimpo.parse.groups.gatry import GatryParser
from garimpo.parse.groups.hardmob import HardmobParser
from garimpo.parse.groups.pelando import PelandoParser
from garimpo.parse.groups.promobit import PromobitParser


class ParserRegistry:
    def __init__(self, index: ModelIndex) -> None:
        self._generic = GenericParser(index)
        self._by_name: dict[str, GenericParser] = {
            "generic": self._generic,
            "promobit": PromobitParser(index),
            "pelando": PelandoParser(index),
            "hardmob": HardmobParser(index),
            "gatry": GatryParser(index),
        }

    def get(self, name: str | None) -> GenericParser:
        if name and name in self._by_name:
            return self._by_name[name]
        return self._generic

    def parse(self, msg: RawMessage) -> Offer | None:
        hint = msg.parser_hint or "generic"
        parser = self.get(hint)
        if parser.can_handle(msg):
            offer = parser.parse(msg)
            if offer is not None:
                return offer
        if hint != "generic":
            return self._generic.parse(msg)
        return None
