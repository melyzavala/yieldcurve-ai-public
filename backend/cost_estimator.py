"""Estimación determinista con tarifas de referencia versionadas."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path
from typing import Any


def model_rates(path: Path, model: str) -> dict[str, Decimal]:
    with path.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            if (
                row["proveedor"] == "OpenAI"
                and row["servicio"] == "API"
                and row["modelo"] == model
                and row["estado_verificacion"] == "verificado"
            ):
                return {
                    "input": Decimal(row["precio_entrada_usd"]),
                    "cached_input": Decimal(row["precio_entrada_cache_usd"]),
                    "output": Decimal(row["precio_salida_usd"]),
                }
    raise ValueError(f"No existe una tarifa verificada para {model}.")


def estimate_cost_usd(record: dict[str, Any], rates: dict[str, Decimal]) -> dict[str, str]:
    input_tokens = int(record.get("input_tokens") or 0)
    cached_tokens = min(int(record.get("cached_input_tokens") or 0), input_tokens)
    output_tokens = int(record.get("output_tokens") or 0)
    million = Decimal("1000000")
    input_cost = Decimal(input_tokens - cached_tokens) * rates["input"] / million
    cached_cost = Decimal(cached_tokens) * rates["cached_input"] / million
    output_cost = Decimal(output_tokens) * rates["output"] / million
    total = input_cost + cached_cost + output_cost
    return {
        "input_uncached_usd": str(input_cost), "input_cached_usd": str(cached_cost),
        "output_usd": str(output_cost), "total_usd": str(total),
    }
