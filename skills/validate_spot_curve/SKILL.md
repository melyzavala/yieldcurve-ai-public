---
name: validate-spot-curve
version: 1.0.0
description: Valida independientemente curvas spot simuladas mediante repricing reconstruido y metodología explícita.
---

# Validate Spot Curve

## Identidad, activador y alcance

**Nombre:** `validate-spot-curve`. **Versión:** `1.0.0`. **Descripción:** auditoría independiente determinista de una curva construida por Nash. **Activador:** una salida de `build-spot-curve` con payload original, pilares y `invocation_id`. Su alcance termina en el dictamen técnico; no sustituye la aprobación humana ni autoriza publicación u operación.

## Activador y objetivo

Se activa después de `build-spot-curve` y antes del dictamen de Atenea. Recibe el payload cuantitativo original, los pilares reportados por Nash y un `invocation_id`; reconstruye precios de forma independiente. No acepta como evidencia suficiente los precios recalculados, errores o flags declarados por Nash.

Sólo acepta `SIMULADO`, identificadores y versiones coincidentes, precio sucio `DIRTY` en `MXN_PER_100_FACE`, pilares finitos, únicos y ordenados. La metodología se selecciona desde las convenciones de la curva y no se convierte entre ramas.

## Ruta A: `EXCEL_BOOTSTRAP_182D_V1`

### Convenciones

- Método: `EXCEL_BOOTSTRAP_182D_V1`.
- Interpolación lineal de tasas spot (`LINEAR_SPOT_RATE`).
- Descuento `(1 + r × 182/360)^(-t/182)`.
- Cupones M-Bono `100 × tasa_cupon × 182/360`, principal al vencimiento y precio sucio.
- Periodicidad: 182 días.

### Validación independiente

1. Verificar metodología, unidades, identificadores, fechas, nodos, plazos y tasas finitas.
2. Reconstruir CETES desde `excel_cetes_nodes` revirtiendo la equivalencia de tasa 182/360 a YTM y repriciarlos; reconstruir independientemente los flujos de cada M-Bono desde `excel_mbonos` del payload original.
3. Interpolar linealmente tasas sólo entre nodos disponibles; rechazar extrapolación y duplicados.
4. Recalcular factores, precios teóricos y error absoluto de repricing sin usar valores declarados por Nash.
5. Rechazar nodos faltantes, precios no finitos, flujos incompatibles, convenciones distintas o M-Bonos fuera de tolerancia.

Esta rama no carga SciPy ni PCHIP.

### Tolerancias

Los M-Bonos usan la tolerancia general de repricing `1e-8`. Los CETES de la ruta Excel usan `1e-7 MXN por 10 de nominal` únicamente para redondeo del benchmark de referencia, después de invertir correctamente la equivalencia 182/360; no es una excepción metodológica amplia, no sustituye la tolerancia M-Bono y no se aplica a PCHIP.

## Ruta B: `PCHIP_LOG_DISCOUNT_FACTOR`

La ruta histórica conserva `ACT/365F`, factores de descuento positivos y una PCHIP final sobre log-factores. Reconstruye flujos explícitos de CETES y M-Bonos, revaloriza todos los instrumentos con esa misma PCHIP y rechaza extrapolación, pilares faltantes o errores por encima de `1e-8`. Esta rama usa SciPy y no debe recibir las convenciones 182/360 de Excel.

## Salida y aceptación

La salida incluye caso, versión, metodología auditada, pilares, repricing independiente, máximo error, tolerancia y traza SHA-256 sanitizada. Se acepta una curva sólo si todos los controles de la ruta seleccionada pasan; Atenea conserva la aprobación humana fuera del validator.

## Límites

No usa LLM, API, macros, Solver, credenciales ni red. No convierte YTM o precio limpio a precio sucio, no infiere metadatos individuales de M-Bonos desde CF300 y no aprueba publicaciones u operaciones.

## Herramientas, errores, aceptación y ejemplos

Herramientas permitidas: únicamente `backend/spot_curve_validator.py`, cálculos locales, el payload original y SHA-256 del archivo cargado. Fuentes permitidas: el payload original y la curva de Nash; no hay fuentes externas. Un identificador, versión, convención, pilar o repricing inválido produce `REJECTED`; el adaptador no corrige datos. Se acepta sólo cuando el repricing reconstruido, la metodología y las tolerancias pasan. Ejemplo válido: `skills/build_spot_curve/examples/caso_valido.json` junto con su curva Nash. Ejemplo rechazado/aclaración: `caso_invalido_metadatos.json`; requiere metadatos completos, no una inferencia.
