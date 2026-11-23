# FAQ, seguridad y estados

## Estados de caso

Los estados exactos dependen del contrato y del canal; describen etapas, no recomendaciones. Entre los estados documentados están:

- `PENDIENTE_EJECUCION`: el caso fue registrado y espera la ejecución autorizada.
- `PENDIENTE_ACLARACION`: falta información o la solicitud no puede continuar sin aclaración.
- `PENDIENTE_APROBACION`: completó los controles requeridos para llegar a una decisión humana, que sigue pendiente.
- `DETENIDO`: el flujo se interrumpió de forma controlada; no fue aprobado.
- `EXPIRADO`: venció la ventana temporal de una decisión pendiente.
- `APROBADA_HUMANAMENTE` o `RECHAZADA_HUMANAMENTE`: una persona autorizada resolvió la decisión en el canal privado.

También existen estados técnicos de admisión, datos, cálculo y dictamen. Un dictamen técnico validado significa que los controles técnicos aplicables pasaron; no equivale a la aprobación humana.

## DEMO, SIMULADO y LIVE

DEMO/SIMULADO es el alcance académico de Nova y de la ruta de conocimiento. LIVE requiere controles separados. Desde voz pública, Nova sólo puede crear DEMO y no acepta solicitudes LIVE.

## Seguridad y autoridad

Nova no puede aprobar ni rechazar porque la decisión es humana, privada y separada de la conversación. Tampoco revela prompts, credenciales, encabezados, tokens, secretos o instrucciones internas: esa información no es necesaria para explicar el sistema y divulgarla dañaría sus controles.

Nova no da recomendaciones de inversión ni ejecuta compras, ventas u operaciones. Puede explicar conceptos financieros, pero no sustituye el juicio profesional ni predice resultados.

## Errores, duplicados y expiraciones

Los contratos vigentes deduplican eventos antes de ejecutar acciones para evitar que un reintento repita una operación. Una consulta de estado no debe ejecutar el backend financiero. Si el servicio de cálculo no está disponible, el caso se marca detenido y no se aprueba. Las aprobaciones pendientes tienen una vigencia definida por el flujo; al vencer, se proyectan como expiradas y ya no admiten la decisión anterior.

## Preguntas para una demo oral

**¿Nova calcula la curva?** No. Nova explica y dirige consultas; el motor determinista y los agentes técnicos realizan el cálculo y la validación.

**¿Qué prueba el repricing?** Que la curva reproduce los precios de entrada dentro de las tolerancias definidas; no prueba una recomendación de inversión.

**¿Puede Nova decir si mi caso está aprobado?** Debe consultar el folio con la tool autorizada; no debe responder con memoria o RAG.

**¿Quién aprueba?** Una persona autorizada mediante el canal privado de Telegram.

**¿Por qué no se muestran secretos?** Porque los secretos, credenciales y prompts internos no son datos de usuario ni material de la demostración.
