"""Orquestación local y determinista de YieldCurve AI."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from backend.curve_quality_loop import run_curve_quality_loop
from backend.guardrails import valid_siena_for_downstream
from backend.security_cost_loop import run_security_cost_loop

ROOT = Path(__file__).resolve().parents[1]


def _schema(name: str) -> dict[str, Any]:
    return json.loads((ROOT / "agents" / "contracts" / name).read_text(encoding="utf-8"))


def _validate(name: str, value: Any) -> None:
    Draft202012Validator(_schema(name), format_checker=FormatChecker()).validate(value)


def _error(code: str, message: str) -> dict[str, str]:
    return {"codigo": code, "mensaje": message}


def _siena_reference(siena: dict[str, Any]) -> str:
    """Describe la procedencia sin confundir modo académico con datos ficticios."""
    source = siena.get("fuente", {}) if isinstance(siena, dict) else {}
    if source.get("proveedor") == "Banco de México" and source.get("datos_mercado") == "REALES":
        return "BANXICO_SIE_REAL"
    return "SIENA_DATOS_VALIDOS"


def execute_orion(case: dict[str, Any], elara: dict[str, Any], siena: dict[str, Any], curve_payload: dict[str, Any], config: dict[str, Any], invocation_id: str) -> dict[str, Any]:
    """Coordina especialistas locales sin alterar la aprobación humana del caso."""
    raw_case_id = case.get("caso_id") if isinstance(case, dict) else "YC-INVALIDO000"
    raw_version = case.get("version_caso") if isinstance(case, dict) else 1
    raw_curve_version = case.get("version_curva") if isinstance(case, dict) else None
    base = {"caso_id": raw_case_id, "version_caso": raw_version, "version_curva": raw_curve_version, "modo": "SIMULADO", "agente": "Orion", "requiere_aprobacion_humana": True, "expediente": {"elara": None, "siena": None, "nash": None, "atenea": None}, "traza": [], "consumo": {"consumo_api_real_usd": 0.0, "costo_estimado_usd": None, "costo_infraestructura_usd": None}}
    try:
        _validate("case.schema.json", case)
        if (not isinstance(config.get("budget_usd"), (int, float)) or isinstance(config["budget_usd"], bool) or not math.isfinite(config["budget_usd"]) or config["budget_usd"] < 0 or not isinstance(config.get("time_limit_seconds"), (int, float)) or isinstance(config["time_limit_seconds"], bool) or not math.isfinite(config["time_limit_seconds"]) or config["time_limit_seconds"] <= 0):
            raise ValueError("PRESUPUESTO_INVALIDO")
        security = run_security_cost_loop(case, config)
        base["traza"].append({"etapa": "seguridad_costos", "estado": security["estado"], "referencia": invocation_id})
        if security["estado"] != "COMPLETADO_SIMULADO":
            return _output({**base, "estado": "DETENIDO", "dictamen_tecnico": "NO_EMITIDO", "errores": [_error("PERMISO_O_PRESUPUESTO_INSUFICIENTE", "La ejecución local no está autorizada.")]})
        _validate("elara.output.schema.json", elara)
        base["expediente"]["elara"] = elara
        base["traza"].append({"etapa": "elara", "estado": elara["decision"], "referencia": None})
        if elara.get("seguridad", {}).get("inyeccion_prompt_detectada"):
            return _output({**base, "estado": "RECHAZADO", "dictamen_tecnico": "NO_EMITIDO", "errores": [_error("SOLICITUD_NO_CONFIABLE", "La solicitud fue detenida por controles de seguridad.")]})
        if elara["decision"] != "ACEPTAR":
            return _output({**base, "estado": "RECHAZADO", "dictamen_tecnico": "NO_EMITIDO", "errores": [_error("SOLICITUD_NO_ACEPTADA", "Elara no aceptó la solicitud.")]})
        if elara["fecha_corte_normalizada"] != case["fecha_corte"]:
            raise ValueError("FECHA_CORTE_INCONSISTENTE")
        _validate("siena.output.schema.json", siena)
        base["expediente"]["siena"] = siena
        base["traza"].append({"etapa": "siena", "estado": siena["estado"], "referencia": _siena_reference(siena)})
        if siena["fecha_corte"] != case["fecha_corte"]:
            raise ValueError("FECHA_CORTE_INCONSISTENTE")
        if any(observation.get("fecha") != case["fecha_corte"] for observation in siena["observaciones"]):
            raise ValueError("FECHA_OBSERVACION_INCONSISTENTE")
        if not valid_siena_for_downstream(siena, case["fecha_corte"]):
            return _output({**base, "estado": "RECHAZADO", "dictamen_tecnico": "NO_EMITIDO", "errores": [_error("DATOS_NO_VALIDOS", "Siena no entregó datos válidos para la fecha de corte.")]})
        if (curve_payload.get("case_id") != case["caso_id"] or curve_payload.get("curve_version") != case["version_curva"] or curve_payload.get("valuation_date") != case["fecha_corte"] or any(observation.get("fecha") != case["fecha_corte"] for observation in siena["observaciones"])):
            raise ValueError("IDENTIFICADORES_O_FECHAS_INCONSISTENTES")
        quality = run_curve_quality_loop(case, curve_payload, f"{invocation_id}-quality", inject_failure=config.get("inject_quality_failure", False) is True)
        base["traza"].extend({"etapa": "calidad_curva", "estado": item["atenea"], "referencia": item["version_curva"]} for item in quality["iterations"])
        base["expediente"]["nash"] = quality.get("nash_output")
        base["expediente"]["atenea"] = quality.get("atenea_output")
        if quality["estado"] != "VALIDADA":
            return _output({**base, "estado": "RECHAZADO", "dictamen_tecnico": "RECHAZADO", "errores": [_error("CURVA_NO_VALIDADA", "El loop de calidad no obtuvo un dictamen técnico válido.")]})
        final_iteration = quality["iterations"][-1]
        return _output({**base, "estado": "PENDIENTE_APROBACION", "version_curva": final_iteration["version_curva"], "dictamen_tecnico": "VALIDADO", "traza": base["traza"], "errores": []})
    except (ValidationError, ValueError, KeyError, TypeError):
        return _output({**base, "estado": "ERROR", "dictamen_tecnico": "NO_EMITIDO", "errores": [_error("ENTRADA_O_CONTRATO_INVALIDO", "El expediente no cumple los controles de orquestación.")]})


def _output(value: dict[str, Any]) -> dict[str, Any]:
    _validate("orion.output.schema.json", value)
    return value
