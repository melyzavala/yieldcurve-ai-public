"""Contratos sanitizados y trazables para resultados de casos.

No calcula curvas ni modifica decisiones. Proyecta resultados ya producidos.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from typing import Any


PRICING = {
    "OpenAI": {
        "gpt-6-luna": {
            "pricing_version": "openai-standard-2026-11-19",
            "pricing_effective_date": "2026-11-19",
            "pricing_source": "https://platform.openai.com/pricing",
            "input_price_per_1m_tokens_usd": 0.10,
            "output_price_per_1m_tokens_usd": 0.50,
        }
    }
}


def _tokens(value: Any) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def _llm_component(telemetry: dict[str, Any], execution_mode: str) -> dict[str, Any]:
    model = telemetry.get("modelo")
    input_tokens, output_tokens = _tokens(telemetry.get("input_tokens")), _tokens(telemetry.get("output_tokens"))
    is_live_llm = execution_mode == "LIVE" and telemetry.get("proveedor") == "OpenAI"
    component: dict[str, Any] = {
        "component": "ELARA", "type": "LLM" if is_live_llm else "LOCAL_RULES",
        "provider": telemetry.get("proveedor") if is_live_llm else "LOCAL", "model": model if is_live_llm else None,
        "api_calls": 1 if is_live_llm else 0, "input_tokens": input_tokens if is_live_llm else None,
        "output_tokens": output_tokens if is_live_llm else None,
        "total_tokens": input_tokens + output_tokens if is_live_llm and input_tokens is not None and output_tokens is not None else None,
        "estimated_cost_usd": None, "pricing_status": "NOT_AVAILABLE",
    }
    rates = PRICING.get("OpenAI", {}).get(model) if is_live_llm else None
    if rates and input_tokens is not None and output_tokens is not None:
        cost = (Decimal(input_tokens) * Decimal(str(rates["input_price_per_1m_tokens_usd"])) + Decimal(output_tokens) * Decimal(str(rates["output_price_per_1m_tokens_usd"]))) / Decimal(1_000_000)
        component.update({**rates, "estimated_cost_usd": float(cost), "pricing_status": "AVAILABLE"})
    return component


def build_cost_trace(result: dict[str, Any]) -> dict[str, Any]:
    """Builds usage and direct-cost evidence without estimating missing values."""
    execution_mode = result.get("execution_mode")
    telemetry = result.get("telemetria", {}).get("elara", {})
    elara = _llm_component(telemetry if isinstance(telemetry, dict) else {}, execution_mode)
    siena = result.get("siena") if isinstance(result.get("siena"), dict) else {}
    source = siena.get("fuente", {}) if isinstance(siena, dict) else {}
    request_count = siena.get("request_count") if isinstance(siena.get("request_count"), int) else 0 if execution_mode == "DEMO" else None
    components = [
        elara,
        {"component": "SIENA", "type": "MARKET_DATA", "provider": "BANXICO", "model": None, "api_calls": request_count, "request_count": request_count, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "source_mode": result.get("fuente_datos", {}).get("source_mode"), "estimated_cost_usd": None, "pricing_status": "NOT_AVAILABLE"},
        {"component": "NASH", "type": "DETERMINISTIC_COMPUTE", "provider": "LOCAL", "model": None, "api_calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0, "pricing_status": "NOT_APPLICABLE"},
        {"component": "ATENEA", "type": "DETERMINISTIC_COMPUTE", "provider": "LOCAL", "model": None, "api_calls": 0, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0, "pricing_status": "NOT_APPLICABLE"},
    ]
    known = [item["estimated_cost_usd"] for item in components]
    complete = all(value is not None for value in known)
    inputs = [item["input_tokens"] for item in components]
    outputs = [item["output_tokens"] for item in components]
    return {
        "currency": "USD", "pricing_status": "AVAILABLE" if complete else "PARTIAL" if any(value is not None for value in known) else "NOT_AVAILABLE",
        "components": components, "total_llm_calls": elara["api_calls"],
        "total_input_tokens": sum(value for value in inputs if value is not None) if all(value is not None for value in inputs) else None,
        "total_output_tokens": sum(value for value in outputs if value is not None) if all(value is not None for value in outputs) else None,
        "total_tokens": sum(item["total_tokens"] for item in components if item["total_tokens"] is not None) if all(item["total_tokens"] is not None for item in components) else None,
        "total_variable_cost_usd": float(sum(Decimal(str(value)) for value in known)) if complete else None,
        "fixed_platform_costs_included": False,
    }


def build_case_artifact(public: dict[str, Any], cost_trace: dict[str, Any], invocation_id: str | None) -> dict[str, Any]:
    """Creates the presentation/audit source without secrets or recalculation."""
    curve = public.get("resultado_curva")
    return {
        "caso_id": public.get("caso_id"), "version_caso": public.get("version_caso"), "version_curva": public.get("version_curva"),
        "fecha_corte": public.get("fecha_corte"), "execution_mode": public.get("execution_mode"), "estado": public.get("estado"),
        "requiere_aprobacion_humana": public.get("requiere_aprobacion_humana"), "agentes": deepcopy(public.get("agentes", {})),
        "fuente_datos": {"source_mode": public.get("fuente_datos", {}).get("source_mode")},
        "curva": deepcopy(curve) if isinstance(curve, dict) else None,
        "auditoria": deepcopy(public.get("auditoria")), "cost_trace": deepcopy(cost_trace),
        "trazabilidad": {"invocation_id": invocation_id},
        "decision_humana": {"approval_status": None, "decision_at": None},
    }
