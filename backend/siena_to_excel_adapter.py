"""Adaptador determinista de Siena validada hacia EXCEL_BOOTSTRAP_182D_V1."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from backend.banxico_client import CF300_SERIES, CURVE_REQUIRED_SERIES, FONDEO_GUBERNAMENTAL_SERIES, SERIES_CATALOG
from backend.excel_bootstrap import METHODOLOGY


ROOT = Path(__file__).resolve().parents[1]
CASE_SCHEMA = ROOT / "agents" / "contracts" / "case.schema.json"
SIENA_SCHEMA = ROOT / "agents" / "contracts" / "siena.output.schema.json"
TOLERANCE = 1e-8
MAX_ITERATIONS = 200

CETES_MAPPING = (
    ("C28", "SF45422", "SF45439"),
    ("C91", "SF45423", "SF45441"),
    ("C182", "SF45424", "SF45443"),
    ("C364", "SF45425", "SF45445"),
    ("C2Y", "SF349886", "SF349888"),
)
MBONOS_MAPPING = (
    ("MBONO_0_3", "SF45427", "SF45449", "SF45475"),
    ("MBONO_3_5", "SF45428", "SF45451", "SF45476"),
    ("MBONO_7_10", "SF45430", "SF45455", "SF45478"),
    ("MBONO_10_20", "SF45431", "SF45457", "SF45479"),
    ("MBONO_20_30", "SF60720", "SF60722", "SF60723"),
)


class SienaToExcelAdapterError(ValueError):
    """Fallo sanitizado y fail-closed de la transformación."""


def _fail(code: str) -> None:
    raise SienaToExcelAdapterError(code)


def _schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_contract(value: Any, path: Path, code: str) -> None:
    try:
        Draft202012Validator(_schema(path), format_checker=FormatChecker()).validate(value)
    except (ValidationError, json.JSONDecodeError, OSError):
        _fail(code)


def _positive_integer(value: Any, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0 or int(value) != value:
        _fail(code)
    return int(value)


def _positive_number(value: Any, code: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        _fail(code)
    return float(value)


def _validate_case(case: Any) -> None:
    _validate_contract(case, CASE_SCHEMA, "CASE_INVALID")
    if case.get("modo") != "SIMULADO" or not isinstance(case.get("version_curva"), str):
        _fail("CASE_INVALID")


def _validate_source(siena: dict[str, Any]) -> None:
    resources = siena["fuente"].get("recursos")
    if not isinstance(resources, list) or len(resources) != 2:
        _fail("SIENA_SOURCE_MISMATCH")
    seen: dict[tuple[str, str], set[str]] = {}
    for resource in resources:
        if not isinstance(resource, dict) or not isinstance(resource.get("series"), list):
            _fail("SIENA_SOURCE_MISMATCH")
        key = (resource.get("tipo"), resource.get("identificador"))
        if key in seen:
            _fail("SIENA_SOURCE_MISMATCH")
        seen[key] = set(resource["series"])
    if seen.get(("CUADRO_SIE", "CF300")) != set(CF300_SERIES) or seen.get(("SERIE_SIE", "SF43774")) != set(FONDEO_GUBERNAMENTAL_SERIES):
        _fail("SIENA_SOURCE_MISMATCH")


def _observations_by_id(case: dict[str, Any], siena: Any) -> dict[str, float]:
    _validate_contract(siena, SIENA_SCHEMA, "SIENA_CONTRACT_INVALID")
    if siena.get("estado") != "DATOS_VALIDOS" or siena.get("modo") != "SIMULADO":
        _fail("SIENA_NOT_VALID")
    source = siena.get("fuente", {})
    if source.get("proveedor") != "Banco de México" or source.get("datos_mercado") != "REALES":
        _fail("SIENA_SOURCE_MISMATCH")
    if siena.get("fecha_corte") != case["fecha_corte"]:
        _fail("SIENA_DATE_MISMATCH")
    summary = siena.get("resumen_validacion", {})
    if summary != {"series_solicitadas": 26, "series_con_observacion": 26, "observaciones_validas": 26, "observaciones_rechazadas": 0} or siena.get("errores") != []:
        _fail("SIENA_NOT_VALID")
    _validate_source(siena)
    metadata = siena.get("series")
    if not isinstance(metadata, list) or len(metadata) != 26:
        _fail("SIENA_SERIES_MISMATCH")
    metadata_ids = [item.get("serie_id") for item in metadata if isinstance(item, dict)]
    if len(metadata_ids) != len(set(metadata_ids)) or set(metadata_ids) != set(CURVE_REQUIRED_SERIES):
        _fail("SIENA_SERIES_MISMATCH")
    for item in metadata:
        expected = SERIES_CATALOG[item["serie_id"]]
        if any(item.get(field) != expected[field] for field in expected):
            _fail("SIENA_SERIES_MISMATCH")
    observations = siena.get("observaciones")
    if not isinstance(observations, list) or len(observations) != 26:
        _fail("SIENA_SERIES_MISMATCH")
    output: dict[str, float] = {}
    for item in observations:
        if not isinstance(item, dict):
            _fail("SIENA_CONTRACT_INVALID")
        serie_id = item.get("serie_id")
        if serie_id in output:
            _fail("SIENA_DUPLICATE_OBSERVATION")
        if serie_id not in SERIES_CATALOG:
            _fail("SIENA_SERIES_MISMATCH")
        if item.get("fecha") != case["fecha_corte"]:
            _fail("SIENA_DATE_MISMATCH")
        if item.get("valida") is not True:
            _fail("SIENA_NOT_VALID")
        if item.get("unidad") != SERIES_CATALOG[serie_id]["unidad"]:
            _fail("SIENA_UNIT_MISMATCH")
        value = item.get("valor")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            _fail("SIENA_CONTRACT_INVALID")
        output[serie_id] = float(value)
    if set(output) != set(CURVE_REQUIRED_SERIES):
        _fail("SIENA_SERIES_MISMATCH")
    return output


def build_excel_payload_from_siena(case: dict[str, Any], siena: dict[str, Any]) -> dict[str, Any]:
    """Convierte datos reales ya validados, sin consultar red ni inferir emisiones."""
    _validate_case(case)
    values = _observations_by_id(case, siena)
    cetes: list[list[Any]] = []
    for instrument_id, days_id, price_id in CETES_MAPPING:
        days = _positive_integer(values[days_id], "CETES_INPUT_INVALID")
        price = _positive_number(values[price_id], "CETES_INPUT_INVALID")
        ytm = (10 / price - 1) * 360 / days
        if not math.isfinite(ytm) or 1 + ytm <= 0:
            _fail("CETES_INPUT_INVALID")
        rate_182 = ((1 + ytm) ** (182 / 360) - 1) * (360 / 182)
        if not math.isfinite(rate_182):
            _fail("CETES_INPUT_INVALID")
        cetes.append([instrument_id, days, price, rate_182])
    mbonos: list[list[Any]] = []
    for instrument_id, days_id, price_id, coupon_id in MBONOS_MAPPING:
        days = _positive_integer(values[days_id], "MBONOS_INPUT_INVALID")
        price = _positive_number(values[price_id], "MBONOS_INPUT_INVALID")
        coupon = values[coupon_id] / 100
        if not math.isfinite(coupon) or not 0 <= coupon < 1:
            _fail("MBONOS_INPUT_INVALID")
        mbonos.append([instrument_id, days, price, coupon])
    overnight = values["SF43774"] / 100
    if not math.isfinite(overnight) or not 0 <= overnight < 1:
        _fail("FUNDING_RATE_INVALID")
    return {
        "case_id": case["caso_id"], "curve_version": case["version_curva"], "mode": "SIMULADO",
        "valuation_date": case["fecha_corte"], "metodologia": METHODOLOGY,
        "overnight_rate": overnight, "tolerance": TOLERANCE, "max_iterations": MAX_ITERATIONS,
        "excel_cetes_nodes": cetes, "excel_mbonos": mbonos,
    }
