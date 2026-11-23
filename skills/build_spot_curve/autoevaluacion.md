# Autoevaluación de `build-spot-curve`

| Aspecto | Puntuación (0–4) | Evidencia verificable |
| --- | ---: | --- |
| Claridad y propósito | 4 | Activador, objetivo y alcance financiero delimitados en `SKILL.md`. |
| Contexto y secuencia | 4 | Procedimiento determinista de ocho pasos, con convenciones explícitas. |
| Evidencia | 4 | Pilares, flujos, repricing y traza con SHA-256 del archivo cargado. |
| Control y retorno | 4 | Rechazos verificables para metadatos faltantes, YTM, fechas, flujos sin nodo y datos inconsistentes. |
| Utilidad | 4 | Dos casos sintéticos ejecutables y un caso inválido reproducible para la etapa cuantitativa. |
| **Total** | **20/20** | Ningún aspecto es inferior a 3. |

La aceptación final depende de que `tests/test_spot_curve.py` se ejecute correctamente en GitHub Actions.
