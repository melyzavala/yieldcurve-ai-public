# Despliegue manual de YieldCurve AI en Render

Esta guía despliega únicamente la capa FastAPI como un Web Service HTTPS. No crea recursos desde el repositorio, no configura n8n y no implementa aprobación humana. El servicio sigue operando en modo `SIMULADO`.

## Configuración versionada

- Python: `3.11`, fijado mediante `.python-version`.
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn backend.api:app --host 0.0.0.0 --port $PORT`
- Health Check Path: `/health`

El comando local es distinto y sólo debe usarse en el equipo de desarrollo:

~~~powershell
uvicorn backend.api:app --host 127.0.0.1 --port 8000
~~~

No se incluye `render.yaml` en esta etapa. La creación manual desde el Dashboard hace visible cada decisión de infraestructura y evita activar despliegues automáticos antes de la revisión humana.

## Pasos en Render

1. Crea una cuenta o inicia sesión en [Render](https://dashboard.render.com/).
2. Conecta GitHub y autoriza únicamente el acceso necesario al repositorio `melyzavala/yieldcurve-ai`.
3. Selecciona **New** → **Web Service** y el repositorio indicado.
4. Elige el runtime **Python** y la rama `main`.
5. Confirma Python 3.11; Render leerá `.python-version`.
6. Usa el Build Command y Start Command indicados arriba.
7. Selecciona el plan **Free** para la demostración académica.
8. Configura `/health` como Health Check Path.
9. En **Environment**, crea estas variables como secretas y sólo con valores introducidos en Render:
   - `YIELDCURVE_API_KEY`
   - `OPENAI_API_KEY`
   - `BANXICO_API_TOKEN`
10. Despliega manualmente y espera a que Render asigne la URL HTTPS pública. No se debe anticipar ni registrar esa URL en el repositorio.
11. Comprueba `<URL_ASIGNADA>/health`. La respuesta esperada es:

~~~json
{"status":"ok","service":"yieldcurve-ai","version":"0.1.0"}
~~~

12. Sólo después del health check, ejecuta una solicitud DEMO autenticada con `POST /v1/orion/run`. No realices una prueba LIVE hasta revisarla explícitamente.

## Generar la clave de servicio

Genera `YIELDCURVE_API_KEY` localmente; no la pegues en el repositorio, documentación, workflows ni chat:

~~~powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
~~~

Guarda el mismo valor posteriormente como secreto en Render y como credencial/secreto de n8n. No debe aparecer dentro de un workflow exportado de n8n.

## Prueba DEMO autenticada

Tras definir localmente el valor de la clave y la URL que Render asignó, una prueba puede usar datos ficticios y el snapshot autorizado. Sustituye las variables locales, no el contenido del repositorio:

~~~powershell
$headers = @{ "X-YieldCurve-Key" = $env:YIELDCURVE_API_KEY }
$body = @{
  caso_id = "YC-API20261111"
  version_caso = 1
  version_curva = "CURVA-API-20261111"
  fecha_corte = "2026-11-11"
  canal_origen = "api"
  solicitud = "Construye una curva CETES y M-Bonos para 2026-11-11 para un portafolio ficticio."
  execution_mode = "DEMO"
  invocation_id = "render-demo-20261111"
} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "$env:YIELDCURVE_RENDER_URL/v1/orion/run" -Headers $headers -ContentType "application/json" -Body $body
~~~

La respuesta debe conservar `requiere_aprobacion_humana: true`; la API no aprueba curvas ni operaciones.

## Seguridad y límites

- `/health` es público, no invoca agentes ni usa secretos.
- `POST /v1/orion/run` exige `X-YieldCurve-Key` y no expone claves, headers, prompts, variables de entorno ni identificadores de respuesta de OpenAI.
- FastAPI se ejecuta con `debug=False`; los errores inesperados retornan una respuesta genérica sin traceback.
- Las claves sólo se almacenan en Render y, posteriormente, en credenciales administradas de n8n.
- El servicio es stateless: no hay base de datos, persistencia ni deduplicación durable todavía.

En el plan Free, Render puede detener un Web Service después de 15 minutos sin tráfico; el siguiente acceso puede requerir aproximadamente un minuto para reactivarlo. El filesystem es efímero, la capacidad es limitada y el plan es apropiado para una demostración académica, no para un servicio productivo crítico. Consulta la [documentación de instancias Free de Render](https://render.com/docs/free) antes de la defensa.
