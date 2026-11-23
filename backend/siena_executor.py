"""Ejecutor determinista de Siena para datos reales del SIE de Banco de México."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from backend.banxico_client import API_BASE, CF300_SERIES, FONDEO_GUBERNAMENTAL_SERIES, SERIES_CATALOG, BanxicoClient, BanxicoClientError, normalize_banxico_response, parse_iso_date, validate_observations


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "agents" / "contracts" / "siena.output.schema.json"


def _issue(code: str, severity: str, message: str) -> dict[str, str]:
    return {"codigo": code, "severidad": severity, "mensaje": message}


def _series_metadata(series_ids: list[str], status: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for serie_id in series_ids:
        metadata = SERIES_CATALOG[serie_id]
        entry: dict[str, Any] = {"serie_id": serie_id, **metadata, "estado": status}
        if metadata["instrumento"] == "MBONOS":
            entry["requiere_flujos_individuales"] = True
        entries.append(entry)
    return entries


def _source_resources(series_ids: list[str]) -> list[dict[str, Any]]:
    """Declara el recurso público de cada conjunto, sin atribuir fondeo a CF300."""
    resources: list[dict[str, Any]] = []
    cf300 = list(dict.fromkeys(serie_id for serie_id in series_ids if serie_id in CF300_SERIES))
    fondeo = list(dict.fromkeys(serie_id for serie_id in series_ids if serie_id in FONDEO_GUBERNAMENTAL_SERIES))
    if cf300:
        resources.append({"tipo": "CUADRO_SIE", "identificador": "CF300", "series": cf300})
    if fondeo:
        resources.append({"tipo": "SERIE_SIE", "identificador": "SF43774", "series": fondeo})
    return resources


def _output(fecha_corte: str, series_ids: list[str], estado: str, observations: list[dict[str, Any]], warnings: list[dict[str, str]], errors: list[dict[str, str]], consulted_at: str, request_count: int | None = None) -> dict[str, Any]:
    issues = validate_observations(fecha_corte, series_ids, observations) if observations else ["SERIE_FALTANTE"]
    if issues and not errors:
        errors = [_issue(code, "ERROR", "La observación no cumple los controles de Siena.") for code in issues]
    valid_count = len(observations) if not issues else 0
    result = {
        "estado": estado,
        "fecha_corte": fecha_corte,
        "modo": "SIMULADO",
        "fuente": {"proveedor": "Banco de México", "cuadro": "CF300", "recursos": _source_resources(series_ids), "api_base": API_BASE, "consultada_en": consulted_at, "datos_mercado": "REALES"},
        "series": _series_metadata(series_ids, "DISPONIBLE" if estado == "DATOS_VALIDOS" else "FALTANTE" if estado == "DATOS_INCOMPLETOS" else "RECHAZADA"),
        "observaciones": [{**item, "valida": not bool(issues)} for item in observations],
        "resumen_validacion": {"series_solicitadas": len(series_ids), "series_con_observacion": len({item["serie_id"] for item in observations}), "observaciones_validas": valid_count, "observaciones_rechazadas": len(observations) - valid_count},
        "advertencias": warnings,
        "errores": errors,
        "request_count": request_count,
    }
    Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")), format_checker=FormatChecker()).validate(result)
    return result


def execute_siena(fecha_corte: str, series_ids: list[str], client: BanxicoClient | None = None) -> dict[str, Any]:
    """Obtiene y valida series SIE autorizadas sin inferir ni completar datos."""
    try:
        parse_iso_date(fecha_corte)
        if not series_ids or len(set(series_ids)) != len(series_ids) or not set(series_ids).issubset(SERIES_CATALOG):
            raise ValueError
    except (TypeError, ValueError):
        safe_date = "2000-01-01"
        return _output(safe_date, [item for item in series_ids if item in SERIES_CATALOG] if isinstance(series_ids, list) else [], "DATOS_RECHAZADOS", [], [], [_issue("SOLICITUD_INVALIDA", "ERROR", "La fecha o las series no cumplen los controles de Siena.")], datetime.now(timezone.utc).isoformat())

    consulted_at = datetime.now(timezone.utc).isoformat()
    try:
        raw_payloads = (client or BanxicoClient.from_environment()).fetch_for_date(series_ids, fecha_corte)
        observations: list[dict[str, Any]] = []
        for serie_id in series_ids:
            observations.extend(normalize_banxico_response(raw_payloads[serie_id], [serie_id]))
    except BanxicoClientError as error:
        if "BANXICO_API_TOKEN" in str(error):
            return _output(fecha_corte, series_ids, "ERROR", [], [], [_issue("CREDENCIAL_BANXICO_NO_CONFIGURADA", "ERROR", "La credencial requerida para Banco de México no está configurada.")], consulted_at)
        return _output(fecha_corte, series_ids, "DATOS_INCOMPLETOS", [], [], [_issue("DATOS_BANXICO_NO_DISPONIBLES", "ERROR", "Banco de México no entregó una observación numérica válida para todas las series.")], consulted_at)
    except Exception:
        return _output(fecha_corte, series_ids, "ERROR", [], [], [_issue("CONSULTA_BANXICO_FALLIDA", "ERROR", "La consulta a Banco de México no pudo completarse.")], consulted_at)

    issues = validate_observations(fecha_corte, series_ids, observations)
    warnings = []
    if any(SERIES_CATALOG[item]["instrumento"] == "MBONOS" for item in series_ids):
        warnings.append(_issue("MBONOS_RANGO", "ADVERTENCIA", "Los Bonos M de CF300 son representativos por rango; no proporcionan flujos de una emisión individual."))
    if issues:
        return _output(fecha_corte, series_ids, "DATOS_RECHAZADOS", observations, warnings, [_issue(code, "ERROR", "La observación no cumple los controles de Siena.") for code in issues], consulted_at)
    return _output(fecha_corte, series_ids, "DATOS_VALIDOS", observations, warnings, [], consulted_at, len(series_ids))
