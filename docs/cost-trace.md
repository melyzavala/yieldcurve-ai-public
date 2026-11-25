# Trazabilidad económica por caso

El registro auditable está en [`costs/costos.csv`](../costs/costos.csv); las tarifas versionadas en [`costs/tarifas.csv`](../costs/tarifas.csv), el resumen en [`costs/resumen_costos.csv`](../costs/resumen_costos.csv), las proyecciones en [`costs/proyecciones.csv`](../costs/proyecciones.csv) y la conciliación en [`cost-reconciliation.md`](cost-reconciliation.md).

`cost_trace` registra uso medido, costo variable directo y el estado del pricing. Elara toma tokens del campo `usage` que devuelve Responses API; nunca se cuentan caracteres. Siena registra solicitudes a Banxico cuando se dispone del dato. Nash y Atenea son cómputo determinista, sin tokens ni llamadas LLM.

Los precios se versionan por proveedor, modelo, fecha efectiva y fuente. La configuración actual de `gpt-6-luna` declara la fuente oficial de OpenAI y la fecha de consulta; si faltan usage o una tarifa aplicable, el costo se devuelve como `null`, nunca como aproximación. Render, n8n y hosting son costos fijos de plataforma: no se reparten entre casos en este hito.

`case_artifact` es la proyección sanitizada para consumidores futuros: `case_id → agentes → curva → auditoría → usage → costo → decisión humana`. Copia los pillars calculados por Nash; no recalcula la curva. Excluye identificadores de Telegram, secretos, prompts, headers, credenciales y trazas internas.

## Esquema de referencia del registro

| Columna | Tipo | Obligatoria |
|---|---|---|
| `cost_id` | String/UUID | Sí |
| `caso_id` | String | Sí |
| `version_caso` | Number | Sí |
| `invocation_id` | String | Sí |
| `component` | String | Sí |
| `component_type` | String | Sí |
| `provider` | String | Sí |
| `model` | String | No |
| `api_calls` | Number | Sí |
| `request_count` | Number | No |
| `input_tokens` | Number | No |
| `output_tokens` | Number | No |
| `total_tokens` | Number | No |
| `estimated_cost_usd` | Number | No |
| `pricing_status` | String | Sí |
| `pricing_version` | String | No |
| `pricing_effective_date` | Date/String ISO | No |
| `recorded_at` | Date/String ISO | Sí |

Las plataformas (Render, n8n, GitHub y ElevenLabs) se registran fuera del costo variable por caso y no se prorratean sin evidencia. No hay una conversación Nova con duración/cargo vinculable versionada en el repositorio: `VOICE COST EVIDENCE PENDING`.
