import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from backend.nash_executor import execute_nash
from backend.spot_curve import SpotCurveValidationError, build_spot_curve


ROOT = Path(__file__).resolve().parents[1]


def load_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def case_for(payload):
    return {
        "contrato_version": "1.0.0", "caso_id": payload["case_id"], "version_caso": 1,
        "version_curva": payload["curve_version"], "fecha_corte": payload["valuation_date"],
        "canal_origen": "manual", "modo": "SIMULADO", "estado": "EN_CALCULO",
        "objetivo": "Construir una curva para un portafolio ficticio.", "agente_responsable": "Nash",
        "referencias": {"datos": [], "calculos": [], "validaciones": []}, "advertencias": [], "errores": [],
        "marcas_tiempo": {"creado_en": "2026-04-14T00:00:00Z", "actualizado_en": "2026-04-14T00:00:00Z"},
        "trazabilidad": {"correlation_id": "CORR-NASH-001", "traza_id": "TRAZA-NASH-001", "referencias_consumo": []},
        "salidas_especializadas": {}
    }


def test_nash_schema_and_examples_are_valid():
    schema = load_json("agents/contracts/nash.output.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for example in load_json("agents/examples/nash/cases.json"):
        validator.validate(example["salida_esperada"])


def test_pchip_additional_mbono_does_not_change_prior_calibration_repricing():
    multiple = load_json("skills/build_spot_curve/examples/caso_multiple_mbonos.json")
    first_only = copy.deepcopy(multiple)
    first_only["instruments"] = first_only["instruments"][:-1]
    before = build_spot_curve(first_only)
    after = build_spot_curve(multiple)
    before_mbono = next(item for item in before["repricing"] if item["instrument_type"] == "MBONOS")
    after_mbono = next(item for item in after["repricing"] if item["instrument_id"] == before_mbono["instrument_id"])
    assert before_mbono["dirty_price_theoretical"] == after_mbono["dirty_price_theoretical"]
    assert after["summary"]["max_absolute_repricing_error"] <= 1e-8


def test_spot_curve_requires_valid_case_and_curve_identifiers():
    payload = load_json("skills/build_spot_curve/examples/caso_valido.json")
    payload["case_id"] = "incorrecto"
    try:
        build_spot_curve(payload)
    except SpotCurveValidationError as error:
        assert "case_id" in str(error)
    else:
        raise AssertionError("Se esperaba el rechazo de case_id inválido.")


def test_nash_invokes_skill_and_records_loaded_instruction_evidence():
    payload = load_json("skills/build_spot_curve/examples/caso_valido.json")
    output = execute_nash(case_for(payload), payload, "nash-invocation-001")
    assert output["estado"] == "CALCULO_COMPLETADO"
    assert output["evidencia_skill"]["skill_status"] == "COMPLETED"
    assert len(output["evidencia_skill"]["nash_instruction_sha256"]) == 64
    assert output["resultado_curva"]["max_absolute_repricing_error"] <= 1e-8


def test_nash_sanitizes_identifier_mismatch_and_skill_rejection():
    payload = load_json("skills/build_spot_curve/examples/caso_valido.json")
    mismatch_case = case_for(payload)
    mismatch_case["version_curva"] = "CURVA-SIM-999"
    mismatch = execute_nash(mismatch_case, payload, "nash-invocation-002")
    assert mismatch["estado"] == "CALCULO_RECHAZADO"
    assert mismatch["errores"][0]["codigo"] == "CASO_CUANTITATIVO_INVALIDO"
    invalid_payload = load_json("skills/build_spot_curve/examples/caso_invalido_metadatos.json")
    rejected = execute_nash(case_for(invalid_payload), invalid_payload, "nash-invocation-003")
    assert rejected["estado"] == "CALCULO_RECHAZADO"
    assert rejected["errores"][0]["codigo"] == "METADATOS_MBONO_FALTANTES"


def test_nash_sanitizes_an_invalid_common_case():
    payload = load_json("skills/build_spot_curve/examples/caso_valido.json")
    invalid_case = case_for(payload)
    invalid_case["caso_id"] = "private-detail"
    output = execute_nash(invalid_case, payload, "nash-invocation-004")
    assert output["estado"] == "CALCULO_RECHAZADO"
    assert output["caso_id"] == "YC-INVALIDO000"
    assert output["errores"][0]["codigo"] == "CASO_CUANTITATIVO_INVALIDO"
