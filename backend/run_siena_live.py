"""Ruta manual y explícita para consultar Siena contra el SIE; no se usa en CI."""

from __future__ import annotations

import argparse
import json

from backend.banxico_client import CURVE_REQUIRED_SERIES
from backend.siena_executor import execute_siena


def main() -> None:
    parser = argparse.ArgumentParser(description="Consulta manual sanitizada de Siena contra Banco de México.")
    parser.add_argument("fecha_corte", help="Fecha ISO YYYY-MM-DD")
    args = parser.parse_args()
    result = execute_siena(args.fecha_corte, list(CURVE_REQUIRED_SERIES))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
