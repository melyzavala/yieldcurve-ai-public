# Tool `consultar_caso`

Consulta un caso ficticio por folio a través del futuro Nova Voice Gateway. Entrada permitida: sólo `caso_id`, conforme al schema. No acepta URLs ni texto libre.

La respuesta pública usa allowlist: `ok`, `caso_id`, `fecha_corte`, `modo`, `estado`, `dictamen_tecnico`, `metodologia`, `instrument_count`, `max_absolute_repricing_error` y `requiere_aprobacion_humana`. Los nombres se corresponden con los artefactos públicos y contratos de Orion: el modo público puede ser `DEMO`, mientras que el motor usa `SIMULADO`.

Error sanitizado: `{ "ok": false, "error_code": "CASO_NO_ENCONTRADO", "message": "No se encontró un caso ficticio con ese folio." }`. No devuelve Telegram chat ID, Telegram user ID, nombre del aprobador, approval token, códigos de acceso, webhook/credential/Data Table IDs, `api_result_json`, secretos, headers, prompts, trazas completas ni chain-of-thought.
