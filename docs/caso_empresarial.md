# Caso empresarial — YieldCurve AI

## 1. Ficha empresarial

| Elemento | Definición |
| --- | --- |
| Empresa ficticia | Firma ficticia de análisis de renta fija y riesgo de mercado. |
| Sector | Servicios financieros, analítica cuantitativa y gestión de riesgos. |
| Usuario principal | Analista de renta fija que prepara curvas para un portafolio ficticio. |
| Supervisor | Responsable de riesgos de mercado que revisa la evidencia y aprueba o rechaza cada curva. |
| Caso de uso | Construcción, validación e interpretación descriptiva de curvas spot de deuda gubernamental mexicana. |

## 2. Problema empresarial y propuesta de valor

La construcción manual de curvas spot puede concentrar errores de transcripción, fechas de corte inconsistentes, convenciones de descuento no documentadas y evidencia insuficiente para revisar precios teóricos. Esto dificulta decidir si una curva es suficientemente confiable para valorar y analizar el riesgo de un portafolio ficticio.

YieldCurve AI organiza un flujo controlado que conserva la trazabilidad entre datos de entrada, convenciones, cálculos, pruebas de precio, dictamen técnico y aprobación humana. No recomienda inversiones ni ejecuta operaciones reales. Su propuesta de valor es reducir el tiempo de preparación y revisión de una curva, manteniendo controles verificables antes de autorizar su uso académico.

## 3. Objetivo, alcance y exclusiones

### Objetivo

Determinar, para cada fecha de corte solicitada, si una curva spot calculada cuenta con evidencia técnica suficiente para utilizarse en la valuación y el análisis de riesgos de un portafolio ficticio.

### Alcance

- CETES y M-Bonos como instrumentos de referencia.
- Precios sucios, plazos, cupones, flujos semestrales y convenciones documentadas.
- Interpolación de nodos y resolución numérica con Python/SciPy.
- Validación de integridad de entrada, consistencia de fecha y calidad de repricing.
- Interpretación descriptiva de la forma de la curva, separada de cualquier recomendación.
- Registro auditable del caso y aprobación humana.

### Exclusiones

- Compra, venta, recomendación o ejecución de operaciones financieras reales.
- Uso de datos privados no autorizados.
- Sustitución del juicio del responsable de riesgos.
- Publicación de credenciales, datos sensibles, archivos no revisados o resultados presentados como asesoría financiera.

## 4. Entradas, fuentes permitidas y resultados esperados

| Tipo | Contenido permitido | Fuente o condición |
| --- | --- | --- |
| Datos de mercado | Plazo, precio sucio, rendimiento, cupón y fecha de observación de CETES y M-Bonos. | API pública autorizada de Banco de México; para el caso histórico, archivo de referencia revisado sin ejecutar macros. |
| Parámetros metodológicos | Convención de días, frecuencia de cupón, nominal, tolerancias y método de interpolación. | Configuración versionada y aprobada para el caso. |
| Solicitud | Fecha de corte, universo de instrumentos y propósito analítico. | Telegram u otra interfaz autorizada; validada por Elara. |
| Datos de demostración | Datos ficticios o sanitizados. | Sólo para demostraciones públicas; deben identificarse como tales. |

Resultados esperados: datos validados, curva spot calculada, precios teóricos en una base nominal comparable, métricas de repricing, interpretación descriptiva, dictamen técnico provisional, registro del caso y estado de aprobación humana.

### Solicitud de ejemplo

**Entrada:** fecha de corte, universo CETES/M-Bonos, propósito «valuación y riesgo de portafolio ficticio» y modo simulado.

**Salida útil:** expediente identificado por caso_id con datos aceptados o rechazados, curva y métricas calculadas cuando proceda, dictamen técnico provisional y estado de aprobación.

## 5. Flujo de principio a fin

1. El usuario solicita un caso con fecha de corte y propósito permitido.
2. Orion asigna un caso_id, registra el caso y coordina las etapas.
3. Elara valida que la solicitud esté completa, dentro del alcance y sin pretender una recomendación de inversión; al aceptarla registra su marca de tiempo.
4. Siena obtiene datos autorizados de Banxico y verifica series, fecha, campos obligatorios, faltantes y consistencia básica.
5. Nash construye la curva con los insumos validados, interpolación documentada y el motor Python/SciPy.
6. Nash repricinga los instrumentos en una misma base nominal y genera evidencia de errores, tolerancias y supuestos.
7. Atenea audita datos, metodología, controles y dicta un resultado técnico provisional.
8. Orion consolida el expediente con el mismo caso_id y una versión específica de curva para aprobación humana.
9. El responsable de riesgos aprueba, rechaza o solicita corrección antes de permitir el uso académico de la curva.
10. Los artefactos sanitizados y autorizados podrán alimentar controles de GitHub Actions y, cuando corresponda, un dashboard de GitHub Pages.

### Estado de implementación

La arquitectura de orquestación, los agentes, n8n, Telegram, Python/SciPy, GitHub Actions, GitHub Pages y Nova están definidos como componentes previstos. Su estado operativo requiere evidencia de ejecución y validación en los hitos de construcción, conexión, control, publicación e integración de voz.

## 6. Indicadores clave de desempeño

| KPI | Fórmula y población | Unidad | Periodicidad | Fuente | Utilidad empresarial |
| --- | --- | --- | --- | --- | --- |
| Error porcentual absoluto medio de repricing (MAPE) | (100/n) × Σi abs((Pi,teórico − Pi,sucio) / Pi,sucio). n es el número de instrumentos aceptados con precio sucio distinto de cero, flujos calculables y precio teórico; ambos precios se expresan en la misma base nominal y fecha de corte. | Porcentaje | Por curva; resumen semanal y mensual | Datos validados de Banxico y motor cuantitativo | Mide el ajuste promedio de la curva a los precios observados comparables. |
| Porcentaje de curvas técnicamente válidas | 100 × (casos finalizados que superan todos los controles técnicos obligatorios / total de casos con evaluación técnica finalizada). La unidad de conteo es un caso_id con una única versión final de curva; las versiones sustituidas no se cuentan de nuevo. Se excluyen solicitudes canceladas antes de la evaluación técnica, casos sin evaluación finalizada y duplicados deduplicados. Si el denominador es cero, el indicador se reporta como «no calculable» y no como 0 %. La aprobación humana no forma parte de este indicador. | Porcentaje | Por curva; resumen semanal y mensual | Registro de casos, controles de Siena, Nash y Atenea | Mide la proporción de expedientes que cumplen controles técnicos antes de la decisión humana. |
| Tiempo de procesamiento técnico | Marca de tiempo del dictamen técnico provisional de Atenea menos marca de tiempo de aceptación de Elara. Se mide sólo en casos finalizados técnica y provisionalmente. Los reportes agregados usan la mediana por periodo. | Minutos | Por caso; resumen semanal y mensual | Registro de orquestación y dictamen técnico | Mide la eficiencia del proceso automatizado sin incorporar la espera de aprobación humana. |

### Métrica técnica complementaria: error máximo individual de repricing

Error máximo individual = max_i [100 × abs((Pi,teórico − Pi,sucio) / Pi,sucio)], sobre la misma población usada para MAPE. Se expresa como porcentaje y se reporta por curva y en resúmenes semanales y mensuales a partir de datos validados de Banxico y del motor cuantitativo. Identifica el instrumento con mayor desviación para revisión específica.

Un MAPE bajo o un error máximo individual dentro de tolerancia evidencian ajuste de calibración al corte evaluado; no garantizan capacidad predictiva ni sustituyen los controles de datos, metodología, trazabilidad y aprobación humana.

## 7. Decisión de negocio y aprobación humana

**Decisión:** determinar si una curva calculada es suficientemente confiable para usarse en la valuación y el análisis de riesgos de un portafolio ficticio.

**Acción que exige aprobación humana:** el responsable de riesgos debe aprobar explícitamente el dictamen y la evidencia antes de marcar la curva como apta para uso académico. La autorización queda vinculada a un caso_id y a una versión específica de curva, y registra identidad del aprobador, fecha y hora, expiración y resultado (aprobado, rechazado o devuelto para corrección). Una aprobación vencida, rechazada o correspondiente a otra versión no libera el caso. Si la evidencia es incompleta, los controles fallan o la metodología no corresponde al caso, el supervisor debe rechazar o devolver el expediente.

El tiempo de aprobación humana se registra por separado del tiempo de procesamiento técnico.

## 8. Datos históricos y demostraciones públicas

Los datos históricos de Banxico se usarán para validación metodológica y pruebas reproducibles. Input1_TasasSpot.xlsm es una referencia metodológica histórica externa al repositorio: sus macros no se ejecutan y el archivo original no se incorpora sin una revisión de seguridad independiente.

Las demostraciones públicas usarán sólo datos ficticios o datos públicos sanitizados, con etiqueta visible. No se publicarán credenciales, trazas sensibles, archivos privados ni registros identificables.

## 9. Restricciones de seguridad, trazabilidad y publicación

- Las credenciales se almacenan fuera del código: variables de entorno, credenciales de n8n o GitHub Secrets cuando una integración específica lo requiera.
- Cada caso conserva caso_id, versión de curva, versión de datos, fecha de corte, parámetros, controles, dictamen, decisión, responsable humano y referencias de consumo aplicables.
- Los resultados no aprobados no deben presentarse como curvas aptas ni alimentar explicaciones de Nova como si fueran definitivas.
- GitHub Actions y GitHub Pages sólo podrán publicar artefactos sanitizados y previamente autorizados.
- El repositorio no debe incluir tokens, archivos .env, datos privados ni el Excel con macros sin revisión explícita.
- Toda afirmación financiera debe distinguir entre dato observado, cálculo, inferencia, supuesto y límite.

### Nova, asistente de voz

Nova es una interfaz prevista de ElevenLabs. Mediante herramientas autenticadas conectadas a n8n podrá crear casos de demostración y consultar su estado con el caso_id. No tendrá autorización para aprobar curvas, modificar dictámenes, acceder a información privada ni publicar resultados. Toda acción de Nova estará sujeta a validación de campos, autorización y permisos en el receptor.

## 10. Criterios de aceptación

El caso empresarial se considera aceptado para iniciar las etapas posteriores cuando:

1. La empresa ficticia, sector, usuario, problema, objetivo, alcance, exclusiones y decisión están definidos sin ambigüedad material.
2. El proceso está delimitado desde la solicitud hasta el dictamen y la aprobación humana, y conserva un caso_id común entre canales, registro, aprobaciones y costos.
3. Las entradas, fuentes permitidas, reglas metodológicas, salida útil y datos de demostración están documentados.
4. Los KPI de MAPE de repricing, porcentaje de curvas técnicamente válidas y tiempo de procesamiento técnico especifican fórmula, población o denominador, unidad, periodicidad, fuente e interpretación; la métrica de error máximo individual está documentada como control complementario.
5. El porcentaje de curvas técnicamente válidas evita doble conteo por versiones, define exclusiones y el tratamiento de un denominador cero, y no incorpora la aprobación humana.
6. La aprobación humana está vinculada a la versión de curva y contempla identidad, fecha, expiración, resultado y devolución para corrección.
7. Las funcionalidades previstas se distinguen de los componentes con evidencia operativa.
8. La protección de credenciales, datos privados, trazabilidad y publicación sanitizada está definida.
