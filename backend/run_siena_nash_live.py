"""Ruta manual y sanitizada Siena real -> payload Excel -> Nash local."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from backend.banxico_client import CURVE_REQUIRED_SERIES
from backend.atenea_executor import execute_atenea
from backend.nash_executor import execute_nash
from backend.siena_executor import execute_siena
from backend.siena_to_excel_adapter import SienaToExcelAdapterError, build_excel_payload_from_siena


def _case(fecha_corte: str) -> dict:
    compact_date = fecha_corte.replace("-", "")
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "contrato_version": "1.0.0",
        "caso_id": f"YC-SIENANASH{compact_date}",
        "version_caso": 1,
        "version_curva": f"CURVA-SIENA-NASH-{compact_date}",
        "fecha_corte": fecha_corte,
        "canal_origen": "manual",
        "modo": "SIMULADO",
        "estado": "EN_CALCULO",
        "objetivo": "Curva académica de portafolio ficticio.",
        "agente_responsable": "Nash",
        "referencias": {"datos": [], "calculos": [], "validaciones": []},
        "advertencias": [],
        "errores": [],
        "marcas_tiempo": {"creado_en": timestamp, "actualizado_en": timestamp},
        "trazabilidad": {
            "correlation_id": f"CORR-SIENA-NASH-{compact_date}",
            "traza_id": f"TRAZA-SIENA-NASH-{compact_date}",
            "referencias_consumo": [],
        },
        "salidas_especializadas": {},
    }


def _siena_summary(siena: dict) -> dict:
    return {
        "estado": siena.get("estado"),
        "fecha_corte": siena.get("fecha_corte"),
        "modo": siena.get("modo"),
        "datos_mercado": siena.get("fuente", {}).get("datos_mercado"),
        "series_solicitadas": siena.get("resumen_validacion", {}).get("series_solicitadas"),
        "series_con_observacion": siena.get("resumen_validacion", {}).get("series_con_observacion"),
        "observaciones_validas": siena.get("resumen_validacion", {}).get("observaciones_validas"),
        "observaciones_rechazadas": siena.get("resumen_validacion", {}).get("observaciones_rechazadas"),
        "advertencias": [item.get("codigo") for item in siena.get("advertencias", [])],
        "errores": [item.get("codigo") for item in siena.get("errores", [])],
    }


def run(fecha_corte: str) -> dict:
    """Ejecuta la ruta explícita sin imprimir credenciales, headers o payloads crudos."""
    case = _case(fecha_corte)
    siena = execute_siena(fecha_corte, list(CURVE_REQUIRED_SERIES))
    summary = {"siena": _siena_summary(siena)}
    if siena.get("estado") != "DATOS_VALIDOS":
        summary["estado"] = "SIENA_RECHAZADA"
        return summary
    try:
        payload = build_excel_payload_from_siena(case, siena)
    except SienaToExcelAdapterError as error:
        summary.update(estado="ADAPTADOR_RECHAZADO", codigo_error=str(error))
        return summary
    nash = execute_nash(case, payload, "siena-nash-live")
    curve = nash.get("resultado_curva") or {}
    summary.update(
        estado=nash.get("estado"),
        metodologia=curve.get("metodologia"),
        instrument_count=curve.get("instrument_count"),
        repricing_count=len(curve.get("repricing", [])),
        max_absolute_repricing_error=curve.get("max_absolute_repricing_error"),
        nash_errors=[item.get("codigo") for item in nash.get("errores", [])],
    )
    summary["nash"] = {
        "estado": nash.get("estado"),
        "metodologia": curve.get("metodologia"),
        "instrument_count": curve.get("instrument_count"),
        "repricing_count": len(curve.get("repricing", [])),
        "max_absolute_repricing_error": curve.get("max_absolute_repricing_error"),
        "errores": [item.get("codigo") for item in nash.get("errores", [])],
    }
    if nash.get("estado") != "CALCULO_COMPLETADO":
        return summary
    atenea = execute_atenea(case, nash, payload, "siena-nash-atenea-live")
    summary["atenea"] = {
        "estado": atenea.get("estado"),
        "tecnicamente_valida": atenea.get("dictamen", {}).get("tecnicamente_valida"),
        "requiere_aprobacion_humana": atenea.get("dictamen", {}).get("requiere_aprobacion_humana"),
        "validation_status": atenea.get("evidencia", {}).get("validation_status"),
        "errores": [item.get("codigo") for item in atenea.get("errores", [])],
    }
    summary["estado"] = atenea.get("estado")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Prueba manual sanitizada Siena a Nash.")
    parser.add_argument("fecha_corte", help="Fecha ISO YYYY-MM-DD")
    args = parser.parse_args()
    result = run(args.fecha_corte)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["estado"] != "DICTAMEN_TECNICO_VALIDADO":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
