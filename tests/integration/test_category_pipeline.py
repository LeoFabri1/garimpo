"""Watch category notebooks/cpus resolve via merged catalog."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from garimpo.catalog import ModelIndex, load_catalog_for_watch
from garimpo.models.raw import RawMessage
from garimpo.parse.groups import ParserRegistry
from garimpo.pipeline import Pipeline
from garimpo.settings import load_settings


def test_notebook_category_resolves() -> None:
    catalog = load_catalog_for_watch(["notebook"])
    reg = ParserRegistry(ModelIndex(catalog))
    msg = RawMessage(
        source_id=1,
        tg_msg_id=1,
        text="Notebook RTX 4060 Acer — R$ 5.499 no PIX Kabum",
        has_media=False,
        received_at=datetime.now(UTC),
    )
    offer = reg.parse(msg)
    assert offer is not None
    assert offer.model_key == "notebook_rtx_4060"
    assert offer.price.amount == Decimal("5499")


def test_pipeline_with_cpu_watch(tmp_path: Path) -> None:
    settings = load_settings(Path("config/quickstart.yaml"))
    settings.storage.path = str(tmp_path / "garimpo.db")
    settings.alerts.channel = "console"
    # Swap watch to CPU category (models by display name resolved via index)
    from garimpo.settings import WatchRuleConfig

    settings.watch = [
        WatchRuleConfig(
            name="cpu-x3d",
            category="cpu",
            models=["Ryzen 7 7800X3D"],
            max_price=3000,
        )
    ]
    pipe = Pipeline(settings, dry_run=True)
    try:
        assert "ryzen_7_7800x3d" in pipe.catalog.products
        result = pipe.process(
            RawMessage(
                source_id=1,
                tg_msg_id=1,
                text="Ryzen 7 7800X3D — R$ 2.199 no PIX Kabum",
                has_media=False,
                received_at=datetime.now(UTC),
            )
        )
        assert result.status in {"parsed", "alerted"}
        assert result.offer_id is not None
    finally:
        pipe.close()
