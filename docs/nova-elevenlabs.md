# Nova para ElevenLabs — preparación V7.2 a V7.5

## Arquitectura prevista

`ElevenLabs Nova → webhook tool → n8n Nova Voice Gateway → YC_CASES / Orion`.

Esta entrega no configura ElevenLabs, webhook ni n8n. Nova es una interfaz de voz, no un agente financiero adicional. Los secretos se guardarán sólo del lado servidor; no habrá API key en HTML. La futura integración tendrá allowlist de dominios, sanitización de salidas y DEMO únicamente desde voz pública. La aprobación permanece fuera de Nova, en el canal privado autorizado.

## RAG y tools

V7.3A introduce un Knowledge Pack modular de cinco documentos que deben cargarse en ElevenLabs como knowledge base/RAG:

1. `voice/nova/knowledge/01_fundamentos_curva_tasas.md`
2. `voice/nova/knowledge/02_bootstrapping_y_metodologia.md`
3. `voice/nova/knowledge/03_yieldcurve_ai_arquitectura.md`
4. `voice/nova/knowledge/04_guia_de_uso.md`
5. `voice/nova/knowledge/05_faq_seguridad_y_estados.md`

`voice/nova/knowledge/yieldcurve_ai_knowledge.md` queda como índice breve del paquete. El RAG contiene conocimiento estable: propósito, arquitectura, conceptos, metodología `EXCEL_BOOTSTRAP_182D_V1`, estados y límites. No contiene casos vigentes, resultados operativos, IDs privados, aprobaciones, `api_result_json`, secretos ni conversaciones. Los datos dinámicos se obtendrán sólo mediante `consultar_caso` y la creación se limitará a `crear_caso_demo`.

Esta rama no configura ElevenLabs ni tools reales. Antes de cualquier embed público, configure **Security → Allowlist** con el hostname de GitHub Pages. En HTML sólo puede aparecer el `agent-id`; `X-YieldCurve-Voice-Key` permanece server-side y nunca se expone una API key. `crear_caso_demo` permite una creación DEMO por conversación y `consultar_caso` sólo devuelve casos DEMO. No insertar todavía el widget.

## Costos futuros

Sin conversaciones ejecutadas no hay tarifas ni costos que registrar. El gateway deberá registrar, cuando existan: `conversation_id`, `caso_id`, datetime, duración de voz, modelo, proveedor, tool calls, tokens reportados, unidad de facturación, tarifa, costo, moneda, estado, retry y origen medido/estimado.

## Implementación posterior

- V7.2: n8n Nova Voice Gateway.
- V7.3: configurar el agente en ElevenLabs.
- V7.4: pruebas reales de voz y tools.
- V7.5: embed en Pages.
