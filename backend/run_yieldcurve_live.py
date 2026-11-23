"""Runner manual y controlado de la ruta LIVE de YieldCurve AI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from backend.live_dependencies import LiveDependencyError, build_live_elara, build_live_siena_provider, require_live_credentials
from backend.yieldcurve_pipeline import DEMO_DATE, run_yieldcurve_case


AUTHORIZED_REQUEST = (
    "Construye una curva de CETES y M-Bonos con fecha de corte {fecha} para "
    "valuación y análisis de riesgo de un portafolio ficticio."
)
LIVE_CONFIG = {
    "budget_usd": 0.01,
    "time_limit_seconds": 30.0,
    "authorization_scope": "ORCHESTRATION_SIMULATED",
    "execution_authorized": True,
    "authorization_source": "TRUSTED_LOCAL_CONFIG",
    "max_llm_calls": 1,
}


def _case_id(fecha_corte: str) -> str:
    return f"YC-LIVE{fecha_corte.replace('-', '')}"


def _version(fecha_corte: str) -> str:
    return f"CURVA-LIVE-{fecha_corte.replace('-', '')}"


def compare_demo_and_live(demo: dict[str, Any], live: dict[str, Any]) -> dict[str, Any]:
    """Compara datos y pilares sin alterar el fixture histórico DEMO."""
    demo_values = {item["serie_id"]: item["valor"] for item in (demo.get("siena") or {}).get("observaciones", [])}
    live_values = {item["serie_id"]: item["valor"] for item in (live.get("siena") or {}).get("observaciones", [])}
    different_series = sorted(
        serie_id for serie_id in set(demo_values).union(live_values)
        if demo_values.get(serie_id) != live_values.get(serie_id)
    )
    demo_pillars = {item["instrument_id"]: item["spot_rate"] for item in (demo.get("nash") or {}).get("resultado_curva", {}).get("pillars", [])}
    live_pillars = {item["instrument_id"]: item["spot_rate"] for item in (live.get("nash") or {}).get("resultado_curva", {}).get("pillars", [])}
    differences = [abs(demo_pillars[key] - live_pillars[key]) for key in set(demo_pillars).intersection(live_pillars)]
    return {
        "observaciones_coinciden": not different_series,
        "series_diferentes": different_series,
        "pilares_coinciden_tolerancia": max(differences, default=0.0) <= 1e-12 and set(demo_pillars) == set(live_pillars),
        "diferencia_maxima_pilares": max(differences, default=None),
    }


def sanitize_evidence(result: dict[str, Any], comparison: dict[str, Any] | None = None) -> dict[str, Any]:
    """Reduce la salida a evidencia auditable sin prompt, secretos o response ID."""
    telemetry = result.get("telemetria", {}).get("elara", {})
    siena = result.get("siena") or {}
    return {
        "caso_id": result.get("caso_id"), "version_caso": result.get("version_caso"),
        "version_curva": result.get("version_curva"), "fecha_corte": result.get("fecha_corte"),
        "modo": result.get("modo"), "execution_mode": result.get("execution_mode"),
        "fuente_datos": result.get("fuente_datos"), "estado": result.get("estado"),
        "dictamen_tecnico": result.get("dictamen_tecnico"),
        "requiere_aprobacion_humana": result.get("requiere_aprobacion_humana"),
        "elara": {
            "status": telemetry.get("status"), "modelo": telemetry.get("modelo"),
            "input_tokens": telemetry.get("input_tokens"), "cached_input_tokens": telemetry.get("cached_input_tokens"),
            "output_tokens": telemetry.get("output_tokens"), "duracion_ms": telemetry.get("duracion_ms"),
            "error_code": telemetry.get("error_code"),
            "diagnostico_validacion": telemetry.get("diagnostico_validacion"),
            "decision": (result.get("elara") or {}).get("decision"),
            "datos_faltantes": (result.get("elara") or {}).get("datos_faltantes"),
        },
        "siena": {"estado": siena.get("estado"), "resumen_validacion": siena.get("resumen_validacion")},
        "nash": {"estado": (result.get("nash") or {}).get("estado")},
        "atenea": {"estado": (result.get("atenea") or {}).get("estado")},
        "traza": result.get("traza"), "consumo": result.get("consumo"),
        "errores": [item.get("codigo") for item in result.get("errores", []) if isinstance(item, dict)],
        "comparacion_demo_live": comparison,
    }


def write_evidence(path: Path, result: dict[str, Any], comparison: dict[str, Any] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_evidence(result, comparison), ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ejecuta una única prueba LIVE autorizada de YieldCurve AI.")
    parser.add_argument("--date", default=DEMO_DATE)
    parser.add_argument("--evidence", type=Path)
    arguments = parser.parse_args()
    try:
        require_live_credentials()
        result = run_yieldcurve_case(
            caso_id=_case_id(arguments.date), version_caso=1, version_curva=_version(arguments.date),
            fecha_corte=arguments.date, canal_origen="manual",
            solicitud=AUTHORIZED_REQUEST.format(fecha=arguments.date), budget_config=LIVE_CONFIG,
            invocation_id=f"live-{arguments.date}", execution_mode="LIVE",
            elara_executor=build_live_elara(), siena_provider=build_live_siena_provider(),
        )
    except LiveDependencyError as error:
        print(json.dumps({"estado": "DETENIDO", "codigo_error": error.code}, ensure_ascii=False))
        return 2

    comparison = None
    if result.get("estado") == "PENDIENTE_APROBACION":
        demo = run_yieldcurve_case(
            caso_id=f"YC-DEMO{arguments.date.replace('-', '')}", version_caso=1,
            version_curva=f"CURVA-DEMO-{arguments.date.replace('-', '')}", fecha_corte=arguments.date,
            canal_origen="manual", solicitud=AUTHORIZED_REQUEST.format(fecha=arguments.date),
            budget_config=LIVE_CONFIG, invocation_id=f"demo-compare-{arguments.date}", execution_mode="DEMO",
        )
        comparison = compare_demo_and_live(demo, result)
    if arguments.evidence:
        write_evidence(arguments.evidence, result, comparison)
    print(json.dumps(sanitize_evidence(result, comparison), ensure_ascii=False, indent=2))
    return int(result.get("estado") != "PENDIENTE_APROBACION")


if __name__ == "__main__":
    raise SystemExit(main())
