"""Exporta localmente un único caso DEMO aprobado al contrato público sanitizado."""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.public_artifacts import build_public_case_artifact, validate_public_case


CASE_ID = re.compile(r"^YC-[A-Z0-9]{8,32}$")
APPROVAL_STATUS = "APPROVED"
ELIGIBLE_API_STATE = "PENDIENTE_APROBACION"
AGENTS = ("elara", "siena", "nash", "atenea")
AGENT_FIELDS = ("estado", "decision", "dictamen")
COST_FIELDS = (
    "currency", "pricing_status", "total_llm_calls", "total_input_tokens",
    "total_output_tokens", "total_tokens", "total_variable_cost_usd",
    "fixed_platform_costs_included",
)
COMPONENT_FIELDS = (
    "component", "type", "provider", "model", "api_calls", "request_count",
    "input_tokens", "output_tokens", "total_tokens", "estimated_cost_usd",
    "pricing_status", "pricing_version", "pricing_effective_date", "source_mode",
)


class ExportError(ValueError):
    """Error sanitizado para entradas privadas no aptas para publicación."""


def _fail(code: str) -> None:
    raise ExportError(code)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (OSError, ValueError, json.JSONDecodeError):
        _fail("PRIVATE_ROW_JSON_INVALID")
    if not isinstance(value, dict):
        _fail("PRIVATE_ROW_INVALID")
    return value


def _finite(value: Any) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _finite(item) for key, item in value.items())
    if isinstance(value, list):
        return all(_finite(item) for item in value)
    return True


def _scalar(value: Any) -> str | None:
    return value if isinstance(value, str) or value is None else None


def _sanitize_agents(value: Any) -> dict[str, dict[str, str | None]]:
    if not isinstance(value, dict):
        _fail("API_AGENTS_INVALID")
    result: dict[str, dict[str, str | None]] = {}
    for name in AGENTS:
        item = value.get(name)
        if not isinstance(item, dict):
            continue
        clean = {field: _scalar(item.get(field)) for field in AGENT_FIELDS if _scalar(item.get(field)) is not None}
        if clean:
            result[name] = clean
    return result


def _sanitize_costs(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        _fail("API_COST_TRACE_INVALID")
    result = {field: value[field] for field in COST_FIELDS if field in value}
    components = value.get("components")
    if components is not None:
        if not isinstance(components, list) or not all(isinstance(item, dict) for item in components):
            _fail("API_COST_TRACE_INVALID")
        result["components"] = [{field: item[field] for field in COMPONENT_FIELDS if field in item} for item in components]
    return result


def _approved_source(row: dict[str, Any]) -> dict[str, Any]:
    case_id = row.get("caso_id")
    if not isinstance(case_id, str) or not CASE_ID.fullmatch(case_id):
        _fail("CASE_ID_INVALID")
    if row.get("execution_mode") != "DEMO" or row.get("estado") != "APROBADA_HUMANAMENTE":
        _fail("ROW_NOT_APPROVED_DEMO")
    if row.get("approval_status") != APPROVAL_STATUS:
        _fail("APPROVAL_STATUS_INVALID")
    raw = row.get("api_result_json")
    if not isinstance(raw, str):
        _fail("API_RESULT_MISSING")
    try:
        api = json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, json.JSONDecodeError):
        _fail("API_RESULT_JSON_INVALID")
    if not isinstance(api, dict):
        _fail("API_RESULT_INVALID")
    if api.get("caso_id") != case_id or api.get("version_caso") != row.get("version_caso") or api.get("fecha_corte") != row.get("fecha_corte"):
        _fail("API_ROW_MISMATCH")
    if api.get("execution_mode") != "DEMO" or api.get("estado") != ELIGIBLE_API_STATE:
        _fail("API_NOT_ELIGIBLE")
    curve = api.get("resultado_curva")
    audit = api.get("auditoria")
    if not isinstance(curve, dict) or not isinstance(curve.get("pillars"), list) or not curve["pillars"]:
        _fail("API_PILLARS_INVALID")
    if not isinstance(audit, dict) or audit.get("tecnicamente_valida") is not True:
        _fail("API_AUDIT_INVALID")
    if row.get("version_curva") is not None and api.get("version_curva") != row.get("version_curva"):
        _fail("API_ROW_MISMATCH")
    source = {
        "caso_id": case_id,
        "version_caso": row.get("version_caso"),
        "version_curva": api.get("version_curva"),
        "fecha_corte": row.get("fecha_corte"),
        "execution_mode": "DEMO",
        "estado": "APROBADA_HUMANAMENTE",
        "agentes": _sanitize_agents(api.get("agentes", {})),
        "fuente_datos": {"source_mode": (api.get("fuente_datos") or {}).get("source_mode")} if isinstance(api.get("fuente_datos"), dict) else _fail("API_SOURCE_INVALID"),
        "curva": curve,
        "auditoria": audit,
        "cost_trace": _sanitize_costs(api.get("cost_trace")),
    }
    if not _finite(source):
        _fail("PUBLIC_VALUES_NONFINITE")
    return source


def export_approved_case(input_path: Path, output_dir: Path | None = None) -> Path:
    row = _load_json(input_path)
    source = _approved_source(row)
    public = build_public_case_artifact(source)
    validate_public_case(public)
    target_dir = output_dir or ROOT / "data" / "public" / "cases"
    target = target_dir / f"{public['case_id']}.json"
    if target.exists():
        _fail("PUBLIC_OUTPUT_EXISTS")
    target_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(public, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Exporta un DEMO aprobado al contrato público sanitizado.")
    parser.add_argument("private_row", type=Path, help="Fila privada local de YC_CASES en JSON.")
    args = parser.parse_args()
    try:
        target = export_approved_case(args.private_row)
    except ExportError as error:
        print(f"Export rejected: {error}", file=sys.stderr)
        return 2
    public = json.loads(target.read_text(encoding="utf-8"))
    print(f"Exported public DEMO: case_id={public['case_id']} fecha={public['fecha_corte']} technical_audit=true path={target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
