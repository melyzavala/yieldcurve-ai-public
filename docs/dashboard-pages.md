# Dashboard público en GitHub Pages

El sitio separa la capa privada de `case_artifact`, la proyección `public_case_artifact` y la presentación estática. El contrato formal está en `web/public_case.schema.json`. Pages publica únicamente artefactos DEMO sanitizados cuya fuente demuestra estado `APROBADA_HUMANAMENTE`, auditoría técnica válida y curva no vacía. `web/build.py` valida los JSON ya autorizados, agrega `cases.json`, genera un Excel público en `web/dist/downloads` y copia los assets. `web/dist` es un output efímero, no fuente versionada; Pages no genera casos, no invoca Orion, n8n ni Render, y no infiere una aprobación.

El Excel público parte sólo del contrato público adaptado; el endpoint privado autenticado no se expone ni cambia. El deployment falla cerrado ante datos inválidos, pilares vacíos, números no finitos, nombres sensibles o evidencia de aprobación insuficiente.

## Exportación autorizada de un caso DEMO

1. Cree un caso DEMO por un canal autorizado.
2. Complete la aprobación humana en Telegram.
3. Exporte o copie una sola fila aprobada de `YC_CASES` a `data/private/approved_case.json` local.
4. Ejecute `python web/export_approved_case.py data/private/approved_case.json`.
5. Revise el JSON sanitizado generado en `data/public/cases/`.
6. Versione únicamente ese archivo público revisado.
7. GitHub Actions valida el contrato antes de cualquier despliegue de Pages.

`data/private/**` nunca debe versionarse. El exportador no consulta n8n, Render, Telegram ni ElevenLabs; rechaza entradas que no demuestren DEMO, aprobación humana, auditoría técnica y coherencia con el resultado original.

## Limitación conocida de versionamiento

El caso publicado `YC-NV01R0XFRU01` conserva sólo la versión técnica sanitizada `CURVA-YC-NV01R0XFRU01-V1-V1`. La fila privada de origen reportaba `CURVA-YC-NV01R0XFRU01-V1`; esta discrepancia se documenta como limitación de trazabilidad y no se corrige ni se expone mediante Pages. El artefacto público no contiene la fila privada ni campos de decisión, trazas, prompts, cabeceras, tokens o secretos.

En GitHub, configure manualmente **Settings → Pages → Build and deployment → Source: GitHub Actions**. El workflow `pages.yml` prueba, construye, escanea, sube y despliega el artefacto validado; no intenta crear ni habilitar GitHub Pages mediante `GITHUB_TOKEN`.

El repositorio sigue siendo privado. GitHub Pages para repositorios privados requiere un plan compatible; si GitHub obliga a hacerlo público, deténgase antes de habilitarlo y revise/limpie el historial. No se debe cambiar la visibilidad de forma automática.
