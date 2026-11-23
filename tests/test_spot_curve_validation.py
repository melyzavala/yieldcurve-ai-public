import copy
import json
from pathlib import Path

from backend.spot_curve import build_spot_curve
from backend.spot_curve_validator import CurveValidationError, validate_spot_curve
from backend.validate_spot_curve_adapter import apply_validate_spot_curve

ROOT = Path(__file__).resolve().parents[1]

def payload(name="caso_valido.json"):
    return json.loads((ROOT / "skills" / "build_spot_curve" / "examples" / name).read_text(encoding="utf-8"))

def test_final_pchip_reprices_coupon_between_pillars_without_calibration_factors():
    source = payload()
    curve = build_spot_curve(source)
    result = validate_spot_curve(source, curve)
    assert result["estado"] == "VALIDA"
    assert result["max_absolute_repricing_error"] <= 1e-8
    assert any(flow["time_years"] not in {pillar["time_years"] for pillar in curve["pillars"]} for item in curve["repricing"] for flow in item["cashflows"])

def test_validator_rejects_missing_pillar_and_adapter_traces_rejection():
    source = payload()
    curve = build_spot_curve(source)
    curve["pillars"] = curve["pillars"][:-1]
    try:
        validate_spot_curve(source, curve)
    except CurveValidationError as error:
        assert str(error) == "PILARES_INCOMPLETOS"
    else:
        raise AssertionError("Se esperaba rechazo.")
    response = apply_validate_spot_curve(source, curve, "validate-sim-001")
    assert response["status"] == "REJECTED"
    assert response["trace"]["error_code"] == "PILARES_INCOMPLETOS"

def test_validator_detects_repricing_outside_tolerance():
    source = payload("caso_multiple_mbonos.json")
    curve = build_spot_curve(source)
    altered = copy.deepcopy(curve)
    altered["pillars"][-1]["discount_factor"] *= 0.90
    try:
        validate_spot_curve(source, altered)
    except CurveValidationError as error:
        assert str(error) == "REPRICING_FUERA_DE_TOLERANCIA"
    else:
        raise AssertionError("Se esperaba rechazo.")

def test_validator_adapter_accepts_second_synthetic_case():
    source = payload("caso_reutilizacion.json")
    response = apply_validate_spot_curve(source, build_spot_curve(source), "validate-sim-002")
    assert response["status"] == "COMPLETED"
    assert response["result"]["case_id"] == source["case_id"]
