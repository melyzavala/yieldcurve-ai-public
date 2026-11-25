# Conciliación de costos

Fecha de corte de evidencia: 2026-11-25. El registro normalizado está en `costs/costos.csv`, las tarifas en `costs/tarifas.csv`, los resúmenes por caso en `costs/resumen_costos.csv` y las sensibilidades en `costs/proyecciones.csv`.

## Alcance verificable

| Caso | Evidencia | Estado | Costo variable conocido |
|---|---|---|---:|
| `YC-TG177652682` | artefacto público | LIVE publicado | USD 0.00031260 estimado |
| `YC-PIPE20261111` | fixture DEMO del pipeline | pendiente de aprobación | no observado |
| `YC-ARTIFACT01` | fixture DEMO de artefactos | pendiente de aprobación | no observado |
| `YC-SECURITY20260414` | prueba de seguridad | bloqueado | no aplicable |

Los dos DEMO son reproducibles y recorren Elara → Siena → Nash → Atenea → Orion sin red. No se convierten tokens ni consumos no observados en cero.

## Fórmula y prevención de doble conteo

Elara usa `input_no_cache × tarifa_entrada + input_cache × tarifa_cache + cache_write × tarifa_cache_write + output × tarifa_salida`. En `YC-TG177652682` el artefacto público mide 2,201 tokens de entrada y 185 de salida de `gpt-6-luna`; `tarifas.csv` verifica USD 0.10/M y USD 0.50/M.

`(2201 × 0.10 + 185 × 0.50) / 1,000,000 = USD 0.00031260`.

El cache no se publicó: permanece vacío y el resultado es `ESTIMATED`, no un cargo efectivo. Skills y loops reutilizan estas llamadas/control; no son filas cobrables adicionales. El costo conocido del caso es la suma de componentes con precio disponible. El total variable completo sigue parcial/nulo porque Siena/Banxico no tiene tarifa documentada.

| Componente | Evidencia | Estado |
|---|---|---|
| Elara / OpenAI | 1 llamada, 2,201 entrada, 185 salida | USD 0.00031260 estimado |
| Siena / Banxico | 26 solicitudes | `NOT_PRICED` |
| Orion, Nash, Atenea y guardrails | ejecución determinista | `NOT_APPLICABLE` |

Render, n8n, GitHub Actions/Pages, el plan ElevenLabs y desarrollo se separan como costos fijos/no medidos, sin prorratearlos por caso.

## Voz, proyecciones y optimización

**VOICE COST EVIDENCE PENDING.** El repositorio sólo contiene tarifas/documentación de Nova. Falta una exportación de ElevenLabs Detailed costs/conversation con `case_id`, duración, modelo/plan y cargo. Esa única captura manual se añade al registro sin inferir duración.

Las proyecciones cubren 100, 1,000 y 10,000 casos; muestran mezcla base de 10% LIVE y sensibilidad de 100% LIVE, exclusivamente con el perfil Elara medido. No representan presupuesto total porque voz, plataforma y componentes no tarifados permanecen fuera.

La optimización comprobable es máximo una llamada LLM por LIVE. No existe una serie histórica “antes”: el antes es contrafactual `ESTIMATED` de dos llamadas idénticas (USD 0.00062520), frente al límite probado de una (USD 0.00031260). Ahorro contrafactual: USD 0.00031260 por LIVE, sin reducir guardrails.
