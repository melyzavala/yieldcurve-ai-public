# Tool `crear_caso_demo`

Solicita al futuro Nova Voice Gateway crear exclusivamente un caso `DEMO`/`SIMULADO`. La entrada permitida es sólo `fecha_corte` ISO 8601. La disponibilidad de fecha se valida en el gateway contra la configuración DEMO vigente; Nova no puede elegir metodología, parámetros financieros, código, URLs ni modo LIVE.

La respuesta sanitizada prevista contiene `ok`, `caso_id`, `modo`, `estado` y `requiere_aprobacion_humana`. El estado puede ser pendiente mientras el flujo termina; Nova nunca afirma aprobación. No existe, ni se autoriza, una herramienta de aprobar, rechazar o modificar aprobación.
