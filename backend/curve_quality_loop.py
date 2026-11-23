"""Loop Nash → Atenea con corrección determinista, limitado y sin LLM."""

from __future__ import annotations

import copy
import math
import time
from typing import Any

from backend.atenea_executor import execute_atenea
from backend.excel_bootstrap import METHODOLOGY as EXCEL_METHODOLOGY
from backend.nash_executor import execute_nash


MAX_ITERATIONS = 3
MAX_SECONDS = 30.0
PCHIP_METHODOLOGY = "PCHIP_LOG_DISCOUNT_FACTOR"


def _inject_controlled_failure(nash: dict[str, Any]) -> bool:
    """Altera sólo el resultado de V1; nunca la entrada original del caso."""
    result = nash.get("resultado_curva")
    if not isinstance(result, dict) or not isinstance(result.get("pillars"), list) or not result["pillars"]:
        return False
    methodology = result.get("metodologia") or result.get("interpolation_method")
    final_pillar = result["pillars"][-1]
    if methodology == EXCEL_METHODOLOGY:
        rate = final_pillar.get("spot_rate")
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate):
            return False
        final_pillar["spot_rate"] = float(rate) + 0.01
        return True
    if methodology == PCHIP_METHODOLOGY:
        factor = final_pillar.get("discount_factor")
        if isinstance(factor, bool) or not isinstance(factor, (int, float)) or not math.isfinite(factor) or factor <= 0:
            return False
        final_pillar["discount_factor"] = float(factor) * 0.9
        return True
    return False


def run_curve_quality_loop(case: dict[str, Any], original: dict[str, Any], invocation_prefix: str, inject_failure: bool = True) -> dict[str, Any]:
    """Reconstruye cada versión desde ``original`` y se detiene de forma fail-closed."""
    started = time.monotonic()
    trace: list[dict[str, Any]] = []
    payload = copy.deepcopy(original)
    for iteration in range(1, MAX_ITERATIONS + 1):
        iteration_started = time.monotonic()
        if time.monotonic() - started > MAX_SECONDS:
            return {"estado": "LIMITE_TIEMPO", "iterations": trace, "costo_adicional_usd": 0.0, "duracion_segundos": time.monotonic() - started}
        payload["curve_version"] = f"{original['curve_version']}-V{iteration}"
        current = copy.deepcopy(case)
        current["version_curva"] = payload["curve_version"]
        nash = execute_nash(current, payload, f"{invocation_prefix}-nash-{iteration}")
        result = nash.get("resultado_curva")
        methodology = result.get("metodologia") or result.get("interpolation_method") if isinstance(result, dict) else None
        if nash.get("estado") != "CALCULO_COMPLETADO":
            trace.append({"iteracion": iteration, "caso_id": current.get("caso_id", "YC-INVALIDO000"), "version_curva": payload["curve_version"], "metodologia": methodology, "nash": nash.get("estado", "CALCULO_RECHAZADO"), "atenea": "NO_EJECUTADA", "diagnostico": nash.get("errores", []), "reconstruida_desde_entrada_original": True, "duracion_segundos": time.monotonic() - iteration_started, "tokens_llm": 0, "costo_adicional_usd": 0.0})
            return {"estado": "RECHAZADA_NASH", "iterations": trace, "nash_output": nash, "atenea_output": None, "costo_adicional_usd": 0.0, "duracion_segundos": time.monotonic() - started}
        if iteration == 1 and inject_failure and not _inject_controlled_failure(nash):
            trace.append({"iteracion": iteration, "caso_id": current["caso_id"], "version_curva": payload["curve_version"], "metodologia": methodology, "nash": nash["estado"], "atenea": "NO_EJECUTADA", "diagnostico": [{"codigo": "METODOLOGIA_NO_INYECTABLE", "mensaje": "No fue posible aplicar la prueba controlada de calidad."}], "reconstruida_desde_entrada_original": True, "duracion_segundos": time.monotonic() - iteration_started, "tokens_llm": 0, "costo_adicional_usd": 0.0})
            return {"estado": "RECHAZADA_NASH", "iterations": trace, "nash_output": nash, "atenea_output": None, "costo_adicional_usd": 0.0, "duracion_segundos": time.monotonic() - started}
        atenea = execute_atenea(current, nash, payload, f"{invocation_prefix}-atenea-{iteration}")
        trace.append({"iteracion": iteration, "caso_id": current["caso_id"], "version_curva": payload["curve_version"], "metodologia": methodology, "nash": nash["estado"], "atenea": atenea["estado"], "diagnostico": atenea["errores"], "reconstruida_desde_entrada_original": True, "duracion_segundos": time.monotonic() - iteration_started, "tokens_llm": 0, "costo_adicional_usd": 0.0, "evidencia_nash": nash.get("evidencia_skill"), "evidencia_atenea": atenea.get("evidencia")})
        if atenea["estado"] == "DICTAMEN_TECNICO_VALIDADO":
            return {"estado": "VALIDADA", "iterations": trace, "nash_output": nash, "atenea_output": atenea, "costo_adicional_usd": 0.0, "duracion_segundos": time.monotonic() - started}
    return {"estado": "LIMITE_ITERACIONES", "iterations": trace, "costo_adicional_usd": 0.0, "duracion_segundos": time.monotonic() - started}
