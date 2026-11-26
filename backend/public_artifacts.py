"""Fail-closed projection for static public case artifacts."""
from __future__ import annotations

import json
import math
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FORBIDDEN = (
    "telegram_user_id", "telegram_chat_id", "approval_status", "decision_at",
    "decision_event_id", "created_event_id", "invocation_id", "api_result_json",
    "x-yieldcurve-key", "api_key", "access_code", "prompt", "stack trace",
    "credential", "response_id", "response id",
)
PUBLIC_FIELDS = {
    "public_schema_version", "case_id", "version_caso", "version_curva", "fecha_corte",
    "execution_mode", "publication_status", "publication_authorized", "published_at",
    "agentes", "fuente", "curva", "auditoria", "costos", "indicadores",
}
CASE_ID = re.compile(r"^YC-[A-Z0-9]{8,32}$")

_COST_FIELDS = (
    "currency", "pricing_status", "known_cost_usd", "cost_completeness",
    "total_variable_cost_usd", "fixed_platform_costs_included", "total_llm_calls",
    "total_input_tokens", "total_output_tokens", "total_tokens",
)
_COST_COMPONENT_FIELDS = (
    "component", "type", "provider", "model", "api_calls", "request_count",
    "input_tokens", "cached_input_tokens", "cache_write_tokens", "output_tokens",
    "total_tokens", "cost_usd", "cost_status", "pricing_status", "pricing_version",
    "pricing_effective_date",
)
_AGENT_FIELDS = ("estado", "decision", "dictamen", "datos_faltantes")
_CURVE_FIELDS = ("metodologia", "instrument_count", "max_absolute_repricing_error", "pillars", "curve_points")
_PILLAR_FIELDS = (
    "instrument_id", "days", "time_years", "spot_rate", "discount_factor",
    "observed_price", "recalculated_price", "dirty_price_theoretical", "iterations",
    "converged",
)
_CURVE_POINT_FIELDS = (
    "instrument_id", "days", "time_years", "spot_rate", "discount_factor", "point_type",
    "left_pillar", "right_pillar", "source_method",
)
_AUDIT_FIELDS = ("tecnicamente_valida", "tolerancia", "requiere_aprobacion_humana", "lectura_curva")


def _fail(code: str) -> None:
    raise ValueError(code)


def _valid_version(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _contains_nonfinite(value: Any) -> bool:
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, dict):
        return any(_contains_nonfinite(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_nonfinite(item) for item in value)
    return False


def _sanitized_agents(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    agents: dict[str, Any] = {}
    for name, agent in value.items():
        if not isinstance(name, str) or not isinstance(agent, dict):
            continue
        clean = {field: deepcopy(agent[field]) for field in _AGENT_FIELDS if field in agent}
        if clean:
            agents[name] = clean
    return agents


def _sanitized_curve(curve: dict[str, Any]) -> dict[str, Any]:
    pillars = curve.get("pillars")
    if not isinstance(pillars, list) or not pillars:
        _fail("PUBLIC_CASE_PILLARS_INVALID")
    clean_pillars = []
    for pillar in pillars:
        if not isinstance(pillar, dict):
            _fail("PUBLIC_CASE_PILLARS_INVALID")
        clean_pillars.append({field: deepcopy(pillar[field]) for field in _PILLAR_FIELDS if field in pillar})
    points = curve.get("curve_points")
    if points is not None and (not isinstance(points, list) or not all(isinstance(point, dict) for point in points)):
        _fail("PUBLIC_CASE_CURVE_POINTS_INVALID")
    clean_points = [
        {field: deepcopy(point[field]) for field in _CURVE_POINT_FIELDS if field in point}
        for point in points or []
    ]
    return {
        field: (clean_pillars if field == "pillars" else clean_points if field == "curve_points" else deepcopy(curve.get(field)))
        for field in _CURVE_FIELDS
    }


def _sanitized_costs(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        _fail("PUBLIC_COST_TRACE_INVALID")
    costs = {field: deepcopy(value[field]) for field in _COST_FIELDS if field in value}
    components = value.get("components")
    if components is not None:
        if not isinstance(components, list) or not all(isinstance(item, dict) for item in components):
            _fail("PUBLIC_COST_TRACE_INVALID")
        costs["components"] = [
            {field: deepcopy(item[field]) for field in _COST_COMPONENT_FIELDS if field in item}
            for item in components
        ]
    return costs


def _public_document(case_artifact: dict[str, Any], execution_mode: str, published_at: str | None) -> dict[str, Any]:
    curve = case_artifact.get("curva")
    audit = case_artifact.get("auditoria")
    source = case_artifact.get("fuente_datos")
    if not isinstance(curve, dict) or not isinstance(audit, dict) or not isinstance(source, dict):
        _fail("PUBLIC_CASE_INVALID")
    public = {
        "public_schema_version": "1.0.0",
        "case_id": case_artifact.get("caso_id"),
        "version_caso": case_artifact.get("version_caso"),
        "version_curva": case_artifact.get("version_curva"),
        "fecha_corte": case_artifact.get("fecha_corte"),
        "execution_mode": execution_mode,
        "publication_status": "PUBLISHED",
        "publication_authorized": True,
        "published_at": published_at or datetime.now(timezone.utc).isoformat(),
        "agentes": _sanitized_agents(case_artifact.get("agentes")),
        "fuente": {"source_mode": source.get("source_mode")},
        "curva": _sanitized_curve(curve),
        "auditoria": {field: deepcopy(audit[field]) for field in _AUDIT_FIELDS if field in audit},
        "costos": _sanitized_costs(case_artifact.get("cost_trace")),
        "indicadores": {key: deepcopy(value) for key, value in (case_artifact.get("indicadores") or {}).items() if key in {"mape_repricing_pct", "technical_valid_curves_pct", "technical_processing_minutes"}},
    }
    if _contains_nonfinite(public):
        _fail("PUBLIC_CASE_NON_FINITE")
    if any(field in json.dumps(public, ensure_ascii=False).lower() for field in FORBIDDEN):
        _fail("PUBLIC_CASE_SENSITIVE")
    return public


def build_public_case_artifact(case_artifact: dict[str, Any], published_at: str | None = None) -> dict[str, Any]:
    """Preserves the historical DEMO route; LIVE uses the explicit function below."""
    curve = case_artifact.get("curva") or {}
    audit = case_artifact.get("auditoria") or {}
    if (
        case_artifact.get("execution_mode") != "DEMO"
        or case_artifact.get("estado") != "APROBADA_HUMANAMENTE"
        or audit.get("tecnicamente_valida") is not True
        or not case_artifact.get("caso_id")
        or not isinstance(curve.get("pillars"), list)
        or not curve["pillars"]
    ):
        _fail("PUBLIC_CASE_NOT_AUTHORIZED")
    return _public_document(case_artifact, "DEMO", published_at)


def build_approved_live_public_case_artifact(
    case_artifact: dict[str, Any], approval_evidence: dict[str, Any], published_at: str | None = None,
) -> dict[str, Any]:
    """Builds a LIVE artifact only from technical and persisted approval evidence."""
    if not isinstance(case_artifact, dict) or not isinstance(approval_evidence, dict):
        _fail("LIVE_PUBLIC_INPUT_INVALID")
    case_id = case_artifact.get("caso_id")
    version = case_artifact.get("version_caso")
    curve = case_artifact.get("curva") or {}
    audit = case_artifact.get("auditoria") or {}
    source = case_artifact.get("fuente_datos") or {}
    if (
        not isinstance(case_id, str) or not CASE_ID.fullmatch(case_id)
        or not _valid_version(version)
        or case_artifact.get("execution_mode") != "LIVE"
        or source.get("source_mode") != "BANXICO_SIE_LIVE"
        or audit.get("tecnicamente_valida") is not True
        or not isinstance(curve.get("pillars"), list) or not curve["pillars"]
    ):
        _fail("LIVE_PUBLIC_TECHNICAL_EVIDENCE_INVALID")
    if (
        approval_evidence.get("caso_id") != case_id
        or approval_evidence.get("version_caso") != version
        or approval_evidence.get("estado") != "APROBADA_HUMANAMENTE"
        or approval_evidence.get("approval_status") != "APPROVED"
    ):
        _fail("LIVE_PUBLIC_APPROVAL_EVIDENCE_INVALID")
    return _public_document(case_artifact, "LIVE", published_at)


def validate_public_case(public: dict[str, Any]) -> None:
    # indicadores is optional for historical artifacts published before KPI projection.
    required_fields = PUBLIC_FIELDS - {"indicadores"}
    if not isinstance(public, dict) or not required_fields <= set(public) or set(public) - PUBLIC_FIELDS:
        _fail("PUBLIC_CASE_SCHEMA")
    mode = public.get("execution_mode")
    audit = public.get("auditoria")
    curve = public.get("curva")
    source = public.get("fuente")
    if (
        public.get("public_schema_version") != "1.0.0"
        or mode not in {"DEMO", "LIVE"}
        or public.get("publication_status") != "PUBLISHED"
        or public.get("publication_authorized") is not True
        or not isinstance(audit, dict) or audit.get("tecnicamente_valida") is not True
        or not isinstance(public.get("case_id"), str)
        or not isinstance(curve, dict) or not curve.get("pillars")
    ):
        _fail("PUBLIC_CASE_INVALID")
    if mode == "LIVE" and (not isinstance(source, dict) or source.get("source_mode") != "BANXICO_SIE_LIVE"):
        _fail("PUBLIC_CASE_LIVE_SOURCE_INVALID")
    points = curve.get("curve_points")
    if points is not None:
        if not isinstance(points, list):
            _fail("PUBLIC_CASE_CURVE_POINTS_INVALID")
        pillar_days = {item.get("days") for item in curve["pillars"] if isinstance(item, dict)}
        prior, seen = 0, set()
        for point in points:
            if not isinstance(point, dict) or point.get("point_type") not in {"PILLAR", "INTERPOLATED"}:
                _fail("PUBLIC_CASE_CURVE_POINTS_INVALID")
            days = point.get("days")
            if not isinstance(days, int) or days <= prior or days in seen:
                _fail("PUBLIC_CASE_CURVE_POINTS_INVALID")
            prior, seen = days, seen | {days}
            if point["point_type"] == "PILLAR" and days not in pillar_days:
                _fail("PUBLIC_CASE_CURVE_POINTS_INVALID")
            if point["point_type"] == "INTERPOLATED" and days in pillar_days:
                _fail("PUBLIC_CASE_CURVE_POINTS_INVALID")
    if _contains_nonfinite(public):
        _fail("PUBLIC_CASE_NON_FINITE")
    if any(field in json.dumps(public, ensure_ascii=False).lower() for field in FORBIDDEN):
        _fail("PUBLIC_CASE_SENSITIVE")


def canonical_public_json(public: dict[str, Any]) -> str:
    """Canonical serialization used by publication clients for no-op detection."""
    validate_public_case(public)
    return json.dumps(public, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_public_case_idempotently(public: dict[str, Any], target_dir: Path) -> tuple[Path, str]:
    """Local equivalent of GitHub publication: CREATE, NOOP, or fail-closed conflict."""
    content = canonical_public_json(public)
    target = target_dir / f"{public['case_id']}.json"
    if target.exists():
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
            existing_content = canonical_public_json(existing)
        except (OSError, ValueError, json.JSONDecodeError):
            _fail("PUBLIC_OUTPUT_INVALID")
        if existing.get("version_caso") != public["version_caso"]:
            _fail("PUBLIC_OUTPUT_VERSION_CONFLICT")
        if existing_content != content:
            _fail("PUBLIC_OUTPUT_CONTENT_CONFLICT")
        return target, "NOOP"
    target_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(content + "\n", encoding="utf-8")
    return target, "CREATED"
