"""Static, semantic checks for the verified n8n V6 export."""

from __future__ import annotations

import json
from pathlib import Path


WORKFLOW = Path(__file__).parents[1] / "n8n" / "YieldCurve_AI_Telegram_Orchestration_V6_API.json"
SETUP = WORKFLOW.parent / "YieldCurve_AI_Telegram_Orchestration_V6_API_SETUP.md"


def load_workflow() -> dict:
    return json.loads(WORKFLOW.read_text(encoding="utf-8"))


def nodes_by_name(workflow: dict) -> dict:
    return {node["name"]: node for node in workflow["nodes"]}


def destinations(workflow: dict, source: str, output: int = 0) -> set[str]:
    return {edge["node"] for edge in workflow["connections"][source]["main"][output]}


def filters_require_all(filters: dict, node: dict) -> bool:
    """Accept equivalent export layouts, but never an implicit OR mutation."""
    match_type = node["parameters"].get("matchType", filters.get("matchType"))
    return match_type == "allConditions" or filters.get("type") == "and"


def test_v6_workflow_is_valid_json_and_inactive() -> None:
    workflow = load_workflow()
    triggers = [node for node in workflow["nodes"] if node["type"] == "n8n-nodes-base.telegramTrigger"]
    assert workflow["name"].endswith("V6 API")
    assert workflow["active"] is False
    assert len(triggers) == 1
    assert set(triggers[0]["parameters"]["updates"]) == {"message", "callback_query"}


def test_v6_calls_only_render_once_with_safe_http_configuration() -> None:
    workflow = load_workflow()
    nodes = nodes_by_name(workflow)
    expected = {
        "Invoke YieldCurve API once",
        "Generate curve PNG",
        "Build sanitized LIVE public artifact",
        "GitHub | Get public case",
        "GitHub | Create approved LIVE case",
    }
    http_nodes = {node["name"]: node for node in workflow["nodes"] if node["type"] == "n8n-nodes-base.httpRequest"}
    assert set(http_nodes) == expected
    for name in expected:
        assert http_nodes[name]["parameters"]["authentication"] == "genericCredentialType"
        credential = http_nodes[name]["credentials"]["httpHeaderAuth"]
        assert credential["id"].startswith("__YC_")
        assert credential["name"].startswith("__YC_")
    params = nodes["Invoke YieldCurve API once"]["parameters"]
    assert params["url"] == "https://yieldcurve-ai.onrender.com/v1/orion/run"
    assert params["method"] == "POST"
    assert params["options"]["timeout"] == 90000
    assert params["options"].get("retry", {}).get("maxTries", 1) == 1
    assert "execution_mode" in params["jsonBody"]
    assert "authorization_source" not in params["jsonBody"]
    assert "execution_authorized" not in params["jsonBody"]


def test_v6_keeps_orchestration_free_of_unapproved_services_and_computation() -> None:
    serialized = json.dumps(load_workflow(), ensure_ascii=False).lower()
    for forbidden in ("sk-", "bearer ", "openai.com", "banxico.org.mx/sieapi", "api_key", 'x-yieldcurve-key": "', "least_squares", "scipy", "pchip"):
        assert forbidden not in serialized
    formatter = nodes_by_name(load_workflow())["Format provisional result and buttons"]["parameters"]["jsCode"].lower()
    assert "bootstrap" in formatter  # Presentation label only, not an executed calculation.


def test_v6_execution_retention_is_explicitly_disabled() -> None:
    settings = load_workflow()["settings"]
    assert settings["saveDataSuccessExecution"] == "none"
    assert settings["saveDataErrorExecution"] == "none"
    setup = SETUP.read_text(encoding="utf-8")
    assert "no dependa de los valores predeterminados" in setup.lower()
    assert "90 segundos" in setup


def test_v6_export_uses_portable_markers_for_instance_metadata() -> None:
    """The public template must not expose one n8n instance's identifiers."""
    workflow = load_workflow()
    serialized = json.dumps(workflow)
    expected_markers = {
        "__YC_TELEGRAM_CREDENTIAL__",
        "__YC_RENDER_AUTH__",
        "__YC_TELEGRAM_WEBHOOK__",
        "__YC_PROJECT__",
        "__YC_EVENTS_TABLE_ID__",
        "__YC_CASES_TABLE_ID__",
        "__YC_ACCESS_TABLE_ID__",
        "__YC_ACCESS_CODES_TABLE_ID__",
        "__YC_GITHUB_AUTH__",
    }
    assert all(marker in serialized for marker in expected_markers)

    for node in workflow["nodes"]:
        for credential in node.get("credentials", {}).values():
            assert credential["id"].startswith("__YC_")
            assert credential["name"].startswith("__YC_")
        if "webhookId" in node:
            assert node["webhookId"] == "__YC_TELEGRAM_WEBHOOK__"

        table = node.get("parameters", {}).get("dataTableId")
        if table:
            assert table["value"].startswith("__YC_")
            assert "__YC_PROJECT__" in table["cachedResultUrl"]
            assert table["cachedResultName"]

    setup = SETUP.read_text(encoding="utf-8")
    assert "marcadores de importación" in setup
    assert "identificadores privados" in setup


def test_v6_sensitive_data_table_mutations_require_all_filters() -> None:
    nodes = nodes_by_name(load_workflow())
    expected_conditions = {
        "YC_CASES | Save API result": {"caso_id", "version_caso", "estado", "approval_status"},
        "YC_CASES | Persist API error": {"caso_id", "version_caso", "estado"},
        "YC_ACCESS_CODES | Consume code": {"status", "used_at"},
        "YC_EVENTS | Mark processed": {"event_id"},
        "YC_ACCESS | Create evaluator": {"telegram_user_id", "telegram_chat_id"},
        "YC_CASES | Persist expired": {"caso_id", "version_caso", "approval_status"},
        "YC_CASES | Persist allowed decision": {"caso_id", "version_caso", "estado", "approval_status"},
    }
    for name, required in expected_conditions.items():
        node = nodes[name]
        filters = node["parameters"]["filters"]
        names = {condition.get("keyName") for condition in filters["conditions"]}
        assert filters_require_all(filters, node), name
        assert required <= names, name


def test_v6_save_result_retains_its_four_compare_and_set_guards() -> None:
    node = nodes_by_name(load_workflow())["YC_CASES | Save API result"]
    conditions = node["parameters"]["filters"]["conditions"]
    values = {item["keyName"]: item["keyValue"] for item in conditions}
    assert len(conditions) == 4
    assert set(values) == {"caso_id", "version_caso", "estado", "approval_status"}
    assert values["estado"] == "PENDIENTE_EJECUCION"
    assert values["approval_status"] == "NOT_AVAILABLE"


def test_v6_approval_keyboard_is_real_and_only_eligible_branch_reaches_it() -> None:
    workflow = load_workflow()
    nodes = nodes_by_name(workflow)
    approval = nodes["Telegram | Send approval response"]["parameters"]
    gate = nodes["If"]["parameters"]["conditions"]
    assert approval["replyMarkup"] == "inlineKeyboard"
    buttons = approval["inlineKeyboard"]["rows"][0]["row"]["buttons"]
    assert [button["text"] for button in buttons] == ["✅ Aprobar", "❌ Rechazar"]
    callback_data = [button["additionalFields"]["callback_data"] for button in buttons]
    assert "APR|" in callback_data[0] and "case_artifact.caso_id" in callback_data[0] and "case_artifact.version_caso" in callback_data[0]
    assert "REJ|" in callback_data[1] and "case_artifact.caso_id" in callback_data[1] and "case_artifact.version_caso" in callback_data[1]
    assert "Prepare curve artifact payload" in approval["chatId"] and "Prepare curve artifact payload" in approval["text"]
    assert "eligible_for_approval" in json.dumps(gate)
    assert destinations(workflow, "If", 0) == {"Prepare curve artifact payload"}
    assert destinations(workflow, "If", 1) == {"Telegram | Send response"}
    assert destinations(workflow, "Generate curve PNG", 0) == {"Telegram | Send curve photo"}
    assert destinations(workflow, "Telegram | Send curve photo") == {"Telegram | Send approval response"}
    assert destinations(workflow, "Telegram | Send approval response") == {"YC_EVENTS | Mark processed"}
    assert destinations(workflow, "Telegram | Send response") == {"YC_EVENTS | Mark processed"}


def test_v6_eligible_curve_image_uses_artifact_binary_and_preserves_approval() -> None:
    workflow = load_workflow(); nodes = nodes_by_name(workflow)
    prepare = nodes["Prepare curve artifact payload"]["parameters"]["jsCode"]
    png = nodes["Generate curve PNG"]["parameters"]
    photo = nodes["Telegram | Send curve photo"]["parameters"]
    assert "api_result_json" in prepare and "caseArtifact = apiResult.case_artifact" in prepare
    assert "...current" in prepare and "pillars" not in prepare
    assert png["url"].endswith("/v1/artifacts/curve.png")
    assert png["authentication"] == "genericCredentialType"
    assert "case_artifact" in png["jsonBody"]
    assert png["options"]["response"]["response"]["responseFormat"] == "file"
    assert png["options"]["response"]["response"]["outputPropertyName"] == "data"
    assert photo["binaryData"] is True and photo["binaryPropertyName"] == "data"
    assert destinations(workflow, "Generate curve PNG", 1) == {"Telegram | Send approval response"}


def test_v6_formatter_preserves_contract_and_friendly_presentation() -> None:
    code = nodes_by_name(load_workflow())["Format provisional result and buttons"]["parameters"]["jsCode"]
    for key in ("agents.elara", "agents.siena", "agents.nash", "agents.atenea"):
        assert key in code
    assert "elara.decision || elara.estado" in code
    for contract_value in ("PENDIENTE_APROBACION", "curve.pillars", "audit.tecnicamente_valida", "p.approval_status === 'PENDING'", "Bootstrap 182 días · V1"):
        assert contract_value in code


def test_v6_callback_guard_requires_each_authorization_condition() -> None:
    code = nodes_by_name(load_workflow())["Guard status callback and expiry"]["parameters"]["jsCode"]
    for required in ("e.route === 'CALLBACK'", "owner || owned", "e.private_chat", "['OWNER', 'EVALUATOR'].includes(e.access?.role)", "String(c.caso_id) === String(callbackCaseId)", "c.estado === 'PENDIENTE_APROBACION'", "c.approval_status === 'PENDING'", "!expired", "String(c.version_caso) === String(callbackVersion)", "['APR', 'REJ'].includes(act)"):
        assert required in code


def test_v6_context_restoration_always_uses_normal_response_branch() -> None:
    workflow = load_workflow()
    nodes = nodes_by_name(workflow)
    for name in ("Restore access confirmation context", "Restore callback response context"):
        assert "reply_markup:null" in nodes[name]["parameters"]["jsCode"]
        assert destinations(workflow, name) == {"If"}
    assert "Acceso temporal habilitado." in nodes["Restore access confirmation context"]["parameters"]["jsCode"]
    assert "Decisión no autorizada o caso no vigente." in nodes["Restore callback response context"]["parameters"]["jsCode"]


def test_v6_routes_errors_callbacks_and_status_without_backend_reexecution() -> None:
    workflow = load_workflow()
    connections = workflow["connections"]
    assert destinations(workflow, "Invoke YieldCurve API once", 1) == {"YC_CASES | Persist API error"}
    assert destinations(workflow, "Gate expired or allowed callback", 1) == {"YC_CASES | Persist allowed decision"}
    assert destinations(workflow, "YC_CASES | Persist allowed decision") == {"Telegram | Answer callback", "Route approved decision to publication"}
    assert destinations(workflow, "Route non-allowed callback", 0) == {"Telegram | Answer callback"}
    assert destinations(workflow, "Route expired response", 0) == {"Telegram | Answer callback"}
    assert "Invoke YieldCurve API once" not in json.dumps(connections["YC_CASES | Load case"])


def test_v6_publication_requires_persisted_approved_state_and_routes_create_idempotently() -> None:
    workflow = load_workflow()
    nodes = nodes_by_name(workflow)

    assert destinations(workflow, "YC_CASES | Persist allowed decision") == {
        "Telegram | Answer callback", "Route approved decision to publication",
    }
    assert destinations(workflow, "Route approved decision to publication") == {"YC_CASES | Reload approved case"}
    validate = nodes["Validate persisted approval for publication"]["parameters"]["jsCode"]
    for required in ("APROBADA_HUMANAMENTE", "APPROVED", "PUBLICATION_APPROVAL_NOT_PERSISTED"):
        assert required in validate
    assert destinations(workflow, "Route GitHub publication action", 0) == {"Prepare GitHub publication payload"}
    assert destinations(workflow, "Route GitHub publication action", 1) == {"Prepare publication result message"}
    assert nodes["GitHub | Create approved LIVE case"]["parameters"]["jsonBody"] == "={{ $json.github_body }}"


def test_v6_persisted_decision_uses_pending_state_as_compare_and_set_guard() -> None:
    node = nodes_by_name(load_workflow())["YC_CASES | Persist allowed decision"]
    conditions = node["parameters"]["filters"]["conditions"]
    guards = {condition["keyName"]: condition["keyValue"] for condition in conditions}

    assert guards == {
        "caso_id": "={{ $json.case_row.caso_id }}",
        "version_caso": "={{ $json.case_row.version_caso }}",
        "estado": "PENDIENTE_APROBACION",
        "approval_status": "PENDING",
    }
