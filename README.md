# YieldCurve AI

> Nota de publicación: este repositorio es una versión pública sanitizada de YieldCurve AI, generada desde el estado de entrega `c16a8a9679e015c2c6a8b541902fe1751f2da057`. El historial de desarrollo completo permanece en un repositorio privado. Esta réplica contiene únicamente archivos sanitizados destinados a evaluación, reproducción y GitHub Pages; no reproduce el historial original.

YieldCurve AI es una plataforma agéntica para construir, validar y analizar curvas spot de deuda gubernamental mexicana. Su propósito empresarial es apoyar la decisión de si una curva calculada es suficientemente confiable para valuación y análisis de riesgo de un portafolio **ficticio**. No emite recomendaciones de inversión ni ejecuta operaciones.

## Metodología prevista

1. Obtener series públicas autorizadas de Banco de México.
2. Usar CETES y Bonos M como instrumentos de referencia.
3. Validar fecha de corte, plazos, cupones, precios sucios y convenciones.
4. Construir nodos spot mediante descuento de flujos e interpolación.
5. Resolver nodos terminales con Python y SciPy.
6. Comparar precios teóricos y precios sucios bajo tolerancias documentadas.

El archivo histórico `Input1_TasasSpot.xlsm` se utiliza fuera del repositorio como referencia metodológica y caso de validación. No se versiona en este proyecto.

## Agentes previstos

| Agente | Responsabilidad prevista |
| --- | --- |
| Orion | Orquestación, control de etapas y entrega de expediente. |
| Elara | Interpretación y validación de solicitudes. |
| Siena | Obtención y verificación de datos de Banco de México. |
| Nash | Construcción cuantitativa de la curva con Python/SciPy. |
| Atenea | Auditoría financiera, controles y dictamen. |

## Arquitectura prevista

Telegram recibirá solicitudes autorizadas. n8n coordinará los flujos. Python/SciPy realizará los cálculos. ElevenLabs podrá proporcionar una interfaz de voz. GitHub Actions validará el repositorio y GitHub Pages podrá publicar documentación o un dashboard estático cuando sea autorizado.

Estas integraciones no están implementadas en este hito.

## Estado actual

**Hito 2 — preparación del repositorio y entorno.**

La estructura, reglas de seguridad, variables de entorno de ejemplo y documentación inicial están preparadas. Aún faltan el motor de cálculo, los agentes, las skills, los loops, las consultas a Banxico, los workflows de n8n, el dashboard y las pruebas funcionales.

## Requisitos previstos para reproducibilidad

- Python 3.11 o superior.
- SciPy y dependencias que se definirán al implementar el motor.
- Credenciales configuradas fuera del repositorio mediante variables de entorno o GitHub Secrets cuando una integración las necesite.
- Acceso autorizado a las APIs que se incorporen posteriormente.

## Seguridad

No subas archivos `.env`, tokens, claves, credenciales de n8n ni el libro Excel original. Copia `.env.example` a `.env` sólo en tu entorno local y completa exclusivamente las variables necesarias.
