"""Validación independiente para curvas PCHIP históricas y Excel 182/360."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from backend.excel_bootstrap import METHODOLOGY as EXCEL_METHODOLOGY
class CurveValidationError(ValueError):
    """Resultado de curva no apto para validación técnica."""


EXCEL_PERIOD_DAYS = 182
EXCEL_DAY_COUNT = "182/360"
EXCEL_INTERPOLATION_METHOD = "LINEAR_SPOT_RATE"
# Tolerancia exclusiva para CETES de la ruta Excel, en MXN por 10 de nominal.
# Cubre sólo redondeo del benchmark histórico después de invertir la equivalencia
# 182/360 (máximo observado cercano a 5.61e-08). No sustituye la tolerancia de
# M-Bonos de 1e-8 ni se extiende a PCHIP u otras metodologías.
EXCEL_CETES_PRICE_TOLERANCE = 1e-7
PCHIP_METHODOLOGY = "PCHIP_LOG_DISCOUNT_FACTOR"
PCHIP_DAY_COUNT = "ACT/365F"
PRICE_BASIS = "DIRTY"
PRICE_UNIT = "MXN_PER_100_FACE"
CALIBRATION_TOLERANCE = 1e-8


@dataclass(frozen=True)
class _ExcelNode:
    instrument_id: str
    days: int
    spot_rate: float


def _finite_number(value: Any, code: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CurveValidationError(code)
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0):
        raise CurveValidationError(code)
    return result


def _validate_identity(payload: dict[str, Any], curve: dict[str, Any]) -> None:
    if not isinstance(payload, dict) or not isinstance(curve, dict):
        raise CurveValidationError("ENTRADA_INVALIDA")
    if curve.get("case_id") != payload.get("case_id") or curve.get("curve_version") != payload.get("curve_version"):
        raise CurveValidationError("IDENTIFICADORES_INCONSISTENTES")
    if curve.get("mode") != "SIMULADO" or payload.get("mode") != "SIMULADO":
        raise CurveValidationError("MODO_NO_PERMITIDO")


def _validate_pchip(payload: dict[str, Any], curve: dict[str, Any], tolerance: float) -> dict[str, Any]:
    """Conserva la validación histórica; SciPy sólo se importa en esta rama."""
    from scipy.interpolate import PchipInterpolator
    from backend.spot_curve import SpotCurveValidationError, _Node, _parse_date, _parse_instruments

    conventions = curve.get("conventions", {})
    if conventions.get("price_basis") != PRICE_BASIS or conventions.get("price_unit") != PRICE_UNIT or conventions.get("day_count") != PCHIP_DAY_COUNT or conventions.get("interpolation_method") != PCHIP_METHODOLOGY:
        raise CurveValidationError("CONVENCIONES_INCONSISTENTES")
    try:
        valuation_date = _parse_date(payload.get("valuation_date"), "valuation_date")
        instruments = _parse_instruments(payload.get("instruments", []), valuation_date)
    except SpotCurveValidationError as error:
        raise CurveValidationError("ENTRADA_CUANTITATIVA_INVALIDA") from error
    raw_pillars = curve.get("pillars")
    if not isinstance(raw_pillars, list) or len(raw_pillars) != len(instruments):
        raise CurveValidationError("PILARES_INCOMPLETOS")
    nodes = [_Node(0.0, 1.0, "ANCHOR")]
    expected = {item.instrument_id: item.maturity_time for item in instruments}
    for pillar in raw_pillars:
        if not isinstance(pillar, dict) or pillar.get("instrument_id") not in expected:
            raise CurveValidationError("PILAR_INVALIDO")
        time, factor = pillar.get("time_years"), pillar.get("discount_factor")
        if isinstance(time, bool) or isinstance(factor, bool) or not isinstance(time, (int, float)) or not isinstance(factor, (int, float)) or not math.isfinite(time) or not math.isfinite(factor) or time <= 0 or factor <= 0:
            raise CurveValidationError("PILAR_INVALIDO")
        if not math.isclose(float(time), expected[pillar["instrument_id"]], abs_tol=1e-12):
            raise CurveValidationError("FECHA_PILAR_INCONSISTENTE")
        nodes.append(_Node(float(time), float(factor), pillar["instrument_id"]))
    nodes.sort(key=lambda node: node.time)
    if any(right.time <= left.time for left, right in zip(nodes, nodes[1:])):
        raise CurveValidationError("PILARES_DUPLICADOS")
    interpolator = PchipInterpolator([node.time for node in nodes], [math.log(node.discount_factor) for node in nodes], extrapolate=False)
    details, max_error = [], 0.0
    for item in instruments:
        theoretical = 0.0
        for time, amount in item.cashflows:
            log_factor = float(interpolator(time))
            if not math.isfinite(log_factor):
                raise CurveValidationError("EXTRAPOLACION_NO_PERMITIDA")
            theoretical += amount * math.exp(log_factor)
        error = abs(theoretical - item.dirty_price)
        max_error = max(max_error, error)
        details.append({"instrument_id": item.instrument_id, "dirty_price_input": item.dirty_price, "dirty_price_recalculated": theoretical, "absolute_repricing_error": error})
    if max_error > tolerance:
        raise CurveValidationError("REPRICING_FUERA_DE_TOLERANCIA")
    return {"case_id": curve["case_id"], "curve_version": curve["curve_version"], "mode": "SIMULADO", "estado": "VALIDA", "metodologia": PCHIP_METHODOLOGY, "tolerance": tolerance, "max_absolute_repricing_error": max_error, "repricing": details, "pillars": curve["pillars"]}


def _excel_discount(rate: float, days: int) -> float:
    return (1.0 + rate * EXCEL_PERIOD_DAYS / 360.0) ** (-days / EXCEL_PERIOD_DAYS)


def _excel_linear_rate(nodes: list[_ExcelNode], days: int) -> float:
    ordered = sorted(nodes, key=lambda node: node.days)
    for left, right in zip(ordered, ordered[1:]):
        if left.days <= days <= right.days:
            return left.spot_rate + (days - left.days) * (right.spot_rate - left.spot_rate) / (right.days - left.days)
    if ordered and days == ordered[-1].days:
        return ordered[-1].spot_rate
    raise CurveValidationError("EXTRAPOLACION_NO_PERMITIDA")


def _excel_cashflows(days: int, coupon_rate: float, face: float = 100.0) -> list[tuple[int, float]]:
    if days <= 0 or not math.isfinite(coupon_rate) or not math.isfinite(face) or face <= 0:
        raise CurveValidationError("FLUJOS_INCONSISTENTES")
    schedule = list(range(days % EXCEL_PERIOD_DAYS or EXCEL_PERIOD_DAYS, days + 1, EXCEL_PERIOD_DAYS))
    if schedule[-1] != days:
        schedule.append(days)
    coupon = face * coupon_rate * EXCEL_PERIOD_DAYS / 360.0
    return [(item, coupon + (face if item == days else 0.0)) for item in schedule]


def _excel_cetes_price(rate_182: float, days: int) -> float:
    """Reprice CETES by independently reversing the 182/360 equivalence."""
    if not math.isfinite(rate_182) or not isinstance(days, int) or days <= 0:
        raise CurveValidationError("CETES_CONVENCION_INVALIDA")
    base = 1.0 + rate_182 * EXCEL_PERIOD_DAYS / 360.0
    if base <= 0:
        raise CurveValidationError("CETES_CONVENCION_INVALIDA")
    ytm = base ** (360.0 / EXCEL_PERIOD_DAYS) - 1.0
    if not math.isfinite(ytm):
        raise CurveValidationError("CETES_CONVENCION_INVALIDA")
    denominator = 1.0 + ytm * days / 360.0
    if denominator <= 0 or not math.isfinite(denominator):
        raise CurveValidationError("CETES_CONVENCION_INVALIDA")
    theoretical = 10.0 / denominator
    if not math.isfinite(theoretical) or theoretical <= 0:
        raise CurveValidationError("CETES_CONVENCION_INVALIDA")
    return theoretical


def _excel_payload(payload: dict[str, Any]) -> tuple[list[tuple[str, int, float, float]], list[tuple[str, int, float, float]]]:
    if payload.get("metodologia") != EXCEL_METHODOLOGY:
        raise CurveValidationError("METODOLOGIA_INCOMPATIBLE")
    cetes, bonds = payload.get("excel_cetes_nodes"), payload.get("excel_mbonos")
    if not isinstance(cetes, list) or not isinstance(bonds, list) or not cetes or not bonds:
        raise CurveValidationError("ENTRADA_CUANTITATIVA_INVALIDA")
    parsed_cetes, parsed_bonds = [], []
    for entry in cetes:
        if not isinstance(entry, list) or len(entry) != 4 or not isinstance(entry[0], str) or not isinstance(entry[1], int):
            raise CurveValidationError("ENTRADA_CUANTITATIVA_INVALIDA")
        instrument_id, days = entry[0], entry[1]
        price, rate = _finite_number(entry[2], "PRECIO_NO_FINITO", positive=True), _finite_number(entry[3], "TASA_NO_FINITA")
        if days <= 0:
            raise CurveValidationError("PLAZO_NO_FINITO")
        parsed_cetes.append((instrument_id, days, price, rate))
    for entry in bonds:
        if not isinstance(entry, list) or len(entry) != 4 or not isinstance(entry[0], str) or not isinstance(entry[1], int):
            raise CurveValidationError("ENTRADA_CUANTITATIVA_INVALIDA")
        instrument_id, days = entry[0], entry[1]
        price, coupon_rate = _finite_number(entry[2], "PRECIO_NO_FINITO", positive=True), _finite_number(entry[3], "TASA_NO_FINITA", positive=True)
        if days <= 0:
            raise CurveValidationError("PLAZO_NO_FINITO")
        parsed_bonds.append((instrument_id, days, price, coupon_rate))
    source = parsed_cetes + parsed_bonds
    if len({item[0] for item in source}) != len(source) or len({item[1] for item in source}) != len(source):
        raise CurveValidationError("PILARES_DUPLICADOS")
    return parsed_cetes, parsed_bonds


def _validate_excel(payload: dict[str, Any], curve: dict[str, Any], tolerance: float) -> dict[str, Any]:
    conventions = curve.get("conventions", {})
    expected_conventions = {"methodology": EXCEL_METHODOLOGY, "price_basis": PRICE_BASIS, "price_unit": PRICE_UNIT, "day_count": EXCEL_DAY_COUNT, "coupon_period_days": EXCEL_PERIOD_DAYS, "interpolation_method": EXCEL_INTERPOLATION_METHOD}
    if not isinstance(conventions, dict) or any(conventions.get(key) != value for key, value in expected_conventions.items()):
        raise CurveValidationError("CONVENCIONES_INCONSISTENTES")
    cetes, bonds = _excel_payload(payload)
    raw_pillars = curve.get("pillars")
    source = cetes + bonds
    if not isinstance(raw_pillars, list) or len(raw_pillars) != len(source):
        raise CurveValidationError("PILARES_INCOMPLETOS")
    expected = {item[0]: item[1] for item in source}
    overnight_rate = _finite_number(payload.get("overnight_rate", 0.0675), "TASA_NO_FINITA")
    nodes: list[_ExcelNode] = [_ExcelNode("OVERNIGHT", 1, overnight_rate)]
    for pillar in raw_pillars:
        if not isinstance(pillar, dict) or pillar.get("instrument_id") not in expected:
            raise CurveValidationError("PILAR_INVALIDO")
        days = pillar.get("days")
        rate = _finite_number(pillar.get("spot_rate"), "TASA_NO_FINITA")
        if isinstance(days, bool) or not isinstance(days, int) or days <= 0:
            raise CurveValidationError("PLAZO_NO_FINITO")
        if days != expected[pillar["instrument_id"]]:
            raise CurveValidationError("FECHA_PILAR_INCONSISTENTE")
        nodes.append(_ExcelNode(pillar["instrument_id"], days, rate))
    nodes.sort(key=lambda node: node.days)
    if any(right.days <= left.days for left, right in zip(nodes, nodes[1:])):
        raise CurveValidationError("PILARES_DUPLICADOS")
    details: list[dict[str, Any]] = []
    max_error = 0.0
    for instrument_id, days, observed, rate in cetes:
        theoretical = _excel_cetes_price(rate, days)
        error = abs(theoretical - observed)
        if error > EXCEL_CETES_PRICE_TOLERANCE:
            raise CurveValidationError("REPRICING_FUERA_DE_TOLERANCIA")
        details.append({"instrument_id": instrument_id, "dirty_price_input": observed, "dirty_price_recalculated": theoretical, "absolute_repricing_error": error})
        max_error = max(max_error, error)
    for instrument_id, days, observed, coupon_rate in bonds:
        theoretical = sum(amount * _excel_discount(_excel_linear_rate(nodes, flow_day), flow_day) for flow_day, amount in _excel_cashflows(days, coupon_rate))
        error = abs(theoretical - observed)
        max_error = max(max_error, error)
        details.append({"instrument_id": instrument_id, "dirty_price_input": observed, "dirty_price_recalculated": theoretical, "absolute_repricing_error": error})
        if error > tolerance:
            raise CurveValidationError("REPRICING_FUERA_DE_TOLERANCIA")
    return {"case_id": curve["case_id"], "curve_version": curve["curve_version"], "mode": "SIMULADO", "estado": "VALIDA", "metodologia": EXCEL_METHODOLOGY, "tolerance": tolerance, "cetes_price_tolerance": EXCEL_CETES_PRICE_TOLERANCE, "max_absolute_repricing_error": max_error, "repricing": details, "pillars": curve["pillars"]}


def validate_spot_curve(payload: dict[str, Any], curve: dict[str, Any], tolerance: float = CALIBRATION_TOLERANCE) -> dict[str, Any]:
    """Despacha validación independiente sin reinterpretar metodologías."""
    _validate_identity(payload, curve)
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise CurveValidationError("TOLERANCIA_INVALIDA")
    methodology = curve.get("conventions", {}).get("methodology")
    if methodology == EXCEL_METHODOLOGY:
        return _validate_excel(payload, curve, tolerance)
    if methodology in {None, PCHIP_METHODOLOGY}:
        return _validate_pchip(payload, curve, tolerance)
    raise CurveValidationError("METODOLOGIA_INCOMPATIBLE")
