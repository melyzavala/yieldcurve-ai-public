"""Fail-closed projection for static public case artifacts."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

FORBIDDEN = ("telegram_user_id","telegram_chat_id","approval_status","decision_at","decision_event_id","created_event_id","invocation_id","api_result_json","x-yieldcurve-key","api_key","access_code","prompt","stack trace","credential")
PUBLIC_FIELDS = {"public_schema_version","case_id","version_caso","version_curva","fecha_corte","execution_mode","publication_status","publication_authorized","published_at","agentes","fuente","curva","auditoria","costos"}

def build_public_case_artifact(case_artifact: dict[str, Any], published_at: str | None = None) -> dict[str, Any]:
    curve=case_artifact.get("curva") or {}; audit=case_artifact.get("auditoria") or {}; pillars=curve.get("pillars")
    if (case_artifact.get("execution_mode") != "DEMO" or case_artifact.get("estado") != "APROBADA_HUMANAMENTE" or audit.get("tecnicamente_valida") is not True or not case_artifact.get("caso_id") or not isinstance(pillars,list) or not pillars): raise ValueError("PUBLIC_CASE_NOT_AUTHORIZED")
    public={"public_schema_version":"1.0.0","case_id":case_artifact["caso_id"],"version_caso":case_artifact.get("version_caso"),"version_curva":case_artifact.get("version_curva"),"fecha_corte":case_artifact.get("fecha_corte"),"execution_mode":"DEMO","publication_status":"PUBLISHED","publication_authorized":True,"published_at":published_at or datetime.now(timezone.utc).isoformat(),"agentes":deepcopy(case_artifact.get("agentes",{})),"fuente":{"source_mode":case_artifact.get("fuente_datos",{}).get("source_mode")},"curva":{"metodologia":curve.get("metodologia"),"instrument_count":curve.get("instrument_count"),"max_absolute_repricing_error":curve.get("max_absolute_repricing_error"),"pillars":deepcopy(pillars)},"auditoria":deepcopy(audit),"costos":deepcopy(case_artifact.get("cost_trace",{}))}
    text=str(public).lower()
    if any(field in text for field in FORBIDDEN): raise ValueError("PUBLIC_CASE_SENSITIVE")
    return public

def validate_public_case(public: dict[str, Any]) -> None:
    if not isinstance(public,dict) or set(public)!=PUBLIC_FIELDS: raise ValueError("PUBLIC_CASE_SCHEMA")
    if public.get("public_schema_version")!="1.0.0" or public.get("execution_mode")!="DEMO" or public.get("publication_status")!="PUBLISHED" or public.get("publication_authorized") is not True or public.get("auditoria",{}).get("tecnicamente_valida") is not True or not public.get("case_id") or not public.get("curva",{}).get("pillars"): raise ValueError("PUBLIC_CASE_INVALID")
    import math
    for p in public["curva"]["pillars"]:
        for key in ("spot_rate",):
            if key in p and (not isinstance(p[key],(int,float)) or not math.isfinite(p[key])): raise ValueError("PUBLIC_CASE_NON_FINITE")
    if any(field in str(public).lower() for field in FORBIDDEN): raise ValueError("PUBLIC_CASE_SENSITIVE")
