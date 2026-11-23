# Fundamentos de la curva de tasas

## Propósito académico

YieldCurve AI explica y analiza curvas de instrumentos gubernamentales mexicanos en casos ficticios. Una curva es una herramienta de valuación y análisis; no es una recomendación de inversión, una orden de operación ni una predicción garantizada de tasas futuras.

## Curva de rendimientos y curva spot

Una curva de rendimientos organiza tasas o rendimientos por plazo. Permite observar cómo cambia la compensación exigida por el mercado entre vencimientos cortos y largos, siempre bajo una convención definida.

Una **curva spot** asigna una tasa cero cupón a cada plazo o pilar. Cada tasa spot sirve para descontar un flujo único pagadero en ese plazo. Por ello es especialmente útil para valuar instrumentos con varios flujos: cada flujo se descuenta con la información de su propio plazo.

Un **pilar** es un plazo para el cual la metodología obtuvo una tasa spot o un factor de descuento. Entre pilares puede requerirse una regla de interpolación; fuera del rango disponible no debe suponerse una tasa sin una regla autorizada.

## YTM, tasa spot y tasa forward

- **YTM (yield to maturity):** tasa única que iguala el precio observado de un instrumento con el valor presente de todos sus flujos, bajo su convención. Depende de los flujos y del precio de ese instrumento.
- **Tasa spot:** tasa asociada a un solo plazo; descuenta un flujo único de ese vencimiento.
- **Tasa forward:** tasa implícita entre dos fechas futuras, derivada de factores de descuento o tasas spot bajo una convención. No es una predicción garantizada de la tasa que se observará en el futuro.

Estas tasas no son intercambiables sin respetar la convención, el plazo y los flujos. Un YTM de un bono con cupón no equivale, en general, a una tasa spot del mismo vencimiento.

## Factor de descuento y valor presente

El factor de descuento `DF(t)` convierte un flujo futuro `CF(t)` a valor presente:

`VP = CF(t) × DF(t)`

Para varios flujos, el precio teórico es la suma de cada flujo descontado:

`Precio = Σ [CF(t) × DF(t)]`

Un factor de descuento positivo y menor que uno suele reflejar que un pago futuro vale menos hoy bajo tasas positivas; la interpretación concreta depende de la convención aplicada.

## CETES y M-Bonos

Los **CETES** son instrumentos gubernamentales de descuento. No pagan cupones periódicos: su lógica de descuento permite inferir información de plazos cortos a partir de precio y vencimiento bajo la convención aplicable.

Los **M-Bonos** son bonos gubernamentales con cupones. Su precio representa varios flujos —cupones y principal al vencimiento—, por lo que para valorarlos se deben descontar todos los pagos de acuerdo con sus fechas y la curva.

## Precio limpio, precio sucio e intereses devengados

El **precio limpio** excluye el interés devengado desde el último cupón. El **precio sucio** lo incluye:

`Precio sucio = Precio limpio + Interés devengado`

Los intereses devengados son la parte del cupón acumulada entre fechas de pago conforme a la convención aplicable. Mezclar precio limpio y sucio rompe la comparabilidad de la valuación. La metodología vigente de YieldCurve AI utiliza precio sucio.

## Para qué sirve una curva

Una curva puede apoyar, dentro de su alcance y evidencia, la valuación de flujos, tesorería, ALM (gestión de activos y pasivos), riesgo de tasa, pricing, sensibilidad y análisis de escenarios. En sensibilidad, DV01 resume el cambio aproximado de valor ante un movimiento de un punto base, siempre que se especifique el instrumento, el método y el escenario. Los análisis de escenarios cambian supuestos de tasas; no garantizan resultados futuros.

Una curva no valida por sí misma una decisión, no sustituye la auditoría técnica y no implica que un instrumento sea adecuado para comprar o vender.
