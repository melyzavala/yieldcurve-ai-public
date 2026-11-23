# Evidencia de skills y loops

`build-spot-curve` v1.0.0 se carga desde `skills/build_spot_curve/SKILL.md` por `build_spot_curve_adapter.py`, invocado por Nash. `validate-spot-curve` v1.0.0 se carga desde su `SKILL.md` por `validate_spot_curve_adapter.py`, invocado por Atenea. Ambas trazas observables incluyen `invocation_id`, nombre, ruta relativa, versión, SHA-256 y estado, sin prompts ni razonamiento interno.

El loop de calidad (`run_curve_quality_loop`) recibe caso y entrada original; Nash genera, Atenea mide/repricea y diagnostica, y el retorno reconstruye desde la entrada original. Está limitado a tres iteraciones y 30 segundos, y falla cerrado. La evidencia Excel P11 registra V1 alterada sólo en memoria para la prueba, rechazada técnicamente, y V2 reconstruida como validada con el mismo caso y nueva versión de curva. La operación normal de Orion usa `inject_quality_failure=false` salvo pruebas explícitas.

El loop de seguridad/costo (`run_security_cost_loop`) verifica permisos y presupuesto, permite únicamente `SIMULATED_VALIDATION`, registra consumo y detiene cualquier acción no autorizada. V1 bloqueada y V2 autorizada conservan el caso; no se desactivan guardrails. Orion invoca primero seguridad/costos y después Elara, Siena y calidad de curva. Un dictamen técnico válido conserva `PENDIENTE_APROBACION` hasta la decisión humana.

Responsables: Orion coordina; Nash construye; Atenea valida; la persona responsable aprueba. No se realizaron llamadas LLM ni externas: tokens y costo variable API son 0; infraestructura no medida es `null`.
