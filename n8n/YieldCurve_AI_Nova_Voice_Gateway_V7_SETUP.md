# YieldCurve AI — Nova Voice Gateway V7

## Objetivo y arquitectura

Este workflow es el gateway independiente y desactivado de Nova: `Nova → webhook autenticado n8n → YC_CASES / Orion → respuesta sanitizada`. Para casos técnicamente válidos pendientes, consulta un OWNER activo en `YC_ACCESS` y prepara una notificación Telegram compatible con el callback de V6. No configura ElevenLabs ni modifica el workflow Telegram V6.

## Importación y marcadores

Importe `YieldCurve_AI_Nova_Voice_Gateway_V7.json`, sustituya sólo los marcadores `__YC_*__` del proyecto, Data Tables, webhooks y credenciales, y manténgalo inactivo hasta las pruebas. No publique IDs de instancia, tokens, headers, transcripciones, prompts ni valores de credenciales.

## Endpoints y autenticación

- POST `yieldcurve-ai/nova/consultar-caso`
- POST `yieldcurve-ai/nova/crear-caso-demo`

Ambos requieren la credencial server-side de header `X-YieldCurve-Voice-Key`, configurada en n8n como `__YC_NOVA_VOICE_AUTH__`; V7.3 enlazará ese secreto desde ElevenLabs mediante Secret/Auth Connection. La credencial de Render es `__YC_RENDER_AUTH__` y usa el header `X-YieldCurve-Key`. Las llamadas fallan cerradas antes de leer Data Tables cuando no pasa autenticación.

## Datos y deduplicación

`consultar_caso` lee exclusivamente `YC_CASES` por un folio válido y proyecta una allowlist pública. Si una aprobación interna caducó, proyecta `EXPIRADO` sin exponer su fecha. La consulta no muta la fila.

`crear_caso_demo` acepta sólo `fecha_corte`, `conversation_id` y `agent_turn` técnicos desde variables de sistema de ElevenLabs (`system__conversation_id`, `system__agent_turns`). Sólo existe fixture DEMO para `2026-11-11`; otras fechas devuelven error. El gateway construye un `event_id` y un folio pseudonimizado deterministas, reclama `YC_EVENTS`, crea la fila DEMO en `YC_CASES` y llama Orion una vez por evento. La solicitud es fija; no reenvía habla libre del usuario.

## Aprobación y respuestas

Nova no aprueba, rechaza ni actualiza decisiones. Si Orion devuelve un caso elegible, se busca `role=OWNER` y `status=ACTIVE` en `YC_ACCESS`; las credenciales Telegram y los IDs se resuelven sólo en runtime. Los botones usan `APR|{caso_id}|{version_caso}` y `REJ|{caso_id}|{version_caso}` para que V6 procese la decisión. Si no hay OWNER o falla la notificación, el caso sigue pendiente.

Los `Respond to Webhook` devuelven JSON sanitizado: 200 en éxito, 400 para entrada inválida, 404 para folio inexistente y 503 con `SERVICIO_NO_DISPONIBLE` para indisponibilidad. No devolver `api_result_json`, IDs privados, secretos, headers, conversación o trazas.

## Pruebas manuales y prohibiciones

Pruebe autenticación inválida, consulta existente/no existente, fecha DEMO permitida/no permitida, reintento idéntico, respuesta de Orion y OWNER activo/inexistente. Verifique que sólo se use DEMO, que no se guarden cuerpos completos en execution history y que no haya publicación. No configure ElevenLabs real ni incluya valores de secretos en este repositorio.

## Nota de validación operativa

Las búsquedas de `YC_CASES` y `YC_EVENTS` usan la propiedad exportada `alwaysOutputData: true`: cuando Data Tables no encuentra filas, n8n entrega un item vacío para que las ramas de caso inexistente y evento nuevo puedan responder o reclamar correctamente. La solicitud controlada a Orion incorpora explícitamente `fecha_corte`, como exige el preflight de Elara. La notificación Telegram usa `appendAttribution: false` y `Parse Mode = HTML` (`additionalFields.parse_mode: "HTML"`) de forma explícita: así, estados o metodologías con `_` se tratan como texto ordinario y no como entidades Markdown. El hallazgo surgió en la prueba real ElevenLabs → Nova Gateway → Telegram; esta corrección no cambia callbacks ni controles de seguridad. Estas condiciones no implican cambios de contratos ni de guardrails.
