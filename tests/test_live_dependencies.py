"""Pruebas con mocks de dependencias y runner LIVE; nunca usan red."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

import backend.live_dependencies as live
from backend.banxico_client import CURVE_REQUIRED_SERIES
from backend.elara_executor import ElaraResult, InvocationRecord
from backend.run_yieldcurve_live import compare_demo_and_live, sanitize_evidence
from backend.yieldcurve_pipeline import load_demo_siena, run_yieldcurve_case


CONFIG = {
    "budget_usd": 0.01,
    "time_limit_seconds": 30.0,
    "authorization_scope": "ORCHESTRATION_SIMULATED",
    "execution_authorized": True,
    "authorization_source": "TRUSTED_LOCAL_CONFIG",
    "max_llm_calls": 1,
}


class FakeElara:
    def __init__(self, output: dict[str, Any] | None, status: str = "VALID") -> None:
        self.output = output
        self.status = status
        self.calls = 0
        self.trusted_contexts: list[dict[str, str] | None] = []

    def run(self, _message: str, trusted_context: dict[str, str] | None = None) -> ElaraResult:
        self.calls += 1
        self.trusted_contexts.append(trusted_context)
        return ElaraResult(
            self.output,
            InvocationRecord("gpt-6-luna", "resp-test", 100, 20, 11, self.status, "API_ERROR" if self.status == "API_ERROR" else None, cached_input_tokens=10),
        )


def accepted_elara() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0", "decision": "ACEPTAR", "fecha_corte_normalizada": "2026-11-11",
        "instrumentos_solicitados": ["CETES", "MBONOS"], "proposito": "Valuación académica.",
        "datos_faltantes": [], "motivos_rechazo": [], "advertencias": [],
        "seguridad": {"inyeccion_prompt_detectada": False, "instrucciones_no_confiables_ignoradas": False},
    }


def run_live(elara: FakeElara, provider: Any, **overrides: Any) -> dict[str, Any]:
    options: dict[str, Any] = {
        "caso_id": "YC-LIVE20261111", "version_caso": 1, "version_curva": "CURVA-LIVE-20261111",
        "fecha_corte": "2026-11-11", "canal_origen": "manual",
        "solicitud": "Construye una curva CETES y M-Bonos para 2026-11-11.",
        "budget_config": deepcopy(CONFIG), "invocation_id": "live-test", "execution_mode": "LIVE",
        "elara_executor": elara, "siena_provider": provider,
    }
    options.update(overrides)
    return run_yieldcurve_case(**options)


def test_live_elara_factory_requires_key_without_constructing_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(live, "build_openai_client", lambda: pytest.fail("No debe crear cliente sin clave"))

    with pytest.raises(live.LiveDependencyError, match="OPENAI_API_KEY_NO_CONFIGURADA"):
        live.build_live_elara()


def test_live_elara_factory_uses_existing_executor_without_exposing_key(monkeypatch: pytest.MonkeyPatch) -> None:
    client = object()
    captured: dict[str, Any] = {}
    monkeypatch.setenv("OPENAI_API_KEY", "mock-value")
    monkeypatch.setattr(live, "build_openai_client", lambda: client)

    def fake_executor(received_client: Any, model: str) -> tuple[Any, str]:
        captured.update(client=received_client, model=model)
        return received_client, model

    monkeypatch.setattr(live, "ElaraExecutor", fake_executor)
    assert live.build_live_elara() == (client, "gpt-6-luna")
    assert captured == {"client": client, "model": "gpt-6-luna"}


def test_live_siena_provider_uses_exactly_the_authorized_curve_series(monkeypatch: pytest.MonkeyPatch) -> None:
    requested: list[tuple[str, list[str]]] = []
    monkeypatch.setenv("BANXICO_API_TOKEN", "mock-value")
    monkeypatch.setattr(live, "execute_siena", lambda fecha, series: requested.append((fecha, series)) or {"estado": "DATOS_INCOMPLETOS"})

    result = live.build_live_siena_provider()("2026-11-11")

    assert result == {"estado": "DATOS_INCOMPLETOS"}
    assert requested == [("2026-11-11", list(CURVE_REQUIRED_SERIES))]


def test_live_credentials_require_both_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("BANXICO_API_TOKEN", raising=False)
    with pytest.raises(live.LiveDependencyError, match="OPENAI_API_KEY_NO_CONFIGURADA"):
        live.require_live_credentials()
    monkeypatch.setenv("OPENAI_API_KEY", "mock-value")
    with pytest.raises(live.LiveDependencyError, match="BANXICO_API_TOKEN_NO_CONFIGURADO"):
        live.require_live_credentials()


def test_live_openai_failure_stops_before_siena_nash_and_atenea() -> None:
    provider_calls: list[str] = []
    result = run_live(FakeElara(None, "API_ERROR"), lambda date: provider_calls.append(date) or load_demo_siena(date))

    assert result["estado"] == "RECHAZADO"
    assert result["errores"][0]["codigo"] == "ELARA_API_ERROR"
    assert provider_calls == []
    assert result["nash"] is None and result["atenea"] is None


def test_live_banxico_failure_stops_before_nash_and_never_falls_back_to_demo() -> None:
    failure = {
        "estado": "DATOS_INCOMPLETOS", "fecha_corte": "2026-11-11", "observaciones": [],
        "errores": [{"codigo": "DATOS_BANXICO_NO_DISPONIBLES"}],
    }
    result = run_live(FakeElara(accepted_elara()), lambda _date: failure)

    assert result["estado"] == "RECHAZADO"
    assert result["errores"][0]["codigo"] == "DATOS_BANXICO_NO_DISPONIBLES"
    assert result["siena"] == failure
    assert result["nash"] is None and result["atenea"] is None
    assert result["fuente_datos"]["source_mode"] == "BANXICO_SIE_LIVE"


def test_live_keeps_identifiers_and_exposes_sanitized_measured_telemetry() -> None:
    result = run_live(FakeElara(accepted_elara()), load_demo_siena)

    assert result["estado"] == "PENDIENTE_APROBACION"
    assert result["caso_id"] == "YC-LIVE20261111"
    assert result["version_caso"] == 1
    assert result["fecha_corte"] == "2026-11-11"
    assert result["modo"] == "SIMULADO"
    assert result["telemetria"]["elara"] == {
        "agente": "Elara", "proveedor": "OpenAI", "modelo": "gpt-6-luna", "model": "gpt-6-luna", "response_id": "resp-test",
        "input_tokens": 100, "cached_input_tokens": 10, "output_tokens": 20, "total_tokens": 120,
        "cache_write_tokens": None, "ttl_30m_tokens": None, "ttl_12h_tokens": None,
        "duracion_ms": 11, "cost_usd": 0.0000191, "cost_status": "ESTIMATED_FROM_VERIFIED_RATE",
        "status": "VALID", "error_code": None, "diagnostico_validacion": None,
    }
    assert result["consumo"]["consumo_medido"]["input_tokens"] == 100
    assert result["consumo"]["costo_estimado_usd"] == "0.0000191"
    evidence = sanitize_evidence(result)
    assert "response_id" not in evidence["elara"]
    assert "mock-value" not in str(evidence)
    assert evidence["elara"]["decision"] == "ACEPTAR"
    assert evidence["elara"]["datos_faltantes"] == []


def test_live_requires_one_llm_call_limit_before_elara() -> None:
    fake = FakeElara(accepted_elara())
    result = run_live(fake, load_demo_siena, budget_config={**CONFIG, "max_llm_calls": 2})

    assert result["estado"] == "DETENIDO"
    assert result["errores"][0]["codigo"] == "LIMITE_LLM_INVALIDO"
    assert fake.calls == 0


def test_live_executes_exactly_one_llm_invocation() -> None:
    fake = FakeElara(accepted_elara())

    result = run_live(fake, load_demo_siena)

    assert result["estado"] == "PENDIENTE_APROBACION"
    assert fake.calls == 1


def test_demo_live_comparison_reports_equal_mocked_market_data_and_pillars() -> None:
    live_result = run_live(FakeElara(accepted_elara()), load_demo_siena)
    demo_result = run_yieldcurve_case(
        caso_id="YC-DEMO20261111", version_caso=1, version_curva="CURVA-DEMO-20261111",
        fecha_corte="2026-11-11", canal_origen="manual",
        solicitud="Construye una curva CETES y M-Bonos para 2026-11-11.",
        budget_config=CONFIG, invocation_id="demo-compare-test", execution_mode="DEMO",
    )

    comparison = compare_demo_and_live(demo_result, live_result)

    assert comparison["observaciones_coinciden"] is True
    assert comparison["pilares_coinciden_tolerancia"] is True
    assert comparison["diferencia_maxima_pilares"] == 0.0
