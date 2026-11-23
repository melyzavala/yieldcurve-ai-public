# Bootstrapping y metodología vigente

## Qué es bootstrapping

El bootstrapping construye una curva por secuencia de vencimientos. Parte de instrumentos de plazo corto y, con los factores ya obtenidos, despeja la información del siguiente vencimiento. Es una técnica de construcción de curva, no una recomendación financiera ni un cálculo que Nova deba ejecutar por voz.

## Idea paso a paso

1. Se valida que los datos, instrumentos, fechas y convenciones sean compatibles.
2. Se incorporan nodos de descuento de corto plazo, como CETES, bajo la convención definida.
3. Para cada M-Bono se arma el calendario de cupones y principal.
4. Los flujos anteriores se descuentan usando nodos existentes o la interpolación autorizada.
5. Se resuelve la tasa spot del siguiente pilar para que el precio teórico iguale el precio sucio observado.
6. Se agrega el pilar y se continúa en orden creciente de plazo.
7. Se reprician los instrumentos y se realiza validación técnica independiente.

Conceptualmente, un instrumento cero cupón relaciona un único pago futuro con su precio mediante un factor de descuento, bajo la convención correspondiente: `Precio = Pago al vencimiento × DF(T)`. En un bono con cupón, el precio contiene varios pagos: `Precio sucio = Σ [Flujo_i × DF(t_i)]`. Por eso los factores de flujos previos deben estar disponibles antes de despejar el factor o la tasa del siguiente plazo.

## De factor de descuento a tasa spot

La relación exacta depende de la convención. Para `EXCEL_BOOTSTRAP_182D_V1`, la implementación aplica una tasa con periodo de 182 días y base 360:

`DF(d) = (1 + r × 182/360)^(-d/182)`

donde `r` es la tasa spot del nodo y `d` son días al flujo. En forma conceptual, si se conoce el factor, la tasa compatible se despeja invirtiendo esa relación. No se deben mezclar esta convención con una convención anual distinta sin conversión explícita.

## EXCEL_BOOTSTRAP_182D_V1

Esta es la metodología vigente implementada en el repositorio para la ruta Excel. Sus propiedades documentadas son:

- modo `SIMULADO`;
- CETES y M-Bonos como nodos de entrada;
- la validación declara precio sucio y la base `MXN_PER_100_FACE`; el repricing de CETES conserva su fórmula específica y no debe equipararse mecánicamente a la de M-Bonos;
- periodicidad de cupón de 182 días y base `182/360`;
- ancla overnight de un día;
- conversión de la tasa de CETES a una tasa compatible con 182/360;
- bootstrap secuencial de M-Bonos;
- interpolación lineal de tasas spot entre pilares;
- bisección para resolver cada nodo de M-Bono, con máximo de iteraciones y tolerancia recibidos en la entrada validada;
- repricing de CETES y M-Bonos por una validación independiente.

En la ruta Excel, los CETES entran como nodos con precio y una tasa ya compatible cuando el adapter la proporciona. Si la tasa no viene incluida, `excel_bootstrap.py` puede obtenerla desde precio y plazo con su fórmula específica. Después, la curva usa la convención `DF(d) = (1 + r × 182/360)^(-d/182)`.

La validación independiente de CETES revierte la equivalencia 182/360 para calcular su precio teórico; no los trata como un M-Bono con cupones ni supone que ambos comparten la misma lógica de obtención de nodo. Los M-Bonos sí usan cupón por periodo `nominal × tasa de cupón × 182/360`, incluyen principal en el último flujo y resuelven el nuevo spot por bisección.

Para cada M-Bono, el motor busca una tasa entre los límites definidos por la bisección de modo que el precio calculado de todos sus flujos coincida con el precio sucio de entrada dentro de la tolerancia. “Convergió” indica que ese procedimiento encontró una solución bajo esos controles; no es una aprobación humana ni una garantía de mercado.

## Pilares, interpolación y repricing

Un pilar conserva instrumento, plazo, tasa spot, precio observado, precio recalculado, iteraciones y señal de convergencia. Para un flujo situado entre dos pilares, la ruta Excel interpola **linealmente la tasa spot**. La interpolación no autoriza extrapolar fuera del intervalo de pilares.

El **repricing** vuelve a calcular el precio de entrada con la curva construida. Construir la curva resuelve los nodos; validarla comprueba de forma independiente identidad, convenciones, pilares, flujos, interpolación y error máximo contra tolerancias. Son controles distintos: un cálculo terminado aún requiere dictamen técnico y, si corresponde, aprobación humana.

## Ejemplo conceptual ficticio

Si un bono ficticio paga un cupón en una fecha intermedia y principal más cupón al vencimiento, el primer flujo se descuenta con un nodo previo o una tasa interpolada. La tasa del nuevo pilar se ajusta hasta que la suma de ambos valores presentes iguale su precio sucio. Este ejemplo describe la lógica; no sustituye al motor ni aporta una cifra para casos reales.
