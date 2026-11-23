# Loop de calidad financiera de curva

## Propósito y responsables

Nash construye; Atenea audita técnicamente; la orquestación local registra y decide retorno. El objetivo es corregir una curva simulada sin aprobación automática.

## Entradas y límites

Caso, entrada original intacta, máximo tres iteraciones, 30 segundos totales y presupuesto de tokens `0`. No hay llamadas externas ni consumo real.

## Secuencia

1. Inventariar caso, versión y entrada original.
2. Nash construye la curva determinista.
3. Atenea compara el repricing independiente, identificadores, fecha y convenciones.
4. Si rechaza, registrar diagnóstico y devolver a construcción.
5. Reconstruir desde la entrada original con nueva versión de curva.
6. Revalidar con Atenea.
7. Cerrar como `VALIDADA`, `LIMITE_ITERACIONES` o `LIMITE_TIEMPO`.

## Evidencia y aceptación

Cada iteración registra caso, versión, dictámenes, diagnóstico, duración y costo adicional cero. V1 alterada debe rechazarse; V2 corregida debe validarse con el mismo `caso_id`. No se habilita aprobación, publicación ni operación.
