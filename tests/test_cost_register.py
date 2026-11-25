from __future__ import annotations

import csv
import math
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {"datetime", "case_id", "version_caso", "call_id", "stage", "agent", "component_type", "provider", "model_or_version", "input_tokens", "cached_input_tokens", "cache_write_tokens", "output_tokens", "total_tokens", "voice_duration_seconds", "api_calls", "request_count", "billing_unit", "input_rate_usd", "output_rate_usd", "cached_input_rate_usd", "cost_usd", "currency", "status", "retry", "data_origin", "pricing_status", "notes"}


def rows(name: str) -> list[dict[str, str]]:
    with (ROOT / "costs" / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_cost_register_has_required_fields_and_no_secrets() -> None:
    data = rows("costos.csv")
    assert data and REQUIRED <= set(data[0])
    assert not any(token in str(data).lower() for token in ("api_key", "authorization: bearer", "sk-"))


def test_unknown_usage_is_blank_and_deterministic_rows_have_no_tokens() -> None:
    data = rows("costos.csv")
    unknown = next(row for row in data if row["case_id"] == "YC-ARTIFACT01" and row["stage"] == "ELARA")
    assert unknown["input_tokens"] == unknown["cost_usd"] == ""
    for row in data:
        if row["pricing_status"] == "NOT_APPLICABLE":
            assert not any(row[key].strip() for key in ("input_tokens", "cached_input_tokens", "cache_write_tokens", "output_tokens", "total_tokens"))


def test_live_elara_cost_reconciles_and_no_cost_is_nonfinite() -> None:
    data = rows("costos.csv")
    elara = next(row for row in data if row["call_id"] == "YC-TG177652682:elara:1")
    assert Decimal(elara["cost_usd"]) == (Decimal("2201") * Decimal("0.10") + Decimal("185") * Decimal("0.50")) / Decimal("1000000")
    assert all(not row["cost_usd"].strip() or math.isfinite(float(row["cost_usd"])) for row in data)


def test_sample_rejection_and_voice_gap_are_explicit() -> None:
    data = rows("costos.csv")
    assert {"YC-TG177652682", "YC-PIPE20261111", "YC-ARTIFACT01", "YC-SECURITY20260414"} <= {row["case_id"] for row in data}
    voice = next(row for row in data if row["stage"] == "NOVA_VOICE")
    assert voice["voice_duration_seconds"] == voice["cost_usd"] == ""
    assert "VOICE COST EVIDENCE PENDING" in voice["notes"]


def test_summaries_and_projections_cover_required_scenarios() -> None:
    assert {row["monthly_cases"] for row in rows("proyecciones.csv")} == {"100", "1000", "10000"}
    assert {row["scenario"] for row in rows("proyecciones.csv")} == {"base", "high_consumption"}
