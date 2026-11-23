---
name: build-spot-curve
version: 1.0.0
description: Construye curvas spot simuladas de CETES y M-Bonos con metodología explícita, precios sucios y evidencia verificable.
---

# Build Spot Curve

## Identidad, activador y alcance

**Nombre:** `build-spot-curve`. **Versión:** `1.0.0`. **Descripción:** construcción determinista y auditable de curvas spot simuladas. **Activador:** una solicitud `SIMULADO` de valuación o riesgo que incluya el payload cuantitativo completo. No es un mecanismo de publicación, operación, aprobación humana ni consulta de mercado.

## Activador y objetivo

Se activa sólo para un caso `SIMULADO` que requiera una curva spot para valuación o análisis de riesgo de un portafolio ficticio. El payload selecciona explícitamente una de las metodologías siguientes; el motor no convierte ni mezcla convenciones entre ellas.

## Entradas comunes y fuentes permitidas

- `case_id`, `curve_version`, `mode=SIMULADO` y `valuation_date` ISO 8601.
- Precio sucio (`DIRTY`) y unidad `MXN_PER_100_FACE`; YTM y precio limpio no sustituyen el precio de calibración.
- Salida validada de Siena y metadatos verificables de cada emisión cuando aplique: cupón, vencimiento, nominal y calendario.
- Casos sintéticos versionados de esta carpeta.

Las series CF300 representativas no aportan por sí solas cupón, vencimiento ni calendario de cada M-Bono. El cálculo se bloquea cuando falten metadatos requeridos. No utiliza LLM, APIs, macros, Solver ni credenciales.

## Ruta A: `EXCEL_BOOTSTRAP_182D_V1`

### Entradas y convenciones

- `metodologia=EXCEL_BOOTSTRAP_182D_V1` y nodos iniciales `excel_cetes_nodes`.
- M-Bonos representativos CF300 en `excel_mbonos`, ordenados aproximadamente 3Y → 5Y → 10Y → 20Y → 30Y; cada nodo resuelto queda fijo antes de resolver el siguiente. Cada entrada contiene plazo, precio sucio y cupón vigente del rango representativo.
- Los CETES representativos CF300 suministran plazo y precio sucio; la tasa equivalente de 182 días se deriva de esos dos campos. La tasa de fondeo gubernamental overnight se recibe como insumo explícito.
- Interpolación lineal de tasas spot, periodicidad de 182 días y descuento `(1 + r × 182/360)^(-t/182)`.
- Cupón por periodo: `100 × tasa_cupon × 182/360`; principal al vencimiento.
- Precio sucio como objetivo de cada etapa y una tasa terminal desconocida por M-Bono.

### Procedimiento

1. Validar identificadores, finitud, plazos, precios y unicidad de los nodos CETES y M-Bonos.
2. Fijar CETES y el nodo overnight como soporte inicial.
3. Construir flujos sintéticos de nominal 100 para cada M-Bono con cupones de 182 días y principal final.
4. Resolver secuencialmente la tasa terminal por bisección determinista con bracket obligatorio, tolerancia y máximo de iteraciones configurables.
5. Recalcular cada precio sucio con los nodos ya fijados y registrar error, bracket, iteraciones, convergencia y advertencias.

Esta ruta usa `backend/excel_bootstrap.py`, no importa SciPy y no usa Solver. Es una simplificación académica reproducible del Excel: los rangos CF300 no son una emisión individual ni sustituyen calendarios legales de flujos.

## Ruta B: `PCHIP_LOG_DISCOUNT_FACTOR`

### Entradas y convenciones

- `day_count=ACT/365F` e `interpolation_method=PCHIP_LOG_DISCOUNT_FACTOR`.
- CETES con vencimiento, nominal y precio sucio.
- M-Bonos con `coupon_rate_annual`, `coupon_frequency` y `coupon_dates` completos, ordenados y con vencimiento final.

### Procedimiento

1. Convertir fechas de flujos a años con `ACT/365F`.
2. Obtener factores de CETES desde precio sucio y nominal.
3. Construir flujos de M-Bonos con `nominal × cupón_anual / frecuencia` y principal final.
4. Formar una PCHIP única sobre log-factores, sin extrapolación, y calibrar los factores terminales de M-Bonos.
5. Calcular tasa spot continua y repricing final con esa misma PCHIP.

Esta ruta histórica usa `backend/spot_curve.py` y SciPy. No debe recibir ni reinterpretar la convención 182/360 de la ruta Excel.

## Salida, controles y aceptación

La salida conserva identificador, versión, metodología, convenciones, pilares, precios teóricos, error absoluto de repricing y traza SHA-256 de la skill. En la ruta Excel los flujos sintéticos son un cálculo interno; la salida no declara que conserva flujos legales completos de emisiones individuales. Rechaza modo distinto de `SIMULADO`, datos no finitos, identificadores o vencimientos duplicados, extrapolación, metadatos M-Bono faltantes y errores fuera de tolerancia.

Se acepta únicamente cuando la metodología seleccionada se ejecuta sin conversión, los precios sucios se reprician dentro de su tolerancia y queda evidencia sanitizada de la invocación.

## Herramientas permitidas, errores y límites

Herramientas permitidas: sólo los motores locales `backend/excel_bootstrap.py` o `backend/spot_curve.py`, validadores locales y SHA-256 del archivo cargado. Fuentes permitidas: payload proporcionado y ejemplos versionados; no se consulta ninguna fuente externa. Errores de entrada o metodología se devuelven como rechazo determinista, sin aproximar ni completar datos faltantes. No usa LLM, red, API, macros, Solver ni credenciales; tampoco expone prompts privados o razonamiento interno.

## Ejemplos

- `examples/caso_valido.json`: ruta PCHIP histórica válida.
- `examples/caso_invalido_metadatos.json`: rechazo por metadatos faltantes.
- `examples/caso_reutilizacion.json`: reutilización PCHIP.
- `tests/fixtures_excel_bootstrap.py`: fixture sintético reproducible de la ruta Excel, extraído de valores de referencia sin incluir el archivo original.

El primer ejemplo es válido; `caso_invalido_metadatos.json` es el ejemplo rechazado que solicita completar metadatos antes de continuar.
