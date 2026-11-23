"""Fixture público normalizado de Siena Live para 2026-11-11; no contiene secretos."""

from backend.banxico_client import CF300_SERIES, CURVE_REQUIRED_SERIES, SERIES_CATALOG

VALUES = {
    "SF45422": 22.0, "SF45439": 9.962168, "SF45423": 85.0, "SF45441": 9.849535,
    "SF45424": 169.0, "SF45443": 9.702206, "SF45425": 337.0, "SF45445": 9.393273,
    "SF349886": 687.0, "SF349888": 8.705960,
    "SF45427": 1205.0, "SF45449": 102.964751, "SF45475": 8.5,
    "SF45428": 1982.0, "SF45451": 97.805938, "SF45476": 8.0,
    "SF45430": 3389.0, "SF45455": 94.005726, "SF45478": 8.0,
    "SF45431": 5846.0, "SF45457": 87.436980, "SF45479": 7.75,
    "SF60720": 10396.0, "SF60722": 85.852819, "SF60723": 8.0, "SF43774": 6.2600,
}

CASE = {
    "contrato_version": "1.0.0", "caso_id": "YC-SIENA20261111", "version_caso": 1,
    "version_curva": "CURVA-SIENA-20261111", "fecha_corte": "2026-11-11", "canal_origen": "manual",
    "modo": "SIMULADO", "estado": "EN_CALCULO", "objetivo": "Curva académica de portafolio ficticio.",
    "agente_responsable": "Nash", "referencias": {"datos": [], "calculos": [], "validaciones": []},
    "advertencias": [], "errores": [],
    "marcas_tiempo": {"creado_en": "2026-11-11T00:00:00Z", "actualizado_en": "2026-11-11T00:00:00Z"},
    "trazabilidad": {"correlation_id": "CORR-SIENA-20261111", "traza_id": "TRAZA-SIENA-20261111", "referencias_consumo": []},
    "salidas_especializadas": {},
}

SIENA = {
    "estado": "DATOS_VALIDOS", "fecha_corte": "2026-11-11", "modo": "SIMULADO",
    "fuente": {"proveedor": "Banco de México", "cuadro": "CF300", "recursos": [
        {"tipo": "CUADRO_SIE", "identificador": "CF300", "series": [key for key in CURVE_REQUIRED_SERIES if key in CF300_SERIES]},
        {"tipo": "SERIE_SIE", "identificador": "SF43774", "series": ["SF43774"]},
    ], "api_base": "https://www.banxico.org.mx/SieAPIRest/service", "consultada_en": "2026-11-18T23:09:43Z", "datos_mercado": "REALES"},
    "series": [{"serie_id": key, **SERIES_CATALOG[key], "estado": "DISPONIBLE", **({"requiere_flujos_individuales": True} if SERIES_CATALOG[key]["instrumento"] == "MBONOS" else {})} for key in CURVE_REQUIRED_SERIES],
    "observaciones": [{"serie_id": key, "fecha": "2026-11-11", "valor": value, "unidad": SERIES_CATALOG[key]["unidad"], "valida": True} for key, value in VALUES.items()],
    "resumen_validacion": {"series_solicitadas": 26, "series_con_observacion": 26, "observaciones_validas": 26, "observaciones_rechazadas": 0},
    "advertencias": [{"codigo": "MBONOS_RANGO", "severidad": "ADVERTENCIA", "mensaje": "Los Bonos M de CF300 son representativos por rango; no proporcionan flujos de una emisión individual."}], "errores": [],
}
