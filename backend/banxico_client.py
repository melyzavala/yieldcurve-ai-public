"""Cliente y normalizadores defensivos de datos de Banxico para Siena."""

from __future__ import annotations

import json
import math
import os
import re
import socket
from datetime import date, datetime
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_BASE = "https://www.banxico.org.mx/SieAPIRest/service"
REQUEST_TIMEOUT_SECONDS = 15
SERIE_ID_PATTERN = re.compile(r"^S[FP]\d+$")


def _serie(
    instrumento: str, campo: str, unidad: str, representatividad: str, etiqueta_oficial: str
) -> dict[str, str]:
    return {
        "instrumento": instrumento,
        "campo": campo,
        "unidad": unidad,
        "representatividad": representatividad,
        "etiqueta_oficial": etiqueta_oficial,
    }


# Fuente de identificadores y etiquetas: catálogo oficial SIE. Las series de
# CF300 son referencias on-the-run; los Bonos M no son emisiones individuales.
SERIES_CATALOG: dict[str, dict[str, str]] = {
    "SF45422": _serie("CETES", "PLAZO_DIAS", "DIAS", "INSTRUMENTO_ON_THE_RUN", "Cetes 28 días - Plazo"),
    "SF45439": _serie("CETES", "PRECIO_SUCIO", "SIN_UNIDAD_PUBLICADA", "INSTRUMENTO_ON_THE_RUN", "Cetes 28 días - Precio Sucio"),
    "SF45423": _serie("CETES", "PLAZO_DIAS", "DIAS", "INSTRUMENTO_ON_THE_RUN", "Cetes 91 días - Plazo"),
    "SF45441": _serie("CETES", "PRECIO_SUCIO", "SIN_UNIDAD_PUBLICADA", "INSTRUMENTO_ON_THE_RUN", "Cetes 91 días - Precio Sucio"),
    "SF45424": _serie("CETES", "PLAZO_DIAS", "DIAS", "INSTRUMENTO_ON_THE_RUN", "Cetes 182 días - Plazo"),
    "SF45443": _serie("CETES", "PRECIO_SUCIO", "SIN_UNIDAD_PUBLICADA", "INSTRUMENTO_ON_THE_RUN", "Cetes 182 días - Precio Sucio"),
    "SF45425": _serie("CETES", "PLAZO_DIAS", "DIAS", "INSTRUMENTO_ON_THE_RUN", "Cetes 364 días - Plazo"),
    "SF45445": _serie("CETES", "PRECIO_SUCIO", "SIN_UNIDAD_PUBLICADA", "INSTRUMENTO_ON_THE_RUN", "Cetes 364 días - Precio Sucio"),
    "SF349886": _serie("CETES", "PLAZO_DIAS", "DIAS", "INSTRUMENTO_ON_THE_RUN", "Cetes 2 años - Plazo"),
    "SF349888": _serie("CETES", "PRECIO_SUCIO", "SIN_UNIDAD_PUBLICADA", "INSTRUMENTO_ON_THE_RUN", "Cetes 2 años - Precio Sucio"),
    "SF45427": _serie("MBONOS", "PLAZO_DIAS", "DIAS", "RANGO_ON_THE_RUN", "Bonos 0 a 3 años - Plazo"),
    "SF45449": _serie("MBONOS", "PRECIO_SUCIO", "SIN_UNIDAD_PUBLICADA", "RANGO_ON_THE_RUN", "Bonos 0 a 3 años - Precio Sucio"),
    "SF45475": _serie("MBONOS", "CUPON_VIGENTE", "PORCENTAJE", "RANGO_ON_THE_RUN", "Bonos 0 a 3 años - Cupón Vigente"),
    "SF45428": _serie("MBONOS", "PLAZO_DIAS", "DIAS", "RANGO_ON_THE_RUN", "Bonos 3 a 5 años - Plazo"),
    "SF45451": _serie("MBONOS", "PRECIO_SUCIO", "SIN_UNIDAD_PUBLICADA", "RANGO_ON_THE_RUN", "Bonos 3 a 5 años - Precio Sucio"),
    "SF45476": _serie("MBONOS", "CUPON_VIGENTE", "PORCENTAJE", "RANGO_ON_THE_RUN", "Bonos 3 a 5 años - Cupón Vigente"),
    "SF45430": _serie("MBONOS", "PLAZO_DIAS", "DIAS", "RANGO_ON_THE_RUN", "Bonos 7 a 10 años - Plazo"),
    "SF45455": _serie("MBONOS", "PRECIO_SUCIO", "SIN_UNIDAD_PUBLICADA", "RANGO_ON_THE_RUN", "Bonos 7 a 10 años - Precio Sucio"),
    "SF45478": _serie("MBONOS", "CUPON_VIGENTE", "PORCENTAJE", "RANGO_ON_THE_RUN", "Bonos 7 a 10 años - Cupón Vigente"),
    "SF45431": _serie("MBONOS", "PLAZO_DIAS", "DIAS", "RANGO_ON_THE_RUN", "Bonos 10 a 20 años - Plazo"),
    "SF45457": _serie("MBONOS", "PRECIO_SUCIO", "SIN_UNIDAD_PUBLICADA", "RANGO_ON_THE_RUN", "Bonos 10 a 20 años - Precio Sucio"),
    "SF45479": _serie("MBONOS", "CUPON_VIGENTE", "PORCENTAJE", "RANGO_ON_THE_RUN", "Bonos 10 a 20 años - Cupón Vigente"),
    "SF60720": _serie("MBONOS", "PLAZO_DIAS", "DIAS", "RANGO_ON_THE_RUN", "Bonos 20 a 30 años - Plazo"),
    "SF60722": _serie("MBONOS", "PRECIO_SUCIO", "SIN_UNIDAD_PUBLICADA", "RANGO_ON_THE_RUN", "Bonos 20 a 30 años - Precio Sucio"),
    "SF60723": _serie("MBONOS", "CUPON_VIGENTE", "PORCENTAJE", "RANGO_ON_THE_RUN", "Bonos 20 a 30 años - Cupón Vigente"),
    "SF43774": _serie("FONDEO_GUBERNAMENTAL", "TASA_ANUAL", "PORCENTAJE", "SERIE_MERCADO", "Tasa de fondeo gubernamental, mediana ponderada por volumen, tasa de interés en por ciento anual"),
}

CURVE_REQUIRED_SERIES = tuple(SERIES_CATALOG)
# SF349889 (Cetes 2 años - Tasa Rendimiento) es sólo control diagnóstico: el
# rendimiento puede reconstruirse determinísticamente desde plazo y precio sucio.
CF300_SERIES = frozenset(serie_id for serie_id in SERIES_CATALOG if serie_id != "SF43774")
FONDEO_GUBERNAMENTAL_SERIES = frozenset({"SF43774"})
DIAGNOSTIC_DATA_SERIES = frozenset({"SF43718", "SF45422"})
DIAGNOSTIC_METADATA_SERIES = "SF45422"


class BanxicoClientError(RuntimeError):
    """Error sanitizado de integración o normalización de Banxico."""

    def __init__(self, code: str, http_status: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.http_status = http_status


def _http_error_code(status: int) -> str:
    if status == 400:
        return "BANXICO_HTTP_400"
    if status == 401:
        return "BANXICO_HTTP_401"
    if status == 403:
        return "BANXICO_HTTP_403"
    if status == 404:
        return "BANXICO_HTTP_404"
    if status == 429:
        return "BANXICO_HTTP_429"
    if 500 <= status <= 599:
        return "BANXICO_HTTP_5XX"
    return "BANXICO_HTTP_ERROR"


def _sanitized_transport_error(error: Exception) -> BanxicoClientError:
    if isinstance(error, HTTPError):
        return BanxicoClientError(_http_error_code(error.code), error.code)
    if isinstance(error, (TimeoutError, socket.timeout)):
        return BanxicoClientError("BANXICO_TIMEOUT")
    if isinstance(error, URLError):
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            return BanxicoClientError("BANXICO_TIMEOUT")
        return BanxicoClientError("BANXICO_NETWORK_ERROR")
    if isinstance(error, json.JSONDecodeError):
        return BanxicoClientError("BANXICO_JSON_INVALIDO")
    return BanxicoClientError("BANXICO_NETWORK_ERROR")


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise ValueError("La fecha debe usar ISO 8601 YYYY-MM-DD.") from error


def banxico_date(value: str) -> str:
    return parse_iso_date(value).isoformat()


def _normalize_source_date(value: Any) -> str:
    if not isinstance(value, str):
        raise BanxicoClientError("BANXICO_RESPUESTA_INVALIDA")
    for parser in (date.fromisoformat, lambda item: datetime.strptime(item, "%d/%m/%Y").date()):
        try:
            return parser(value).isoformat()
        except ValueError:
            continue
    raise BanxicoClientError("BANXICO_RESPUESTA_INVALIDA")


def _normalize_value(value: Any) -> float:
    if isinstance(value, bool) or value is None:
        raise BanxicoClientError("BANXICO_RESPUESTA_INVALIDA")
    text = str(value).strip()
    if not text:
        raise BanxicoClientError("BANXICO_RESPUESTA_INVALIDA")
    numeric_pattern = re.compile(r"[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?")
    if not numeric_pattern.fullmatch(text):
        raise BanxicoClientError("BANXICO_RESPUESTA_INVALIDA")
    try:
        normalized = float(text.replace(",", ""))
    except (TypeError, ValueError) as error:
        raise BanxicoClientError("BANXICO_RESPUESTA_INVALIDA") from error
    if not math.isfinite(normalized):
        raise BanxicoClientError("BANXICO_RESPUESTA_INVALIDA")
    return normalized


def normalize_banxico_response(payload: dict[str, Any], requested_series: list[str]) -> list[dict[str, Any]]:
    requested = set(requested_series)
    if not requested or not requested.issubset(SERIES_CATALOG):
        raise BanxicoClientError("BANXICO_SERIE_NO_AUTORIZADA")
    try:
        groups = payload["bmx"]["series"]
    except (KeyError, TypeError) as error:
        raise BanxicoClientError("BANXICO_RESPUESTA_INVALIDA") from error
    if not isinstance(groups, list) or not groups:
        raise BanxicoClientError("BANXICO_RESPUESTA_INVALIDA")

    observations: list[dict[str, Any]] = []
    returned: set[str] = set()
    for group in groups:
        if not isinstance(group, dict):
            raise BanxicoClientError("BANXICO_RESPUESTA_INVALIDA")
        serie_id = group.get("idSerie")
        if not isinstance(serie_id, str) or serie_id not in requested or serie_id not in SERIES_CATALOG:
            raise BanxicoClientError("BANXICO_RESPUESTA_INVALIDA")
        if serie_id in returned:
            raise BanxicoClientError("BANXICO_RESPUESTA_INVALIDA")
        datos = group.get("datos")
        if not isinstance(datos, list) or not datos:
            raise BanxicoClientError("BANXICO_RESPUESTA_INVALIDA")
        returned.add(serie_id)
        for item in datos:
            if not isinstance(item, dict) or "fecha" not in item or "dato" not in item:
                raise BanxicoClientError("BANXICO_RESPUESTA_INVALIDA")
            observations.append({
                "serie_id": serie_id,
                "fecha": _normalize_source_date(item["fecha"]),
                "valor": _normalize_value(item["dato"]),
                "unidad": SERIES_CATALOG[serie_id]["unidad"],
            })
    if returned != requested:
        raise BanxicoClientError("BANXICO_RESPUESTA_INVALIDA")
    return observations


class BanxicoClient:
    def __init__(self, token: str, transport: Callable[[str, dict[str, str], float], dict[str, Any]] | None = None) -> None:
        if not token:
            raise BanxicoClientError("BANXICO_API_TOKEN_NO_CONFIGURADO")
        self._token = token
        self._transport = transport or self._default_transport

    @classmethod
    def from_environment(cls, transport: Callable[[str, dict[str, str], float], dict[str, Any]] | None = None) -> "BanxicoClient":
        return cls(os.environ.get("BANXICO_API_TOKEN", ""), transport=transport)

    def fetch_series(self, serie_id: str, fecha_inicial: str, fecha_final: str) -> dict[str, Any]:
        if not SERIE_ID_PATTERN.fullmatch(serie_id) or serie_id not in SERIES_CATALOG:
            raise ValueError("El identificador de serie no está autorizado.")
        if parse_iso_date(fecha_inicial) > parse_iso_date(fecha_final):
            raise ValueError("La fecha inicial no puede ser posterior a la fecha final.")
        url = f"{API_BASE}/v1/series/{serie_id}/datos/{banxico_date(fecha_inicial)}/{banxico_date(fecha_final)}"
        return self._request(url)

    def fetch_diagnostic_data(self, serie_id: str, fecha_corte: str) -> dict[str, Any]:
        """Probe limitado a las dos series autorizadas para diagnóstico manual."""
        if serie_id not in DIAGNOSTIC_DATA_SERIES:
            raise ValueError("La serie no está autorizada para diagnóstico.")
        url = f"{API_BASE}/v1/series/{serie_id}/datos/{banxico_date(fecha_corte)}/{banxico_date(fecha_corte)}"
        return self._request(url)

    def fetch_diagnostic_metadata(self) -> dict[str, Any]:
        """Consulta de metadatos limitada a la primera serie objetivo de Siena."""
        return self._request(f"{API_BASE}/v1/series/{DIAGNOSTIC_METADATA_SERIES}")

    def _request(self, url: str) -> dict[str, Any]:
        try:
            return self._transport(url, {"Bmx-Token": self._token, "Accept": "application/json"}, REQUEST_TIMEOUT_SECONDS)
        except BanxicoClientError:
            raise
        except Exception as error:
            raise _sanitized_transport_error(error) from error

    def fetch_for_date(self, series_ids: list[str], fecha_corte: str) -> dict[str, dict[str, Any]]:
        """Consulta exactamente la fecha solicitada, sin sustitución por días previos."""
        parse_iso_date(fecha_corte)
        if not series_ids or len(set(series_ids)) != len(series_ids) or not set(series_ids).issubset(SERIES_CATALOG):
            raise ValueError("Las series solicitadas deben ser autorizadas y no duplicadas.")
        return {serie_id: self.fetch_series(serie_id, fecha_corte, fecha_corte) for serie_id in series_ids}

    @staticmethod
    def _default_transport(url: str, headers: dict[str, str], timeout: float) -> dict[str, Any]:
        request = Request(url, headers=headers)
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))


def validate_observations(fecha_corte: str, series_ids: list[str], observaciones: list[dict[str, Any]]) -> list[str]:
    cutoff = parse_iso_date(fecha_corte)
    expected = set(series_ids)
    issues: list[str] = []
    seen: set[tuple[str, str]] = set()
    observed: set[str] = set()
    for observation in observaciones:
        serie_id = observation.get("serie_id")
        fecha = observation.get("fecha")
        key = (str(serie_id), str(fecha))
        if key in seen:
            issues.append("OBSERVACION_DUPLICADA")
        seen.add(key)
        if serie_id not in expected:
            issues.append("SERIE_NO_SOLICITADA")
            continue
        observed.add(serie_id)
        if serie_id not in SERIES_CATALOG:
            issues.append("SERIE_SIN_METADATOS")
            continue
        try:
            if parse_iso_date(str(fecha)) != cutoff:
                issues.append("FECHA_CORTE_INCONSISTENTE")
        except ValueError:
            issues.append("FECHA_INVALIDA")
        if observation.get("unidad") != SERIES_CATALOG[serie_id]["unidad"]:
            issues.append("UNIDAD_INCONSISTENTE")
        value = observation.get("valor")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            issues.append("VALOR_FALTANTE_O_INVALIDO")
    if expected - observed:
        issues.append("SERIE_FALTANTE")
    return sorted(set(issues))
