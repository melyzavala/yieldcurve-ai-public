"""Pruebas sin red ni LLM para la capa única DEMO/LIVE."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

import backend.yieldcurve_pipeline as pipeline
from backend.elara_executor import ElaraResult, InvocationRecord


CONFIG = {
    "budget_usd": 0.0,
    "time_limit_seconds": 30.0,
    "authorization_scope": "ORCHESTRATION_SIMULATED",
    "execution_authorized": True,
    "authorization_source": "TRUSTED_LOCAL_CONFIG",
    "max_llm_calls": 1,
}


def elara_output(decision: str = "ACEPTAR") -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": "1.0.0",
        "decision": decision,
        "fecha_corte_normalizada": "2026-11-11",
        "instrumentos_solicitados": ["CETES", "MBONOS"],
        "proposito": "Valuación y análisis de riesgo de un portafolio ficticio.",
        "datos_faltantes": [],
        "motivos_rechazo": [],
        "advertencias": [],
        "seguridad": {"inyeccion_prompt_detectada": False, "instrucciones_no_confiables_ignoradas": False},
    }
    if decision == "RECHAZAR":
        result["motivos_rechazo"] = [{"codigo": "FUERA_ALCANCE", "severidad": "ERROR", "mensaje": "Fuera de alcance."}]
    if decision == "SOLICITAR_ACLARACION":
        result["fecha_corte_normalizada"] = None
        result["datos_faltantes"] = ["FECHA_CORTE"]
    return result


@dataclass
class FakeElara:
    output: dict[str, Any] | None
    status: str = "VALID"
    calls: int = 0
    trusted_contexts: list[dict[str, str] | None] | None = None

    def run(self, _message: str, trusted_context: dict[str, str] | None = None) -> ElaraResult:
        self.calls += 1
        if self.trusted_contexts is None:
            self.trusted_contexts = []
        self.trusted_contexts.append(trusted_context)
        return ElaraResult(
            output=deepcopy(self.output),
            record=InvocationRecord("TEST_LOCAL", None, None, None, 0, self.status),
        )


def run_demo(**overrides: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "caso_id": "YC-PIPE20261111",
        "version_caso": 1,
        "version_curva": "CURVA-PIPE-20261111",
        "fecha_corte": "2026-11-11",
        "canal_origen": "manual",
        "solicitud": "Construye una curva CETES y M-Bonos para 2026-11-11.",
        "budget_config": deepcopy(CONFIG),
        "invocation_id": "pipeline-test",
        "execution_mode": "DEMO",
        "elara_executor": FakeElara(elara_output()),
    }
    defaults.update(overrides)
    return pipeline.run_yieldcurve_case(**defaults)


def test_demo_runs_the_real_siena_adapter_orion_nash_and_atenea_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    original_loader = pipeline.load_demo_siena
    calls: list[str] = []

    def local_loader(fecha: str, data_path: Path = pipeline.DEFAULT_DEMO_DATA) -> dict[str, Any]:
        calls.append(fecha)
        return original_loader(fecha, data_path)

    monkeypatch.setattr(pipeline, "load_demo_siena", local_loader)

    result = run_demo(elara_executor=None)

    assert calls == ["2026-11-11"]
    assert "execute_siena" not in pipeline.__dict__
    assert result["estado"] == "PENDIENTE_APROBACION"
    assert result["dictamen_tecnico"] == "VALIDADO"
    assert result["requiere_aprobacion_humana"] is True
    assert result["fuente_datos"] == {"execution_mode": "DEMO", "source_mode": "FIXTURE_BANXICO_2026-11-11"}
    assert result["siena"]["resumen_validacion"] == {"series_solicitadas": 26, "series_con_observacion": 26, "observaciones_validas": 26, "observaciones_rechazadas": 0}
    assert result["nash"]["estado"] == "CALCULO_COMPLETADO"
    assert result["atenea"]["estado"] == "DICTAMEN_TECNICO_VALIDADO"
    assert result["version_curva"] == result["nash"]["version_curva"] == result["atenea"]["version_curva"]


def test_demo_is_reproducible_for_market_data_and_curve() -> None:
    first = run_demo(invocation_id="pipeline-repro-1")
    second = run_demo(invocation_id="pipeline-repro-2")

    assert first["siena"]["observaciones"] == second["siena"]["observaciones"]
    assert first["nash"]["resultado_curva"] == second["nash"]["resultado_curva"]
    assert first["caso_id"] == second["caso_id"]
    assert first["version_caso"] == second["version_caso"]


def test_live_uses_injected_siena_and_never_reads_the_demo_snapshot(tmp_path: Path) -> None:
    calls: list[str] = []

    def live_provider(fecha: str) -> dict[str, Any]:
        calls.append(fecha)
        return pipeline.load_demo_siena(fecha)

    result = run_demo(
        execution_mode="LIVE", siena_provider=live_provider,
        demo_data_path=tmp_path / "must-not-be-read.json",
    )

    assert calls == ["2026-11-11"]
    assert result["estado"] == "PENDIENTE_APROBACION"
    assert result["fuente_datos"] == {"execution_mode": "LIVE", "source_mode": "BANXICO_SIE_LIVE"}


def test_live_failure_has_no_demo_fallback() -> None:
    def unavailable(_fecha: str) -> dict[str, Any]:
        return {"estado": "DATOS_INCOMPLETOS", "fecha_corte": "2026-11-11", "observaciones": [], "errores": []}

    result = run_demo(execution_mode="LIVE", siena_provider=unavailable)

    assert result["estado"] == "RECHAZADO"
    assert result["nash"] is None and result["atenea"] is None
    assert result["errores"][0]["codigo"] == "SIENA_DATOS_NO_VALIDOS"
    assert result["fuente_datos"]["source_mode"] == "BANXICO_SIE_LIVE"


@pytest.mark.parametrize(
    ("decision", "expected_state"),
    [("RECHAZAR", "RECHAZADO"), ("SOLICITAR_ACLARACION", "PENDIENTE_ACLARACION")],
)
def test_elara_non_acceptance_stops_before_siena(decision: str, expected_state: str) -> None:
    fake = FakeElara(elara_output(decision))
    result = run_demo(elara_executor=fake)

    assert result["estado"] == expected_state
    assert result["siena"] is None and result["nash"] is None and result["atenea"] is None
    assert result["fuente_datos"]["source_mode"] == "NOT_QUERIED"


def test_pipeline_derives_trusted_context_only_from_validated_case() -> None:
    fake = FakeElara(elara_output())
    result = run_demo(elara_executor=fake, canal_origen="manual")

    assert result["estado"] == "PENDIENTE_APROBACION"
    assert fake.trusted_contexts == [{"modo": "SIMULADO", "fecha_corte": "2026-11-11", "canal_origen": "manual"}]


def test_elara_unavailable_or_security_block_stops_before_siena() -> None:
    fake = FakeElara(None, status="UNSAFE_REQUEST")
    result = run_demo(elara_executor=fake)

    assert result["estado"] == "RECHAZADO"
    assert result["errores"][0]["codigo"] == "ELARA_NO_DISPONIBLE"
    assert result["siena"] is None
    assert result["fuente_datos"]["source_mode"] == "NOT_QUERIED"


def test_insufficient_budget_or_authorization_stops_before_elara() -> None:
    fake = FakeElara(elara_output())
    result = run_demo(elara_executor=fake, budget_config={**CONFIG, "execution_authorized": False})

    assert result["estado"] == "DETENIDO"
    assert fake.calls == 0


@pytest.mark.parametrize(
    ("serie_id", "value", "expected_code"),
    [
        ("SF45439", float("nan"), "SIENA_DATOS_NO_VALIDOS"),
        ("SF45439", float("inf"), "SIENA_DATOS_NO_VALIDOS"),
        ("SF45439", 0.0, "ADAPTADOR_SIENA_RECHAZADO"),
    ],
)
def test_demo_rejects_nonfinite_or_invalid_market_prices(tmp_path: Path, serie_id: str, value: float, expected_code: str) -> None:
    snapshot = json.loads(pipeline.DEFAULT_DEMO_DATA.read_text(encoding="utf-8"))
    snapshot["observaciones"][serie_id] = value
    path = tmp_path / "invalid-snapshot.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")

    result = run_demo(demo_data_path=path)

    assert result["estado"] == "RECHAZADO"
    assert result["nash"] is None and result["atenea"] is None
    assert result["errores"][0]["codigo"] == expected_code


def test_demo_rejects_invalid_snapshot_date_before_quantitative_processing(tmp_path: Path) -> None:
    snapshot = json.loads(pipeline.DEFAULT_DEMO_DATA.read_text(encoding="utf-8"))
    snapshot["fecha_corte"] = "2026-11-10"
    path = tmp_path / "wrong-date.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")

    result = run_demo(demo_data_path=path)

    assert result["estado"] == "RECHAZADO"
    assert result["errores"][0]["codigo"] == "SIENA_DATOS_NO_VALIDOS"


def test_invalid_common_case_is_rejected_before_elara() -> None:
    fake = FakeElara(elara_output())
    result = run_demo(canal_origen="untrusted", elara_executor=fake)

    assert result["estado"] == "RECHAZADO"
    assert result["errores"][0]["codigo"] == "CASO_INVALIDO"
    assert fake.calls == 0


def test_pipeline_respects_an_atenea_rejection(monkeypatch: pytest.MonkeyPatch) -> None:
    def rejected_orion(case: dict[str, Any], *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {
            "estado": "RECHAZADO", "dictamen_tecnico": "RECHAZADO", "version_curva": case["version_curva"],
            "expediente": {"nash": {"estado": "CALCULO_COMPLETADO"}, "atenea": {"estado": "DICTAMEN_TECNICO_RECHAZADO"}},
            "traza": [{"etapa": "atenea", "estado": "DICTAMEN_TECNICO_RECHAZADO"}],
            "errores": [{"codigo": "CURVA_NO_VALIDADA", "mensaje": "Rechazada."}],
            "consumo": {"consumo_api_real_usd": 0.0, "costo_estimado_usd": None, "costo_infraestructura_usd": None},
        }

    monkeypatch.setattr(pipeline, "execute_orion", rejected_orion)
    result = run_demo()

    assert result["estado"] == "RECHAZADO"
    assert result["dictamen_tecnico"] == "RECHAZADO"
    assert result["requiere_aprobacion_humana"] is True
