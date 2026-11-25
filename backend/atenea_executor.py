"""Auditor determinista de Atenea."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from backend.excel_bootstrap import METHODOLOGY as EXCEL_METHODOLOGY
from backend.guardrails import first_nonfinite
from backend.validate_spot_curve_adapter import apply_validate_spot_curve


ROOT = Path(__file__).resolve().parents[1]
PCHIP_METHODOLOGY = "PCHIP_LOG_DISCOUNT_FACTOR"
PCHIP_DAY_COUNT = "ACT/365F"
PRICE_BASIS = "DIRTY"
PRICE_UNIT = "MXN_PER_100_FACE"
EXCEL_CONVENTIONS = {
    "methodology": EXCEL_METHODOLOGY,
    "price_basis": PRICE_BASIS,
    "price_unit": PRICE_UNIT,
    "day_count": "182/360",
    "coupon_period_days": 182,
    "interpolation_method": "LINEAR_SPOT_RATE",
}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite(value: Any) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _expanded_curve_points_valid(result: dict[str, Any]) -> bool:
    """Validate trace-only points without changing the independent repricing path."""
    points = result.get("curve_points")
    pillars = result.get("pillars")
    if points is None:
        return True
    if not isinstance(points, list) or not isinstance(pillars, list):
        return False
    pillar_by_day = {item.get("days"): item for item in pillars if isinstance(item, dict)}
    if len(pillar_by_day) != len(pillars):
        return False
    previous = 0
    seen = set()
    for point in points:
        if not isinstance(point, dict):
            return False
        days, rate, kind = point.get("days"), point.get("spot_rate"), point.get("point_type")
        if not isinstance(days, int) or days <= previous or days in seen or not _finite(rate) or kind not in {"PILLAR", "INTERPOLATED"}:
            return False
        previous, seen = days, seen | {days}
        if kind == "PILLAR":
            pillar = pillar_by_day.get(days)
            if not pillar or point.get("instrument_id") != pillar.get("instrument_id") or point.get("spot_rate") != pillar.get("spot_rate"):
                return False
        else:
            left = point.get("left_pillar")
            right = point.get("right_pillar")
            bounds = [{"instrument_id": "OVERNIGHT", "days": 1}, *sorted((item for item in pillars if isinstance(item, dict)), key=lambda item: item.get("days", 0))]
            pairs = [(a, b) for a, b in zip(bounds, bounds[1:]) if a.get("instrument_id") == left and b.get("instrument_id") == right and a.get("days", 0) < days < b.get("days", 0)]
            if len(pairs) != 1 or point.get("source_method") != "LINEAR_SPOT_RATE":
                return False
    return set(pillar_by_day).issubset(seen)


def _nash_matches_independent(methodology: str, independent: list[dict[str, Any]], nash_repricing: list[dict[str, Any]]) -> bool:
    if not isinstance(nash_repricing, list):
        return False
    nash_prices = {item.get("instrument_id"): item for item in nash_repricing if isinstance(item, dict)}
    if methodology == EXCEL_METHODOLOGY:
        targets = [item for item in independent if item["instrument_id"].startswith("M")]
        for item in targets:
            reported = nash_prices.get(item["instrument_id"])
            if not reported:
                return False
            price = reported.get("recalculated_price")
            observed = reported.get("observed_price")
            if not _finite(price) or not _finite(observed):
                return False
            if abs(item["dirty_price_recalculated"] - price) > 1e-8 or abs(item["dirty_price_input"] - observed) > 1e-8:
                return False
        return len(nash_prices) == len(targets)
    independent_prices = {item["instrument_id"]: item for item in independent}
    return len(independent_prices) == len(nash_prices) and all(
        key in nash_prices
        and _finite(nash_prices[key].get("dirty_price_theoretical"))
        and _finite(nash_prices[key].get("absolute_repricing_error"))
        and abs(value["dirty_price_recalculated"] - nash_prices[key]["dirty_price_theoretical"]) <= 1e-8
        and abs(value["absolute_repricing_error"] - nash_prices[key]["absolute_repricing_error"]) <= 1e-8
        for key, value in independent_prices.items()
    )


def execute_atenea(case: dict[str, Any], nash: dict[str, Any], payload: dict[str, Any], invocation_id: str) -> dict[str, Any]:
    aid = _hash(ROOT / "agents" / "atenea.md")
    skill_path = ROOT / "skills" / "validate_spot_curve" / "SKILL.md"
    sid = _hash(skill_path)
    base = {
        "caso_id": case.get("caso_id", "YC-INVALIDO000"),
        "version_curva": case.get("version_curva", "CURVA-INVALIDO"),
        "modo": "SIMULADO",
        "agente": "Atenea",
        "dictamen": {"tecnicamente_valida": False, "tolerancia": 1e-8, "requiere_aprobacion_humana": True},
        "evidencia": {"atenea_instruction_sha256": aid, "invocation_id": invocation_id, "skill_name": "validate-spot-curve", "skill_path": "skills/validate_spot_curve/SKILL.md", "skill_version": "1.0.0", "validation_skill_sha256": sid, "validation_status": "REJECTED"},
    }
    result = nash.get("resultado_curva", {}) if isinstance(nash, dict) else {}
    invalid = (
        case.get("modo") != "SIMULADO"
        or nash.get("estado") != "CALCULO_COMPLETADO"
        or nash.get("caso_id") != case.get("caso_id")
        or nash.get("version_curva") != case.get("version_curva")
        or payload.get("valuation_date") != case.get("fecha_corte")
        or not nash.get("evidencia_skill", {}).get("skill_sha256")
        or not isinstance(result, dict)
        or not isinstance(result.get("repricing"), list)
        or not _expanded_curve_points_valid(result)
        or first_nonfinite(payload) is not None
        or first_nonfinite(result) is not None
    )
    if invalid:
        output = {**base, "estado": "DICTAMEN_TECNICO_RECHAZADO", "errores": [{"codigo": "EVIDENCIA_INCONSISTENTE", "mensaje": "Las evidencias cuantitativas no son consistentes."}]}
    else:
        methodology = result.get("metodologia") or result.get("interpolation_method")
        if methodology == EXCEL_METHODOLOGY:
            conventions = EXCEL_CONVENTIONS
        elif methodology == PCHIP_METHODOLOGY:
            conventions = {"price_basis": PRICE_BASIS, "price_unit": PRICE_UNIT, "day_count": PCHIP_DAY_COUNT, "interpolation_method": PCHIP_METHODOLOGY}
        else:
            conventions = {"methodology": "NO_RECONOCIDA"}
        curve = {
            "case_id": nash["caso_id"],
            "curve_version": nash["version_curva"],
            "mode": "SIMULADO",
            "valuation_date": payload["valuation_date"],
            "conventions": conventions,
            "pillars": result.get("pillars"),
        }
        response = apply_validate_spot_curve(payload, curve, invocation_id)
        evidence = {**base["evidencia"], "invocation_id": response["trace"]["invocation_id"], "skill_name": response["trace"]["skill_name"], "skill_path": response["trace"]["skill_path"], "skill_version": response["trace"]["skill_version"], "validation_skill_sha256": response["trace"]["skill_sha256"], "validation_status": response["trace"]["skill_status"]}
        if response["status"] == "COMPLETED" and _nash_matches_independent(methodology, response["result"]["repricing"], result["repricing"]):
            output = {**base, "estado": "DICTAMEN_TECNICO_VALIDADO", "dictamen": {**base["dictamen"], "tecnicamente_valida": True}, "evidencia": evidence, "errores": []}
        elif response["status"] == "COMPLETED":
            output = {**base, "estado": "DICTAMEN_TECNICO_RECHAZADO", "evidencia": evidence, "errores": [{"codigo": "REPRICING_INCONSISTENTE", "mensaje": "El repricing de Nash no coincide con la validación independiente."}]}
        else:
            output = {**base, "estado": "DICTAMEN_TECNICO_RECHAZADO", "evidencia": evidence, "errores": [{"codigo": response["trace"]["error_code"], "mensaje": "La validación técnica rechazó la curva."}]}
    Draft202012Validator(json.loads((ROOT / "agents/contracts/atenea.output.schema.json").read_text())).validate(output)
    return output
