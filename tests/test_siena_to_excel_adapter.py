"""Pruebas deterministas del adaptador Siena validada hacia Nash Excel."""

from __future__ import annotations

from copy import deepcopy

import pytest

from backend.nash_executor import execute_nash
from backend.siena_to_excel_adapter import SienaToExcelAdapterError, build_excel_payload_from_siena
from tests.fixtures_siena_real_20261111 import CASE, SIENA


EXPECTED_CETES_RATES = {
    "C28": 0.061215779576995324,
    "C91": 0.06369703629377282,
    "C182": 0.06435869599253852,
    "C364": 0.06786175352437335,
    "C2Y": 0.07644480580101735,
}
EXPECTED_MBOND_SPOTS = {
    "MBONO_0_3": 0.08094906318001449,
    "MBONO_3_5": 0.087427856575232,
    "MBONO_7_10": 0.09482458786806092,
    "MBONO_10_20": 0.10270057077286765,
    "MBONO_20_30": 0.10530454153195024,
}


def _inputs() -> tuple[dict, dict]:
    return deepcopy(CASE), deepcopy(SIENA)


def _observation(siena: dict, serie_id: str) -> dict:
    return next(item for item in siena["observaciones"] if item["serie_id"] == serie_id)


def test_builds_exact_excel_payload_from_public_siena_fixture() -> None:
    case, siena = _inputs()
    payload = build_excel_payload_from_siena(case, siena)

    assert payload["case_id"] == case["caso_id"]
    assert payload["curve_version"] == case["version_curva"]
    assert payload["valuation_date"] == "2026-11-11"
    assert payload["mode"] == "SIMULADO"
    assert payload["metodologia"] == "EXCEL_BOOTSTRAP_182D_V1"
    assert payload["tolerance"] == 1e-8
    assert payload["max_iterations"] == 200
    assert payload["overnight_rate"] == pytest.approx(0.0626)
    assert [node[0] for node in payload["excel_cetes_nodes"]] == list(EXPECTED_CETES_RATES)
    assert [node[0] for node in payload["excel_mbonos"]] == list(EXPECTED_MBOND_SPOTS)
    for node in payload["excel_cetes_nodes"]:
        assert node[3] == pytest.approx(EXPECTED_CETES_RATES[node[0]], abs=1e-15)
    assert [node[3] for node in payload["excel_mbonos"]] == pytest.approx([0.085, 0.08, 0.08, 0.0775, 0.08])


def test_adapter_payload_runs_the_excel_nash_route() -> None:
    case, siena = _inputs()
    result = execute_nash(case, build_excel_payload_from_siena(case, siena), "siena-nash-fixture")

    assert result["estado"] == "CALCULO_COMPLETADO"
    curve = result["resultado_curva"]
    assert curve["metodologia"] == "EXCEL_BOOTSTRAP_182D_V1"
    assert curve["instrument_count"] == 10
    assert len(curve["pillars"]) == 10
    assert len(curve["repricing"]) == 5
    assert curve["max_absolute_repricing_error"] <= 1e-8
    spots = {node["instrument_id"]: node["spot_rate"] for node in curve["pillars"]}
    for instrument_id, expected in EXPECTED_MBOND_SPOTS.items():
        assert spots[instrument_id] == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda case, siena: siena.update(estado="DATOS_INCOMPLETOS"), "SIENA_NOT_VALID"),
        (lambda case, siena: siena.update(fecha_corte="2026-11-10"), "SIENA_DATE_MISMATCH"),
        (lambda case, siena: siena["observaciones"].pop(), "SIENA_SERIES_MISMATCH"),
        (lambda case, siena: siena["observaciones"].append(deepcopy(siena["observaciones"][0])), "SIENA_SERIES_MISMATCH"),
        (lambda case, siena: _observation(siena, "SF45422").update(valida=False), "SIENA_NOT_VALID"),
        (lambda case, siena: _observation(siena, "SF45439").update(unidad="PORCENTAJE"), "SIENA_UNIT_MISMATCH"),
        (lambda case, siena: _observation(siena, "SF45439").update(valor=0.0), "CETES_INPUT_INVALID"),
        (lambda case, siena: _observation(siena, "SF45422").update(valor=22.5), "CETES_INPUT_INVALID"),
        (lambda case, siena: _observation(siena, "SF45475").update(valor=100.0), "MBONOS_INPUT_INVALID"),
        (lambda case, siena: _observation(siena, "SF43774").update(valor=100.0), "FUNDING_RATE_INVALID"),
        (lambda case, siena: siena["fuente"]["recursos"][0]["series"].pop(), "SIENA_SOURCE_MISMATCH"),
        (lambda case, siena: case.update(version_curva=None), "CASE_INVALID"),
    ],
)
def test_rejects_invalid_or_inconsistent_inputs(mutate, code: str) -> None:
    case, siena = _inputs()
    mutate(case, siena)
    with pytest.raises(SienaToExcelAdapterError, match=f"^{code}$"):
        build_excel_payload_from_siena(case, siena)


def test_rejects_duplicate_observation_even_when_total_count_is_26() -> None:
    case, siena = _inputs()
    duplicate = deepcopy(siena["observaciones"][0])
    siena["observaciones"] = [item for item in siena["observaciones"] if item["serie_id"] != "SF45439"]
    siena["observaciones"].append(duplicate)
    with pytest.raises(SienaToExcelAdapterError, match="^SIENA_DUPLICATE_OBSERVATION$"):
        build_excel_payload_from_siena(case, siena)
