"""Regresión determinista de la ruta Siena validada a Atenea."""

from __future__ import annotations

from copy import deepcopy

from backend.atenea_executor import EXCEL_CONVENTIONS, execute_atenea
from backend.nash_executor import execute_nash
from backend.siena_to_excel_adapter import build_excel_payload_from_siena
from backend.spot_curve_validator import validate_spot_curve
from tests.fixtures_siena_real_20261111 import CASE, SIENA


def _run() -> tuple[dict, dict, dict]:
    case, siena = deepcopy(CASE), deepcopy(SIENA)
    payload = build_excel_payload_from_siena(case, siena)
    nash = execute_nash(case, payload, "siena-nash-atenea-fixture")
    return case, payload, nash


def _curve(nash: dict, payload: dict) -> dict:
    return {
        "case_id": nash["caso_id"],
        "curve_version": nash["version_curva"],
        "mode": "SIMULADO",
        "valuation_date": payload["valuation_date"],
        "conventions": EXCEL_CONVENTIONS,
        "pillars": nash["resultado_curva"]["pillars"],
    }


def test_real_siena_fixture_validates_independently_and_in_atenea() -> None:
    case, payload, nash = _run()
    independent = validate_spot_curve(payload, _curve(nash, payload))
    cetes = [item for item in independent["repricing"] if item["instrument_id"].startswith("C")]
    mbonos = [item for item in independent["repricing"] if item["instrument_id"].startswith("M")]

    assert independent["estado"] == "VALIDA"
    assert independent["metodologia"] == "EXCEL_BOOTSTRAP_182D_V1"
    assert len(independent["repricing"]) == 10
    assert len(cetes) == 5
    assert len(mbonos) == 5
    assert max(item["absolute_repricing_error"] for item in cetes) <= 1e-10
    assert max(item["absolute_repricing_error"] for item in mbonos) <= 1e-8

    atenea = execute_atenea(case, nash, payload, "siena-nash-atenea-valid")
    assert atenea["estado"] == "DICTAMEN_TECNICO_VALIDADO"
    assert atenea["dictamen"]["tecnicamente_valida"] is True
    assert atenea["dictamen"]["requiere_aprobacion_humana"] is True
    assert atenea["evidencia"]["validation_status"] == "COMPLETED"
    assert atenea["errores"] == []


def test_atenea_rejects_an_altered_real_mbono_node() -> None:
    case, payload, nash = _run()
    altered = deepcopy(nash)
    pillar = next(item for item in altered["resultado_curva"]["pillars"] if item["instrument_id"] == "MBONO_20_30")
    pillar["spot_rate"] += 0.01

    result = execute_atenea(case, altered, payload, "siena-nash-atenea-altered")
    assert result["estado"] == "DICTAMEN_TECNICO_RECHAZADO"
    assert result["dictamen"]["tecnicamente_valida"] is False
