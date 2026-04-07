from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from helper_bist_price_steps import BistPayPriceStep
from helper_bist_price_steps import example_normalize_price_steps


class TestGetPriceStep:
    @pytest.mark.parametrize(
        "price, expected_step, expected_step_str, expected_band",
        [
            ("19.999", 0.01, "0.010", "0.010 - 19.999"),
            ("20", 0.02, "0.020", "20.000 - 49.999"),
            ("49.999", 0.02, "0.020", "20.000 - 49.999"),
            ("50", 0.05, "0.050", "50.000 - 99.999"),
            ("99.999", 0.05, "0.050", "50.000 - 99.999"),
            ("100", 0.10, "0.100", "100.000 - 249.999"),
            ("249.999", 0.10, "0.100", "100.000 - 249.999"),
            ("250", 0.25, "0.250", "250.000 - 499.999"),
            ("499.999", 0.25, "0.250", "250.000 - 499.999"),
            ("500", 0.50, "0.500", "500.000 - 999.999"),
            ("999.999", 0.50, "0.500", "500.000 - 999.999"),
            ("1000", 1.00, "1.000", "1,000.000 - 2,499.999"),
            ("2499.999", 1.00, "1.000", "1,000.000 - 2,499.999"),
            ("2500", 2.50, "2.500", "2,500.000 and above"),
            ("2502.5", 2.50, "2.500", "2,500.000 and above"),
        ],
    )
    def test_returns_correct_band_info(self, price, expected_step, expected_step_str, expected_band):
        result = BistPayPriceStep.get_price_step(price)

        assert result["step"] == expected_step
        assert result["step_str"] == expected_step_str
        assert result["band"] == expected_band


class TestIsValidPriceStep:
    @pytest.mark.parametrize(
        "price, expected_is_valid, expected_step",
        [
            ("19.99", True, 0.01),
            ("20.00", True, 0.02),
            ("20.01", False, 0.02),
            ("20.02", True, 0.02),
            ("49.98", True, 0.02),
            ("50.00", True, 0.05),
            ("50.03", False, 0.05),
            ("50.05", True, 0.05),
            ("100.10", True, 0.10),
            ("100.11", False, 0.10),
            ("250.25", True, 0.25),
            ("250.30", False, 0.25),
            ("500.50", True, 0.50),
            ("500.25", False, 0.50),
            ("1001.00", True, 1.00),
            ("1001.49", False, 1.00),
            ("2502.50", True, 2.50),
            ("2501.00", False, 2.50),
        ],
    )
    def test_validity_detection(self, price, expected_is_valid, expected_step):
        result = BistPayPriceStep.is_valid_price_step(price)

        assert result["is_valid"] is expected_is_valid
        assert result["step"] == expected_step


class TestRoundPriceToStep:
    @pytest.mark.parametrize(
        "price, mode, expected_output",
        [
            ("20.031", "nearest", "20.04"),
            ("20.031", "floor", "20.02"),
            ("20.031", "ceil", "20.04"),
            ("50.09", "nearest", "50.10"),
            ("50.09", "floor", "50.05"),
            ("50.09", "ceil", "50.10"),
            ("250.26", "nearest", "250.25"),
            ("250.26", "floor", "250.25"),
            ("250.26", "ceil", "250.50"),
            ("250.38", "nearest", "250.50"),
            ("1001.49", "nearest", "1001.00"),
            ("1001.49", "floor", "1001.00"),
            ("1001.49", "ceil", "1002.00"),
            ("2501.49", "nearest", "2502.50"),
            ("2501.49", "floor", "2500.00"),
            ("2501.49", "ceil", "2502.50"),
        ],
    )
    def test_rounding_modes(self, price, mode, expected_output):
        result = BistPayPriceStep.round_price_to_step(price, mode)

        assert result["output"] == expected_output
        assert result["mode"] == mode

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="Invalid mode"):
            BistPayPriceStep.round_price_to_step("250.26", "not-defined-mode")


class TestNormalizeInput:
    @pytest.mark.parametrize(
        "raw_price, expected",
        [
            ("72.65", "72.65"),
            ("72,65", "72.65"),
            ("1.234,56", "1234.56"),
            ("1,234.56", "1234.56"),
            ("00072.6500", "72.65"),
            ("00072", "72"),
            (72, "72"),
            (72.65, "72.65"),
        ],
    )
    def test_normalizes_supported_formats(self, raw_price, expected):
        result = BistPayPriceStep._normalize_input(raw_price)
        assert result == expected

    @pytest.mark.parametrize(
        "raw_price",
        [
            "",
            "   ",
            "abc",
            "-10",
            "0",
            0,
            0.0,
            None,
            [],
            {},
        ],
    )
    def test_invalid_inputs_raise(self, raw_price):
        with pytest.raises((ValueError, TypeError)):
            BistPayPriceStep._normalize_input(raw_price)


class TestHelperFunction:
    @pytest.mark.parametrize(
        "raw_price, expected",
        [
            ("72.6531", "72.65"),
            ("250.26", "250.25"),
            ("250.38", "250.50"),
            (1001.49, "1001.00"),
            ("1.234,56", "1235.00"),
        ],
    )
    def test_example_normalize_price_steps(self, raw_price, expected):
        assert example_normalize_price_steps(raw_price) == expected