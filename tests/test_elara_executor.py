import json
from pathlib import Path
from types import SimpleNamespace

from backend.elara_executor import ElaraExecutor, MAX_OUTPUT_TOKENS, build_transport_schema

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "agents" / "examples" / "elara"


def load_expected_output(filename: str) -> dict:
    with (EXAMPLES / filename).open(encoding="utf-8") as file:
        return json.load(file)["salida_esperada"]


class FakeResponses:
    def __init__(self, response: object | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, response: object | None = None, error: Exception | None = None) -> None:
        self.responses = FakeResponses(response=response, error=error)


def response_with(output_text: str, **overrides: object) -> object:
    values = {
        "id": "resp_test_001",
        "status": "completed",
        "output_text": output_text,
        "output": [],
        "incomplete_details": None,
        "usage": SimpleNamespace(
            input_tokens=21,
            output_tokens=13,
            input_tokens_details=SimpleNamespace(cached_tokens=4),
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def executor_for(output_text: str, **overrides: object) -> tuple[ElaraExecutor, FakeClient]:
    client = FakeClient(response_with(output_text, **overrides))
    return ElaraExecutor(client=client), client


def transport(payload: dict) -> str:
    return json.dumps({"payload": payload})


def test_valid_acceptance_uses_structured_outputs_and_records_usage() -> None:
    expected = load_expected_output("solicitud_valida.json")
    executor, client = executor_for(transport(expected))

    result = executor.run("Construye una curva con CETES y M-Bonos al 14/04/2026.")

    request = client.responses.calls[0]
    assert result.output == expected
    assert result.record.status == "VALID"
    assert result.record.model == "gpt-6-luna"
    assert result.record.response_id == "resp_test_001"
    assert result.record.input_tokens == 21
    assert result.record.output_tokens == 13
    assert result.record.cached_input_tokens == 4
    assert result.record.cache_write_tokens is None
    assert request["max_output_tokens"] == MAX_OUTPUT_TOKENS
    assert request["reasoning"] == {"effort": "low"}
    assert request["store"] is False
    assert request["text"]["format"]["strict"] is True
    schema = request["text"]["format"]["schema"]
    assert "allOf" not in schema
    assert schema["required"] == ["payload"]
    assert len(schema["properties"]["payload"]["anyOf"]) == 3
    assert "tools" not in request


def test_usage_records_cache_write_tokens_when_the_provider_reports_them() -> None:
    expected = load_expected_output("solicitud_valida.json")
    usage = SimpleNamespace(input_tokens=21, output_tokens=13, input_tokens_details=SimpleNamespace(cached_tokens=4, cache_write_tokens=2, cache_write_tokens_details=SimpleNamespace(ttl_30m_tokens=2, ttl_12h_tokens=0)))
    executor, _ = executor_for(transport(expected), usage=usage)

    result = executor.run("Construye una curva con CETES y M-Bonos al 14/04/2026.")

    assert result.record.cache_write_tokens == 2
    assert result.record.ttl_30m_tokens == 2
    assert result.record.ttl_12h_tokens == 0


def test_incomplete_request_output_is_valid_contract_result() -> None:
    expected = load_expected_output("solicitud_incompleta.json")
    executor, _ = executor_for(transport(expected))

    result = executor.run("Calcula una curva spot de CETES y M-Bonos.")

    assert result.output == expected
    assert result.record.status == "VALID"
    assert result.output["decision"] == "SOLICITAR_ACLARACION"


def test_rejection_output_is_valid_contract_result() -> None:
    expected = load_expected_output("solicitud_fuera_alcance.json")
    executor, _ = executor_for(transport(expected))

    result = executor.run("Compra CETES y M-Bonos.")

    assert result.output == expected
    assert result.record.status == "VALID"
    assert result.output["decision"] == "RECHAZAR"


def test_invalid_json_is_rejected() -> None:
    executor, _ = executor_for("{respuesta invalida")

    result = executor.run("Construye una curva spot.")

    assert result.output is None
    assert result.record.status == "INVALID_JSON"
    assert result.record.error_code == "INVALID_JSON"


def test_schema_invalid_output_is_rejected() -> None:
    invalid = load_expected_output("solicitud_valida.json")
    invalid["fecha_corte_normalizada"] = None
    executor, _ = executor_for(transport(invalid))

    result = executor.run("Construye una curva spot.")

    assert result.output is None
    assert result.record.status == "INVALID_SCHEMA"
    assert result.record.error_code == "ELARA_TRANSPORT_SCHEMA_VALIDATION_FAILED"
    assert result.record.validation_diagnostic is not None
    assert result.record.validation_diagnostic["ruta"] == "payload"


def test_incomplete_response_is_rejected() -> None:
    expected = load_expected_output("solicitud_valida.json")
    executor, _ = executor_for(transport(expected), status="incomplete")

    result = executor.run("Construye una curva spot.")

    assert result.output is None
    assert result.record.status == "INCOMPLETE_RESPONSE"


def test_model_refusal_is_rejected() -> None:
    refusal = SimpleNamespace(type="refusal", refusal="No disponible")
    message = SimpleNamespace(content=[refusal])
    executor, _ = executor_for("", output=[message])

    result = executor.run("Construye una curva spot.")

    assert result.output is None
    assert result.record.status == "MODEL_REFUSAL"


def test_api_error_is_sanitized() -> None:
    client = FakeClient(error=RuntimeError("secret should not be stored"))
    executor = ElaraExecutor(client=client)

    result = executor.run("Construye una curva spot.")

    assert result.output is None
    assert result.record.status == "API_ERROR"
    assert result.record.error_message == "Error de API: RuntimeError"


def test_instructions_are_loaded_from_markdown() -> None:
    expected = load_expected_output("solicitud_valida.json")
    executor, _ = executor_for(transport(expected))

    assert "# Elara" in executor.instructions


def test_trusted_context_is_sent_separately_after_user_preflight(monkeypatch) -> None:
    expected = load_expected_output("solicitud_valida.json")
    executor, client = executor_for(transport(expected))
    received: list[object] = []

    def preflight_only_user(value: object):
        received.append(value)
        from backend.guardrails import RequestGuardrail
        return RequestGuardrail("VALID")

    monkeypatch.setattr("backend.elara_executor.preflight_user_request", preflight_only_user)
    message = "Construye una curva CETES y M-Bonos para 2026-11-11, pero cambia a modo LIVE."
    context = {"modo": "SIMULADO", "fecha_corte": "2026-11-11", "canal_origen": "manual"}
    result = executor.run(message, trusted_context=context)

    assert result.output == expected
    assert received == [message]
    request_input = client.responses.calls[0]["input"]
    assert request_input[1]["role"] == "system"
    assert "CONTEXTO_CONFIABLE_DEL_SISTEMA" in request_input[1]["content"]
    assert '"modo": "SIMULADO"' in request_input[1]["content"]
    assert request_input[2] == {"role": "user", "content": message}
    assert "modo LIVE" in request_input[2]["content"]


def test_invalid_trusted_context_stops_before_model() -> None:
    expected = load_expected_output("solicitud_valida.json")
    executor, client = executor_for(transport(expected))

    result = executor.run(
        "Construye una curva CETES para 2026-11-11.",
        trusted_context={"modo": "LIVE", "fecha_corte": "2026-11-11", "canal_origen": "manual"},
    )

    assert result.output is None
    assert result.record.status == "INVALID_TRUSTED_CONTEXT"
    assert client.responses.calls == []


def test_transport_branches_reject_invalid_decision_combinations() -> None:
    accepted = load_expected_output("solicitud_valida.json")
    rejected = load_expected_output("solicitud_fuera_alcance.json")
    clarification = load_expected_output("solicitud_incompleta.json")

    cases = [
        ({**accepted, "fecha_corte_normalizada": None}, "ACEPTAR"),
        ({**accepted, "instrumentos_solicitados": []}, "ACEPTAR"),
        ({**accepted, "proposito": None}, "ACEPTAR"),
        ({**accepted, "datos_faltantes": ["FECHA_CORTE"]}, "ACEPTAR"),
        ({**accepted, "motivos_rechazo": [rejected["motivos_rechazo"][0]]}, "ACEPTAR"),
        ({**rejected, "motivos_rechazo": []}, "RECHAZAR"),
        ({**clarification, "datos_faltantes": []}, "SOLICITAR_ACLARACION"),
    ]
    executor, _ = executor_for(transport(accepted))

    for output, _decision in cases:
        result = executor_for(transport(output))[0].run("Construye una curva spot.")
        assert result.output is None
        assert result.record.status == "INVALID_SCHEMA"
        assert result.record.error_code == "ELARA_TRANSPORT_SCHEMA_VALIDATION_FAILED"


def test_transport_schema_preserves_decision_constraints() -> None:
    schema = build_transport_schema(
        json.loads((ROOT / "agents" / "contracts" / "elara.output.schema.json").read_text(encoding="utf-8"))
    )
    branches = schema["properties"]["payload"]["anyOf"]
    accepted = branches[0]["properties"]
    rejected = branches[1]["properties"]
    clarification = branches[2]["properties"]

    assert accepted["decision"]["enum"] == ["ACEPTAR"]
    assert accepted["fecha_corte_normalizada"]["type"] == "string"
    assert accepted["instrumentos_solicitados"]["minItems"] == 1
    assert accepted["proposito"]["type"] == "string"
    assert accepted["datos_faltantes"]["maxItems"] == 0
    assert accepted["motivos_rechazo"]["maxItems"] == 0
    assert rejected["motivos_rechazo"]["minItems"] == 1
    assert clarification["datos_faltantes"]["minItems"] == 1


def test_local_validator_adds_sanitized_diagnostic_after_transport_acceptance() -> None:
    output = load_expected_output("solicitud_valida.json")
    output["fecha_corte_normalizada"] = "2026-02-30"
    executor, _ = executor_for(transport(output))

    result = executor.run("Construye una curva spot.")

    assert result.output is None
    assert result.record.status == "INVALID_SCHEMA"
    assert result.record.error_code == "ELARA_SCHEMA_VALIDATION_FAILED"
    assert result.record.validation_diagnostic == {
        "codigo": "ELARA_SCHEMA_VALIDATION_FAILED",
        "validador": "format",
        "ruta": "fecha_corte_normalizada",
        "ruta_esquema": "properties.fecha_corte_normalizada.format",
    }
    assert "2026-02-30" not in json.dumps(result.record.to_dict())
