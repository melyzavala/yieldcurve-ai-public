from copy import deepcopy

from backend.case_artifacts import build_case_artifact, build_cost_trace
from backend.yieldcurve_pipeline import run_yieldcurve_case


def live_result() -> dict:
    return {"execution_mode": "LIVE", "fuente_datos": {"source_mode": "BANXICO_SIE_LIVE"}, "telemetria": {"elara": {"proveedor": "OpenAI", "modelo": "gpt-6-luna", "input_tokens": 100, "output_tokens": 50}}, "siena": {"request_count": 26}}


def test_provider_usage_and_official_pricing_are_recorded() -> None:
    trace = build_cost_trace(live_result())
    elara = next(item for item in trace["components"] if item["component"] == "ELARA")
    assert elara["input_tokens"] == 100 and elara["output_tokens"] == 50
    assert elara["api_calls"] == 1 and elara["pricing_status"] == "AVAILABLE"
    assert elara["estimated_cost_usd"] == 0.000035
    assert elara["cost_usd"] == 0.000035
    assert elara["cost_status"] == "ESTIMATED_FROM_VERIFIED_RATE"
    assert trace["known_cost_usd"] == 0.000035
    assert trace["cost_completeness"] == "PARTIAL"
    assert trace["total_variable_cost_usd"] is None
    assert trace["input_tokens"] == trace["total_input_tokens"] == 100
    assert trace["output_tokens"] == trace["total_output_tokens"] == 50


def test_missing_usage_or_pricing_never_invents_tokens_or_cost() -> None:
    result = live_result(); result["telemetria"]["elara"]["input_tokens"] = None
    trace = build_cost_trace(result)
    elara = next(item for item in trace["components"] if item["component"] == "ELARA")
    assert elara["estimated_cost_usd"] is None
    assert elara["input_tokens"] is None
    assert elara["cost_status"] == "USAGE_UNAVAILABLE"
    assert trace["known_cost_usd"] is None
    assert trace["cost_completeness"] == "UNAVAILABLE"
    assert trace["total_variable_cost_usd"] is None


def test_siena_and_deterministic_components_have_truthful_usage() -> None:
    trace = build_cost_trace(live_result())
    siena = next(item for item in trace["components"] if item["component"] == "SIENA")
    assert siena["request_count"] == 26
    assert siena["estimated_cost_usd"] is None
    assert siena["cost_status"] == "NOT_PRICED"
    for name in ("ORION", "NASH", "ATENEA"):
        component = next(item for item in trace["components"] if item["component"] == name)
        assert component["cost_usd"] == 0.0 and component["cost_status"] == "NOT_APPLICABLE"


def test_cached_input_is_not_charged_twice() -> None:
    result = live_result()
    result["telemetria"]["elara"]["cached_input_tokens"] = 10
    result["telemetria"]["elara"]["output_tokens"] = 20
    trace = build_cost_trace(result)
    elara = next(item for item in trace["components"] if item["component"] == "ELARA")
    assert elara["total_tokens"] == 120
    assert elara["cost_usd"] == 0.0000191
    assert elara["input_uncached_usd"] == "0.000009"
    assert elara["input_cached_usd"] == "1E-7"


def test_artifact_copies_pillars_and_excludes_sensitive_fields() -> None:
    public = {"caso_id": "YC-CASE1234", "version_caso": 1, "version_curva": "CURVA-CASE1234", "fecha_corte": "2026-11-11", "execution_mode": "DEMO", "estado": "PENDIENTE_APROBACION", "requiere_aprobacion_humana": True, "agentes": {}, "fuente_datos": {"source_mode": "FIXTURE"}, "auditoria": {"tecnicamente_valida": True}, "resultado_curva": {"pillars": [{"instrument_id": "C28", "spot_rate": .1}]}}
    artifact = build_case_artifact(public, build_cost_trace({"execution_mode": "DEMO"}), "inv-1")
    assert artifact["curva"]["pillars"] == public["resultado_curva"]["pillars"]
    assert artifact["curva"]["pillars"] is not public["resultado_curva"]["pillars"]
    text = str(artifact).lower()
    for forbidden in ("telegram_user_id", "api_key", "x-yieldcurve-key", "prompt", "secret"):
        assert forbidden not in text


def test_demo_has_no_simulated_llm_usage() -> None:
    result = run_yieldcurve_case(caso_id="YC-ARTIFACT01", version_caso=1, version_curva="CURVA-ARTIFACT01", fecha_corte="2026-11-11", canal_origen="api", solicitud="Construye una curva CETES y M-Bonos para 2026-11-11 para un portafolio ficticio.", budget_config={"execution_authorized": True, "budget_usd": 0, "time_limit_seconds": 30}, invocation_id="artifact-demo")
    trace = build_cost_trace(result)
    elara = next(item for item in trace["components"] if item["component"] == "ELARA")
    assert elara["api_calls"] == 0
    assert elara["input_tokens"] is None
    assert elara["cost_status"] == "NOT_OBSERVED_DEMO"
    assert trace["cost_completeness"] == "UNAVAILABLE"
