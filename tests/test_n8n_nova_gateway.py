"""Structural guardrails for the inactive Nova Voice Gateway export."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).parents[1]
WORKFLOW = ROOT / "n8n" / "YieldCurve_AI_Nova_Voice_Gateway_V7.json"
V6 = ROOT / "n8n" / "YieldCurve_AI_Telegram_Orchestration_V6_API.json"


def load() -> dict:
    return json.loads(WORKFLOW.read_text(encoding="utf-8"))


def node_map(workflow: dict) -> dict:
    return {node["name"]: node for node in workflow["nodes"]}


def test_nova_gateway_is_portable_inactive_and_has_two_authenticated_post_webhooks():
    workflow = load()
    assert workflow["active"] is False
    assert workflow["settings"]["saveDataSuccessExecution"] == "none"
    assert workflow["settings"]["saveDataErrorExecution"] == "none"
    hooks = [n for n in workflow["nodes"] if n["type"] == "n8n-nodes-base.webhook"]
    assert len(hooks) == 2
    assert {n["parameters"]["path"] for n in hooks} == {"yieldcurve-ai/nova/consultar-caso", "yieldcurve-ai/nova/crear-caso-demo"}
    for hook in hooks:
        assert hook["parameters"]["httpMethod"] == "POST"
        assert hook["parameters"]["authentication"] == "headerAuth"
        assert hook["credentials"]["httpHeaderAuth"]["id"] == "__YC_NOVA_VOICE_AUTH__"
        assert hook["webhookId"].startswith("__YC_")


def test_query_is_read_only_sanitized_and_never_calls_orion():
    nodes = node_map(load())
    query = nodes["Build sanitized query response"]["parameters"]["jsCode"]
    assert "^YC-[A-Z0-9]{8,32}$" in nodes["Validate query input"]["parameters"]["jsCode"]
    assert load()["connections"]["Gate valid Nova query"]["main"][0][0]["node"] == "YC_CASES | Find Nova case"
    assert "YC_CASES" in nodes["YC_CASES | Find Nova case"]["parameters"]["dataTableId"]["cachedResultName"]
    assert nodes["YC_CASES | Find Nova case"]["alwaysOutputData"] is True
    lookup = nodes["YC_CASES | Find Nova case"]["parameters"]
    assert lookup["matchType"] == "allConditions"
    assert {(item["keyName"], item["keyValue"]) for item in lookup["filters"]["conditions"]} == {
        ("caso_id", "={{ $('Validate query input').first().json.caso_id }}"),
        ("execution_mode", "DEMO"),
    }
    for allowed in ("caso_id", "fecha_corte", "modo", "estado", "dictamen_tecnico", "metodologia", "instrument_count", "max_absolute_repricing_error", "auditoria_tecnicamente_valida", "requiere_aprobacion_humana"):
        assert allowed in query
    for private in ("telegram_chat_id", "telegram_user_id", "api_result_json", "invocation_id", "conversation_id"):
        assert private not in query
    assert "/v1/orion/run" not in json.dumps([nodes["Webhook | Nova consultar caso"], nodes["Validate query input"], nodes["YC_CASES | Find Nova case"], nodes["Build sanitized query response"]])


def test_create_is_demo_only_idempotent_and_never_accepts_extra_fields_or_live():
    workflow = load(); nodes = node_map(workflow)
    validate = nodes["Validate DEMO creation input"]["parameters"]["jsCode"]
    assert "execution_mode:'DEMO'" in validate and "d!=='2026-11-11'" in validate
    assert "conversation_id" in validate and "agent_turn" in validate and "extras.length" in validate
    assert workflow["connections"]["Gate valid DEMO creation"]["main"][0][0]["node"] == "YC_EVENTS | Find Nova event"
    assert "EL-NOVA-" in validate and "YC-NV" in validate
    assert "const raw=`NOVA|${b.conversation_id}|CREATE|${d}`" in validate
    assert "${b.agent_turn}" not in validate
    assert re.search(r"YC-NV", validate)
    assert nodes["YC_EVENTS | Find Nova event"]["parameters"]["dataTableId"]["value"] == "__YC_EVENTS_TABLE_ID__"
    assert nodes["YC_EVENTS | Find Nova event"]["alwaysOutputData"] is True
    assert nodes["YC_CASES | Create Nova pending case"]["parameters"]["columns"]["value"]["canal_origen"] == "nova"
    call = nodes["Invoke Orion once for Nova"]["parameters"]
    assert call["url"].endswith("/v1/orion/run") and call["options"]["retry"]["maxTries"] == 1
    assert json.dumps(call).count("execution_mode:'DEMO'") == 1
    assert "fecha de corte ' + $('Validate DEMO creation input').first().json.fecha_corte" in call["jsonBody"]
    assert "metodología autorizada" in call["jsonBody"]


def test_duplicate_demo_uses_persisted_case_without_orion_or_notification():
    workflow = load(); nodes = node_map(workflow)
    duplicate = nodes["YC_CASES | Find duplicate Nova case"]
    response = nodes["Build sanitized duplicate create response"]["parameters"]["jsCode"]
    assert workflow["connections"]["Gate new Nova event"]["main"][1][0]["node"] == "YC_CASES | Find duplicate Nova case"
    assert workflow["connections"]["YC_CASES | Find duplicate Nova case"]["main"][0][0]["node"] == "Build sanitized duplicate create response"
    assert workflow["connections"]["Build sanitized duplicate create response"]["main"][0][0]["node"] == "Respond | Nova create"
    assert duplicate["alwaysOutputData"] is True
    assert duplicate["parameters"]["matchType"] == "allConditions"
    assert {(item["keyName"], item["keyValue"]) for item in duplicate["parameters"]["filters"]["conditions"]} == {
        ("caso_id", "={{ $('Validate DEMO creation input').first().json.caso_id }}"),
        ("execution_mode", "DEMO"),
    }
    for required in ("r.caso_id", "r.estado", "SERVICIO_NO_DISPONIBLE"):
        assert required in response
    for forbidden in ("Invoke Orion once for Nova", "Notify active OWNER via Telegram", "api_result_json", "conversation_id"):
        assert forbidden not in response


def test_gateway_has_no_human_decision_mutation_and_owner_notification_is_private_runtime_data():
    workflow = load(); nodes = node_map(workflow); serialized = json.dumps(workflow)
    assert "decision_at" not in serialized and "decision_event_id" not in serialized
    assert "PENDING" in json.dumps(nodes["YC_CASES | Persist Nova result"])
    owner = nodes["YC_ACCESS | Find active OWNER"]["parameters"]["filters"]["conditions"]
    assert {(item["keyName"], item["keyValue"]) for item in owner} == {("role", "OWNER"), ("status", "ACTIVE")}
    notification = json.dumps(nodes["Notify active OWNER via Telegram"])
    assert "APR|" in notification and "REJ|" in notification
    assert "__YC_TELEGRAM_CREDENTIAL__" in notification
    assert nodes["Notify active OWNER via Telegram"]["parameters"]["additionalFields"]["appendAttribution"] is False
    assert workflow["connections"]["Gate eligible Nova OWNER notification"]["main"][0][0]["node"] == "Notify active OWNER via Telegram"
    assert not re.search(r"telegram_(?:chat|user)_id\"\s*:\s*\"[0-9]", serialized)


def test_owner_telegram_notification_uses_explicit_html_without_changing_payload_or_security():
    workflow = load(); nodes = node_map(workflow)
    notification = nodes["Notify active OWNER via Telegram"]
    additional = notification["parameters"]["additionalFields"]
    prepared = nodes["Prepare OWNER notification only"]["parameters"]["jsCode"]
    serialized = json.dumps(notification, ensure_ascii=False).lower()

    assert additional["parse_mode"] == "HTML"
    assert additional["appendAttribution"] is False
    assert "APR|" in json.dumps(notification) and "REJ|" in json.dumps(notification)
    for field in ("Estado:", "Dictamen:", "Instrumentos:", "repricing"):
        assert field in prepared
    for forbidden in ("sk-", "bearer ", "api_key", "x-yieldcurve-voice-key\": \""):
        assert forbidden not in serialized
    assert not re.search(r"telegram_(?:chat|user)_id\"\s*:\s*\"[0-9]", serialized)


def test_no_secret_literals_and_v6_is_not_modified():
    serialized = json.dumps(load(), ensure_ascii=False).lower()
    for forbidden in ("sk-", "bearer ", "api_key", "x-yieldcurve-voice-key\": \"", "x-yieldcurve-key\": \""):
        assert forbidden not in serialized
    assert V6.exists()
