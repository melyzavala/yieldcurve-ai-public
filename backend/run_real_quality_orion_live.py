"""Ruta manual sanitizada: Siena real, quality loop y Orion local."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from backend.banxico_client import CURVE_REQUIRED_SERIES
from backend.orion_executor import execute_orion
from backend.siena_executor import execute_siena
from backend.siena_to_excel_adapter import SienaToExcelAdapterError, build_excel_payload_from_siena


def _case(fecha_corte: str) -> dict:
    compact = fecha_corte.replace("-", "")
    now = datetime.now(timezone.utc).isoformat()
    return {
        "contrato_version": "1.0.0", "caso_id": f"YC-ORION{compact}", "version_caso": 1,
        "version_curva": f"CURVA-ORION-{compact}", "fecha_corte": fecha_corte,
        "canal_origen": "manual", "modo": "SIMULADO", "estado": "RECIBIDO",
        "objetivo": "Curva académica de portafolio ficticio.", "agente_responsable": "Orion",
        "solicitud": {"universo_instrumentos": ["CETES", "MBONOS"], "proposito": "Valuación y análisis de riesgo de un portafolio ficticio."},
        "referencias": {"datos": [], "calculos": [], "validaciones": []}, "advertencias": [], "errores": [],
        "marcas_tiempo": {"creado_en": now, "actualizado_en": now},
        "trazabilidad": {"correlation_id": f"CORR-ORION-{compact}", "traza_id": f"TRAZA-ORION-{compact}", "referencias_consumo": []},
        "aprobacion_humana": {"estado": "PENDIENTE"}, "salidas_especializadas": {},
    }


def _elara_fixture(fecha_corte: str) -> dict:
    """Fixture local para orquestación; no constituye una llamada live de Elara."""
    return {
        "schema_version": "1.0.0", "decision": "ACEPTAR", "fecha_corte_normalizada": fecha_corte,
        "instrumentos_solicitados": ["CETES", "MBONOS"], "proposito": "Valuación y análisis de riesgo de un portafolio ficticio.",
        "datos_faltantes": [], "motivos_rechazo": [], "advertencias": [],
        "seguridad": {"inyeccion_prompt_detectada": False, "instrucciones_no_confiables_ignoradas": False},
    }


def _siena_summary(siena: dict) -> dict:
    summary = siena.get("resumen_validacion", {})
    return {
        "estado": siena.get("estado"), "series_solicitadas": summary.get("series_solicitadas"),
        "observaciones_validas": summary.get("observaciones_validas"),
        "datos_mercado": siena.get("fuente", {}).get("datos_mercado"),
        "errores": [item.get("codigo") for item in siena.get("errores", [])],
    }


def run(fecha_corte: str) -> dict:
    """Ejecuta una sola consulta SIE y nunca imprime payloads, headers o secretos."""
    case = _case(fecha_corte)
    siena = execute_siena(fecha_corte, list(CURVE_REQUIRED_SERIES))
    output: dict = {"case_id": case["caso_id"], "fecha_corte": fecha_corte, "siena": _siena_summary(siena)}
    if siena.get("estado") != "DATOS_VALIDOS":
        output["estado"] = "SIENA_RECHAZADA"
        return output
    try:
        payload = build_excel_payload_from_siena(case, siena)
    except SienaToExcelAdapterError as error:
        output.update(estado="ADAPTADOR_RECHAZADO", codigo_error=str(error))
        return output
    config = {
        "budget_usd": 0.0, "time_limit_seconds": 30.0, "authorization_scope": "ORCHESTRATION_SIMULATED",
        "execution_authorized": True, "authorization_source": "TRUSTED_LOCAL_CONFIG", "inject_quality_failure": True,
    }
    orion = execute_orion(case, _elara_fixture(fecha_corte), siena, payload, config, "real-quality-orion-live")
    quality = [item for item in orion.get("traza", []) if item.get("etapa") == "calidad_curva"]
    nash = orion.get("expediente", {}).get("nash") or {}
    atenea = orion.get("expediente", {}).get("atenea") or {}
    output.update(
        estado=orion.get("estado"),
        quality={"estado": "VALIDADA" if orion.get("estado") == "PENDIENTE_APROBACION" else "NO_VALIDADA", "numero_iteraciones": len(quality), "iteraciones": [{"version": item.get("referencia"), "atenea": item.get("estado")} for item in quality]},
        final={"nash_estado": nash.get("estado"), "atenea_estado": atenea.get("estado")},
        orion={"estado": orion.get("estado"), "version_curva": orion.get("version_curva"), "dictamen_tecnico": orion.get("dictamen_tecnico"), "requiere_aprobacion_humana": orion.get("requiere_aprobacion_humana"), "errores": [item.get("codigo") for item in orion.get("errores", [])]},
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Prueba manual Siena real, quality loop y Orion.")
    parser.add_argument("fecha_corte", help="Fecha ISO YYYY-MM-DD")
    args = parser.parse_args()
    result = run(args.fecha_corte)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get("estado") != "PENDIENTE_APROBACION":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
