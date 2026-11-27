# YieldCurve AI

> **Réplica pública académica, reproducible y sanitizada.** Este repositorio no contiene credenciales, datos privados ni historiales operativos.

YieldCurve AI es una plataforma multiagente que construye y valida curvas spot de deuda gubernamental mexicana para apoyar una decisión de uso técnico: determinar si una curva cuenta con evidencia suficiente para incorporarse a un ejercicio académico de valuación y análisis de riesgo de un portafolio ficticio. Su alcance es académico; **no constituye recomendación de inversión, asesoría financiera ni ejecución de operaciones**.

## Arquitectura

```text
Telegram → n8n → FastAPI / Orion → Elara → Siena → Nash → Atenea
         → aprobación humana → publicación sanitizada
Nova / ElevenLabs → n8n Nova Gateway → consulta de casos / creación DEMO
```

Nova sólo consulta respuestas sanitizadas y puede crear un caso **DEMO** bajo reglas controladas. Nova **no puede aprobar ni rechazar** casos; esas decisiones requieren el canal privado autorizado de Telegram.

| Componente | Función |
|---|---|
| Orion | Orquesta etapas, guardrails y expediente del caso. |
| Elara | Valida solicitud, alcance y precondiciones. |
| Siena | Obtiene y valida datos de mercado autorizados. |
| Nash | Construye cuantitativamente la curva spot. |
| Atenea | Audita resultados, repricing y dictamen técnico. |
| Nova | Interfaz de voz con consultas sanitizadas y DEMO controlado. |

## Metodología financiera implementada

La implementación final utiliza CETES y M-Bonos. En modo LIVE, Siena consulta Banxico SIE; en DEMO consume el fixture versionado. La curva se construye con `EXCEL_BOOTSTRAP_182D_V1`, bootstrap secuencial y convención 182/360. Para plazos entre pilares aplica `LINEAR_SPOT_RATE`; el control técnico realiza repricing con tolerancia máxima `1e-8`.

El frontend público y el Excel de salida consumen los `curve_points` producidos por el backend: no recalculan la curva. Consulte [docs/case-excel.md](docs/case-excel.md), [docs/curve-visualization.md](docs/curve-visualization.md) y [docs/dashboard-pages.md](docs/dashboard-pages.md).

## Estructura del repositorio

| Ruta | Contenido |
|---|---|
| `agents/` | Contratos, responsabilidades, ejemplos y guardrails de los agentes. |
| `backend/` | API FastAPI, cálculo, auditoría, guardrails y adaptadores. |
| `data/` | Fixture DEMO y proyecciones públicas sanitizadas. |
| `docs/` | Guías de entorno, API, publicación, Nova, anexos y trazabilidad. |
| `evidence/` / `evidencias/` | Artefactos de skills/loops e inventario P01–P14. |
| `loops/` / `skills/` | Definiciones de loops y skills reutilizables. |
| `n8n/` | Exports finales sanitizados y guías de importación V6/V7. |
| `tests/` | Pruebas automatizadas y matriz P01–P14. |
| `costs/` | Registro, resumen, tarifas y proyecciones de costos. |
| `voice/nova/` | Configuración documental, knowledge base, tools y pruebas de Nova. |
| `web/` | Dashboard estático, contrato público y generadores de Pages. |
| `.github/workflows/` | Automatizaciones de validación y despliegue controlado. |

## Requisitos y configuración segura

- Python objetivo: **3.11**; dependencias fijadas en [requirements.txt](requirements.txt).
- Backend: FastAPI/Uvicorn local o entorno equivalente autorizado.
- Orquestación: n8n con workflows importados y desactivados hasta validar configuración.
- Dashboard: artefacto estático desde `web/`; no calcula ni publica casos por sí mismo.

Mantenga `.env.example` como plantilla y configure valores sólo fuera del repositorio. Variables por nombre: `BANXICO_API_TOKEN`, `OPENAI_API_KEY`, `YIELDCURVE_API_KEY`, `TELEGRAM_BOT_TOKEN`, `ELEVENLABS_API_KEY`, `N8N_BASE_URL` y `N8N_API_KEY`. Nunca copie valores reales a archivos, exports, capturas ni mensajes.

En n8n se requieren credenciales por propósito: bot de Telegram; autenticación HTTP `X-YieldCurve-Key` para FastAPI/Render; autenticación de voz `X-YieldCurve-Voice-Key`; y tablas `YC_CASES`, `YC_EVENTS`, `YC_ACCESS` y, opcionalmente, `YC_ACCESS_CODES`. Consulte las guías [V6](n8n/YieldCurve_AI_Telegram_Orchestration_V6_API_SETUP.md) y [V7](n8n/YieldCurve_AI_Nova_Voice_Gateway_V7_SETUP.md).

## Instalación y reproducción controlada

Estas instrucciones explican el flujo sin secretos ni ejecución de un caso nuevo.

1. Cree un entorno virtual de Python 3.11 e instale `pip install -r requirements.txt`.
2. Copie `.env.example` a `.env` sólo localmente y complete variables autorizadas; no versione `.env`.
3. Importe los workflows V6 y V7 desde `n8n/`; seleccione tablas y credenciales en n8n. Manténgalos desactivados hasta validar configuración.
4. Inicie FastAPI mediante el mecanismo de su entorno autorizado; consulte [docs/api.md](docs/api.md) y [docs/entorno.md](docs/entorno.md).
5. Para revisión sin tráfico, use `data/demo_banxico_2026-11-11.json` y los artefactos sanitizados versionados. Cuando Python 3.11 esté disponible, ejecute `python -m pytest -q`.
6. En un entorno autorizado, la guía V6 define el caso DEMO permitido, `/estado FOLIO` y las verificaciones en `YC_CASES`/`YC_EVENTS`. No ejecute LIVE con estas instrucciones académicas.
7. Una ruta DEMO válida entrega un caso técnicamente válido, pendiente de aprobación humana; sólo aprobación autorizada permite proyección pública sanitizada.
8. Detenga Uvicorn y desactive workflows temporales al terminar. Elimine `.env` local si ya no se requiere.

### Caso reproducible sanitizado

[data/public/cases/YC-NV01R0XFRU01.json](data/public/cases/YC-NV01R0XFRU01.json) documenta un caso DEMO publicado y sanitizado.

- **Entrada controlada:** fixture Banxico DEMO, fecha `2026-11-11`.
- **Ruta esperada:** fixture → Siena → Nash → Atenea → aprobación humana previa → proyección pública.
- **Resultado esperado:** `EXCEL_BOOTSTRAP_182D_V1`, 10 instrumentos, repricing menor que `1e-8` y publicación sólo tras autorización previa.
- **Evidencia:** [docs/dashboard-pages.md](docs/dashboard-pages.md), [evidencias/P03](evidencias/P03) y [web/public_case.schema.json](web/public_case.schema.json).

No use el JSON público para reactivar una operación ni inferir datos privados.

## Skills, loops y fail-closed

- `build_spot_curve`: aplicado por Nash; [definición](skills/build_spot_curve/SKILL.md).
- `validate_spot_curve`: aplicado por Atenea; [definición](skills/validate_spot_curve/SKILL.md).
- `curve_quality_loop`: máximo tres iteraciones y 30 segundos; falla cerrado si no alcanza el criterio técnico.
- `security_cost_loop`: verifica autorización y presupuesto antes de la ruta técnica; acciones no autorizadas quedan bloqueadas.

La evidencia V1 fallida → V2 validada está en [quality_loop_v1_v2.json](evidence/skills_loops/quality_loop_v1_v2.json). La evidencia de seguridad/costo está en [security_cost_loop_v1_v2.json](evidence/skills_loops/security_cost_loop_v1_v2.json). Véase también [docs/skills-loops-evidence.md](docs/skills-loops-evidence.md).

## Guardrails

- Autorización, chat privado, roles activos y acceso temporal de un solo uso.
- Validación estricta de formato, fecha, alcance y entrada incompleta.
- Bloqueo de prompt injection, fuentes no autorizadas y exposición de secretos.
- Banxico SIE en LIVE y fixture explícito en DEMO.
- Aprobación, rechazo y vencimiento humanos; Nova no altera decisiones.
- Deduplicación de eventos y callbacks; un repetido no ejecuta una segunda operación.
- Errores externos controlados sin fallback inseguro.
- Sanitización antes de Pages: sin prompts, headers, tokens, IDs privados ni trazas.

## Pruebas y evidencia

**P01–P14: 14/14 APROBADAS · 0 FALLIDAS · 0 PENDIENTES.**

Consulte [tests/pruebas.csv](tests/pruebas.csv), [tests/resumen_pruebas.md](tests/resumen_pruebas.md), [evidencias/INDICE.md](evidencias/INDICE.md) y [docs/anexos/anexo_pruebas.md](docs/anexos/anexo_pruebas.md).

## Costos y tokenización

Los registros finales están en [costs/costos.csv](costs/costos.csv), [costs/resumen_por_caso.csv](costs/resumen_por_caso.csv), [costs/proyecciones.csv](costs/proyecciones.csv), [costs/tarifas.md](costs/tarifas.md) y [costs/resumen_costos_informe.md](costs/resumen_costos_informe.md).

Caso conciliado: `YC-TG177652706`: 2,201 tokens de entrada, 211 de salida, 2,412 totales, una llamada LLM y costo conocido aproximado de USD 0.000128. Los valores sin medición o tarifa verificable permanecen como desconocidos: **no se representan como cero**.

## Enlaces y acceso

- Repositorio: https://github.com/melyzavala/yieldcurve-ai-public
- GitHub Pages: https://melyzavala.github.io/yieldcurve-ai-public/
- GitHub Actions: https://github.com/melyzavala/yieldcurve-ai-public/actions
- Nova/ElevenLabs: no se publica URL de agente; consulte [docs/nova-elevenlabs.md](docs/nova-elevenlabs.md).
- Telegram: no se expone token, enlace de bot ni identificadores. El acceso usa `YC_ACCESS` y `/acceso CODIGO` según la guía V6.

## Troubleshooting

| Situación | Comportamiento seguro / acción |
|---|---|
| Render o backend no disponible | Caso detenido, no aprobado; confirme URL, autenticación y rama de error HTTP V6. |
| Datos Banxico incompletos | Siena detiene la ruta; no complete datos con fuentes no autorizadas. |
| Usuario no autorizado | No se crea caso; valide `YC_ACCESS`, rol, expiración y chat privado. |
| Fecha inválida | Use ISO `YYYY-MM-DD`; el workflow rechaza entradas incompletas o fuera de regla. |
| Caso vencido | La decisión se rechaza como no vigente. |
| Publicación bloqueada por tests | Corrija el artefacto y vuelva a validar; no eluda GitHub Actions. |
| Micrófono denegado | Nova mantiene alternativa de texto; no fuerce permiso. |
