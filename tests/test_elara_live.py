from decimal import Decimal
from pathlib import Path

from backend.run_elara_live import estimate_cost_usd, expectations_met, model_rates

ROOT = Path(__file__).resolve().parents[1]


def test_cost_estimate_separates_uncached_cached_and_output_tokens() -> None:
    rates = {
        "input": Decimal("0.10"),
        "cached_input": Decimal("0.01"),
        "output": Decimal("0.50"),
    }

    estimate = estimate_cost_usd(
        {"input_tokens": 100, "cached_input_tokens": 40, "output_tokens": 20},
        rates,
    )

    assert estimate == {
        "input_uncached_usd": "0.000006",
        "input_cached_usd": "4E-7",
        "output_usd": "0.00001",
        "total_usd": "0.0000164",
    }


def test_tariffs_and_expected_live_output_are_verified() -> None:
    rates = model_rates(ROOT / "costs" / "tarifas.csv", "gpt-6-luna")
    output = {
        "decision": "ACEPTAR",
        "fecha_corte_normalizada": "2026-04-14",
        "instrumentos_solicitados": ["CETES", "MBONOS"],
    }

    assert rates["input"] == Decimal("0.10")
    assert rates["cached_input"] == Decimal("0.01")
    assert rates["output"] == Decimal("0.50")
    assert expectations_met(output) is True
