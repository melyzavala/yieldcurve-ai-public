"""Contratos sanitizados y trazables para resultados de casos.

No calcula curvas ni modifica decisiones. Proyecta resultados ya producidos.
Las tarifas se leen exclusivamente de ``costs/tarifas.csv``.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from typing import Any

from backend.cost_estimator import CostEstimationError, estimate_cost_usd, model_rates


def _mape_from_repricing(curve: Any) -> float | None:
    """Deterministic MAPE on repricing evidence; never substitutes absent inputs."""
    if not isinstance(curve, dict) or not isinstance(curve.get("repricing"), list):
        return None
    errors: list[float] = []
    for item in curve["repricing"]:
        if not isinstance(item, dict):
            continue
        observed = item.get("dirty_price_input", item.get("observed_price"))
        theoretical = item.get("dirty_price_theoretical", item.get("recalculated_price"))
        if not all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in (observed, theoretical)) or observed == 0:
            continue
        errors.append(abs((theoretical - observed) / observed) * 100)
    return sum(errors) / len(errors) if errors else None


ROOT = Path(__file__).resolve().parents[1]


def _tokens(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _elara_usage(telemetry: dict[str, Any]) -> dict[str, Any]:
    input_tokens = _tokens(telemetry.get("input_tokens"))
    output_tokens = _tokens(telemetry.get("output_tokens"))
    cached_input_tokens = _tokens(telemetry.get("cached_input_tokens"))
    cache_write_tokens = _tokens(telemetry.get("cache_write_tokens"))
    ttl_30m_tokens = _tokens(telemetry.get("ttl_30m_tokens"))
    ttl_12h_tokens = _tokens(telemetry.get("ttl_12h_tokens"))
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "cache_write_tokens": cache_write_tokens,
        "ttl_30m_tokens": ttl_30m_tokens,
        "ttl_12h_tokens": ttl_12h_tokens,
        "total_tokens": input_tokens + output_tokens if input_tokens is not None and output_tokens is not None else None,
    }


def _llm_component(telemetry: dict[str, Any], execution_mode: str) -> dict[str, Any]:
    model = telemetry.get("model", telemetry.get("modelo"))
    usage = _elara_usage(telemetry)
    is_live_llm = execution_mode == "LIVE" and telemetry.get("proveedor") == "OpenAI"
    component: dict[str, Any] = {
        "component": "ELARA", "type": "LLM" if is_live_llm else "LOCAL_RULES",
        "provider": telemetry.get("proveedor") if is_live_llm else "LOCAL", "model": model if is_live_llm else None,
        "api_calls": 1 if is_live_llm else 0, **usage,
        "estimated_cost_usd": None, "cost_usd": None,
        "pricing_status": "NOT_AVAILABLE", "cost_status": "NOT_OBSERVED_DEMO" if execution_mode == "DEMO" else "USAGE_UNAVAILABLE",
    }
    if not is_live_llm:
        component.update({key: None for key in usage})
        return component
    if usage["input_tokens"] is None or usage["output_tokens"] is None:
        return component
    try:
        rates = model_rates(ROOT / "costs" / "tarifas.csv", str(model))
        estimate = estimate_cost_usd(usage, rates)
    except CostEstimationError as error:
        component["cost_status"] = error.code
        return component
    except (OSError, ValueError):
        return component
    cost = float(Decimal(str(estimate["total_usd"])))
    component.update({
        "estimated_cost_usd": cost,
        "cost_usd": cost,
        "cost_status": "ESTIMATED_FROM_VERIFIED_RATE",
        "pricing_status": "AVAILABLE",
        "pricing_effective_date": rates["pricing_effective_date"],
        "pricing_source": rates["pricing_source"],
        "input_uncached_usd": estimate["input_uncached_usd"],
        "input_cached_usd": estimate["input_cached_usd"],
        "cache_write_30m_usd": estimate["cache_write_30m_usd"],
        "cache_write_12h_usd": estimate["cache_write_12h_usd"],
        "output_usd": estimate["output_usd"],
    })
    return component


def _fixed_component(component: str) -> dict[str, Any]:
    return {
        "component": component, "type": "DETERMINISTIC_COMPUTE", "provider": "LOCAL", "model": None,
        "api_calls": 0, "input_tokens": 0, "cached_input_tokens": 0, "cache_write_tokens": 0, "ttl_30m_tokens": 0, "ttl_12h_tokens": 0,
        "output_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0, "cost_usd": 0.0,
        "pricing_status": "NOT_APPLICABLE", "cost_status": "NOT_APPLICABLE",
    }


def build_cost_trace(result: dict[str, Any]) -> dict[str, Any]:
    """Build usage and direct-cost evidence without inventing absent usage or pricing."""
    execution_mode = result.get("execution_mode")
    telemetry = result.get("telemetria", {}).get("elara", {})
    elara = _llm_component(telemetry if isinstance(telemetry, dict) else {}, execution_mode)
    siena = result.get("siena") if isinstance(result.get("siena"), dict) else {}
    request_count = siena.get("request_count") if isinstance(siena.get("request_count"), int) else 0 if execution_mode == "DEMO" else None
    components = [
        _fixed_component("ORION"),
        elara,
        {"component": "SIENA", "type": "MARKET_DATA", "provider": "BANXICO", "model": None,
         "api_calls": request_count, "request_count": request_count, "input_tokens": 0, "cached_input_tokens": 0,
         "cache_write_tokens": 0, "ttl_30m_tokens": 0, "ttl_12h_tokens": 0, "output_tokens": 0, "total_tokens": 0,
         "source_mode": result.get("fuente_datos", {}).get("source_mode"), "estimated_cost_usd": None,
         "cost_usd": None, "pricing_status": "NOT_AVAILABLE", "cost_status": "NOT_PRICED"},
        _fixed_component("NASH"),
        _fixed_component("ATENEA"),
    ]
    known_costs = [item["cost_usd"] for item in components if isinstance(item.get("cost_usd"), (int, float))]
    not_priced = any(item.get("cost_status") == "NOT_PRICED" for item in components)
    observed_cost = any(item.get("cost_status") == "ESTIMATED_FROM_VERIFIED_RATE" for item in components)
    if not known_costs or not observed_cost:
        completeness = "UNAVAILABLE"
    elif not_priced:
        completeness = "PARTIAL"
    else:
        completeness = "COMPLETE"
    complete = completeness == "COMPLETE"
    inputs = [item["input_tokens"] for item in components]
    outputs = [item["output_tokens"] for item in components]
    total_input = sum(value for value in inputs if value is not None) if all(value is not None for value in inputs) else None
    total_output = sum(value for value in outputs if value is not None) if all(value is not None for value in outputs) else None
    total_tokens = sum(item["total_tokens"] for item in components if item["total_tokens"] is not None) if all(item["total_tokens"] is not None for item in components) else None
    known_cost = float(sum(Decimal(str(value)) for value in known_costs)) if observed_cost else None
    return {
        "currency": "USD", "pricing_status": "AVAILABLE" if complete else "PARTIAL" if observed_cost else "NOT_AVAILABLE",
        "components": components, "total_llm_calls": elara["api_calls"],
        "total_input_tokens": total_input, "total_output_tokens": total_output, "total_tokens": total_tokens,
        "input_tokens": total_input, "output_tokens": total_output,
        "known_cost_usd": known_cost, "cost_completeness": completeness,
        "total_variable_cost_usd": known_cost if complete else None,
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
        "indicadores": {
            "mape_repricing_pct": _mape_from_repricing(curve),
            "technical_valid_curves_pct": None,
            "technical_processing_minutes": None,
        },
        "trazabilidad": {"invocation_id": invocation_id},
        "decision_humana": {"approval_status": None, "decision_at": None},
    }
