import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "agents" / "contracts"
EXAMPLES = ROOT / "agents" / "examples" / "elara"


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


CASE_SCHEMA = load_json(CONTRACTS / "case.schema.json")
ELARA_SCHEMA = load_json(CONTRACTS / "elara.output.schema.json")
CASE_EXAMPLE = load_json(CONTRACTS / "case.example.json")
ELARA_EXAMPLES = [
    load_json(EXAMPLES / filename)
    for filename in (
        "solicitud_valida.json",
        "solicitud_incompleta.json",
        "solicitud_fuera_alcance.json",
        "solicitud_maliciosa.json",
    )
]
FORMAT_CHECKER = FormatChecker()
CASE_VALIDATOR = Draft202012Validator(CASE_SCHEMA, format_checker=FORMAT_CHECKER)
ELARA_VALIDATOR = Draft202012Validator(ELARA_SCHEMA, format_checker=FORMAT_CHECKER)


def test_case_schema_is_valid() -> None:
    Draft202012Validator.check_schema(CASE_SCHEMA)


def test_elara_schema_is_valid() -> None:
    Draft202012Validator.check_schema(ELARA_SCHEMA)


def test_case_example_conforms_to_common_schema() -> None:
    CASE_VALIDATOR.validate(CASE_EXAMPLE)


@pytest.mark.parametrize("example", ELARA_EXAMPLES, ids=lambda item: item["caso_prueba"])
def test_elara_expected_outputs_conform_to_schema(example: dict) -> None:
    ELARA_VALIDATOR.validate(example["salida_esperada"])


def test_acceptance_without_a_valid_cutoff_date_is_rejected() -> None:
    invalid_output = copy.deepcopy(ELARA_EXAMPLES[0]["salida_esperada"])
    invalid_output["fecha_corte_normalizada"] = None

    with pytest.raises(ValidationError):
        ELARA_VALIDATOR.validate(invalid_output)


def test_rejection_without_reasons_is_rejected() -> None:
    invalid_output = copy.deepcopy(ELARA_EXAMPLES[2]["salida_esperada"])
    invalid_output["motivos_rechazo"] = []

    with pytest.raises(ValidationError):
        ELARA_VALIDATOR.validate(invalid_output)


def test_unpermitted_instrument_is_rejected() -> None:
    invalid_output = copy.deepcopy(ELARA_EXAMPLES[0]["salida_esperada"])
    invalid_output["instrumentos_solicitados"] = ["BONDES"]

    with pytest.raises(ValidationError):
        ELARA_VALIDATOR.validate(invalid_output)


def test_additional_field_is_rejected() -> None:
    invalid_output = copy.deepcopy(ELARA_EXAMPLES[0]["salida_esperada"])
    invalid_output["campo_no_permitido"] = True

    with pytest.raises(ValidationError):
        ELARA_VALIDATOR.validate(invalid_output)


@pytest.mark.parametrize("invalid_date", ["2026-02-30", "2026-13-01", "14/04/2026"])
def test_invalid_iso_dates_are_rejected(invalid_date: str) -> None:
    invalid_output = copy.deepcopy(ELARA_EXAMPLES[0]["salida_esperada"])
    invalid_output["fecha_corte_normalizada"] = invalid_date

    with pytest.raises(ValidationError):
        ELARA_VALIDATOR.validate(invalid_output)
