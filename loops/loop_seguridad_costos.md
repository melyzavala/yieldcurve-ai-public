# Loop de seguridad y costos

Responsables: orquestación local verifica permisos, presupuesto y límites; humano conserva autorización; el sistema sólo ejecuta una validación simulada. Entradas: caso, presupuesto configurable y acción autorizada. Máximo tres iteraciones y 30 segundos por defecto.

1. Revisar modo, usuario/estado de autorización y permisos mínimos.
2. Comprobar presupuesto antes de actuar.
3. Ejecutar sólo `SIMULATED_VALIDATION` autorizada.
4. Registrar consumo real, costo estimado e infraestructura por separado.
5. Verificar resultado y límites.
6. Continuar, corregir datos simulados o detener.

Estados: `COMPLETADO_SIMULADO`, `BLOQUEADO_SEGURIDAD_O_PRESUPUESTO`, `LIMITE_TIEMPO`, `RECHAZADO_ENTRADA`. En esta implementación el consumo real de API es siempre `0`; costo estimado queda `null` sin unidades medidas; infraestructura queda separada y no se atribuye a API. V1 bloqueada conserva el caso; V2 corrige sólo autorización/mode y reutiliza el mismo `caso_id`.
