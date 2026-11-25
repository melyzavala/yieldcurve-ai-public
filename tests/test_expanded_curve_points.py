"""Trace-only tests for the existing Excel bootstrap curve representation."""

from copy import deepcopy
import math

import pytest

from backend.excel_bootstrap import build_from_payload
from backend.public_artifacts import build_public_case_artifact, validate_public_case
from backend.siena_to_excel_adapter import build_excel_payload_from_siena
from tests.fixtures_siena_real_20261111 import CASE, SIENA


def curve_result():
    payload = build_excel_payload_from_siena(deepcopy(CASE), deepcopy(SIENA))
    return build_from_payload(payload)


def test_expanded_points_preserve_the_ten_existing_pillars_and_repricing():
    result = curve_result()
    expected = {
        "C28": (22, 0.061215779576995324), "C91": (85, 0.06369703629377282),
        "C182": (169, 0.06435869599253852), "C364": (337, 0.06786175352437335),
        "C2Y": (687, 0.07644480580101735), "MBONO_0_3": (1205, 0.08094906318001449),
        "MBONO_3_5": (1982, 0.087427856575232), "MBONO_7_10": (3389, 0.09482458786806092),
        "MBONO_10_20": (5846, 0.10270057077286765), "MBONO_20_30": (10396, 0.10530454153195024),
    }
    assert {(row["instrument_id"]): (row["days"], row["spot_rate"]) for row in result["pillars"]} == expected
    assert result["summary"]["max_absolute_repricing_error"] == pytest.approx(5.799378755000362e-09)


def test_expanded_points_are_ordered_finite_and_identical_to_discount_flow_inputs():
    result = curve_result()
    points = result["curve_points"]
    pillars = {row["days"]: row for row in result["pillars"]}
    by_day = {row["days"]: row for row in points}

    assert len(points) > len(pillars)
    assert [row["days"] for row in points] == sorted(by_day)
    assert len(by_day) == len(points)
    assert all(row["point_type"] in {"PILLAR", "INTERPOLATED"} for row in points)
    assert all(math.isfinite(row[key]) for row in points for key in ("time_years", "spot_rate", "discount_factor"))
    for days, pillar in pillars.items():
        point = by_day[days]
        assert point["point_type"] == "PILLAR"
        assert point["instrument_id"] == pillar["instrument_id"]
        assert point["spot_rate"] == pillar["spot_rate"]
    for point in points:
        if point["point_type"] == "INTERPOLATED":
            assert point["days"] not in pillars
            assert point["source_method"] == "LINEAR_SPOT_RATE"
            assert point["left_pillar"] in {"OVERNIGHT", *(row["instrument_id"] for row in result["pillars"])}
            assert point["right_pillar"] in {row["instrument_id"] for row in result["pillars"]}
    for bond in result["repricing"]:
        recalculated = sum(flow["amount"] * flow["discount_factor"] for flow in bond["cashflows"])
        assert recalculated == pytest.approx(bond["recalculated_price"])
        for flow in bond["cashflows"]:
            point = by_day[flow["days"]]
            assert (flow["spot_rate"], flow["discount_factor"], flow["point_type"]) == (
                point["spot_rate"], point["discount_factor"], point["point_type"],
            )


def test_public_curve_points_are_allowlisted_and_validate_without_private_flow_trace():
    result = curve_result()
    source = {
        "caso_id": "YC-EXPANDED01", "version_caso": 1, "version_curva": result["curve_version"],
        "fecha_corte": result["valuation_date"], "execution_mode": "DEMO", "estado": "APROBADA_HUMANAMENTE",
        "agentes": {}, "fuente_datos": {"source_mode": "FIXTURE"},
        "curva": {"metodologia": result["metodologia"], "instrument_count": 10,
                  "max_absolute_repricing_error": result["summary"]["max_absolute_repricing_error"],
                  "pillars": result["pillars"], "curve_points": result["curve_points"]},
        "auditoria": {"tecnicamente_valida": True}, "cost_trace": {},
    }
    public = build_public_case_artifact(source, "2026-01-01T00:00:00Z")
    validate_public_case(public)
    assert public["curva"]["curve_points"] == result["curve_points"]
    assert "amount" not in str(public["curva"]["curve_points"])
