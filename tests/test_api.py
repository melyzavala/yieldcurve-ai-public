"""Pruebas sin red para el adaptador HTTP de YieldCurve AI."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi.testclient import TestClient

import backend.api as api
from backend.elara_executor import ElaraResult, InvocationRecord
from backend.live_dependencies import LiveDependencyError
from backend.yieldcurve_pipeline import load_demo_siena


KEY = "test-server-key"
HEADERS = {"X-YieldCurve-Key": KEY}
PAYLOAD = {
    "caso_id": "YC-API20261111",
    "version_caso": 1,
    "version_curva": "CURVA-API-20261111",
    "fecha_corte": "2026-11-11",
    "canal_origen": "api",
    "solicitud": "Construye una curva CETES y M-Bonos para 2026-11-11 para un portafolio ficticio.",
    "execution_mode": "DEMO",
    "invocation_id": "api-test-20261111",
}


def client(monkeypatch) -> TestClient:
    monkeypatch.setenv("YIELDCURVE_API_KEY", KEY)
    return TestClient(api.app)


def accepted_elara() -> dict[str, Any]:
    return {
        "schema_version": "1.0.0", "decision": "ACEPTAR", "fecha_corte_normalizada": "2026-11-11",
        "instrumentos_solicitados": ["CETES", "MBONOS"], "proposito": "Valuación académica ficticia.",
        "datos_faltantes": [], "motivos_rechazo": [], "advertencias": [],
        "seguridad": {"inyeccion_prompt_detectada": False, "instrucciones_no_confiables_ignoradas": False},
    }


class FakeElara:
    def __init__(self, output: dict[str, Any] | None = None) -> None:
        self.output = output or accepted_elara()
        self.contexts: list[dict[str, str] | None] = []

    def run(self, _message: str, trusted_context: dict[str, str] | None = None) -> ElaraResult:
        self.contexts.append(trusted_context)
        return ElaraResult(self.output, InvocationRecord("TEST_LOCAL", None, None, None, 0, "VALID"))


def test_health_is_public_and_does_not_invoke_pipeline(monkeypatch) -> None:
    monkeypatch.setattr(api, "run_yieldcurve_case", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("No pipeline")))

    response = TestClient(api.app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "yieldcurve-ai", "version": api.SERVICE_VERSION}


def test_post_requires_valid_api_key(monkeypatch) -> None:
    test_client = client(monkeypatch)

    assert test_client.post("/v1/orion/run", json=PAYLOAD).status_code == 401
    assert test_client.post("/v1/orion/run", json=PAYLOAD, headers={"X-YieldCurve-Key": "incorrecta"}).status_code == 401


def test_post_rejects_invalid_payload_and_extra_fields(monkeypatch) -> None:
    test_client = client(monkeypatch)
    invalid = {**PAYLOAD, "execution_mode": "PRODUCCION"}
    extra = {**PAYLOAD, "execution_authorized": True}
    extra_source = {**PAYLOAD, "authorization_source": "TRUSTED_LOCAL_CONFIG"}

    assert test_client.post("/v1/orion/run", json=invalid, headers=HEADERS).status_code == 422
    assert test_client.post("/v1/orion/run", json=extra, headers=HEADERS).status_code == 422
    assert test_client.post("/v1/orion/run", json=extra_source, headers=HEADERS).status_code == 422


def test_demo_runs_without_live_factories_or_network(monkeypatch) -> None:
    test_client = client(monkeypatch)
    monkeypatch.setattr(api, "build_live_elara", lambda: (_ for _ in ()).throw(AssertionError("No OpenAI en DEMO")))
    monkeypatch.setattr(api, "build_live_siena_provider", lambda: (_ for _ in ()).throw(AssertionError("No Banxico en DEMO")))

    response = test_client.post("/v1/orion/run", json=PAYLOAD, headers=HEADERS)

    body = response.json()
    assert response.status_code == 200
    assert body["estado"] == "PENDIENTE_APROBACION"
    assert body["fuente_datos"]["source_mode"] == "FIXTURE_BANXICO_2026-11-11"
    assert body["requiere_aprobacion_humana"] is True
    assert body["resultado_curva"] is not None
    assert body["resultado_curva"]["pillars"]
    assert body["resultado_curva"]["instrument_count"] == len(body["resultado_curva"]["pillars"])
    assert body["auditoria"] == {
        "tecnicamente_valida": True, "tolerancia": 1e-8, "requiere_aprobacion_humana": True,
    }


def test_live_reuses_mocked_existing_dependencies_and_preserves_invocation(monkeypatch) -> None:
    test_client = client(monkeypatch)
    fake_elara = FakeElara()
    captured: dict[str, Any] = {}
    monkeypatch.setattr(api, "build_live_elara", lambda: fake_elara)
    monkeypatch.setattr(api, "build_live_siena_provider", lambda: load_demo_siena)
    original = api.run_yieldcurve_case

    def captured_pipeline(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(api, "run_yieldcurve_case", captured_pipeline)
    response = test_client.post("/v1/orion/run", json={**PAYLOAD, "execution_mode": "LIVE"}, headers=HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["estado"] == "PENDIENTE_APROBACION"
    assert body["resultado_curva"] is not None and body["resultado_curva"]["pillars"]
    assert body["auditoria"]["tecnicamente_valida"] is True
    assert captured["invocation_id"] == PAYLOAD["invocation_id"]
    assert captured["execution_mode"] == "LIVE"
    assert fake_elara.contexts == [{"modo": "SIMULADO", "fecha_corte": "2026-11-11", "canal_origen": "api"}]


def test_live_missing_dependency_is_controlled_and_never_falls_back(monkeypatch) -> None:
    test_client = client(monkeypatch)
    monkeypatch.setattr(api, "build_live_elara", lambda: (_ for _ in ()).throw(LiveDependencyError("OPENAI_API_KEY_NO_CONFIGURADA")))
    monkeypatch.setattr(api, "run_yieldcurve_case", lambda **_kwargs: (_ for _ in ()).throw(AssertionError("No fallback")))

    response = test_client.post("/v1/orion/run", json={**PAYLOAD, "execution_mode": "LIVE"}, headers=HEADERS)

    assert response.status_code == 503
    assert response.json() == {"detail": "Dependencia LIVE no disponible."}


def test_business_clarification_rejection_and_siena_failure_remain_http_200(monkeypatch) -> None:
    test_client = client(monkeypatch)
    base = {
        "caso_id": PAYLOAD["caso_id"], "version_caso": 1, "version_curva": PAYLOAD["version_curva"],
        "fecha_corte": "2026-11-11", "modo": "SIMULADO", "execution_mode": "DEMO",
        "dictamen_tecnico": "NO_EMITIDO", "requiere_aprobacion_humana": True,
        "elara": None, "siena": None, "nash": None, "atenea": None,
        "fuente_datos": {"execution_mode": "DEMO", "source_mode": "NOT_QUERIED"},
        "traza": [], "advertencias": [], "errores": [], "consumo": {}, "telemetria": {},
    }
    cases = [
        ("PENDIENTE_ACLARACION", "SOLICITAR_ACLARACION", None),
        ("RECHAZADO", "RECHAZAR", None),
        ("RECHAZADO", "ACEPTAR", {"estado": "DATOS_INCOMPLETOS"}),
    ]
    for state, decision, siena in cases:
        result = deepcopy(base)
        result["estado"] = state
        result["elara"] = {**accepted_elara(), "decision": decision}
        if decision == "SOLICITAR_ACLARACION":
            result["elara"]["datos_faltantes"] = ["FECHA_CORTE"]
        if decision == "RECHAZAR":
            result["elara"]["motivos_rechazo"] = [{"codigo": "FUERA_ALCANCE", "severidad": "ERROR", "mensaje": "Rechazada."}]
        result["siena"] = siena
        monkeypatch.setattr(api, "run_yieldcurve_case", lambda **_kwargs: result)
        response = test_client.post("/v1/orion/run", json=PAYLOAD, headers=HEADERS)
        assert response.status_code == 200
        assert response.json()["estado"] == state
        assert response.json()["resultado_curva"] is None
        assert response.json()["auditoria"] is None


def test_sanitized_response_omits_secrets_headers_prompts_and_response_id(monkeypatch) -> None:
    test_client = client(monkeypatch)
    result = {
        "caso_id": PAYLOAD["caso_id"], "version_caso": 1, "version_curva": PAYLOAD["version_curva"],
        "fecha_corte": "2026-11-11", "modo": "SIMULADO", "execution_mode": "DEMO",
        "estado": "PENDIENTE_ACLARACION", "dictamen_tecnico": "NO_EMITIDO", "requiere_aprobacion_humana": True,
        "elara": {**accepted_elara(), "decision": "SOLICITAR_ACLARACION", "datos_faltantes": ["FECHA_CORTE"]},
        "siena": None,
        "nash": {"resultado_curva": {"instrument_count": 99, "max_absolute_repricing_error": 0.0, "pillars": [{"instrument_id": "M1", "spot_rate": 0.08, "evidencia_skill": "privada", "hash": "interno"}]}, "evidencia_skill": {"skill_sha256": "interno"}},
        "atenea": {"dictamen": {"tecnicamente_valida": False, "tolerancia": 1e-8, "requiere_aprobacion_humana": True}, "evidencia": {"hash": "interno"}},
        "fuente_datos": {"source_mode": "NOT_QUERIED"},
        "traza": [{"etapa": "elara", "estado": "VALID", "prompt": "privado"}], "advertencias": [], "errores": [], "consumo": {},
        "telemetria": {"elara": {"response_id": "resp-private", "status": "VALID", "error_code": None}},
    }
    monkeypatch.setattr(api, "run_yieldcurve_case", lambda **_kwargs: result)

    response = test_client.post("/v1/orion/run", json=PAYLOAD, headers=HEADERS)

    text = response.text
    assert response.status_code == 200
    assert "resp-private" not in text and "privado" not in text and KEY not in text
    assert "evidencia_skill" not in text and "interno" not in text and '"hash"' not in text
    assert response.json()["agentes"]["elara"]["datos_faltantes"] == ["FECHA_CORTE"]
    assert response.json()["resultado_curva"]["instrument_count"] == 99
