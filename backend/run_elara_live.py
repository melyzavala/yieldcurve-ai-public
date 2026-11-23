"""Ejecución manual y controlada de Elara para GitHub Actions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from .elara_executor import DEFAULT_MODEL, ElaraExecutor, build_openai_client
except ImportError:
    from elara_executor import DEFAULT_MODEL, ElaraExecutor, build_openai_client

from backend.cost_estimator import estimate_cost_usd, model_rates

ROOT = Path(__file__).resolve().parents[1]
AUTHORIZED_MESSAGE = (
    "En modo SIMULADO, construye una curva spot con CETES y M-Bonos para el "
    "14 de abril de 2026, con el propósito de valorar un portafolio ficticio "
    "y analizar su riesgo."
)


def expectations_met(output: dict[str, Any] | None) -> bool:
    if output is None:
        return False
    return (
        output.get("decision") == "ACEPTAR"
        and output.get("fecha_corte_normalizada") == "2026-04-14"
        and {"CETES", "MBONOS"}.issubset(set(output.get("instrumentos_solicitados", [])))
    )


def write_evidence(path: Path, evidence: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    arguments = parser.parse_args()
    tariffs_path = ROOT / "costs" / "tarifas.csv"

    try:
        executor = ElaraExecutor(build_openai_client(), model=DEFAULT_MODEL)
        result = executor.run(AUTHORIZED_MESSAGE)
        record = result.record.to_dict()
        evidence = {
            "model": DEFAULT_MODEL,
            "record": record,
            "expected_output_met": expectations_met(result.output),
            "estimated_cost_usd": estimate_cost_usd(record, model_rates(tariffs_path, DEFAULT_MODEL)),
        }
    except Exception as error:
        evidence = {
            "model": DEFAULT_MODEL,
            "record": {
                "status": "RUNNER_ERROR",
                "error_code": "RUNNER_ERROR",
                "error_message": f"Error de configuración: {type(error).__name__}",
            },
            "expected_output_met": False,
            "estimated_cost_usd": None,
        }

    write_evidence(arguments.evidence, evidence)
    return int(
        evidence["record"].get("status") != "VALID"
        or not evidence["expected_output_met"]
    )


if __name__ == "__main__":
    raise SystemExit(main())
