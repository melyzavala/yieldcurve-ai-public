"""Ejecutor determinista de Nash que evidencia el uso de build-spot-curve."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from backend.build_spot_curve_adapter import apply_build_spot_curve
from backend.excel_bootstrap import METHODOLOGY
from backend.guardrails import validate_quantitative_payload


ROOT = Path(__file__).resolve().parents[1]
NASH_PATH = ROOT / "agents" / "nash.md"
CASE_SCHEMA_PATH = ROOT / "agents" / "contracts" / "case.schema.json"
NASH_SCHEMA_PATH = ROOT / "agents" / "contracts" / "nash.output.schema.json"
CASE_ID_PATTERN = re.compile(r"^YC-[A-Z0-9]{8,32}$")
CURVE_VERSION_PATTERN = re.compile(r"^CURVA-[A-Z0-9-]{4,64}$")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _incident(code: str, message: str) -> dict[str, str]:
    return {"codigo": code, "severidad": "ERROR", "mensaje": message}


def _validate_case(case: dict[str, Any], skill_payload: dict[str, Any]) -> None:
    Draft202012Validator(_load_json(CASE_SCHEMA_PATH), format_checker=FormatChecker()).validate(case)
    if skill_payload.get("metodologia") == METHODOLOGY:
        if skill_payload.get("mode") != "SIMULADO" or case.get("caso_id") != skill_payload.get("case_id") or case.get("version_curva") != skill_payload.get("curve_version"):
            raise ValueError("CASO_EXCEL_INCONSISTENTE")
        return
    if case.get("modo") != "SIMULADO" or skill_payload.get("mode") != "SIMULADO":
        raise ValueError("MODO_NO_PERMITIDO")
    if case.get("caso_id") != skill_payload.get("case_id"):
        raise ValueError("CASO_ID_INCONSISTENTE")
    if case.get("version_curva") != skill_payload.get("curve_version"):
        raise ValueError("VERSION_CURVA_INCONSISTENTE")
    if not isinstance(case.get("version_curva"), str):
        raise ValueError("VERSION_CURVA_FALTANTE")


def execute_nash(case: dict[str, Any], skill_payload: dict[str, Any], invocation_id: str) -> dict[str, Any]:
    """Carga instrucciones, valida el caso e invoca el adaptador cuantitativo local."""
    nash_text = NASH_PATH.read_text(encoding="utf-8")
    nash_hash = hashlib.sha256(nash_text.encode("utf-8")).hexdigest()
    raw_case_id = case.get("caso_id") if isinstance(case, dict) else None
    raw_version_case = case.get("version_caso") if isinstance(case, dict) else None
    raw_curve_version = case.get("version_curva") if isinstance(case, dict) else None
    case_id = raw_case_id if isinstance(raw_case_id, str) and CASE_ID_PATTERN.fullmatch(raw_case_id) else "YC-INVALIDO000"
    version_case = raw_version_case if isinstance(raw_version_case, int) and raw_version_case >= 1 else 1
    curve_version = raw_curve_version if isinstance(raw_curve_version, str) and CURVE_VERSION_PATTERN.fullmatch(raw_curve_version) else "CURVA-INVALIDO"
    base = {
        "caso_id": case_id,
        "version_caso": version_case,
        "version_curva": curve_version,
        "modo": "SIMULADO",
        "agente": "Nash",
    }
    try:
        _validate_case(case, skill_payload)
        guardrail_code = validate_quantitative_payload(skill_payload)
        if guardrail_code:
            raise ValueError(guardrail_code)
    except (ValidationError, ValueError) as error:
        code = str(error) if isinstance(error, ValueError) and str(error).startswith(("VALOR_", "FECHA_", "PRECIO_", "VENCIMIENTO_", "PAYLOAD_", "INSTRUMENTO_", "TIPO_")) else "CASO_CUANTITATIVO_INVALIDO"
        output = {**base, "estado": "CALCULO_RECHAZADO", "interpretacion": {"mensaje": "El cálculo se detuvo porque el caso o sus identificadores no cumplen los controles de Nash.", "requiere_auditoria_humana": True}, "resultado_curva": None, "evidencia_skill": {"invocation_id": invocation_id, "skill_name": "build-spot-curve", "skill_path": "skills/build_spot_curve/SKILL.md", "skill_version": "1.0.0", "skill_sha256": hashlib.sha256((ROOT / "skills" / "build_spot_curve" / "SKILL.md").read_bytes()).hexdigest(), "skill_status": "REJECTED", "nash_instruction_sha256": nash_hash}, "advertencias": [], "errores": [_incident("CASO_CUANTITATIVO_INVALIDO", "El caso no cumple los controles cuantitativos requeridos.")]}
        output["errores"] = [_incident(code, "El cálculo se detuvo por una validación cuantitativa determinista.")]
        return _validated_output(output)
    response = apply_build_spot_curve(skill_payload, invocation_id)
    trace = response["trace"]
    evidence = {"invocation_id": trace["invocation_id"], "skill_name": trace["skill_name"], "skill_path": trace["skill_path"], "skill_version": trace["skill_version"], "skill_sha256": trace["skill_sha256"], "skill_status": trace["skill_status"], "nash_instruction_sha256": nash_hash}
    if response["status"] != "COMPLETED":
        output = {**base, "estado": "CALCULO_RECHAZADO", "interpretacion": {"mensaje": "El cálculo se detuvo por un control determinista de la skill.", "requiere_auditoria_humana": True}, "resultado_curva": None, "evidencia_skill": evidence, "advertencias": [], "errores": [_incident(trace["error_code"], "La skill rechazó la entrada cuantitativa.")]}
        return _validated_output(output)
    result = response["result"]
    if result.get("metodologia") == "EXCEL_BOOTSTRAP_182D_V1":
        output = {**base, "estado": "CALCULO_COMPLETADO", "interpretacion": {"mensaje": "Bootstrap Excel determinista completado; requiere auditoría financiera.", "requiere_auditoria_humana": True}, "resultado_curva": {"instrument_count": len(result["pillars"]), "max_absolute_repricing_error": result["summary"]["max_absolute_repricing_error"], "interpolation_method": "EXCEL_BOOTSTRAP_182D_V1", "metodologia": "EXCEL_BOOTSTRAP_182D_V1", "pillars": result["pillars"], "curve_points": result["curve_points"], "repricing": result["repricing"]}, "evidencia_skill": evidence, "advertencias": [], "errores": []}
        return _validated_output(output)
    summary = result["summary"]
    output = {**base, "estado": "CALCULO_COMPLETADO", "interpretacion": {"mensaje": "Cálculo determinista completado; requiere auditoría financiera antes de cualquier uso.", "requiere_auditoria_humana": True}, "resultado_curva": {"instrument_count": summary["instrument_count"], "max_absolute_repricing_error": summary["max_absolute_repricing_error"], "interpolation_method": result["conventions"]["interpolation_method"], "pillars": result["pillars"], "repricing": result["repricing"]}, "evidencia_skill": evidence, "advertencias": [], "errores": []}
    return _validated_output(output)


def _validated_output(output: dict[str, Any]) -> dict[str, Any]:
    Draft202012Validator(_load_json(NASH_SCHEMA_PATH), format_checker=FormatChecker()).validate(output)
    return output
