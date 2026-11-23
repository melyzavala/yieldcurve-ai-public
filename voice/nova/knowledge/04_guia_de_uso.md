# Guía de uso de Nova, Telegram y dashboard

## Nova

Tras el saludo, Nova requiere consentimiento explícito antes de usar tools. Puede responder preguntas educativas sobre la curva y la metodología. Para crear una demostración usa `crear_caso_demo`; sólo admite el modo DEMO/SIMULADO y la fecha aceptada por su contrato. Para consultar información dinámica, pide un folio válido y usa `consultar_caso`.

Nova no debe responder desde memoria un estado, fecha, dictamen, resultado, instrumento, repricing o aprobación de un caso. Si una tool falla, debe comunicar que no pudo recuperar el dato y orientar a consultar por Telegram. La voz pública no admite LIVE.

## Telegram V6

Telegram es el canal privado de acceso y aprobación humana. Los comandos documentados en V6 son:

- `/start` o `/ayuda`: muestra ayuda; pueden usarse antes del acceso.
- `/demo`: crea un caso DEMO con la fecha configurada por el flujo.
- `/nuevo YYYY-MM-DD`: solicita un caso LIVE con fecha ISO estricta en el flujo de Telegram; su ejecución depende de controles y no queda habilitada desde Nova.
- `/estado FOLIO`: consulta la tabla de casos sin invocar el backend financiero.
- `/acceso CODIGO`: consume una vez un código temporal válido.

Los comandos operativos exigen chat privado, acceso activo y el rol permitido. Las decisiones humanas se procesan mediante Telegram; Nova no puede presionarlas, producirlas ni modificarlas.

## Dashboard y GitHub Pages

La documentación describe una proyección pública sanitizada, generación de casos DEMO y un workflow de Pages. El dashboard debe presentar información pública permitida, no el expediente privado. GitHub Pages **aún no está habilitado/publicado**: su habilitación requiere configuración manual compatible y no se cambia la visibilidad privada del repositorio.

Cuando esté publicado, la lectura prevista es:

- **Curva y pilares:** tasas spot por plazo; los pilares son los nodos calculados.
- **instrument_count:** número de instrumentos/nodos reportados por la curva.
- **max_absolute_repricing_error:** mayor diferencia absoluta entre precio observado y precio recalculado bajo la validación aplicable.
- **Dictamen técnico:** resultado de controles técnicos; no es aprobación humana.
- **Auditoría:** evidencia de la revisión independiente de Atenea.
- **Estado:** etapa operativa del expediente; para su valor actual debe usarse una fuente dinámica autorizada.

## Problemas frecuentes

- **Servicio caído:** no inventes resultados; consulta después con el folio o usa Telegram.
- **Micrófono negado:** habilita el permiso del navegador o continúa por el canal de texto disponible; Nova no puede cambiar permisos del dispositivo.
- **Información insuficiente:** proporciona un folio válido para consulta, o formula una pregunta conceptual. Nova no completa datos ni inventa un caso.
