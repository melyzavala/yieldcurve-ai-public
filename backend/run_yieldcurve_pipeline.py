"""Runner manual sanitizado del pipeline; DEMO es seguro por defecto."""
from __future__ import annotations

import argparse
import json
from typing import Any

from backend.yieldcurve_pipeline import DEMO_DATE, run_yieldcurve_case


def main() -> None:
    parser = argparse.ArgumentParser(description="Ejecuta YieldCurve AI sin exponer secretos.")
    parser.add_argument("--mode", choices=("DEMO", "LIVE"), default="DEMO")
    parser.add_argument("--date", default=DEMO_DATE)
    args = parser.parse_args()
    if args.mode != "DEMO":
        raise SystemExit("LIVE requiere una interfaz autenticada que inyecte Elara y Siena; este runner sólo habilita DEMO.")
    result = run_yieldcurve_case(
        caso_id="YC-PIPE20261111", version_caso=1, version_curva="CURVA-PIPE-20261111",
        fecha_corte=args.date, canal_origen="manual", solicitud="Construye una curva CETES y M-Bonos para 2026-11-11.",
        budget_config={"budget_usd": 0.0, "time_limit_seconds": 30.0, "authorization_scope": "ORCHESTRATION_SIMULATED", "execution_authorized": True, "authorization_source": "TRUSTED_LOCAL_CONFIG"},
        invocation_id="yieldcurve-demo-cli", execution_mode="DEMO",
    )
    summary: dict[str, Any] = {
        "caso_id": result["caso_id"], "fecha_corte": result["fecha_corte"],
        "execution_mode": result["execution_mode"], "estado": result["estado"],
        "dictamen_tecnico": result["dictamen_tecnico"],
        "requiere_aprobacion_humana": result["requiere_aprobacion_humana"],
        "fuente_datos": result["fuente_datos"],
        "especialistas": {
            "elara": result["elara"].get("decision") if result["elara"] else None,
            "siena": result["siena"].get("estado") if result["siena"] else None,
            "nash": result["nash"].get("estado") if result["nash"] else None,
            "atenea": result["atenea"].get("estado") if result["atenea"] else None,
        },
        "errores": [item.get("codigo") for item in result["errores"]],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
