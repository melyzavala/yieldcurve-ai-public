from decimal import Decimal

import pytest

from backend.cost_estimator import CostEstimationError, estimate_cost_usd


RATES = {
    "input": Decimal("0.10"), "cached_input": Decimal("0.01"),
    "cache_write_30m": Decimal("0.125"), "cache_write_12h": Decimal("0.25"),
    "output": Decimal("0.50"),
}


@pytest.mark.parametrize(("record", "expected"), [
    ({"input_tokens": 100, "output_tokens": 20}, "0.00002"),
    ({"input_tokens": 100, "cached_input_tokens": 40, "output_tokens": 20}, "0.0000164"),
    ({"input_tokens": 100, "cache_write_tokens": 20, "ttl_30m_tokens": 20, "ttl_12h_tokens": 0, "output_tokens": 20}, "0.0000205"),
    ({"input_tokens": 100, "cache_write_tokens": 20, "ttl_30m_tokens": 0, "ttl_12h_tokens": 20, "output_tokens": 20}, "0.000023"),
    ({"input_tokens": 100, "cached_input_tokens": 30, "cache_write_tokens": 20, "ttl_30m_tokens": 10, "ttl_12h_tokens": 10, "output_tokens": 20}, "0.00001905"),
])
def test_exclusive_input_categories(record: dict, expected: str) -> None:
    estimate = estimate_cost_usd(record, RATES)
    assert estimate["total_usd"] == expected


def test_manual_example_has_no_double_counted_categories() -> None:
    # 100 input = 70 normal + 20 cached reads + 10 cache writes (30m), plus 20 output.
    estimate = estimate_cost_usd({"input_tokens": 100, "cached_input_tokens": 20, "cache_write_tokens": 10, "ttl_30m_tokens": 10, "ttl_12h_tokens": 0, "output_tokens": 20}, RATES)
    assert estimate["uncached_input_tokens"] == "70"
    assert estimate["total_usd"] == "0.00001845"


@pytest.mark.parametrize("record", [
    {"input_tokens": 10, "cached_input_tokens": 8, "cache_write_tokens": 3, "ttl_30m_tokens": 3, "ttl_12h_tokens": 0, "output_tokens": 1},
    {"input_tokens": 10, "cache_write_tokens": 3, "ttl_30m_tokens": 2, "ttl_12h_tokens": 0, "output_tokens": 1},
])
def test_inconsistent_cache_usage_is_not_costed(record: dict) -> None:
    with pytest.raises(CostEstimationError, match="CACHE_USAGE_INCONSISTENT"):
        estimate_cost_usd(record, RATES)


def test_undisclosed_cache_write_ttl_is_not_costed() -> None:
    with pytest.raises(CostEstimationError, match="CACHE_WRITE_TTL_UNAVAILABLE"):
        estimate_cost_usd({"input_tokens": 10, "cache_write_tokens": 1, "output_tokens": 1}, RATES)
