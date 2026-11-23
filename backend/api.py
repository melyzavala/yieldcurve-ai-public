"""Adaptador HTTP stateless para el pipeline ya validado de YieldCurve AI."""

from __future__ import annotations

import os
import secrets
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import Response

from backend.api_models import ExecutionMode, OrionRunRequest, OrionRunResponse
from backend.live_dependencies import LiveDependencyError, build_live_elara, build_live_siena_provider
from backend.yieldcurve_pipeline import run_yieldcurve_case
from backend.case_artifacts import build_case_artifact, build_cost_trace
from backend.case_excel import build_case_workbook
from backend.curve_visualization import build_curve_png


SERVICE_VERSION = "0.1.0"
TRUSTED_AUTHORIZATION_SOURCE = "TRUSTED_LOCAL_CONFIG"
DEMO_BUDGET = {
    "budget_usd": 0.0,
    "time_limit_seconds": 30.0,
    "authorization_scope": "ORCHESTRATION_SIMULATED",
    "execution_authorized": True,
    "authorization_source": TRUSTED_AUTHORIZATION_SOURCE,
    "max_llm_calls": 1,
}
LIVE_BUDGET = {
    "budget_usd": 0.01,
    "time_limit_seconds": 30.0,
    "authorization_scope": "ORCHESTRATION_SIMULATED",
    "execution_authorized": True,
    "authorization_source": TRUSTED_AUTHORIZATION_SOURCE,
    "max_llm_calls": 1,
}

app = FastAPI(
    title="YieldCurve AI API",
    version=SERVICE_VERSION,
    description="Interfaz académica en modo SIMULADO; no aprueba operaciones ni recomendaciones de inversión.",
    debug=False,
)


def require_api_key(x_yieldcurve_key: str | None = Header(default=None)) -> None:
    """Autentica llamadas server-to-server sin exponer el secreto configurado."""
    configured_key = os.environ.get("YIELDCURVE_API_KEY")
    if not configured_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Servicio no configurado.")
    if not x_yieldcurve_key or not secrets.compare_digest(x_yieldcurve_key, configured_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autorizado.")


def _agent_state(result: dict[str, Any], name: str, key: str = "estado") -> dict[str, Any] | None:
    output = result.get(name)
    if not isinstance(output, dict):
        return None
    agent: dict[str, Any] = {"estado": output.get(key)}
    if name == "elara":
        agent["decision"] = output.get("decision")
        agent["datos_faltantes"] = output.get("datos_faltantes", [])
    return agent


_PUBLIC_PILLAR_FIELDS = (
    "instrument_id", "days", "time_years", "spot_rate", "discount_factor",
    "observed_price", "recalculated_price", "dirty_price_theoretical",
    "iterations", "converged",
)


def _public_curve(result: dict[str, Any]) -> dict[str, Any] | None:
    """Proyecta, sin recalcular, los datos cuantitativos ya producidos por Nash."""
    nash = result.get("nash")
    curve = nash.get("resultado_curva") if isinstance(nash, dict) else None
    if not isinstance(curve, dict) or not isinstance(curve.get("pillars"), list):
        return None
    pillars = [
        {field: item[field] for field in _PUBLIC_PILLAR_FIELDS if field in item}
        for item in curve["pillars"] if isinstance(item, dict)
    ]
    return {
        "instrument_count": curve.get("instrument_count"),
        "max_absolute_repricing_error": curve.get("max_absolute_repricing_error"),
        "interpolation_method": curve.get("interpolation_method"),
        "metodologia": curve.get("metodologia"),
        "pillars": pillars,
    }


def _public_audit(result: dict[str, Any]) -> dict[str, Any] | None:
    """Expone únicamente el dictamen de Atenea, no su evidencia interna."""
    atenea = result.get("atenea")
    audit = atenea.get("dictamen") if isinstance(atenea, dict) else None
    if not isinstance(audit, dict):
        return None
    return {
        "tecnicamente_valida": audit.get("tecnicamente_valida"),
        "tolerancia": audit.get("tolerancia"),
        "requiere_aprobacion_humana": audit.get("requiere_aprobacion_humana"),
    }


def sanitize_pipeline_result(result: dict[str, Any], invocation_id: str | None = None) -> dict[str, Any]:
    """Expone sólo evidencia operativa; mantiene el resultado interno intacto."""
    telemetry = result.get("telemetria", {})
    elara_telemetry = telemetry.get("elara", {}) if isinstance(telemetry, dict) else {}
    safe_telemetry = {
        "elara": {
            "agente": elara_telemetry.get("agente"),
            "proveedor": elara_telemetry.get("proveedor"),
            "modelo": elara_telemetry.get("modelo"),
            "input_tokens": elara_telemetry.get("input_tokens"),
            "cached_input_tokens": elara_telemetry.get("cached_input_tokens"),
            "output_tokens": elara_telemetry.get("output_tokens"),
            "duracion_ms": elara_telemetry.get("duracion_ms"),
            "status": elara_telemetry.get("status"),
            "error_code": elara_telemetry.get("error_code"),
            "diagnostico_validacion": elara_telemetry.get("diagnostico_validacion"),
        }
    }
    public = {
        "caso_id": result.get("caso_id"), "version_caso": result.get("version_caso"),
        "version_curva": result.get("version_curva"), "fecha_corte": result.get("fecha_corte"),
        "modo": result.get("modo"), "execution_mode": result.get("execution_mode"),
        "estado": result.get("estado"), "dictamen_tecnico": result.get("dictamen_tecnico"),
        "requiere_aprobacion_humana": result.get("requiere_aprobacion_humana"),
        "resultado_curva": _public_curve(result), "auditoria": _public_audit(result),
        "agentes": {
            "elara": _agent_state(result, "elara", "decision"),
            "siena": _agent_state(result, "siena"),
            "nash": _agent_state(result, "nash"),
            "atenea": _agent_state(result, "atenea"),
        },
        "fuente_datos": result.get("fuente_datos", {}),
        "traza": [
            {"etapa": item.get("etapa"), "estado": item.get("estado")}
            for item in result.get("traza", []) if isinstance(item, dict)
        ],
        "advertencias": result.get("advertencias", []), "errores": result.get("errores", []),
        "consumo": result.get("consumo", {}), "telemetria": safe_telemetry,
    }
    cost_trace = build_cost_trace(result)
    public["cost_trace"] = cost_trace
    public["case_artifact"] = build_case_artifact(public, cost_trace, invocation_id)
    return public


@app.get("/health")
def health() -> dict[str, str]:
    """Disponibilidad del transporte HTTP; no invoca el pipeline ni dependencias."""
    return {"status": "ok", "service": "yieldcurve-ai", "version": SERVICE_VERSION}

@app.post("/v1/artifacts/excel", dependencies=[Depends(require_api_key)])
def build_excel(case_artifact: dict[str, Any]) -> Response:
    try:
        content = build_case_workbook(case_artifact)
        name = "".join(char for char in str(case_artifact["caso_id"]) if char.isalnum() or char in "-_")
        date = "".join(char for char in str(case_artifact.get("fecha_corte", "")) if char.isdigit() or char == "-")
    except (KeyError, ValueError):
        raise HTTPException(status_code=422, detail="case_artifact inválido o sensible.") from None
    return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="YieldCurve_{name}_{date}.xlsx"'})

@app.post("/v1/artifacts/curve.png", dependencies=[Depends(require_api_key)])
def build_curve_image(case_artifact: dict[str, Any]) -> Response:
    try:
        content = build_curve_png(case_artifact); name="".join(c for c in str(case_artifact["caso_id"]) if c.isalnum() or c in "-_"); date="".join(c for c in str(case_artifact.get("fecha_corte","")) if c.isdigit() or c=="-")
    except (KeyError, ValueError): raise HTTPException(status_code=422, detail="case_artifact inválido o sensible.") from None
    return Response(content,media_type="image/png",headers={"Content-Disposition":f'inline; filename="YieldCurve_{name}_{date}.png"'})


@app.post("/v1/orion/run", response_model=OrionRunResponse, dependencies=[Depends(require_api_key)])
def run_orion(request: OrionRunRequest) -> dict[str, Any]:
    """Ejecuta una única solicitud; la API no aprueba resultados ni reintenta."""
    values = request.model_dump(mode="json")
    mode = request.execution_mode
    elara_executor = None
    siena_provider = None
    budget = DEMO_BUDGET
    if mode is ExecutionMode.LIVE:
        try:
            elara_executor = build_live_elara()
            siena_provider = build_live_siena_provider()
        except LiveDependencyError:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Dependencia LIVE no disponible.") from None
        budget = LIVE_BUDGET
    try:
        result = run_yieldcurve_case(
            caso_id=values["caso_id"], version_caso=values["version_caso"],
            version_curva=values["version_curva"], fecha_corte=values["fecha_corte"],
            canal_origen=values["canal_origen"], solicitud=values["solicitud"],
            budget_config=budget, invocation_id=values["invocation_id"],
            execution_mode=mode.value, elara_executor=elara_executor, siena_provider=siena_provider,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno del servicio.") from None
    return sanitize_pipeline_result(result, values["invocation_id"])
