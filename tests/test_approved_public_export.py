import json
from copy import deepcopy

import pytest

from backend.public_artifacts import FORBIDDEN, validate_public_case
from web.export_approved_case import ExportError, export_approved_case


def private_row() -> dict:
    api = {
        "caso_id": "YC-APPROVEDDEMO01",
        "version_caso": 1,
        "version_curva": "CURVA-APPROVED-DEMO-01",
        "fecha_corte": "2026-11-11",
        "execution_mode": "DEMO",
        "estado": "PENDIENTE_APROBACION",
        "agentes": {"elara": {"estado": "ACEPTAR", "evidencia": "private"}, "atenea": {"estado": "DICTAMEN_TECNICO_VALIDADO"}},
        "fuente_datos": {"source_mode": "FIXTURE"},
        "resultado_curva": {"metodologia": "TEST", "instrument_count": 1, "max_absolute_repricing_error": 0.0, "pillars": [{"days": 28, "spot_rate": 0.08}]},
        "auditoria": {"tecnicamente_valida": True, "tolerancia": 1e-8},
        "cost_trace": {"currency": "USD", "components": [{"component": "NASH", "api_calls": 0, "invocation_id": "private"}]},
    }
    return {
        "caso_id": api["caso_id"], "version_caso": api["version_caso"], "version_curva": api["version_curva"],
        "fecha_corte": api["fecha_corte"], "execution_mode": "DEMO", "estado": "APROBADA_HUMANAMENTE",
        "approval_status": "APPROVED", "telegram_chat_id": "private", "api_result_json": json.dumps(api),
    }


def write_row(tmp_path, row: dict) -> None:
    (tmp_path / "approved_case.json").write_text(json.dumps(row), encoding="utf-8")


def test_exported_approved_demo_is_public_sanitized_and_never_copies_private_row(tmp_path):
    row = private_row(); write_row(tmp_path, row)
    target = export_approved_case(tmp_path / "approved_case.json", tmp_path / "public")
    public = json.loads(target.read_text(encoding="utf-8"))
    validate_public_case(public)
    assert public["case_id"] == row["caso_id"]
    assert public["execution_mode"] == "DEMO" and public["publication_authorized"] is True
    serialized = json.dumps(public).lower()
    assert not any(field in serialized for field in FORBIDDEN)
    assert "telegram_chat_id" not in serialized and "private" not in serialized
    assert not (tmp_path / "web" / "dist").exists()


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda row: row.update(estado="PENDIENTE_APROBACION"), "ROW_NOT_APPROVED_DEMO"),
        (lambda row: row.update(estado="RECHAZADO"), "ROW_NOT_APPROVED_DEMO"),
        (lambda row: row.update(approval_status="PENDING"), "APPROVAL_STATUS_INVALID"),
        (lambda row: row.update(execution_mode="LIVE"), "ROW_NOT_APPROVED_DEMO"),
        (lambda row: row.update(api_result_json="not-json"), "API_RESULT_JSON_INVALID"),
    ],
)
def test_export_rejects_invalid_private_row_state(tmp_path, mutate, code):
    row = private_row(); mutate(row); write_row(tmp_path, row)
    with pytest.raises(ExportError, match=code):
        export_approved_case(tmp_path / "approved_case.json", tmp_path / "public")


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda api: api.update(caso_id="YC-OTHERCASE01"), "API_ROW_MISMATCH"),
        (lambda api: api.update(version_caso=2), "API_ROW_MISMATCH"),
        (lambda api: api.update(fecha_corte="2026-11-12"), "API_ROW_MISMATCH"),
        (lambda api: api["auditoria"].update(tecnicamente_valida=False), "API_AUDIT_INVALID"),
        (lambda api: api["resultado_curva"].update(pillars=[]), "API_PILLARS_INVALID"),
    ],
)
def test_export_rejects_incoherent_or_technically_invalid_api_result(tmp_path, mutate, code):
    row = private_row(); api = json.loads(row["api_result_json"]); mutate(api); row["api_result_json"] = json.dumps(api); write_row(tmp_path, row)
    with pytest.raises(ExportError, match=code):
        export_approved_case(tmp_path / "approved_case.json", tmp_path / "public")


def test_export_rejects_existing_output_and_nonfinite_values(tmp_path):
    row = private_row(); write_row(tmp_path, row)
    export_approved_case(tmp_path / "approved_case.json", tmp_path / "public")
    with pytest.raises(ExportError, match="PUBLIC_OUTPUT_EXISTS"):
        export_approved_case(tmp_path / "approved_case.json", tmp_path / "public")
    row = deepcopy(private_row()); api = json.loads(row["api_result_json"]); api["resultado_curva"]["pillars"][0]["spot_rate"] = float("nan")
    row["api_result_json"] = json.dumps(api); write_row(tmp_path, row)
    with pytest.raises(ExportError, match="API_RESULT_JSON_INVALID"):
        export_approved_case(tmp_path / "approved_case.json", tmp_path / "another-public")
