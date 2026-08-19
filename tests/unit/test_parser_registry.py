"""Parser registry selects named parsers."""

from datetime import UTC, datetime

from garimpo.catalog import ModelIndex, load_gpu_catalog
from garimpo.models.raw import RawMessage
from garimpo.parse.groups import ParserRegistry


def test_registry_promobit_parses() -> None:
    reg = ParserRegistry(ModelIndex(load_gpu_catalog()))
    msg = RawMessage(
        source_id=1,
        tg_msg_id=1,
        text="RTX 5070 Ti ASUS — R$ 5.799 no PIX Kabum",
        has_media=False,
        received_at=datetime.now(UTC),
        parser_hint="promobit",
    )
    offer = reg.parse(msg)
    assert offer is not None
    assert offer.model_key == "rtx_5070_ti"
