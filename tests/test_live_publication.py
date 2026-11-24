import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import app
from backend.public_artifacts import (
    build_approved_live_public_case_artifact,
    validate_public_case,
    write_public_case_idempotently,
)


def live_artifact() -> dict:
    return {
        "caso_id": "YC-LIVEAPPROVED01",
        "version_caso": 1,
        "version_curva": "CURVA-LIVE-APPROVED-01",
        "fecha_corte": "2026-11-23",
        "execution_mode": "LIVE",
        "estado": "PENDIENTE_APROBACION",
        "agentes": {"elara": {"estado": "ACEPTAR", "private": "drop"}},
        "fuente_datos": {"source_mode": "BANXICO_SIE_LIVE", "payload": "drop"},
        "curva": {"metodologia": "TEST", "instrument_count": 1, "max_absolute_repricing_error": 0.0, "pillars": [{"days": 28, "spot_rate": 0.08, "private": "drop"}]},
        "auditoria": {"tecnicamente_valida": True, "tolerancia": 1e-8, "private": "drop"},
        "cost_trace": {
            "currency": "USD", "known_cost_usd": 0.0003126, "cost_completeness": "PARTIAL",
            "components": [{"component": "ELARA", "input_tokens": 2201, "output_tokens": 185, "cost_usd": 0.0003126, "cost_status": "ESTIMATED_FROM_VERIFIED_RATE", "response_id": "drop"}],
        },
    }


def approval(**changes) -> dict:
    value = {"caso_id": "YC-LIVEAPPROVED01", "version_caso": 1, "estado": "APROBADA_HUMANAMENTE", "approval_status": "APPROVED"}
    value.update(changes)
    return value


def test_approved_live_projection_uses_persisted_evidence_and_allowlists_costs():
    public = build_approved_live_public_case_artifact(live_artifact(), approval(), "2026-11-24T00:00:00+00:00")
    validate_public_case(public)
    assert public["execution_mode"] == "LIVE"
    assert public["fuente"] == {"source_mode": "BANXICO_SIE_LIVE"}
    assert public["costos"]["known_cost_usd"] == 0.0003126
    assert public["costos"]["components"][0]["cost_usd"] == 0.0003126
    serialized = json.dumps(public).lower()
    for forbidden in ("pending_aprobacion", "private", "payload", "response_id", "approval_status"):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    ("artifact_changes", "approval_changes", "code"),
    [
        ({}, {"estado": "PENDIENTE_APROBACION"}, "LIVE_PUBLIC_APPROVAL_EVIDENCE_INVALID"),
        ({}, {"estado": "RECHAZADA_HUMANAMENTE"}, "LIVE_PUBLIC_APPROVAL_EVIDENCE_INVALID"),
        ({}, {"approval_status": "EXPIRED"}, "LIVE_PUBLIC_APPROVAL_EVIDENCE_INVALID"),
        ({}, {"approval_status": "PENDING"}, "LIVE_PUBLIC_APPROVAL_EVIDENCE_INVALID"),
        ({}, {"caso_id": "YC-OTHERCASE01"}, "LIVE_PUBLIC_APPROVAL_EVIDENCE_INVALID"),
        ({}, {"version_caso": 2}, "LIVE_PUBLIC_APPROVAL_EVIDENCE_INVALID"),
        ({"fuente_datos": {"source_mode": "FIXTURE"}}, {}, "LIVE_PUBLIC_TECHNICAL_EVIDENCE_INVALID"),
        ({"auditoria": {"tecnicamente_valida": False}}, {}, "LIVE_PUBLIC_TECHNICAL_EVIDENCE_INVALID"),
        ({"curva": {"pillars": []}}, {}, "LIVE_PUBLIC_TECHNICAL_EVIDENCE_INVALID"),
    ],
)
def test_live_projection_fails_closed(artifact_changes, approval_changes, code):
    artifact = live_artifact(); artifact.update(artifact_changes)
    with pytest.raises(ValueError, match=code):
        build_approved_live_public_case_artifact(artifact, approval(**approval_changes))


def test_local_publication_is_idempotent_and_conflicts_fail_closed(tmp_path):
    public = build_approved_live_public_case_artifact(live_artifact(), approval(), "2026-11-24T00:00:00+00:00")
    target, action = write_public_case_idempotently(public, tmp_path)
    assert action == "CREATED" and target.exists()
    assert write_public_case_idempotently(public, tmp_path)[1] == "NOOP"
    changed = json.loads(json.dumps(public)); changed["curva"]["pillars"][0]["spot_rate"] = 0.09
    with pytest.raises(ValueError, match="PUBLIC_OUTPUT_CONTENT_CONFLICT"):
        write_public_case_idempotently(changed, tmp_path)
    changed = json.loads(json.dumps(public)); changed["version_caso"] = 2
    with pytest.raises(ValueError, match="PUBLIC_OUTPUT_VERSION_CONFLICT"):
        write_public_case_idempotently(changed, tmp_path)


def test_live_projection_endpoint_is_authenticated_and_never_returns_approval_evidence(monkeypatch):
    monkeypatch.setenv("YIELDCURVE_API_KEY", "test-key")
    client = TestClient(app)
    payload = {"case_artifact": live_artifact(), "approval_evidence": approval()}
    assert client.post("/v1/artifacts/public/live", json=payload).status_code == 401
    response = client.post("/v1/artifacts/public/live", json=payload, headers={"X-YieldCurve-Key": "test-key"})
    assert response.status_code == 200
    assert "approval_evidence" not in response.json()


def test_n8n_live_publication_branch_uses_managed_credentials_and_no_secret_literal():
    workflow = json.loads((Path(__file__).parents[1] / "n8n/YieldCurve_AI_Telegram_Orchestration_V6_API.json").read_text(encoding="utf-8"))
    nodes = {node["name"]: node for node in workflow["nodes"]}
    required = {
        "Route approved decision to publication", "YC_CASES | Reload approved case",
        "Validate persisted approval for publication", "Parse original technical artifact",
        "Build sanitized LIVE public artifact", "Validate public artifact identity",
        "GitHub | Get public case", "Decide idempotent GitHub publication",
        "GitHub | Create approved LIVE case",
    }
    assert required <= set(nodes)
    assert "__YC_GITHUB_AUTH__" in json.dumps(nodes["GitHub | Create approved LIVE case"])
    assert "ghp_" not in json.dumps(workflow).lower()
