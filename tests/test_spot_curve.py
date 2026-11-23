import json
from pathlib import Path

import pytest

from backend.build_spot_curve_adapter import apply_build_spot_curve
from backend.spot_curve import SpotCurveValidationError, build_spot_curve


ROOT = Path(__file__).resolve().parents[1]


def load_example(name):
    return json.loads((ROOT / "skills" / "build_spot_curve" / "examples" / name).read_text(encoding="utf-8"))


def test_valid_case_builds_positive_pillars_and_reprices():
    result = build_spot_curve(load_example("caso_valido.json"))
    assert result["mode"] == "SIMULADO"
    assert result["conventions"]["price_basis"] == "DIRTY"
    assert len(result["pillars"]) == 5
    assert all(item["discount_factor"] > 0 for item in result["pillars"])
    assert result["summary"]["max_absolute_repricing_error"] <= 1e-8


def test_reuse_case_is_independent_and_reprices():
    first = build_spot_curve(load_example("caso_valido.json"))
    second = build_spot_curve(load_example("caso_reutilizacion.json"))
    assert first["case_id"] != second["case_id"]
    assert second["summary"]["instrument_count"] == 4
    assert second["summary"]["max_absolute_repricing_error"] <= 1e-8


def test_missing_individual_mbono_metadata_is_blocked():
    with pytest.raises(SpotCurveValidationError, match="METADATOS_MBONO_FALTANTES"):
        build_spot_curve(load_example("caso_invalido_metadatos.json"))


@pytest.mark.parametrize("field,value", [("price_basis", "YTM"), ("mode", "REAL")])
def test_rejects_nonpermitted_mode_or_price_basis(field, value):
    payload = load_example("caso_valido.json")
    payload[field] = value
    with pytest.raises(SpotCurveValidationError):
        build_spot_curve(payload)


def test_adapter_loads_skill_and_records_sanitized_trace():
    response = apply_build_spot_curve(load_example("caso_valido.json"), "invocation-sim-001")
    assert response["status"] == "COMPLETED"
    assert response["trace"]["skill_name"] == "build-spot-curve"
    assert response["trace"]["skill_path"] == "skills/build_spot_curve/SKILL.md"
    assert len(response["trace"]["skill_sha256"]) == 64


def test_adapter_records_rejection_without_secret_data():
    response = apply_build_spot_curve(load_example("caso_invalido_metadatos.json"), "invocation-sim-002")
    assert response["status"] == "REJECTED"
    assert response["trace"]["error_code"] == "METADATOS_MBONO_FALTANTES"
