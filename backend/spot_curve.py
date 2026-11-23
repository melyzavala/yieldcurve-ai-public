"""Motor determinista para curvas spot simuladas de CETES y M-Bonos."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from scipy.interpolate import PchipInterpolator
from scipy.optimize import least_squares


class SpotCurveValidationError(ValueError):
    """Entrada insuficiente o inconsistente para construir una curva spot."""


DAY_COUNT = "ACT/365F"
PRICE_BASIS = "DIRTY"
PRICE_UNIT = "MXN_PER_100_FACE"
INTERPOLATION_METHOD = "PCHIP_LOG_DISCOUNT_FACTOR"
CASE_ID_PATTERN = re.compile(r"^YC-[A-Z0-9]{8,32}$")
CURVE_VERSION_PATTERN = re.compile(r"^CURVA-[A-Z0-9-]{4,64}$")
CALIBRATION_TOLERANCE = 1e-8


@dataclass(frozen=True)
class _Node:
    time: float
    discount_factor: float
    instrument_id: str


@dataclass(frozen=True)
class _Instrument:
    instrument_id: str
    instrument_type: str
    maturity_date: date
    maturity_time: float
    face_value: float
    dirty_price: float
    cashflows: tuple[tuple[float, float], ...]


def _parse_date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise SpotCurveValidationError(f"{field} debe usar ISO 8601 YYYY-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise SpotCurveValidationError(f"{field} debe usar ISO 8601 YYYY-MM-DD.") from error


def _number(value: Any, field: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SpotCurveValidationError(f"{field} debe ser numérico.")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0):
        raise SpotCurveValidationError(f"{field} debe ser un número finito positivo.")
    return result


def _time(valuation_date: date, cashflow_date: date, field: str) -> float:
    days = (cashflow_date - valuation_date).days
    if days <= 0:
        raise SpotCurveValidationError(f"{field} debe ser posterior a valuation_date.")
    return days / 365.0


def _interpolator(nodes: list[_Node]) -> PchipInterpolator:
    ordered = sorted(nodes, key=lambda node: node.time)
    times = [node.time for node in ordered]
    if len(times) < 2 or any(right <= left for left, right in zip(times, times[1:])):
        raise SpotCurveValidationError("Los nodos de descuento deben tener plazos estrictamente crecientes.")
    return PchipInterpolator(times, [math.log(node.discount_factor) for node in ordered], extrapolate=False)


def _discount_factor(interpolator: PchipInterpolator, nodes: list[_Node], time: float) -> float:
    for node in nodes:
        if math.isclose(node.time, time, rel_tol=0.0, abs_tol=1e-12):
            return node.discount_factor
    value = float(interpolator(time))
    if not math.isfinite(value):
        raise SpotCurveValidationError("No existe soporte de nodos para interpolar un flujo.")
    return math.exp(value)


def _validate_common(payload: dict[str, Any]) -> tuple[date, list[dict[str, Any]]]:
    if not isinstance(payload, dict):
        raise SpotCurveValidationError("La entrada debe ser un objeto JSON.")
    if not isinstance(payload.get("case_id"), str) or not CASE_ID_PATTERN.fullmatch(payload["case_id"]):
        raise SpotCurveValidationError("case_id inválido.")
    if not isinstance(payload.get("curve_version"), str) or not CURVE_VERSION_PATTERN.fullmatch(payload["curve_version"]):
        raise SpotCurveValidationError("curve_version inválida.")
    if payload.get("mode") != "SIMULADO":
        raise SpotCurveValidationError("La skill sólo acepta mode=SIMULADO.")
    if payload.get("price_basis") != PRICE_BASIS or payload.get("price_unit") != PRICE_UNIT:
        raise SpotCurveValidationError("La skill requiere precio sucio en MXN por 100 de nominal.")
    if payload.get("day_count") != DAY_COUNT or payload.get("interpolation_method") != INTERPOLATION_METHOD:
        raise SpotCurveValidationError("Las convenciones de días o interpolación no son compatibles.")
    valuation_date = _parse_date(payload.get("valuation_date"), "valuation_date")
    instruments = payload.get("instruments")
    if not isinstance(instruments, list) or not instruments:
        raise SpotCurveValidationError("instruments debe contener al menos un instrumento.")
    return valuation_date, instruments


def _cashflows(raw: dict[str, Any], valuation_date: date, maturity_date: date, face_value: float, instrument_id: str) -> tuple[tuple[float, float], ...]:
    if raw["instrument_type"] == "CETES":
        return ((_time(valuation_date, maturity_date, f"maturity_date de {instrument_id}"), face_value),)
    required = ("coupon_rate_annual", "coupon_frequency", "coupon_dates")
    missing = [item for item in required if item not in raw]
    if missing:
        raise SpotCurveValidationError(f"METADATOS_MBONO_FALTANTES:{instrument_id}:{','.join(missing)}")
    coupon_rate = _number(raw["coupon_rate_annual"], f"coupon_rate_annual de {instrument_id}", positive=True)
    frequency = raw["coupon_frequency"]
    if isinstance(frequency, bool) or not isinstance(frequency, int) or frequency <= 0:
        raise SpotCurveValidationError(f"coupon_frequency de {instrument_id} debe ser entero positivo.")
    dates = raw["coupon_dates"]
    if not isinstance(dates, list) or not dates:
        raise SpotCurveValidationError(f"coupon_dates de {instrument_id} es obligatorio.")
    parsed_dates = [_parse_date(item, f"coupon_dates de {instrument_id}") for item in dates]
    if parsed_dates != sorted(parsed_dates) or len(parsed_dates) != len(set(parsed_dates)) or parsed_dates[-1] != maturity_date:
        raise SpotCurveValidationError(f"coupon_dates de {instrument_id} es inconsistente.")
    coupon = face_value * coupon_rate / frequency
    return tuple((_time(valuation_date, item, f"coupon_dates de {instrument_id}"), coupon + (face_value if item == maturity_date else 0.0)) for item in parsed_dates)


def _parse_instruments(raw_instruments: list[dict[str, Any]], valuation_date: date) -> list[_Instrument]:
    parsed: list[_Instrument] = []
    for raw in raw_instruments:
        if not isinstance(raw, dict):
            raise SpotCurveValidationError("Cada instrumento debe ser un objeto.")
        instrument_id, instrument_type = raw.get("instrument_id"), raw.get("instrument_type")
        if not isinstance(instrument_id, str) or not instrument_id.strip() or instrument_type not in {"CETES", "MBONOS"}:
            raise SpotCurveValidationError("Cada instrumento requiere instrument_id y tipo CETES o MBONOS.")
        maturity_date = _parse_date(raw.get("maturity_date"), f"maturity_date de {instrument_id}")
        maturity_time = _time(valuation_date, maturity_date, f"maturity_date de {instrument_id}")
        face_value = _number(raw.get("face_value"), f"face_value de {instrument_id}", positive=True)
        dirty_price = _number(raw.get("dirty_price"), f"dirty_price de {instrument_id}", positive=True)
        parsed.append(_Instrument(instrument_id, instrument_type, maturity_date, maturity_time, face_value, dirty_price, _cashflows(raw, valuation_date, maturity_date, face_value, instrument_id)))
    if len({item.instrument_id for item in parsed}) != len(parsed) or len({item.maturity_time for item in parsed}) != len(parsed):
        raise SpotCurveValidationError("Los identificadores o vencimientos se repiten.")
    return sorted(parsed, key=lambda item: item.maturity_time)


def _final_nodes(instruments: list[_Instrument], log_mbono_factors: list[float]) -> list[_Node]:
    factors = iter(log_mbono_factors)
    nodes = [_Node(0.0, 1.0, "ANCHOR")]
    for item in instruments:
        factor = item.dirty_price / item.face_value if item.instrument_type == "CETES" else math.exp(next(factors))
        nodes.append(_Node(item.maturity_time, factor, item.instrument_id))
    return nodes


def _calibrate_final_pchip(instruments: list[_Instrument]) -> list[_Node]:
    mbonos = [item for item in instruments if item.instrument_type == "MBONOS"]
    if not mbonos:
        return _final_nodes(instruments, [])
    largest_time = instruments[-1].maturity_time
    if any(flow_time > largest_time for item in mbonos for flow_time, _ in item.cashflows):
        raise SpotCurveValidationError("FLUJO_FUERA_DE_RANGO")
    initial = [math.log(max(1e-6, item.dirty_price / item.face_value)) for item in mbonos]

    def residuals(log_factors: list[float]) -> list[float]:
        nodes = _final_nodes(instruments, log_factors)
        interpolator = _interpolator(nodes)
        return [sum(amount * _discount_factor(interpolator, nodes, time) for time, amount in item.cashflows) - item.dirty_price for item in mbonos]

    solution = least_squares(residuals, initial, xtol=1e-12, ftol=1e-12, gtol=1e-12, max_nfev=1000)
    if not solution.success or max(abs(value) for value in residuals(solution.x)) > CALIBRATION_TOLERANCE:
        raise SpotCurveValidationError("CALIBRACION_PCHIP_NO_CONVERGE")
    return _final_nodes(instruments, list(solution.x))


def build_spot_curve(payload: dict[str, Any]) -> dict[str, Any]:
    """Calibra nodos terminales contra una única curva PCHIP final."""
    valuation_date, raw_instruments = _validate_common(payload)
    instruments = _parse_instruments(raw_instruments, valuation_date)
    nodes = _calibrate_final_pchip(instruments)
    interpolator = _interpolator(nodes)
    repricing = []
    for item in instruments:
        theoretical = sum(amount * _discount_factor(interpolator, nodes, time) for time, amount in item.cashflows)
        repricing.append({"instrument_id": item.instrument_id, "instrument_type": item.instrument_type, "maturity_date": item.maturity_date.isoformat(), "dirty_price_input": item.dirty_price, "cashflows": [{"time_years": time, "amount": amount} for time, amount in item.cashflows], "dirty_price_theoretical": theoretical, "absolute_repricing_error": abs(theoretical - item.dirty_price)})
    pillars = [{"instrument_id": node.instrument_id, "time_years": node.time, "discount_factor": node.discount_factor, "spot_rate_continuous": -math.log(node.discount_factor) / node.time} for node in nodes[1:]]
    return {"case_id": payload["case_id"], "curve_version": payload["curve_version"], "mode": "SIMULADO", "valuation_date": valuation_date.isoformat(), "conventions": {"price_basis": PRICE_BASIS, "price_unit": PRICE_UNIT, "day_count": DAY_COUNT, "spot_rate_compounding": "CONTINUOUS", "interpolation_method": INTERPOLATION_METHOD}, "pillars": pillars, "repricing": repricing, "summary": {"instrument_count": len(instruments), "max_absolute_repricing_error": max(item["absolute_repricing_error"] for item in repricing)}}
