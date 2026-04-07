from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from helper_bist_scaling_into_position import BistScalingIntoPosition


class TestOneStepDown:
    @pytest.mark.parametrize(
        "price, expected",
        [
            ("20.70", "20.68"),
            ("20.00", "19.99"),
            ("50.00", "49.98"),
            ("100.00", "99.95"),
            ("250.00", "249.90"),
            ("500.00", "499.75"),
            ("1000.00", "999.50"),
            ("2502.50", "2500.00"),
            ("2500.00", "2499.00"),
            ("0.02", "0.01"),
        ],
    )
    def test_returns_previous_valid_bist_step(self, price, expected):
        assert BistScalingIntoPosition.one_step_down(price) == expected


class TestOneStepUp:
    @pytest.mark.parametrize(
        "price, expected",
        [
            ("19.99", "20.00"),
            ("20.70", "20.72"),
            ("49.98", "50.00"),
            ("99.95", "100.00"),
            ("249.90", "250.00"),
            ("499.75", "500.00"),
            ("999.50", "1000.00"),
            ("2499.00", "2500.00"),
            ("2500.00", "2502.50"),
        ],
    )
    def test_returns_next_valid_bist_step(self, price, expected):
        assert BistScalingIntoPosition.one_step_up(price) == expected


class TestScaleOrdersDown:
    def test_ladder_contains_correct_boundary_transition_from_2500_band(self):
        result = BistScalingIntoPosition.scale_orders_down(
            symbol="EXMPL",
            limit_price="2500.00",
            budget=200000,
            max_drop_pct=0.20,
        )

        prices = [order["price"] for order in result["orders"]]

        assert "2500.00" in prices
        assert "2499.00" in prices
        assert "2497.50" not in prices

        idx_2500 = prices.index("2500.00")
        idx_2499_00 = prices.index("2499.00")

        assert idx_2499_00 == idx_2500 + 1

    def test_prices_are_strictly_descending(self):
        result = BistScalingIntoPosition.scale_orders_down(
            symbol="EXMPL",
            limit_price="20.70",
            budget=10000,
            max_drop_pct=1.25,
        )

        prices = [float(order["price"]) for order in result["orders"]]

        for i in range(len(prices) - 1):
            assert prices[i + 1] < prices[i]


class TestScaleOrdersUp:
    def test_prices_are_strictly_ascending(self):
        result = BistScalingIntoPosition.scale_orders_up(
            symbol="EXMPL",
            limit_price="20.70",
            budget=10000,
            max_rise_pct=0.40,
        )

        prices = [float(order["price"]) for order in result["orders"]]

        for i in range(len(prices) - 1):
            assert prices[i + 1] > prices[i]