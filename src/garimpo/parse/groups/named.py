"""Thin group parsers — currently reuse generic; goldens drive specialization."""

from __future__ import annotations

from garimpo.parse.generic import GenericParser


class PromobitParser(GenericParser):
    name = "promobit"


class PelandoParser(GenericParser):
    name = "pelando"


class HardmobParser(GenericParser):
    name = "hardmob"


class GatryParser(GenericParser):
    name = "gatry"
