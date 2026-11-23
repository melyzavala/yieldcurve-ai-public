"""Integración Excel para quality loop y Orion, sin servicios externos."""

import copy
import json
from pathlib import Path

from backend.curve_quality_loop import run_curve_quality_loop
from backend.orion_executor import execute_orion
from tests.fixtures_excel_bootstrap import PAYLOAD
from test_nash import case_for


ROOT = Path(__file__).resolve().parents[1]


def _excel_case():
    case = case_for(PAYLOAD)
    case["estado"] = "RECIBIDO"
    case["aprobacion_humana"] = {"estado": "PENDIENTE"}
    return case


def _orion_inputs():
    case = _excel_case()
    elara = json.loads((ROOT / "agents/examples/elara/solicitud_valida.json").read_text(encoding="utf-8"))["salida_esperada"]
    siena = json.loads((ROOT / "agents/examples/siena/cases.json").read_text(encoding="utf-8"))[0]["salida_esperada"]
    elara["fecha_corte_normalizada"] = PAYLOAD["valuation_date"]
    siena["fecha_corte"] = PAYLOAD["valuation_date"]
    for observation in siena["observaciones"]:
        observation["fecha"] = PAYLOAD["valuation_date"]
    config = {"budget_usd": 0.0, "time_limit_seconds": 30.0, "authorization_scope": "ORCHESTRATION_SIMULATED", "execution_authorized": True, "authorization_source": "TRUSTED_LOCAL_CONFIG", "inject_quality_failure": False}
    return case, elara, siena, copy.deepcopy(PAYLOAD), config


def test_excel_quality_loop_validates_in_one_iteration_without_injection():
    original = copy.deepcopy(PAYLOAD)
    result = run_curve_quality_loop(_excel_case(), original, "excel-loop-clean", inject_failure=False)
    assert result["estado"] == "VALIDADA"
    assert len(result["iterations"]) == 1
    assert result["iterations"][0]["metodologia"] == "EXCEL_BOOTSTRAP_182D_V1"
    assert result["iterations"][0]["atenea"] == "DICTAMEN_TECNICO_VALIDADO"
    assert result["iterations"][0]["version_curva"].endswith("-V1")
    assert original == PAYLOAD


def test_excel_quality_loop_rejects_v1_and_rebuilds_v2_from_original():
    original = copy.deepcopy(PAYLOAD)
    result = run_curve_quality_loop(_excel_case(), original, "excel-loop-repair", inject_failure=True)
    assert result["estado"] == "VALIDADA"
    assert len(result["iterations"]) == 2
    first, second = result["iterations"]
    assert first["caso_id"] == second["caso_id"] == PAYLOAD["case_id"]
    assert first["version_curva"].endswith("-V1")
    assert second["version_curva"].endswith("-V2")
    assert first["metodologia"] == second["metodologia"] == "EXCEL_BOOTSTRAP_182D_V1"
    assert first["atenea"] == "DICTAMEN_TECNICO_RECHAZADO"
    assert second["atenea"] == "DICTAMEN_TECNICO_VALIDADO"
    assert original == PAYLOAD


def test_excel_quality_loop_stops_when_nash_rejects_without_atenea():
    invalid = copy.deepcopy(PAYLOAD)
    invalid.pop("excel_mbonos")
    result = run_curve_quality_loop(_excel_case(), invalid, "excel-loop-rejected", inject_failure=False)
    assert result["estado"] == "RECHAZADA_NASH"
    assert result["iterations"][0]["atenea"] == "NO_EJECUTADA"


def test_orion_completes_excel_path_and_preserves_human_approval():
    case, elara, siena, payload, config = _orion_inputs()
    result = execute_orion(case, elara, siena, payload, config, "orion-excel-valid")
    assert result["estado"] == "PENDIENTE_APROBACION"
    assert result["dictamen_tecnico"] == "VALIDADO"
    assert result["version_curva"].endswith("-V1")
    assert result["requiere_aprobacion_humana"] is True
    assert case["aprobacion_humana"]["estado"] == "PENDIENTE"
    assert all(result["expediente"][role] is not None for role in ("elara", "siena", "nash", "atenea"))
    assert result["expediente"]["nash"]["resultado_curva"]["metodologia"] == "EXCEL_BOOTSTRAP_182D_V1"
    assert result["expediente"]["atenea"]["estado"] == "DICTAMEN_TECNICO_VALIDADO"


def test_orion_does_not_request_approval_when_quality_loop_fails(monkeypatch):
    case, elara, siena, payload, config = _orion_inputs()
    rejected_atenea = {"estado": "DICTAMEN_TECNICO_RECHAZADO", "errores": [{"codigo": "REPRICING_FUERA_DE_TOLERANCIA", "mensaje": "Prueba."}]}
    monkeypatch.setattr("backend.orion_executor.run_curve_quality_loop", lambda *args, **kwargs: {"estado": "LIMITE_ITERACIONES", "iterations": [{"atenea": "DICTAMEN_TECNICO_RECHAZADO", "version_curva": "CURVA-EXCEL-001-V1"}], "nash_output": {"estado": "CALCULO_COMPLETADO"}, "atenea_output": rejected_atenea})
    result = execute_orion(case, elara, siena, payload, config, "orion-excel-invalid")
    assert result["estado"] == "RECHAZADO"
    assert result["dictamen_tecnico"] == "RECHAZADO"
    assert result["expediente"]["atenea"]["estado"] == "DICTAMEN_TECNICO_RECHAZADO"
