# YieldCurve AI — n8n V6 API: instalación controlada

## Propósito y límites

V6 es la capa de interacción de Telegram para YieldCurve AI. Conserva acceso, deduplicación, estado de casos, expiración y decisiones humanas en n8n; el cálculo técnico continúa en FastAPI. No contiene secretos, no llama directamente a OpenAI o Banxico y no sustituye la aprobación humana.

El flujo importa desactivado. No active el workflow hasta completar cada configuración y la prueba DEMO.

## Importación

1. En n8n, cree un workflow nuevo e importe `YieldCurve_AI_Telegram_Orchestration_V6_API.json`. El archivo público usa marcadores `__YC_*__` en lugar de IDs de una instancia concreta; no intente conservarlos como valores operativos.
2. Seleccione una credencial de Telegram en el único nodo **Telegram Trigger** y en los dos nodos de envío de Telegram. Al guardar o activar, n8n asignará sus propios IDs de webhook.
3. Cree una credencial **HTTP Header Auth** para el nodo **Invoke YieldCurve API once**:
   - Header name: `X-YieldCurve-Key`.
   - Header value: el mismo valor secreto configurado como `YIELDCURVE_API_KEY` en Render.
   - Nunca incluya este valor en el export, en campos Code ni en una tabla.
4. Verifique que la URL del nodo HTTP sea `https://yieldcurve-ai.onrender.com/v1/orion/run`, el método sea `POST`, el timeout sea 90 segundos y los intentos máximos sean uno.
5. Para resultados elegibles, **Generate curve PNG** llama `POST /v1/artifacts/curve.png` con el `case_artifact` sanitizado, Header Auth y respuesta binaria `data`; **Telegram | Send curve photo** la envía antes del resumen con botones. El PNG se genera en memoria y no se persiste. Si falla la visualización, la decisión técnica no cambia y el resumen aprobable se conserva: una falla visual no equivale a una falla de curva.

## Tablas de datos

Los identificadores `__YC_*_TABLE_ID__` del archivo son marcadores de importación. Seleccione la tabla real en cada nodo Data Table; n8n asignará su identificador local. Cree estas tablas antes de activar el flujo.

### `YC_CASES`

`caso_id` String; `version_caso` Number; `version_curva` String; `fecha_corte` String; `execution_mode` String; `canal_origen` String; `telegram_user_id` String; `telegram_chat_id` String; `estado` String; `dictamen_tecnico` String; `requiere_aprobacion_humana` Boolean; `source_mode` String; `instrument_count` Number; `max_absolute_repricing_error` Number; `metodologia` String; `auditoria_tecnicamente_valida` Boolean; `approval_status` String; `approval_expires_at` ISO String/DateTime; `created_at` ISO String/DateTime; `updated_at` ISO String/DateTime; `invocation_id` String; `created_event_id` String; `decision_event_id` String; `decision_at` ISO String/DateTime; `api_result_json` String/Long text.

### `YC_EVENTS`

| Campo | Uso |
|---|---|
`event_id` String; `processing_status` String; `received_at` ISO String/DateTime; `processed_at` ISO String/DateTime si se usa.

### `YC_ACCESS`

| Campo | Uso |
|---|---|
`telegram_user_id` String; `telegram_chat_id` String; `role` String; `status` String; `expires_at` ISO String/DateTime; `created_at` ISO String/DateTime; `consumed_code_id` String/Number.

### `YC_ACCESS_CODES` (opcional)

| Campo | Uso |
|---|---|
`code` String; `role` String; `status` String; `expires_at` ISO String/DateTime; `used_at` ISO String/DateTime; `used_by_user_id` String.

Si Data Tables no ofrece DateTime, use String con ISO-8601 UTC.

Registre manualmente el OWNER en `YC_ACCESS` con su usuario y chat privado. Los evaluadores usan `/acceso CODIGO`; V6 valida estado, expiración y rol, consume el código antes de crear el acceso y bloquea reutilizaciones. Un código no puede otorgar más de un acceso.

## Comandos y comportamiento

| Comando | Acción |
|---|---|
| `/start`, `/ayuda` | Muestra ayuda; puede usarse antes de acceso. |
| `/demo` | Crea un caso DEMO con fecha `2026-11-11`. |
| `/nuevo YYYY-MM-DD` | Crea un caso LIVE con fecha ISO estricta. |
| `/estado FOLIO` | Sólo consulta `YC_CASES`; no invoca FastAPI. |
| `/acceso CODIGO` | Consume un código temporal válido, una sola vez. |

Todo comando operativo exige chat privado y un registro `ACTIVE` con rol `OWNER` o `EVALUATOR`. El workflow no toma permisos, presupuesto ni autorización de ejecución desde Telegram.

## Deduplicación, casos y aprobaciones

- El flujo deriva `event_id` del `update_id` de Telegram y persiste el evento antes de la acción. Configure `event_id` como único para que reintentos y callbacks duplicados no vuelvan a invocar FastAPI.
- Cada nuevo caso obtiene `caso_id` con patrón `YC-[A-Z0-9]{8,32}`, `version_caso=1` y `version_curva` compatible. Telegram user IDs no forman parte del folio.
- El resultado provisional muestra Elara, Siena, Nash, Atenea, fuente, método, instrumentos, error de repricing y auditoría. Los botones sólo existen cuando FastAPI devuelve `PENDIENTE_APROBACION` y auditoría técnica válida.
- Los callbacks son `APR|caso_id|version` y `REJ|caso_id|version`. Antes de persistirlos, valide deduplicación, chat privado, acceso activo, rol permitido, identidad de caso, versión y TTL de 15 minutos.
- La aprobación o rechazo actualiza únicamente `YC_CASES`; no llama al backend financiero. La expiración es perezosa: se aplica cuando se consulta estado o se procesa una decisión.

## Ajustes necesarios después de importar

1. En cada nodo Data Table, seleccione la tabla indicada. Según la versión de n8n, confirme las operaciones **Get**, **Insert** y **Update**, y los filtros por `event_id` o `caso_id`.
2. Verifique la rama ya incluida de error HTTP: persiste `DETENIDO` y `NOT_AVAILABLE`, no reintenta ni hace fallback y envía exactamente: `El servicio de cálculo no está disponible en este momento. El caso quedó detenido y no fue aprobado.`
3. V6 contiene las ramas completas de `/estado` y `/acceso`; `/estado` consulta sólo `YC_CASES` y no usa el backend.
4. En los nodos Telegram, active únicamente la credencial de bot seleccionada; no copie tokens a expresiones o Code nodes.
5. La configuración versionada fija `saveDataSuccessExecution` y `saveDataErrorExecution` en `none`. No dependa de los valores predeterminados de la instancia: el workflow productivo no debe guardar datos de ejecución exitosos ni fallidos que puedan incluir comandos, callbacks o códigos temporales. Data Tables conserva la trazabilidad mínima sin el comando crudo ni códigos temporales.

## Prueba DEMO antes de activar

1. Active el flujo de manera temporal y envíe `/demo` desde el chat privado del OWNER.
2. Confirme que se crea una fila en `YC_EVENTS` y otra en `YC_CASES`.
3. Confirme que el resultado llega con estado `PENDIENTE_APROBACION`, fuente de fixture y botones `Aprobar` / `Rechazar`.
4. Pulse un botón una vez: debe cambiar sólo el estado persistido. Pulse de nuevo: debe reportarse como evento duplicado o decisión no vigente.
5. Pruebe `/estado <folio>` y confirme que no aparece una nueva petición HTTP a FastAPI.
6. Pruebe un mensaje desde un grupo: debe responder que sólo opera en chat privado y no crear caso.

## Seguridad operativa

No incluya en exports, Data Tables, notas o mensajes de Telegram: tokens del bot, `YIELDCURVE_API_KEY`, claves de OpenAI o Banxico, encabezados HTTP, prompts internos o respuestas no sanitizadas. Las credenciales n8n se administran separadamente del JSON exportado.

Las tablas, webhooks y credenciales se configuran en la instancia de n8n; por eso el archivo se puede versionar sin identificadores privados ni credenciales. Nunca exporte filas de Data Tables, ejecuciones, códigos de acceso, decisiones ni trazas de Telegram junto con esta plantilla.
