"""Execute critical n8n Code-node guards in a minimal compatible harness."""

from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path

import pytest


WORKFLOW = Path(__file__).parents[1] / "n8n" / "YieldCurve_AI_Telegram_Orchestration_V6_API.json"


def run_code_node(name: str, input_row: dict, references: dict[str, dict]) -> dict:
    workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
    code = next(node for node in workflow["nodes"] if node["name"] == name)["parameters"]["jsCode"]
    harness = """
const fs = require('fs');
const vm = require('vm');
const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
const context = {
  $input: { first: () => ({ json: payload.input }) },
  $: (name) => ({ first: () => ({ json: payload.references[name] }) }),
  Buffer, Date, String, Number, Boolean, JSON, Math,
};
const output = vm.runInNewContext("(() => {\\n" + payload.code + "\\n})()", context);
process.stdout.write(JSON.stringify(output));
"""
    completed = subprocess.run(
        ["node", "-e", harness],
        input=json.dumps({"code": code, "input": input_row, "references": references}),
        text=True,
        capture_output=True,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr)
    return json.loads(completed.stdout)[0]["json"]


def event(**changes: object) -> dict:
    value = {
        "route": "CALLBACK", "args": ["APR", "YC-GUARD001", "1"],
        "private_chat": True, "telegram_user_id": "owner", "telegram_chat_id": "chat-1",
        "access": {"role": "EVALUATOR"},
    }
    value.update(changes)
    return value


def pending_case(**changes: object) -> dict:
    value = {
        "caso_id": "YC-GUARD001", "version_caso": 1,
        "telegram_user_id": "owner", "telegram_chat_id": "chat-1",
        "estado": "PENDIENTE_APROBACION", "approval_status": "PENDING",
        "approval_expires_at": "2099-01-01T00:00:00.000Z",
    }
    value.update(changes)
    return value


def test_authorize_and_route_executes_denial_for_an_unauthorized_telegram_user() -> None:
    result = run_code_node(
        "Authorize and route",
        {"telegram_user_id": "other", "telegram_chat_id": "chat-1", "status": "ACTIVE", "role": "EVALUATOR"},
        {"Normalize safe Telegram event": {"route": "/nuevo", "private_chat": True, "telegram_user_id": "owner", "telegram_chat_id": "chat-1"}},
    )

    assert result["authorized"] is False
    assert result["next"] == "REPLY"
    assert result["reply"] == "Acceso no autorizado."


@pytest.mark.parametrize("callback, case", [
    (event(telegram_user_id="intruder"), pending_case()),
    (event(private_chat=False), pending_case()),
    (event(args=["APR", "YC-GUARD001", "0"]), pending_case()),
    (event(), pending_case(estado="APROBADA_HUMANAMENTE", approval_status="APPROVED")),
])
def test_callback_guard_rejects_unowned_nonprivate_stale_and_repeated_decisions(callback: dict, case: dict) -> None:
    result = run_code_node("Guard status callback and expiry", case, {"Authorize and route": callback})

    assert result["allowed"] is False
    assert result["reply"].endswith("no autorizada o caso no vigente.")


def test_idempotent_publication_returns_create_for_absence_and_noop_for_same_case() -> None:
    public_case = {"case_id": "YC-GUARD001", "version_caso": 1, "execution_mode": "LIVE"}
    references = {"Validate public artifact identity": {"public_case": public_case, "case_id": "YC-GUARD001", "version_caso": 1}}

    missing = run_code_node("Decide idempotent GitHub publication", {"statusCode": 404}, references)
    existing = base64.b64encode(json.dumps(public_case).encode()).decode()
    repeated = run_code_node("Decide idempotent GitHub publication", {"content": existing}, references)

    assert missing["publication_action"] == "CREATE"
    assert repeated["publication_action"] == "NOOP"


@pytest.mark.parametrize("existing_case, error", [
    ({"case_id": "YC-GUARD001", "version_caso": 2, "execution_mode": "LIVE"}, "GITHUB_PUBLIC_CASE_VERSION_CONFLICT"),
    ({"case_id": "YC-GUARD001", "version_caso": 1, "execution_mode": "DEMO"}, "GITHUB_PUBLIC_CASE_CONTENT_CONFLICT"),
])
def test_idempotent_publication_fails_closed_for_conflicting_case(existing_case: dict, error: str) -> None:
    content = base64.b64encode(json.dumps(existing_case).encode()).decode()
    references = {"Validate public artifact identity": {"public_case": {"case_id": "YC-GUARD001", "version_caso": 1, "execution_mode": "LIVE"}, "case_id": "YC-GUARD001", "version_caso": 1}}

    with pytest.raises(RuntimeError, match=error):
        run_code_node("Decide idempotent GitHub publication", {"content": content}, references)
