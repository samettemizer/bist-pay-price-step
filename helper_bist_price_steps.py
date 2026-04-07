import re
from typing import Union, Literal, Any


PriceInput = Union[str, int, float]
RoundMode = Literal["floor", "ceil", "nearest"]


class BistPayPriceStep:
    """
    BIST Equity Market price step calculator.

    Out of scope:
    - ETFs
    - Warrants
    - Certificates

    Notes:
    - Since prices reaching your webhook may arrive in inconsistent formats,
      str | int | float inputs are all supported.
    - https://github.com/samettemizer
    """

    # Internal calculation precision.
    # 6 digits is sufficiently safe for decimal prices coming from webhooks.
    INTERNAL_SCALE = 6

    @staticmethod
    def get_price_step(price: PriceInput) -> dict[str, Any]:
        """
        Returns the BIST price step based on the price band.

        Returns:
            {
                'step': float,
                'step_str': str,
                'band': str
            }
        """
        normalized = BistPayPriceStep._normalize_input(price)
        numeric = float(normalized)

        if numeric < 20:
            return {
                "step": 0.01,
                "step_str": "0.010",
                "band": "0.010 - 19.999",
            }

        if numeric < 50:
            return {
                "step": 0.02,
                "step_str": "0.020",
                "band": "20.000 - 49.999",
            }

        if numeric < 100:
            return {
                "step": 0.05,
                "step_str": "0.050",
                "band": "50.000 - 99.999",
            }

        if numeric < 250:
            return {
                "step": 0.10,
                "step_str": "0.100",
                "band": "100.000 - 249.999",
            }

        if numeric < 500:
            return {
                "step": 0.25,
                "step_str": "0.250",
                "band": "250.000 - 499.999",
            }

        if numeric < 1000:
            return {
                "step": 0.50,
                "step_str": "0.500",
                "band": "500.000 - 999.999",
            }

        if numeric < 2500:
            return {
                "step": 1.00,
                "step_str": "1.000",
                "band": "1,000.000 - 2,499.999",
            }

        return {
            "step": 2.50,
            "step_str": "2.500",
            "band": "2,500.000 and above",
        }

    @staticmethod
    def is_valid_price_step(price: PriceInput) -> dict[str, Any]:
        """
        Checks whether the given price is valid according to the step of its band.

        Returns:
            {
                'is_valid': bool,
                'step': float,
                'step_str': str,
                'band': str,
                'input': str
            }
        """
        normalized = BistPayPriceStep._normalize_input(price)
        info = BistPayPriceStep.get_price_step(normalized)

        price_units = BistPayPriceStep._decimal_to_scaled_int(
            normalized,
            BistPayPriceStep.INTERNAL_SCALE
        )
        step_units = BistPayPriceStep._decimal_to_scaled_int(
            info["step_str"],
            BistPayPriceStep.INTERNAL_SCALE
        )

        return {
            "is_valid": (price_units % step_units) == 0,
            "step": info["step"],
            "step_str": info["step_str"],
            "band": info["band"],
            "input": normalized,
        }

    @staticmethod
    def round_price_to_step(price: PriceInput, mode: RoundMode = "nearest") -> dict[str, Any]:
        """
        Rounds the price to the nearest valid step.

        mode:
        - floor
        - ceil
        - nearest

        Returns:
            {
                'input': str,
                'output': str,
                'step': float,
                'step_str': str,
                'band': str,
                'mode': str
            }
        """
        normalized = BistPayPriceStep._normalize_input(price)
        info = BistPayPriceStep.get_price_step(normalized)

        price_units = BistPayPriceStep._decimal_to_scaled_int(
            normalized,
            BistPayPriceStep.INTERNAL_SCALE
        )
        step_units = BistPayPriceStep._decimal_to_scaled_int(
            info["step_str"],
            BistPayPriceStep.INTERNAL_SCALE
        )

        if mode == "floor":
            rounded_units = (price_units // step_units) * step_units
        elif mode == "ceil":
            rounded_units = ((price_units + step_units - 1) // step_units) * step_units
        elif mode == "nearest":
            rounded_units = BistPayPriceStep._round_nearest_units(price_units, step_units)
        else:
            raise ValueError('Invalid mode. Use "floor", "ceil", or "nearest".')

        return {
            "input": normalized,
            "output": BistPayPriceStep._scaled_int_to_decimal(
                rounded_units,
                BistPayPriceStep.INTERNAL_SCALE,
                2
            ),
            "step": info["step"],
            "step_str": info["step_str"],
            "band": info["band"],
            "mode": mode,
        }

    @staticmethod
    def _normalize_input(price: PriceInput) -> str:
        """
        Normalizes the decimal input value.

        Supported examples:
        - "72.65"
        - "72,65"
        - "1.234,56"
        - "1,234.56"
        - 72.65
        - 72
        """
        if isinstance(price, (int, float)):
            raw = str(price)
        elif isinstance(price, str):
            raw = price.strip()
        else:
            raise TypeError("Price must be str, int, or float")

        if raw == "":
            raise ValueError("Price cannot be empty.")

        raw = raw.replace("\u00A0", "").replace(" ", "")

        comma_pos = raw.rfind(",")
        dot_pos = raw.rfind(".")

        if comma_pos != -1 and dot_pos != -1:
            # Treat the last encountered separator as the decimal separator
            if comma_pos > dot_pos:
                # 1.234,56 -> 1234.56
                raw = raw.replace(".", "")
                raw = raw.replace(",", ".")
            else:
                # 1,234.56 -> 1234.56
                raw = raw.replace(",", "")
        elif comma_pos != -1:
            # 72,65 -> 72.65
            raw = raw.replace(",", ".")

        if not re.fullmatch(r"\d+(\.\d+)?", raw):
            raise ValueError(f"Invalid price format: {raw}")

        parts = raw.split(".", 1)
        int_part = parts[0]
        frac_part = parts[1] if len(parts) > 1 else ""

        int_part = int_part.lstrip("0")
        if int_part == "":
            int_part = "0"

        frac_part = frac_part.rstrip("0")

        normalized = int_part if frac_part == "" else f"{int_part}.{frac_part}"

        if float(normalized) <= 0:
            raise ValueError("Price must be greater than zero")

        return normalized

    @staticmethod
    def _decimal_to_scaled_int(number: str, scale: int) -> int:
        """
        Converts a decimal string value into a fixed-scale integer.

        Example for scale=6:
        - 250.25   -> 250250000
        - 72.6531  -> 72653100
        """
        parts = number.split(".", 1)
        int_part = parts[0]
        frac_part = parts[1] if len(parts) > 1 else ""

        if len(frac_part) > scale:
            kept = frac_part[:scale]
            next_digit = int(frac_part[scale:scale + 1] or "0")

            base = (int(int_part) * (10 ** scale)) + int(kept.ljust(scale, "0"))

            if next_digit >= 5:
                base += 1

            return base

        frac_part = frac_part.ljust(scale, "0")
        return (int(int_part) * (10 ** scale)) + int(frac_part)

    @staticmethod
    def _scaled_int_to_decimal(value: int, scale: int, display_decimals: int = 2) -> str:
        """
        Converts a fixed-scale integer back into a decimal string.
        """
        factor = 10 ** scale

        int_part = value // factor
        frac_part = value % factor

        frac_str = str(frac_part).rjust(scale, "0")

        if display_decimals == 0:
            return str(int_part)

        frac_str = frac_str[:display_decimals]

        return f"{int_part}.{frac_str.ljust(display_decimals, '0')}"

    @staticmethod
    def _round_nearest_units(price_units: int, step_units: int) -> int:
        """
        For nearest rounding, round half and above upward.
        """
        quotient = price_units // step_units
        remainder = price_units % step_units

        if (remainder * 2) >= step_units:
            return (quotient + 1) * step_units

        return quotient * step_units


# Example helper for the "nearest" rounding mode
def example_normalize_price_steps(raw_price: PriceInput, mode: RoundMode = "nearest") -> str:
    return BistPayPriceStep.round_price_to_step(raw_price, mode)["output"]


"""
|--------------------------------------------------------------------------
| Verification outputs:
|--------------------------------------------------------------------------
|
| p1 = example_normalize_price_steps('72.6531')   # "72.65"
| p2 = example_normalize_price_steps('250.26')    # "250.25"
| p3 = example_normalize_price_steps('250.38')    # "250.50"
| p4 = example_normalize_price_steps(1001.49)     # "1001.00"
|
| check = BistPayPriceStep.is_valid_price_step('250.30')
| {
|   'is_valid': False,
|   'step': 0.25,
|   'step_str': '0.250',
|   'band': '250.000 - 499.999',
|   'input': '250.3'
| }
|
"""