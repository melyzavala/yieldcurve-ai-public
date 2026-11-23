"""Loop determinista de seguridad y costos sin llamadas externas."""
from __future__ import annotations

import math
import time
from typing import Any

ALLOWED_ACTIONS = {"SIMULATED_VALIDATION"}


def _result(status: str, trace: list[dict[str, Any]]) -> dict[str, Any]:
    return {"estado": status, "traza": trace, "llamadas_llm": 0, "tokens_llm": 0, "consumo_api_real_usd": 0.0, "costo_infraestructura_usd": None}


def run_security_cost_loop(case: dict[str, Any], config: dict[str, Any], action: str = "SIMULATED_VALIDATION") -> dict[str, Any]:
    """Evalúa una acción simulada bajo política fail-closed."""
    started = time.monotonic()
    trace: list[dict[str, Any]] = []
    if not isinstance(case, dict) or not isinstance(config, dict):
        return _result("RECHAZADO_ENTRADA", trace)
    case_id = case.get("caso_id")
    budget = config.get("budget_usd")
    limit = config.get("time_limit_seconds", 30.0)
    if (not isinstance(case_id, str) or not case_id or isinstance(budget, bool) or not isinstance(budget, (int, float)) or not math.isfinite(budget) or budget < 0 or isinstance(limit, bool) or not isinstance(limit, (int, float)) or not math.isfinite(limit) or limit <= 0):
        return _result("RECHAZADO_ENTRADA", trace)
    if time.monotonic() - started > limit:
        return _result("LIMITE_TIEMPO", trace)
    approval = case.get("aprobacion_humana")
    human_approved = isinstance(approval, dict) and approval.get("estado") == "APROBADO"
    scoped_execution = (
        config.get("authorization_scope") == "ORCHESTRATION_SIMULATED"
        and config.get("execution_authorized") is True
        and config.get("authorization_source") == "TRUSTED_LOCAL_CONFIG"
    )
    approved = case.get("modo") == "SIMULADO" and (human_approved or scoped_execution)
    authorized = approved and action in ALLOWED_ACTIONS
    trace.append({"iteracion": 1, "caso_id": case_id, "accion": action, "allowlist": sorted(ALLOWED_ACTIONS), "autorizada": authorized, "llamadas_llm": 0, "tokens_llm": 0, "consumo_api_real_usd": 0.0, "costo_estimado_usd": None, "costo_infraestructura_usd": None})
    if not authorized:
        return _result("BLOQUEADO_SEGURIDAD_O_PRESUPUESTO", trace)
    return _result("COMPLETADO_SIMULADO", trace)
