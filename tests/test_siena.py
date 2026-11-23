import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from backend.banxico_client import (
    CURVE_REQUIRED_SERIES,
    REQUEST_TIMEOUT_SECONDS,
    SERIES_CATALOG,
    BanxicoClient,
    BanxicoClientError,
    _normalize_value,
    normalize_banxico_response,
    validate_observations,
)
from backend.siena_executor import execute_siena

ROOT = Path(__file__).resolve().parents[1]


def load_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_siena_schema_and_simulated_examples_are_valid():
    schema = load_json("agents/contracts/siena.output.schema.json")
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for case in load_json("agents/examples/siena/cases.json"):
        validator.validate(case["salida_esperada"])


def test_client_uses_iso_dates_mocked_transport_and_sanitized_errors():
    captured = {}
    def transport(url, headers, timeout):
        captured.update(url=url, headers=headers, timeout=timeout)
        return {"bmx": {"series": []}}
    result = BanxicoClient("token-for-test", transport=transport).fetch_series("SF45423", "2026-04-14", "2026-04-14")
    assert result == {"bmx": {"series": []}}
    assert "SF45423/datos/2026-04-14/2026-04-14" in captured["url"]
    assert captured["headers"]["Bmx-Token"] == "token-for-test"
    assert captured["timeout"] == REQUEST_TIMEOUT_SECONDS
    with pytest.raises(BanxicoClientError, match="BANXICO_API_TOKEN"):
        BanxicoClient("")
    def failing_transport(*_args):
        raise RuntimeError("private-token-must-not-appear")
    with pytest.raises(BanxicoClientError) as error:
        BanxicoClient("safe-token", transport=failing_transport).fetch_series("SF45423", "2026-04-14", "2026-04-14")
    assert "private-token-must-not-appear" not in str(error.value)


def test_normalizes_banxico_payload_to_siena_observations():
    payload = {"bmx": {"series": [
        {"idSerie": "SF45423", "datos": [{"fecha": "14/04/2026", "dato": "90"}]},
        {"idSerie": "SF45441", "datos": [{"fecha": "2026-04-14", "dato": "9.84"}]},
    ]}}
    observations = normalize_banxico_response(payload, ["SF45423", "SF45441"])
    assert observations == [
        {"serie_id": "SF45423", "fecha": "2026-04-14", "valor": 90.0, "unidad": "DIAS"},
        {"serie_id": "SF45441", "fecha": "2026-04-14", "valor": 9.84, "unidad": "SIN_UNIDAD_PUBLICADA"},
    ]
    assert validate_observations("2026-04-14", ["SF45423", "SF45441"], observations) == []


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1205", 1205.0),
        ("1205.000000", 1205.0),
        ("1,205.000000", 1205.0),
        ("123,456,789.25", 123456789.25),
        ("1,205.000000", 1205.0),
        ("1,982.000000", 1982.0),
        ("3,389.000000", 3389.0),
        ("5,846.000000", 5846.0),
        ("10,396.000000", 10396.0),
    ],
)
def test_normalizes_strict_banxico_numeric_formats(value, expected):
    assert _normalize_value(value) == expected


@pytest.mark.parametrize("value", ["N/E", "", "   ", None, True, "NaN", "Infinity", "1,2", "12,34", "1,20.5", "1,205,00", "1.205,50"])
def test_rejects_invalid_or_ambiguous_banxico_numeric_formats(value):
    with pytest.raises(BanxicoClientError, match="BANXICO_RESPUESTA_INVALIDA"):
        _normalize_value(value)


def _payload(serie_id, value, fecha="14/04/2026"):
    return {"bmx": {"series": [{"idSerie": serie_id, "datos": [{"fecha": fecha, "dato": value}]}]}}


def test_siena_executor_returns_contractual_real_market_output_without_network():
    values = {"SF45423": "90", "SF45441": "9.84", "SF45427": "640", "SF45449": "101.2", "SF45475": "8.0"}
    def transport(url, _headers, _timeout):
        serie_id = url.split("/series/")[1].split("/")[0]
        return _payload(serie_id, values[serie_id])
    result = execute_siena("2026-04-14", list(values), BanxicoClient("safe-token", transport=transport))
    assert result["estado"] == "DATOS_VALIDOS"
    assert result["fuente"]["datos_mercado"] == "REALES"
    assert result["observaciones"][-1]["unidad"] == "PORCENTAJE"
    assert result["observaciones"][-1]["valor"] == 8.0
    assert "safe-token" not in str(result)


def test_mbonos_catalog_matches_official_cf300_ids_and_excludes_invalid_mappings():
    expected_mbonos = {
        "SF45427", "SF45449", "SF45475",
        "SF45428", "SF45451", "SF45476",
        "SF45430", "SF45455", "SF45478",
        "SF45431", "SF45457", "SF45479",
        "SF60720", "SF60722", "SF60723",
    }
    catalog_mbonos = {serie_id for serie_id, metadata in SERIES_CATALOG.items() if metadata["instrumento"] == "MBONOS"}
    assert catalog_mbonos == expected_mbonos
    assert len(CURVE_REQUIRED_SERIES) == 26
    assert {"SF349886", "SF349888", "SF43774"}.issubset(CURVE_REQUIRED_SERIES)
    assert "SF349889" not in CURVE_REQUIRED_SERIES
    assert not {"SF45454", "SF45458", "SF45459", "SF45432", "SF45480"}.intersection(CURVE_REQUIRED_SERIES)


def test_siena_accepts_all_26_real_market_observations_with_mocked_transport():
    values = {
        "SF45422": "22.000000", "SF45439": "9.962168",
        "SF45423": "85.000000", "SF45441": "9.849535",
        "SF45424": "169.000000", "SF45443": "9.702206",
        "SF45425": "337.000000", "SF45445": "9.393273",
        "SF349886": "687", "SF349888": "8.705960", "SF43774": "6.2600",
        "SF45427": "1,205.000000", "SF45449": "102.964751", "SF45475": "8.500000",
        "SF45428": "1,982.000000", "SF45451": "97.805938", "SF45476": "8.000000",
        "SF45430": "3,389.000000", "SF45455": "94.005726", "SF45478": "8.000000",
        "SF45431": "5,846.000000", "SF45457": "87.436980", "SF45479": "7.750000",
        "SF60720": "10,396.000000", "SF60722": "85.852819", "SF60723": "8.000000",
    }

    def transport(url, _headers, _timeout):
        serie_id = url.split("/series/")[1].split("/")[0]
        return _payload(serie_id, values[serie_id], fecha="11/11/2026")

    result = execute_siena("2026-11-11", list(CURVE_REQUIRED_SERIES), BanxicoClient("safe-token", transport=transport))
    assert result["estado"] == "DATOS_VALIDOS"
    assert result["modo"] == "SIMULADO"
    assert result["fuente"]["datos_mercado"] == "REALES"
    assert result["resumen_validacion"] == {
        "series_solicitadas": 26,
        "series_con_observacion": 26,
        "observaciones_validas": 26,
        "observaciones_rechazadas": 0,
    }
    assert result["errores"] == []
    assert {item["codigo"] for item in result["advertencias"]} == {"MBONOS_RANGO"}
    normalized_terms = {item["serie_id"]: item["valor"] for item in result["observaciones"] if item["serie_id"] in {"SF45427", "SF45428", "SF45430", "SF45431", "SF60720"}}
    assert normalized_terms == {"SF45427": 1205.0, "SF45428": 1982.0, "SF45430": 3389.0, "SF45431": 5846.0, "SF60720": 10396.0}
    observations = {item["serie_id"]: item for item in result["observaciones"]}
    assert observations["SF349886"] == {"serie_id": "SF349886", "fecha": "2026-11-11", "valor": 687.0, "unidad": "DIAS", "valida": True}
    assert observations["SF349888"]["valor"] == 8.705960
    assert observations["SF43774"] == {"serie_id": "SF43774", "fecha": "2026-11-11", "valor": 6.2600, "unidad": "PORCENTAJE", "valida": True}
    assert result["fuente"]["recursos"] == [
        {"tipo": "CUADRO_SIE", "identificador": "CF300", "series": [serie_id for serie_id in CURVE_REQUIRED_SERIES if serie_id != "SF43774"]},
        {"tipo": "SERIE_SIE", "identificador": "SF43774", "series": ["SF43774"]},
    ]


@pytest.mark.parametrize("missing_serie", ["SF349886", "SF349888", "SF43774"])
def test_siena_requires_each_excel_auxiliary_input(missing_serie):
    requested = list(CURVE_REQUIRED_SERIES)

    def transport(url, _headers, _timeout):
        serie_id = url.split("/series/")[1].split("/")[0]
        if serie_id == missing_serie:
            return _payload(serie_id, "N/E", fecha="11/11/2026")
        return _payload(serie_id, "1", fecha="11/11/2026")

    result = execute_siena("2026-11-11", requested, BanxicoClient("safe-token", transport=transport))
    assert result["estado"] != "DATOS_VALIDOS"


def test_siena_rejects_unauthorized_diagnostic_yield_series_and_inconsistent_auxiliary_unit():
    assert execute_siena("2026-11-11", ["SF349889"], BanxicoClient("safe-token", transport=lambda *_: {}))["estado"] == "DATOS_RECHAZADOS"
    issues = validate_observations("2026-11-11", ["SF43774"], [
        {"serie_id": "SF43774", "fecha": "2026-11-11", "valor": 6.26, "unidad": "DIAS"}
    ])
    assert "UNIDAD_INCONSISTENTE" in issues


@pytest.mark.parametrize("value, expected", [("N/E", "DATOS_INCOMPLETOS"), ("", "DATOS_INCOMPLETOS"), (None, "DATOS_INCOMPLETOS")])
def test_siena_marks_non_numeric_sie_values_as_incomplete(value, expected):
    result = execute_siena("2026-04-14", ["SF45423"], BanxicoClient("safe-token", transport=lambda *_: _payload("SF45423", value)))
    assert result["estado"] == expected
    assert result["observaciones"] == []


def test_siena_rejects_bad_date_duplicates_units_and_unauthorized_series():
    client = BanxicoClient("safe-token", transport=lambda *_: _payload("SF45423", "90", "13/04/2026"))
    assert execute_siena("2026-04-14", ["SF45423"], client)["estado"] == "DATOS_RECHAZADOS"
    assert execute_siena("not-a-date", ["SF45423"], client)["estado"] == "DATOS_RECHAZADOS"
    assert execute_siena("2026-04-14", ["SF45423", "SF45423"], client)["estado"] == "DATOS_RECHAZADOS"
    assert execute_siena("2026-04-14", ["SF99999"], client)["estado"] == "DATOS_RECHAZADOS"


def test_siena_handles_transport_failure_missing_token_and_required_catalog_without_exposing_token(monkeypatch):
    def failing(*_args):
        raise TimeoutError("safe-token")
    result = execute_siena("2026-04-14", ["SF45423"], BanxicoClient("safe-token", transport=failing))
    assert result["estado"] == "DATOS_INCOMPLETOS"
    assert "safe-token" not in str(result)
    monkeypatch.delenv("BANXICO_API_TOKEN", raising=False)
    assert execute_siena("2026-04-14", ["SF45423"])["estado"] == "ERROR"
    assert {"SF45449", "SF45475", "SF60722", "SF60723"}.issubset(CURVE_REQUIRED_SERIES)


@pytest.mark.parametrize("payload", [
    {},
    {"bmx": {"series": [{"idSerie": "SF99999", "datos": [{"fecha": "14/04/2026", "dato": "1"}]}]}},
    {"bmx": {"series": [{"idSerie": "SF45423", "datos": []}]}},
    {"bmx": {"series": [{"idSerie": "SF45423", "datos": [{"fecha": "bad-date", "dato": "x"}]}]}},
])
def test_rejects_malformed_or_incomplete_banxico_payloads(payload):
    with pytest.raises(BanxicoClientError):
        normalize_banxico_response(payload, ["SF45423"])


def test_validate_observations_rejects_duplicates_missing_and_inconsistent_data():
    issues = validate_observations("2026-04-14", ["SF45423", "SF45441"], [
        {"serie_id": "SF45423", "fecha": "2026-04-13", "valor": 90, "unidad": "SIN_UNIDAD_PUBLICADA"},
        {"serie_id": "SF45423", "fecha": "2026-04-13", "valor": 90, "unidad": "SIN_UNIDAD_PUBLICADA"},
    ])
    assert {"OBSERVACION_DUPLICADA", "SERIE_FALTANTE", "FECHA_CORTE_INCONSISTENTE", "UNIDAD_INCONSISTENTE"}.issubset(issues)
