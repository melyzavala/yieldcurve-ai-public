"""Pruebas de auditoría independiente para EXCEL_BOOTSTRAP_182D_V1."""

import copy
import subprocess
import sys

import pytest

from backend.atenea_executor import execute_atenea
from backend.excel_bootstrap import METHODOLOGY, build_from_payload
from backend.nash_executor import execute_nash
from backend.spot_curve import INTERPOLATION_METHOD, build_spot_curve
from backend.spot_curve_validator import CurveValidationError, validate_spot_curve
from tests.fixtures_excel_bootstrap import PAYLOAD
from test_nash import case_for


EXCEL_CONVENTIONS = {
    "methodology": METHODOLOGY,
    "price_basis": "DIRTY",
    "price_unit": "MXN_PER_100_FACE",
    "day_count": "182/360",
    "coupon_period_days": 182,
    "interpolation_method": "LINEAR_SPOT_RATE",
}


def excel_curve(payload=PAYLOAD):
    result = build_from_payload(payload)
    return {
        "case_id": result["case_id"],
        "curve_version": result["curve_version"],
        "mode": "SIMULADO",
        "valuation_date": result["valuation_date"],
        "conventions": EXCEL_CONVENTIONS,
        "pillars": result["pillars"],
    }


def test_excel_validator_reprices_independently_without_pchip():
    result = validate_spot_curve(PAYLOAD, excel_curve())
    assert result["estado"] == "VALIDA"
    assert result["metodologia"] == METHODOLOGY
    assert len(result["repricing"]) == 10
    assert max(item["absolute_repricing_error"] for item in result["repricing"] if item["instrument_id"].startswith("M")) <= 1e-8


def test_excel_cetes_historical_benchmark_uses_reversed_182d_equivalence():
    result = validate_spot_curve(PAYLOAD, excel_curve())
    cetes_errors = {
        item["instrument_id"]: item["absolute_repricing_error"]
        for item in result["repricing"]
        if item["instrument_id"].startswith("C")
    }
    assert set(cetes_errors) == {"C28", "C91", "C182", "C364", "C2Y"}
    assert max(cetes_errors.values()) <= 1e-7
    assert cetes_errors["C2Y"] <= 1e-7


def test_excel_validation_modules_do_not_import_scipy():
    script = """
import sys
from backend.excel_bootstrap import METHODOLOGY, build_from_payload
from backend.spot_curve_validator import validate_spot_curve
from tests.fixtures_excel_bootstrap import PAYLOAD
result = build_from_payload(PAYLOAD)
curve = {
    'case_id': result['case_id'], 'curve_version': result['curve_version'],
    'mode': 'SIMULADO', 'valuation_date': result['valuation_date'],
    'conventions': {'methodology': METHODOLOGY, 'price_basis': 'DIRTY',
        'price_unit': 'MXN_PER_100_FACE', 'day_count': '182/360',
        'coupon_period_days': 182, 'interpolation_method': 'LINEAR_SPOT_RATE'},
    'pillars': result['pillars'],
}
validate_spot_curve(PAYLOAD, curve)
assert not any(name == 'scipy' or name.startswith('scipy.') for name in sys.modules)
"""
    probe = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )
    assert probe.returncode == 0, probe.stderr


def test_excel_validator_rejects_altered_node_price_and_nonfinite_values():
    altered = excel_curve()
    altered["pillars"][-1]["spot_rate"] += 0.01
    with pytest.raises(CurveValidationError, match="REPRICING_FUERA_DE_TOLERANCIA"):
        validate_spot_curve(PAYLOAD, altered)
    incompatible = copy.deepcopy(PAYLOAD)
    incompatible["excel_mbonos"][0][2] += 1.0
    with pytest.raises(CurveValidationError, match="REPRICING_FUERA_DE_TOLERANCIA"):
        validate_spot_curve(incompatible, excel_curve())
    nonfinite = excel_curve()
    nonfinite["pillars"][0]["spot_rate"] = float("nan")
    with pytest.raises(CurveValidationError, match="TASA_NO_FINITA"):
        validate_spot_curve(PAYLOAD, nonfinite)
    infinite = excel_curve()
    infinite["pillars"][0]["spot_rate"] = float("inf")
    with pytest.raises(CurveValidationError, match="TASA_NO_FINITA"):
        validate_spot_curve(PAYLOAD, infinite)


def test_excel_validator_rejects_invalid_182d_cetes_base() -> None:
    invalid_payload = copy.deepcopy(PAYLOAD)
    invalid_payload["excel_cetes_nodes"][0][3] = -360.0 / 182.0
    with pytest.raises(CurveValidationError, match="CETES_CONVENCION_INVALIDA"):
        validate_spot_curve(invalid_payload, excel_curve())


def test_excel_and_pchip_methodologies_cannot_be_relabelled():
    relabelled = excel_curve()
    relabelled["conventions"] = {"price_basis": "DIRTY", "price_unit": "MXN_PER_100_FACE", "day_count": "ACT/365F", "interpolation_method": INTERPOLATION_METHOD}
    with pytest.raises(CurveValidationError):
        validate_spot_curve(PAYLOAD, relabelled)
    historical_payload = {
        "case_id": "YC-VALIDA001",
        "curve_version": "CURVA-VALIDA-001",
        "mode": "SIMULADO",
        "valuation_date": "2026-04-14",
        "price_basis": "DIRTY",
        "price_unit": "MXN_PER_100_FACE",
        "day_count": "ACT/365F",
        "interpolation_method": INTERPOLATION_METHOD,
        "instruments": [{"instrument_id": "C1", "instrument_type": "CETES", "maturity_date": "2026-07-13", "face_value": 100, "dirty_price": 98.0}],
    }
    historical_curve = build_spot_curve(historical_payload)
    historical_curve["conventions"] = EXCEL_CONVENTIONS
    with pytest.raises(CurveValidationError):
        validate_spot_curve(historical_payload, historical_curve)


def test_atenea_validates_excel_and_rejects_manipulated_node():
    case = case_for(PAYLOAD)
    nash = execute_nash(case, PAYLOAD, "excel-nash-validation")
    valid = execute_atenea(case, nash, PAYLOAD, "excel-atenea-validation")
    assert valid["estado"] == "DICTAMEN_TECNICO_VALIDADO"
    altered = copy.deepcopy(nash)
    altered["resultado_curva"]["pillars"][-1]["spot_rate"] += 0.01
    rejected = execute_atenea(case, altered, PAYLOAD, "excel-atenea-altered")
    assert rejected["estado"] == "DICTAMEN_TECNICO_RECHAZADO"
