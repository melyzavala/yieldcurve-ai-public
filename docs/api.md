# API local de YieldCurve AI

La API es una capa HTTP stateless para `backend.yieldcurve_pipeline.run_yieldcurve_case`. Opera exclusivamente en modo `SIMULADO`, no aprueba curvas y no ejecuta recomendaciones u operaciones financieras.

## Desarrollo local

Configura `YIELDCURVE_API_KEY` sólo en el entorno local y arranca el servicio desde la raíz del repositorio:

~~~powershell
$env:YIELDCURVE_API_KEY = "valor-local-no-versionado"
uvicorn backend.api:app --host 127.0.0.1 --port 8000
~~~

No expongas este servidor a Internet en esta etapa.

## Endpoints

`GET /health` no requiere autenticación ni invoca agentes:

~~~json
{"status":"ok","service":"yieldcurve-ai","version":"0.1.0"}
~~~

`POST /v1/orion/run` requiere el encabezado `X-YieldCurve-Key`. La clave se compara de forma segura y procede exclusivamente de `YIELDCURVE_API_KEY`.

Ejemplo DEMO sanitizado:

~~~json
{
  "caso_id": "YC-API20261111",
  "version_caso": 1,
  "version_curva": "CURVA-API-20261111",
  "fecha_corte": "2026-11-11",
  "canal_origen": "api",
  "solicitud": "Construye una curva CETES y M-Bonos para 2026-11-11 para un portafolio ficticio.",
  "execution_mode": "DEMO",
  "invocation_id": "api-demo-20261111"
}
~~~

En DEMO se usa el snapshot `FIXTURE_BANXICO_2026-11-11` y no se crean clientes OpenAI o Banxico. En LIVE se reutilizan las dependencias autenticadas existentes; si faltan, se responde `503` sin fallback a DEMO.

Cuando Nash termina el cálculo, la respuesta añade un resultado provisional sanitizado para revisión antes de la aprobación humana. La siguiente es una estructura ilustrativa; los valores concretos proceden del resultado de Nash:

~~~json
{
  "resultado_curva": {
    "instrument_count": "<valor de Nash>",
    "max_absolute_repricing_error": "<valor de Nash>",
    "interpolation_method": "<metodología de Nash>",
    "metodologia": "<metodología de Nash>",
    "pillars": [{"instrument_id":"<id>","days":"<días>","spot_rate":"<tasa>"}]
  },
  "auditoria": {
    "tecnicamente_valida": true,
    "tolerancia": "<tolerancia de Atenea>",
    "requiere_aprobacion_humana": true
  }
}
~~~

La API sólo proyecta valores ya producidos por Nash y Atenea. No incluye evidencia de skills, hashes, payloads de entrada, prompts ni identificadores de respuesta. Si el flujo no llegó al cálculo o auditoría, ambas secciones son `null`.

La deduplicación persistente de `invocation_id` pertenece a una etapa posterior de n8n. La API preserva el valor recibido y no realiza reintentos automáticos.
