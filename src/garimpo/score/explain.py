"""Human-readable score explanation — facts, not synthetic scores."""

from __future__ import annotations

from garimpo.score.baseline import Baseline


def explain(*, price: float, percentile: float, baseline: Baseline) -> str:
    if baseline.kind != "ok" or baseline.median is None or baseline.min_90d is None:
        return f"histórico insuficiente (n={baseline.n})"

    # Approximate rank label from percentile
    # percentile 0.02 with n=47 ≈ "3º menor"
    approx_rank = max(1, int(round(percentile * baseline.n)) + 1)
    discount = (baseline.median - price) / baseline.median * 100.0
    return (
        f"{approx_rank}º menor em 90 dias (mín: R$ {baseline.min_90d:,.0f}) "
        f"· mediana R$ {baseline.median:,.0f} → {discount:+.1f}%".replace(",", ".")
    )
