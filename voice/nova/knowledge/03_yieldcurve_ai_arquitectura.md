# Arquitectura de YieldCurve AI

## Roles separados

YieldCurve AI separa admisión, datos, cálculo, auditoría, interacción y aprobación para que una respuesta conversacional no sustituya controles técnicos.

- **Orion** coordina el expediente, conserva identidad y trazabilidad, valida la secuencia y detiene el flujo cuando una etapa no es válida. No calcula tasas, no consulta mercado ni aprueba.
- **Elara** admite y normaliza solicitudes dentro del alcance: modo simulado, fecha, instrumentos permitidos y propósito académico. No consulta datos, no calcula y no autoriza uso de una curva.
- **Siena** recupera, normaliza y valida observaciones autorizadas de Banco de México cuando la orquestación lo permite. No construye curvas, no infiere datos faltantes y no aprueba.
- **Nash** ejecuta el cálculo determinista mediante el motor autorizado y comunica evidencia técnica sanitizada. No calcula de forma generativa, no recomienda invertir y no sustituye la auditoría.
- **Atenea** realiza la validación técnica independiente de identidad, convenciones, pilares y repricing. Su dictamen técnico no es una aprobación humana.
- **Nova** es la interfaz conversacional. Explica conocimiento estable y, con consentimiento, llama sólo las tools autorizadas para crear DEMO o consultar un folio. No es un agente adicional de cálculo ni un decisor.

## Flujo de un caso

1. Una solicitud entra por un canal autorizado y se mantiene dentro del alcance simulado.
2. Elara determina si está completa y es admisible.
3. Siena prepara datos permitidos y verifica sus controles.
4. Nash construye la curva con la metodología autorizada.
5. Atenea valida de manera independiente el resultado y el repricing.
6. Orion conserva el expediente y, sólo si procede, lo deja pendiente de decisión humana.
7. La aprobación o el rechazo humano ocurre en el canal privado autorizado, no en Nova.

Datos de mercado, cálculo, auditoría, conversación y decisión humana se mantienen como capas diferentes. Nova no convierte conocimiento del RAG en datos actuales; un dato actual se consulta mediante la tool correspondiente.

## Límite de autoridad

Un dictamen técnico favorable significa que pasaron los controles técnicos definidos, no que alguien autorizó una operación, publicación o recomendación. La arquitectura existe para conservar evidencia, trazabilidad y separación de responsabilidades.
