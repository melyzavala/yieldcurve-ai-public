# Expediente Excel por caso

`POST /v1/artifacts/excel` recibe exclusivamente un `case_artifact` sanitizado y, con `X-YieldCurve-Key`, devuelve un `.xlsx` en memoria. No consulta servicios, no persiste archivos y no recalcula curva, bootstrap, YTM, repricing ni auditoría.

El expediente incluye `Resumen`, `Curva_Spot`, `Agentes`, `Auditoria`, `Costos` y `Trazabilidad`. Copia los pillars disponibles y crea una gráfica de línea desde esas mismas filas. n8n o el dashboard podrán solicitarlo posteriormente.

Los campos académicos aún pendientes son llamada_id, timestamps por llamada, caché, duración de voz, unidad de cobro, tarifa individual, reintento y origen medido/estimado. No se inventan mientras no existan en `cost_trace`.
