import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from backend.orion_executor import execute_orion
from test_atenea import case

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def inputs(payload_name="caso_valido.json"):
    payload = load(f"skills/build_spot_curve/examples/{payload_name}")
    common = case(payload)
    common["estado"] = "RECIBIDO"
    common["aprobacion_humana"] = {"estado": "PENDIENTE"}
    elara = load("agents/examples/elara/solicitud_valida.json")["salida_esperada"]
    siena = load("agents/examples/siena/cases.json")[0]["salida_esperada"]
    elara["fecha_corte_normalizada"] = payload["valuation_date"]
    siena["fecha_corte"] = payload["valuation_date"]
    for observation in siena["observaciones"]:
        observation["fecha"] = payload["valuation_date"]
    config = {"budget_usd": 0.0, "time_limit_seconds": 30.0, "authorization_scope": "ORCHESTRATION_SIMULATED", "execution_authorized": True, "authorization_source": "TRUSTED_LOCAL_CONFIG"}
    return common, elara, siena, payload, config


def test_orion_schema_and_valid_explicitly_authorized_case():
    schema = load("agents/contracts/orion.output.schema.json")
    Draft202012Validator.check_schema(schema)
    common, elara, siena, payload, config = inputs()
    result = execute_orion(common, elara, siena, payload, config, "orion-001")
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(result)
    assert result["estado"] == "PENDIENTE_APROBACION"
    assert result["dictamen_tecnico"] == "VALIDADO"
    assert result["version_curva"].endswith("-V1")
    assert result["expediente"]["nash"]["estado"] == "CALCULO_COMPLETADO"
    assert result["expediente"]["atenea"]["estado"] == "DICTAMEN_TECNICO_VALIDADO"
    assert common["aprobacion_humana"]["estado"] == "PENDIENTE"


def test_orion_stops_on_elara_rejection_and_insufficient_permission():
    common, elara, siena, payload, config = inputs()
    elara["decision"] = "RECHAZAR"; elara["motivos_rechazo"] = [{"codigo": "FUERA_ALCANCE", "severidad": "ERROR", "mensaje": "Fuera de alcance."}]
    rejected = execute_orion(common, elara, siena, payload, config, "orion-002")
    assert rejected["estado"] == "RECHAZADO"
    common, elara, siena, payload, config = inputs(); config["execution_authorized"] = False
    stopped = execute_orion(common, elara, siena, payload, config, "orion-003")
    assert stopped["estado"] == "DETENIDO"


def test_orion_rejects_invalid_budget_and_reuses_case_id():
    common, elara, siena, payload, config = inputs(); config["budget_usd"] = -1.0
    v1 = execute_orion(common, elara, siena, payload, config, "orion-004")
    common2, elara2, siena2, payload2, config2 = inputs()
    v2 = execute_orion(common2, elara2, siena2, payload2, config2, "orion-005")
    assert v1["estado"] == "ERROR"
    assert v2["estado"] == "PENDIENTE_APROBACION"
    assert v1["caso_id"] == v2["caso_id"]


def test_orion_injection_is_opt_in_and_rejects_non_finite_values_or_mismatches():
    common, elara, siena, payload, config = inputs(); config["inject_quality_failure"] = True
    assert execute_orion(common, elara, siena, payload, config, "orion-008")["version_curva"].endswith("-V2")
    common, elara, siena, payload, config = inputs(); config["time_limit_seconds"] = float("inf")
    assert execute_orion(common, elara, siena, payload, config, "orion-009")["estado"] == "ERROR"
    common, elara, siena, payload, config = inputs(); siena["observaciones"][0]["fecha"] = "2026-04-13"
    assert execute_orion(common, elara, siena, payload, config, "orion-010")["estado"] == "ERROR"


def test_orion_rejects_invalid_siena_and_second_case_reuse():
    common, elara, siena, payload, config = inputs(); siena["estado"] = "DATOS_RECHAZADOS"
    assert execute_orion(common, elara, siena, payload, config, "orion-006")["estado"] == "RECHAZADO"
    common, elara, siena, payload, config = inputs("caso_reutilizacion.json")
    assert execute_orion(common, elara, siena, payload, config, "orion-007")["estado"] == "PENDIENTE_APROBACION"
