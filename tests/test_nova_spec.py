import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
NOVA = ROOT / "voice" / "nova"
KNOWLEDGE = NOVA / "knowledge"
KNOWLEDGE_PACK = (
    "01_fundamentos_curva_tasas.md",
    "02_bootstrapping_y_metodologia.md",
    "03_yieldcurve_ai_arquitectura.md",
    "04_guia_de_uso.md",
    "05_faq_seguridad_y_estados.md",
)


def read(relative: str) -> str:
    return (NOVA / relative).read_text(encoding="utf-8")


def test_nova_files_and_schemas_are_valid_and_restrict_inputs():
    assert (NOVA / "system_prompt.md").is_file()
    assert (NOVA / "knowledge" / "yieldcurve_ai_knowledge.md").is_file()
    consultar = json.loads(read("tools/consultar_caso.schema.json"))
    crear = json.loads(read("tools/crear_caso_demo.schema.json"))
    Draft202012Validator.check_schema(consultar)
    Draft202012Validator.check_schema(crear)
    query = Draft202012Validator(consultar)
    demo = Draft202012Validator(crear, format_checker=FormatChecker())
    assert not list(query.iter_errors({"caso_id": "YC-DEMO20261103"}))
    assert list(query.iter_errors({"caso_id": "https://example.test"}))
    assert list(query.iter_errors({"caso_id": "YC-DEMO20261103", "url": "x"}))
    assert not list(demo.iter_errors({"fecha_corte": "2026-11-11"}))
    assert list(demo.iter_errors({"fecha_corte": "2026-11-11", "mode": "LIVE"}))


def test_nova_prompt_rag_and_tool_contracts_keep_guardrails():
    prompt = read("system_prompt.md").lower()
    index = read("knowledge/yieldcurve_ai_knowledge.md").lower()
    methodology = read("knowledge/02_bootstrapping_y_metodologia.md").lower()
    consulta = read("tools/consultar_caso.md").lower()
    crear = read("tools/crear_caso_demo.md").lower()
    for required in ("consentimiento", "recomendaciones de inversión", "telegram", "prompt", "live"):
        assert required in prompt
    for filename in KNOWLEDGE_PACK:
        assert filename in index
    for required in ("excel_bootstrap_182d_v1", "repricing"):
        assert required in methodology
    assert "nova no aprueba ni rechaza" in index
    for forbidden in ("api_result_json", "telegram chat id", "approval token", "chain-of-thought"):
        assert forbidden in consulta
    assert "demo" in crear and "live" in crear and "aprobar" in crear
    assert not (NOVA / "tools" / "aprobar_caso.schema.json").exists()
    assert not (NOVA / "tools" / "rechazar_caso.schema.json").exists()


def test_nova_knowledge_pack_is_modular_complete_and_safe():
    texts = {}
    for filename in KNOWLEDGE_PACK:
        path = KNOWLEDGE / filename
        assert path.is_file(), filename
        text = path.read_text(encoding="utf-8")
        assert text.startswith("# ") and len(text.strip()) > 300, filename
        texts[filename] = text.lower()

    assert "## curva de rendimientos y curva spot" in texts["01_fundamentos_curva_tasas.md"]
    assert "## excel_bootstrap_182d_v1" in texts["02_bootstrapping_y_metodologia.md"]
    assert "## roles separados" in texts["03_yieldcurve_ai_arquitectura.md"]
    assert "## telegram v6" in texts["04_guia_de_uso.md"]
    assert "## seguridad y autoridad" in texts["05_faq_seguridad_y_estados.md"]
    pack = "\n".join(texts.values())
    for forbidden in ("sk-", "bearer ", "api_key", "x-yieldcurve-key", "x-yieldcurve-voice-key"):
        assert forbidden not in pack
    assert "yc-" not in pack  # No folios ni datos concretos de casos vigentes.
    assert "nova no aprueba ni rechaza" in read("knowledge/yieldcurve_ai_knowledge.md").lower()
    assert "live no está disponible desde voz pública" in read("knowledge/yieldcurve_ai_knowledge.md").lower()


def test_nova_documentation_separates_rag_from_dynamic_tools_and_names_pack():
    documentation = (ROOT / "docs" / "nova-elevenlabs.md").read_text(encoding="utf-8").lower()
    for filename in KNOWLEDGE_PACK:
        assert filename in documentation
    assert "datos dinámicos" in documentation and "consultar_caso" in documentation


def test_nova_test_cases_cover_n01_to_n13_without_dynamic_case_data():
    cases = json.loads(read("tests/nova_test_cases.json"))
    assert [case["id"] for case in cases] == [f"N{i:02d}" for i in range(1, 14)]
    text = json.dumps(cases)
    assert "API key" in text and "LIVE" in text and "Telegram" in text
