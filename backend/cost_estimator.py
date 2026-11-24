"""Estimación determinista con tarifas de referencia versionadas."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path
from typing import Any


class CostEstimationError(ValueError):
    """Costo no calculable por uso o tarifa incompletos/inconsistentes."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _decimal(row: dict[str, str], field: str) -> Decimal | None:
    return Decimal(row[field]) if row.get(field) else None


def model_rates(path: Path, model: str) -> dict[str, Decimal | str | None]:
    with path.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            if row["proveedor"] == "OpenAI" and row["servicio"] == "API" and row["modelo"] == model and row["estado_verificacion"] == "verificado":
                return {
                    "input": Decimal(row["precio_entrada_usd"]),
                    "cached_input": Decimal(row["precio_entrada_cache_usd"]),
                    "cache_write_30m": _decimal(row, "precio_cache_write_30m_usd"),
                    "cache_write_12h": _decimal(row, "precio_cache_write_12h_usd"),
                    "output": Decimal(row["precio_salida_usd"]),
                    "pricing_effective_date": row["fecha_consulta"],
                    "pricing_source": row["fuente_oficial"],
                    "pricing_status": row["estado_verificacion"],
                }
    raise CostEstimationError("PRICING_UNAVAILABLE")


def _token_count(record: dict[str, Any], field: str, *, default: int | None = None) -> int | None:
    value = record.get(field, default)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _cache_write_tokens(record: dict[str, Any]) -> tuple[int, int, int]:
    total_raw = record.get("cache_write_tokens")
    ttl_30_raw = record.get("ttl_30m_tokens")
    ttl_12_raw = record.get("ttl_12h_tokens")
    total = _token_count(record, "cache_write_tokens") if total_raw is not None else None
    ttl_30 = _token_count(record, "ttl_30m_tokens") if ttl_30_raw is not None else None
    ttl_12 = _token_count(record, "ttl_12h_tokens") if ttl_12_raw is not None else None
    if total_raw is not None and total is None:
        raise CostEstimationError("CACHE_USAGE_INCONSISTENT")
    if ttl_30_raw is not None and ttl_30 is None or ttl_12_raw is not None and ttl_12 is None:
        raise CostEstimationError("CACHE_USAGE_INCONSISTENT")
    if total is None and ttl_30 is None and ttl_12 is None:
        return 0, 0, 0
    if ttl_30 is None or ttl_12 is None:
        raise CostEstimationError("CACHE_WRITE_TTL_UNAVAILABLE")
    ttl_total = ttl_30 + ttl_12
    if total is not None and ttl_total != total:
        raise CostEstimationError("CACHE_USAGE_INCONSISTENT")
    return total if total is not None else ttl_total, ttl_30, ttl_12


def estimate_cost_usd(record: dict[str, Any], rates: dict[str, Decimal | str | None]) -> dict[str, str]:
    input_tokens = _token_count(record, "input_tokens")
    output_tokens = _token_count(record, "output_tokens")
    cached_raw = record.get("cached_input_tokens")
    cached_tokens = 0 if cached_raw is None else _token_count(record, "cached_input_tokens")
    if input_tokens is None or output_tokens is None or cached_tokens is None:
        raise CostEstimationError("USAGE_UNAVAILABLE")
    cache_write_tokens, ttl_30, ttl_12 = _cache_write_tokens(record)
    uncached_tokens = input_tokens - cached_tokens - cache_write_tokens
    if uncached_tokens < 0:
        raise CostEstimationError("CACHE_USAGE_INCONSISTENT")
    input_rate, cached_rate, write_30_rate, write_12_rate, output_rate = (
        rates.get("input"), rates.get("cached_input"), rates.get("cache_write_30m"), rates.get("cache_write_12h"), rates.get("output")
    )
    if not all(isinstance(rate, Decimal) for rate in (input_rate, cached_rate, output_rate)):
        raise CostEstimationError("PRICING_UNAVAILABLE")
    if (ttl_30 and not isinstance(write_30_rate, Decimal)) or (ttl_12 and not isinstance(write_12_rate, Decimal)):
        raise CostEstimationError("PRICING_UNAVAILABLE")
    million = Decimal("1000000")
    input_cost = Decimal(uncached_tokens) * input_rate / million
    cached_cost = Decimal(cached_tokens) * cached_rate / million
    write_30_cost = Decimal(ttl_30) * write_30_rate / million if isinstance(write_30_rate, Decimal) else Decimal(0)
    write_12_cost = Decimal(ttl_12) * write_12_rate / million if isinstance(write_12_rate, Decimal) else Decimal(0)
    output_cost = Decimal(output_tokens) * output_rate / million
    total = input_cost + cached_cost + write_30_cost + write_12_cost + output_cost
    return {
        "uncached_input_tokens": str(uncached_tokens), "input_uncached_usd": str(input_cost),
        "input_cached_usd": str(cached_cost), "cache_write_30m_usd": str(write_30_cost),
        "cache_write_12h_usd": str(write_12_cost), "output_usd": str(output_cost), "total_usd": str(total),
    }
