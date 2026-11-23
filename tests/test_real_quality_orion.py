"""Integración local de Siena real versionada, quality loop y Orion."""

from __future__ import annotations

from copy import deepcopy

import pytest

from backend.curve_quality_loop import run_curve_quality_loop
from backend.orion_executor import execute_orion
from backend.siena_to_excel_adapter import build_excel_payload_from_siena
from tests.fixtures_siena_real_20261111 import CASE, SIENA


def _case() -> dict:
    case = deepcopy(CASE)
    case.update(caso_id="YC-ORION20261111", version_caso=1, version_curva="CURVA-ORION-20261111", estado="RECIBIDO")
    case["solicitud"] = {"universo_instrumentos": ["CETES", "MBONOS"], "proposito": "Valuación y análisis de riesgo de un portafolio ficticio."}
    case["aprobacion_humana"] = {"estado": "PENDIENTE"}
    return case


def _elara() -> dict:
    return {
        "schema_version": "1.0.0", "decision": "ACEPTAR", "fecha_corte_normalizada": "2026-11-11",
        "instrumentos_solicitados": ["CETES", "MBONOS"], "proposito": "Valuación y análisis de riesgo de un portafolio ficticio.",
        "datos_faltantes": [], "motivos_rechazo": [], "advertencias": [],
        "seguridad": {"inyeccion_prompt_detectada": False, "instrucciones_no_confiables_ignoradas": False},
    }


def _config() -> dict:
    return {
        "budget_usd": 0.0, "time_limit_seconds": 30.0,
        "authorization_scope": "ORCHESTRATION_SIMULATED", "execution_authorized": True,
        "authorization_source": "TRUSTED_LOCAL_CONFIG", "inject_quality_failure": True,
    }


def _inputs() -> tuple[dict, dict, dict]:
    case, siena = _case(), deepcopy(SIENA)
    return case, siena, build_excel_payload_from_siena(case, siena)


def test_real_fixture_quality_loop_validates_clean_curve_once() -> None:
    case, _, payload = _inputs()
    original = deepcopy(payload)
    result = run_curve_quality_loop(case, payload, "real-quality-clean", inject_failure=False)

    assert result["estado"] == "VALIDADA"
    assert len(result["iterations"]) == 1
    assert result["iterations"][0]["caso_id"] == case["caso_id"]
    assert result["iterations"][0]["version_curva"] == "CURVA-ORION-20261111-V1"
    assert result["iterations"][0]["nash"] == "CALCULO_COMPLETADO"
    assert result["iterations"][0]["atenea"] == "DICTAMEN_TECNICO_VALIDADO"
    assert result["costo_adicional_usd"] == 0.0
    assert payload == original


def test_real_fixture_quality_loop_rejects_v1_and_rebuilds_clean_v2() -> None:
    case, _, payload = _inputs()
    original = deepcopy(payload)
    result = run_curve_quality_loop(case, payload, "real-quality-repair", inject_failure=True)

    assert result["estado"] == "VALIDADA"
    assert len(result["iterations"]) == 2
    first, second = result["iterations"]
    assert first["caso_id"] == second["caso_id"] == case["caso_id"]
    assert first["version_curva"] == "CURVA-ORION-20261111-V1"
    assert second["version_curva"] == "CURVA-ORION-20261111-V2"
    assert first["atenea"] == "DICTAMEN_TECNICO_RECHAZADO"
    assert second["atenea"] == "DICTAMEN_TECNICO_VALIDADO"
    assert payload == original
    final_spot = result["nash_output"]["resultado_curva"]["pillars"][-1]["spot_rate"]
    assert final_spot == pytest.approx(0.10530454153195024, abs=1e-12)


def test_orion_real_fixture_reaches_pending_human_approval_after_v2() -> None:
    case, siena, payload = _inputs()
    result = execute_orion(case, _elara(), siena, payload, _config(), "real-orion")

    assert result["estado"] == "PENDIENTE_APROBACION"
    assert result["dictamen_tecnico"] == "VALIDADO"
    assert result["version_curva"] == "CURVA-ORION-20261111-V2"
    assert result["requiere_aprobacion_humana"] is True
    assert result["errores"] == []
    assert case["aprobacion_humana"]["estado"] == "PENDIENTE"
    assert all(result["expediente"][role] is not None for role in ("elara", "siena", "nash", "atenea"))
    assert result["expediente"]["nash"]["estado"] == "CALCULO_COMPLETADO"
    assert result["expediente"]["atenea"]["estado"] == "DICTAMEN_TECNICO_VALIDADO"
    assert [item["etapa"] for item in result["traza"]] == ["seguridad_costos", "elara", "siena", "calidad_curva", "calidad_curva"]
    assert result["traza"][2]["referencia"] == "BANXICO_SIE_REAL"
    assert [item["estado"] for item in result["traza"][-2:]] == ["DICTAMEN_TECNICO_RECHAZADO", "DICTAMEN_TECNICO_VALIDADO"]
