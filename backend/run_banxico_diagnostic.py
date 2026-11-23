"""Diagnóstico manual sanitizado y de alcance fijo para la API SIE."""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime
from typing import Any

from backend.banxico_client import (
    API_BASE,
    CURVE_REQUIRED_SERIES,
    DIAGNOSTIC_DATA_SERIES,
    DIAGNOSTIC_METADATA_SERIES,
    SERIES_CATALOG,
    BanxicoClient,
    BanxicoClientError,
    banxico_date,
    normalize_banxico_response,
    validate_observations,
)


# Rango acotado alrededor de las series CF300 ya consultadas. No asigna campos
# por posición: sólo se acepta una serie cuando su título oficial coincide.
METADATA_CANDIDATE_SERIES = tuple(f"SF{number}" for number in range(45427, 45481))
LONG_TERM_CANDIDATE_SERIES = tuple(f"SF{number}" for number in range(45481, 45681))
METADATA_BATCH_SIZE = 20
OFFICIAL_TITLE_PREFIX = "Vector de precios de títulos gubernamentales "
CF300_REQUIRED_TITLES = {
    "Bonos 0 a 3 años - Plazo": ("0–3 años", "PLAZO_DIAS", "1,205.000000"),
    "Bonos 0 a 3 años - Precio Sucio": ("0–3 años", "PRECIO_SUCIO", "102.964751"),
    "Bonos 0 a 3 años - Cupón Vigente": ("0–3 años", "CUPON_VIGENTE", "8.500000"),
    "Bonos 3 a 5 años - Plazo": ("3–5 años", "PLAZO_DIAS", "1,982.000000"),
    "Bonos 3 a 5 años - Precio Sucio": ("3–5 años", "PRECIO_SUCIO", "97.805938"),
    "Bonos 3 a 5 años - Cupón Vigente": ("3–5 años", "CUPON_VIGENTE", "8.000000"),
    "Bonos 7 a 10 años - Plazo": ("7–10 años", "PLAZO_DIAS", "3,389.000000"),
    "Bonos 7 a 10 años - Precio Sucio": ("7–10 años", "PRECIO_SUCIO", "94.005726"),
    "Bonos 7 a 10 años - Cupón Vigente": ("7–10 años", "CUPON_VIGENTE", "8.000000"),
    "Bonos 10 a 20 años - Plazo": ("10–20 años", "PLAZO_DIAS", "5,846.000000"),
    "Bonos 10 a 20 años - Precio Sucio": ("10–20 años", "PRECIO_SUCIO", "87.436980"),
    "Bonos 10 a 20 años - Cupón Vigente": ("10–20 años", "CUPON_VIGENTE", "7.750000"),
    "Bonos 20 a 30 años - Plazo": ("20–30 años", "PLAZO_DIAS", "10,396.000000"),
    "Bonos 20 a 30 años - Precio Sucio": ("20–30 años", "PRECIO_SUCIO", "85.852819"),
    "Bonos 20 a 30 años - Cupón Vigente": ("20–30 años", "CUPON_VIGENTE", "8.000000"),
}
CF300_LONG_TERM_TITLES = {
    "Bonos 20 a 30 años - Plazo": ("PLAZO_DIAS", "10,396.000000"),
    "Bonos 20 a 30 años - Precio Sucio": ("PRECIO_SUCIO", "85.852819"),
    "Bonos 20 a 30 años - Cupón Vigente": ("CUPON_VIGENTE", "8.000000"),
}
EXCEL_AUXILIARY_SERIES = {
    "SF349886": "CETE_2Y_PLAZO",
    "SF349888": "CETE_2Y_PRECIO",
    "SF349889": "CETE_2Y_YTM_CONTROL",
    "SF43774": "OVERNIGHT_FONDEO_GUBERNAMENTAL",
}
_PUBLIC_NUMBER = re.compile(r"[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?")


def _groups(payload: dict[str, Any]) -> list[dict[str, Any]]:
    groups = payload.get("bmx", {}).get("series", []) if isinstance(payload, dict) else []
    return groups if isinstance(groups, list) else []


def _summary(serie_id: str, tipo_consulta: str, payload: dict[str, Any] | None = None, error: BanxicoClientError | None = None) -> dict[str, Any]:
    groups = _groups(payload or {})
    first = groups[0] if groups and isinstance(groups[0], dict) else {}
    data = first.get("datos", []) if isinstance(first.get("datos"), list) else []
    item = data[0] if data and isinstance(data[0], dict) else {}
    return {
        "serie_id": serie_id,
        "tipo_consulta": tipo_consulta,
        "http_status": error.http_status if error else 200,
        "respuesta_json_valida": payload is not None,
        "id_serie_devuelto": first.get("idSerie"),
        "numero_observaciones": len(data),
        "primera_fecha": item.get("fecha"),
        "primer_dato": item.get("dato"),
        "codigo_error_sanitizado": error.code if error else None,
    }


def _probe_data(client: BanxicoClient, serie_id: str, fecha_corte: str) -> dict[str, Any]:
    try:
        return _summary(serie_id, "DATOS", payload=client.fetch_diagnostic_data(serie_id, fecha_corte))
    except BanxicoClientError as error:
        return _summary(serie_id, "DATOS", error=error)


def _probe_metadata(client: BanxicoClient) -> dict[str, Any]:
    try:
        return _summary(DIAGNOSTIC_METADATA_SERIES, "METADATOS", payload=client.fetch_diagnostic_metadata())
    except BanxicoClientError as error:
        return _summary(DIAGNOSTIC_METADATA_SERIES, "METADATOS", error=error)


def _raw_first_observation(payload: dict[str, Any]) -> tuple[str | None, str | None, Any]:
    """Extrae sólo los tres campos públicos necesarios para el diagnóstico."""
    groups = _groups(payload)
    first = groups[0] if groups and isinstance(groups[0], dict) else {}
    data = first.get("datos", []) if isinstance(first.get("datos"), list) else []
    item = data[0] if data and isinstance(data[0], dict) else {}
    returned = first.get("idSerie")
    return (returned if isinstance(returned, str) else None, item.get("fecha"), item.get("dato"))


def _diagnose_series(client: BanxicoClient, serie_id: str, fecha_corte: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Consulta y normaliza una sola serie sin abortar el lote de diagnóstico."""
    metadata = SERIES_CATALOG[serie_id]
    entry: dict[str, Any] = {
        "serie_id": serie_id,
        "instrumento": metadata["instrumento"],
        "campo": metadata["campo"],
        "http_status": None,
        "id_serie_devuelto": None,
        "raw_fecha": None,
        "raw_dato": None,
        "normalizacion_estado": "ERROR",
        "fecha_normalizada": None,
        "valor_normalizado": None,
        "unidad_normalizada": None,
        "codigo_error_sanitizado": None,
    }
    try:
        payload = client.fetch_series(serie_id, fecha_corte, fecha_corte)
    except BanxicoClientError as error:
        entry["http_status"] = error.http_status
        entry["codigo_error_sanitizado"] = error.code
        return entry, []

    entry["http_status"] = 200
    entry["id_serie_devuelto"], entry["raw_fecha"], entry["raw_dato"] = _raw_first_observation(payload)
    try:
        observations = normalize_banxico_response(payload, [serie_id])
    except BanxicoClientError as error:
        entry["codigo_error_sanitizado"] = error.code
        return entry, []

    if len(observations) != 1:
        entry["codigo_error_sanitizado"] = "BANXICO_RESPUESTA_INVALIDA"
        return entry, []
    observation = observations[0]
    entry.update(
        normalizacion_estado="NORMALIZADA",
        fecha_normalizada=observation["fecha"],
        valor_normalizado=observation["valor"],
        unidad_normalizada=observation["unidad"],
    )
    return entry, observations


def diagnose_required_series(client: BanxicoClient, fecha_corte: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Inspecciona las series autorizadas una a una y conserva errores sanitizados."""
    entries: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    for serie_id in CURVE_REQUIRED_SERIES:
        entry, normalized = _diagnose_series(client, serie_id, fecha_corte)
        entries.append(entry)
        observations.extend(normalized)
    return entries, validate_observations(fecha_corte, list(CURVE_REQUIRED_SERIES), observations)


def _metadata_group(payload: dict[str, Any]) -> dict[str, Any]:
    groups = _groups(payload)
    return groups[0] if groups and isinstance(groups[0], dict) else {}


def _metadata_value(group: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in group:
            return group[name]
    return None


def canonicalize_cf300_title(title: Any) -> Any:
    """Retira únicamente el prefijo oficial conocido, sin aproximaciones."""
    if isinstance(title, str) and title.startswith(OFFICIAL_TITLE_PREFIX):
        return title.removeprefix(OFFICIAL_TITLE_PREFIX)
    return title


def _metadata_batches(series_ids: tuple[str, ...]) -> list[tuple[str, ...]]:
    return [series_ids[index:index + METADATA_BATCH_SIZE] for index in range(0, len(series_ids), METADATA_BATCH_SIZE)]


def _fetch_metadata_batch(client: BanxicoClient, series_ids: tuple[str, ...]) -> dict[str, Any]:
    """Usa el endpoint oficial de metadatos múltiples sin exponer URL ni credenciales."""
    return client._request(f"{API_BASE}/v1/series/{','.join(series_ids)}")


def _fetch_candidate_data(client: BanxicoClient, serie_id: str, fecha_corte: str, allowed_series: tuple[str, ...] = METADATA_CANDIDATE_SERIES) -> dict[str, Any]:
    """Consulta datos sólo para una serie validada por el lote diagnóstico actual."""
    if serie_id not in allowed_series:
        raise BanxicoClientError("BANXICO_SERIE_NO_AUTORIZADA")
    fecha = banxico_date(fecha_corte)
    return client._request(f"{API_BASE}/v1/series/{serie_id}/datos/{fecha}/{fecha}")


def _parse_public_number(value: Any) -> float | None:
    """Normaliza sólo un valor público del diagnóstico, sin usar el catálogo productivo."""
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not _PUBLIC_NUMBER.fullmatch(text):
        return None
    parsed = float(text.replace(",", ""))
    return parsed if math.isfinite(parsed) else None


def _normalize_public_date(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    for parser in (lambda item: datetime.strptime(item, "%d/%m/%Y").date(), lambda item: datetime.strptime(item, "%Y-%m-%d").date()):
        try:
            return parser(value).isoformat()
        except ValueError:
            continue
    return None


def _fetch_excel_auxiliary_data(client: BanxicoClient, serie_id: str, fecha_corte: str) -> dict[str, Any]:
    if serie_id not in EXCEL_AUXILIARY_SERIES:
        raise BanxicoClientError("BANXICO_SERIE_NO_AUTORIZADA")
    fecha = banxico_date(fecha_corte)
    return client._request(f"{API_BASE}/v1/series/{serie_id}/datos/{fecha}/{fecha}")


def _auxiliary_metadata_record(group: dict[str, Any]) -> dict[str, Any]:
    return {
        "serie_id": _metadata_value(group, "idSerie"),
        "titulo_oficial": _metadata_value(group, "titulo", "tituloSerie", "nombre"),
        "unidad": _metadata_value(group, "unidad"),
        "periodicidad": _metadata_value(group, "periodicidad"),
        "fecha_inicio": _metadata_value(group, "fechaInicio"),
        "fecha_fin": _metadata_value(group, "fechaFin"),
    }


def diagnose_excel_auxiliary_inputs(client: BanxicoClient, fecha_corte: str) -> dict[str, Any]:
    """Diagnóstico acotado de los cuatro insumos Banxico demostrados por el Excel."""
    ids = tuple(EXCEL_AUXILIARY_SERIES)
    metadata: list[dict[str, Any]] = []
    metadata_error: str | None = None
    try:
        for group in _groups(_fetch_metadata_batch(client, ids)):
            if isinstance(group, dict):
                metadata.append(_auxiliary_metadata_record(group))
    except BanxicoClientError as error:
        metadata_error = error.code

    observations: list[dict[str, Any]] = []
    numeric: dict[str, float] = {}
    for serie_id in ids:
        entry: dict[str, Any] = {"serie_id": serie_id, "fecha": None, "raw_dato": None, "normalizable": False, "codigo_error_sanitizado": None}
        try:
            payload = _fetch_excel_auxiliary_data(client, serie_id, fecha_corte)
            returned, raw_date, raw_value = _raw_first_observation(payload)
            normalized_date = _normalize_public_date(raw_date)
            value = _parse_public_number(raw_value)
            entry.update(fecha=raw_date, raw_dato=raw_value)
            entry["normalizable"] = returned == serie_id and normalized_date == fecha_corte and value is not None
            if entry["normalizable"]:
                numeric[serie_id] = value
            else:
                entry["codigo_error_sanitizado"] = "BANXICO_RESPUESTA_INVALIDA"
        except BanxicoClientError as error:
            entry["codigo_error_sanitizado"] = error.code
        observations.append(entry)

    transformation: dict[str, Any] | None = None
    cete_ids = ("SF349886", "SF349888", "SF349889")
    if all(serie_id in numeric for serie_id in cete_ids):
        days, price, published_ytm_percent = (numeric[serie_id] for serie_id in cete_ids)
        if days > 0 and price > 0:
            ytm_from_price = (10 / price - 1) * 360 / days
            rate_182 = ((1 + ytm_from_price) ** (182 / 360) - 1) * (360 / 182)
            transformation = {
                "dias": days,
                "precio": price,
                "ytm_publicado": published_ytm_percent / 100,
                "ytm_calculado_desde_precio": ytm_from_price,
                "diferencia_absoluta": abs(published_ytm_percent / 100 - ytm_from_price),
                "rate_182": rate_182,
            }

    return {
        "fecha_corte": fecha_corte,
        "series_auxiliares": [{"serie_id": serie_id, "rol": role} for serie_id, role in EXCEL_AUXILIARY_SERIES.items()],
        "metadatos": metadata,
        "codigo_error_metadatos": metadata_error,
        "observaciones": observations,
        "disponibles": sum(item["normalizable"] for item in observations),
        "transformacion_cete_2y": transformation,
        "overnight_rate_propuesto": numeric.get("SF43774") / 100 if "SF43774" in numeric else None,
    }


def acquire_cf300_metadata(client: BanxicoClient) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Obtiene el rango CF300 una sola vez, en lotes acotados y auditables."""
    records: list[dict[str, Any]] = []
    batch_errors: list[dict[str, Any]] = []
    for batch_number, batch in enumerate(_metadata_batches(METADATA_CANDIDATE_SERIES), start=1):
        try:
            groups = _groups(_fetch_metadata_batch(client, batch))
        except BanxicoClientError as error:
            batch_errors.append({"lote": batch_number, "series_solicitadas": len(batch), "codigo_error_sanitizado": error.code})
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            title = _metadata_value(group, "titulo", "tituloSerie", "nombre")
            records.append({
                "serie_id": _metadata_value(group, "idSerie"),
                "titulo_oficial": title,
                "titulo_canonicalizado": canonicalize_cf300_title(title),
                "unidad": _metadata_value(group, "unidad"),
                "periodicidad": _metadata_value(group, "periodicidad"),
                "fecha_inicio": _metadata_value(group, "fechaInicio"),
                "fecha_fin": _metadata_value(group, "fechaFin"),
            })
    return records, batch_errors


def diagnose_cf300_metadata(client: BanxicoClient, fecha_corte: str, records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Encuentra coincidencias por título canonicalizado y contrasta sus datos publicados."""
    matches: list[dict[str, Any]] = []
    for record in records:
        title = record["titulo_canonicalizado"]
        if title not in CF300_REQUIRED_TITLES or not isinstance(record["serie_id"], str):
            continue
        matches.append({
            "serie_id": record["serie_id"],
            "titulo_oficial": record["titulo_oficial"],
            "unidad": record["unidad"],
            "periodicidad": record["periodicidad"],
            "fecha_inicio": record["fecha_inicio"],
            "fecha_fin": record["fecha_fin"],
        })

    comparisons: list[dict[str, Any]] = []
    for match in matches:
        canonical_title = canonicalize_cf300_title(match["titulo_oficial"])
        rango, campo, expected = CF300_REQUIRED_TITLES[canonical_title]
        obtained: Any = None
        error_code: str | None = None
        try:
            payload = _fetch_candidate_data(client, match["serie_id"], fecha_corte)
            _returned, _date, obtained = _raw_first_observation(payload)
        except BanxicoClientError as error:
            error_code = error.code
        comparisons.append({
            "rango": rango,
            "campo": campo,
            "serie_id": match["serie_id"],
            "valor_obtenido": obtained,
            "valor_CF300": expected,
            "coincide": obtained == expected and error_code is None,
            "codigo_error_sanitizado": error_code,
        })
    return matches, comparisons


def inspect_cf300_metadata_candidates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expone sólo los metadatos públicos ya obtenidos, sin repetir consultas."""
    fields = ("serie_id", "titulo_oficial", "unidad", "periodicidad", "fecha_inicio", "fecha_fin")
    return [{field: record[field] for field in fields} for record in records]


def locate_long_term_cf300_series(client: BanxicoClient, fecha_corte: str) -> dict[str, Any]:
    """Busca sólo los tres campos 20–30, por lotes y con corte inmediato al hallarlos."""
    matches: dict[str, dict[str, Any]] = {}
    batch_errors: list[dict[str, Any]] = []
    consulted = 0
    last_id: str | None = None
    batches_used = 0
    for batch_number, batch in enumerate(_metadata_batches(LONG_TERM_CANDIDATE_SERIES), start=1):
        batches_used += 1
        consulted += len(batch)
        last_id = batch[-1]
        try:
            groups = _groups(_fetch_metadata_batch(client, batch))
        except BanxicoClientError as error:
            batch_errors.append({"lote": batch_number, "series_solicitadas": len(batch), "codigo_error_sanitizado": error.code})
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            title = _metadata_value(group, "titulo", "tituloSerie", "nombre")
            canonical_title = canonicalize_cf300_title(title)
            serie_id = _metadata_value(group, "idSerie")
            if canonical_title in CF300_LONG_TERM_TITLES and isinstance(serie_id, str) and serie_id in batch:
                matches[canonical_title] = {"serie_id": serie_id, "titulo_oficial": title}
        if len(matches) == len(CF300_LONG_TERM_TITLES):
            break

    comparisons: list[dict[str, Any]] = []
    for title, (field, expected) in CF300_LONG_TERM_TITLES.items():
        match = matches.get(title)
        obtained: Any = None
        error_code: str | None = None
        serie_id = match["serie_id"] if match else None
        if serie_id:
            try:
                payload = _fetch_candidate_data(client, serie_id, fecha_corte, LONG_TERM_CANDIDATE_SERIES)
                _returned, _date, obtained = _raw_first_observation(payload)
            except BanxicoClientError as error:
                error_code = error.code
        comparisons.append({
            "campo": field,
            "serie_id": serie_id,
            "titulo_oficial": match["titulo_oficial"] if match else None,
            "valor_obtenido": obtained,
            "valor_CF300": expected,
            "coincide": bool(match) and obtained == expected and error_code is None,
            "codigo_error_sanitizado": error_code,
        })
    return {
        "primer_id_revisado": LONG_TERM_CANDIDATE_SERIES[0],
        "ultimo_id_revisado": last_id,
        "candidatos_consultados": consulted,
        "lotes_usados": batches_used,
        "errores_por_lote": batch_errors,
        "campos_encontrados": len(matches),
        "coincidencias": comparisons,
    }


def run_diagnostic(fecha_corte: str) -> dict[str, Any]:
    client = BanxicoClient.from_environment()
    control = _probe_data(client, "SF43718", fecha_corte)
    target = _probe_data(client, "SF45422", fecha_corte)
    metadata = _probe_metadata(client)
    entries, validation_issues = diagnose_required_series(client, fecha_corte)
    metadata_records, metadata_batch_errors = acquire_cf300_metadata(client)
    metadata_matches, cf300_comparisons = diagnose_cf300_metadata(client, fecha_corte, metadata_records)
    metadata_candidates = inspect_cf300_metadata_candidates(metadata_records)
    result: dict[str, Any] = {
        "fecha_corte": fecha_corte,
        "pruebas": [control, target, metadata],
        "series_requeridas": entries,
        "resumen_normalizacion": {
            "normalizadas_correctamente": sum(entry["normalizacion_estado"] == "NORMALIZADA" for entry in entries),
            "fallidas": sum(entry["normalizacion_estado"] == "ERROR" for entry in entries),
            "incidencias_validacion": validation_issues,
        },
        "metadatos_cf300": metadata_matches,
        "metadatos_cf300_candidatos": metadata_candidates,
        "resumen_metadatos_cf300": {
            "series_solicitadas": len(METADATA_CANDIDATE_SERIES),
            "series_recibidas": len(metadata_records),
            "numero_lotes": len(_metadata_batches(METADATA_CANDIDATE_SERIES)),
            "errores_por_lote": metadata_batch_errors,
        },
        "validacion_cf300": cf300_comparisons,
    }
    return result


def run_long_term_diagnostic(fecha_corte: str) -> dict[str, Any]:
    return {"fecha_corte": fecha_corte, "busqueda_20_30": locate_long_term_cf300_series(BanxicoClient.from_environment(), fecha_corte)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnóstico manual sanitizado de Banxico SIE.")
    parser.add_argument("fecha_corte", nargs="?", default="2026-11-11")
    parser.add_argument("--long-term-only", action="store_true")
    parser.add_argument("--excel-auxiliary-only", action="store_true")
    args = parser.parse_args()
    if args.long_term_only and args.excel_auxiliary_only:
        parser.error("Seleccione sólo un diagnóstico acotado.")
    result = diagnose_excel_auxiliary_inputs(BanxicoClient.from_environment(), args.fecha_corte) if args.excel_auxiliary_only else run_long_term_diagnostic(args.fecha_corte) if args.long_term_only else run_diagnostic(args.fecha_corte)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
