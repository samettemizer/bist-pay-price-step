import re
from typing import Union, Literal, Any


PriceInput = Union[str, int, float]
RoundMode = Literal["floor", "ceil", "nearest"]


class BistPayPriceStep:
    """
    BIST Pay Piyasası fiyat adımı hesabı

    kapsam dışı:
    - BYF
    - Varant
    - Sertifika

    bilgi:
    - web kancanıza ulaşan fiyat biçimsiz gelebileceği için str|int|float alayı desteklenir
    - https://github.com/samettemizer
    """

    # İç hesap ölçeği.
    # 6 hane, webhook'tan gelen ondalıklı fiyatlar için yeterince güvenlidir.
    INTERNAL_SCALE = 6

    @staticmethod
    def get_price_step(price: PriceInput) -> dict[str, Any]:
        """
        Fiyat bandına göre BIST fiyat adımını döndürür

        Returns:
            {
                'step': float,
                'stepStr': str,
                'band': str
            }
        """
        normalized = BistPayPriceStep._normalize_input(price)
        numeric = float(normalized)

        if numeric < 20:
            return {
                "step": 0.01,
                "stepStr": "0.010",
                "band": "0.010 - 19.999",
            }

        if numeric < 50:
            return {
                "step": 0.02,
                "stepStr": "0.020",
                "band": "20.000 - 49.999",
            }

        if numeric < 100:
            return {
                "step": 0.05,
                "stepStr": "0.050",
                "band": "50.000 - 99.999",
            }

        if numeric < 250:
            return {
                "step": 0.10,
                "stepStr": "0.100",
                "band": "100.000 - 249.999",
            }

        if numeric < 500:
            return {
                "step": 0.25,
                "stepStr": "0.250",
                "band": "250.000 - 499.999",
            }

        if numeric < 1000:
            return {
                "step": 0.50,
                "stepStr": "0.500",
                "band": "500.000 - 999.999",
            }

        if numeric < 2500:
            return {
                "step": 1.00,
                "stepStr": "1.000",
                "band": "1,000.000 - 2,499.999",
            }

        return {
            "step": 2.50,
            "stepStr": "2.500",
            "band": "2,500.000 ve üzeri",
        }

    @staticmethod
    def is_valid_price_step(price: PriceInput) -> dict[str, Any]:
        """
        Verilen fiyat, bulunduğu banda göre geçerli fiyat adımında mı?

        Returns:
            {
                'isValid': bool,
                'step': float,
                'stepStr': str,
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
            info["stepStr"],
            BistPayPriceStep.INTERNAL_SCALE
        )

        return {
            "isValid": (price_units % step_units) == 0,
            "step": info["step"],
            "stepStr": info["stepStr"],
            "band": info["band"],
            "input": normalized,
        }

    @staticmethod
    def round_price_to_step(price: PriceInput, mode: RoundMode = "nearest") -> dict[str, Any]:
        """
        Fiyatı geçerli adıma yuvarlar

        mode:
        - floor
        - ceil
        - nearest

        Returns:
            {
                'input': str,
                'output': str,
                'step': float,
                'stepStr': str,
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
            info["stepStr"],
            BistPayPriceStep.INTERNAL_SCALE
        )

        if mode == "floor":
            rounded_units = (price_units // step_units) * step_units
        elif mode == "ceil":
            rounded_units = ((price_units + step_units - 1) // step_units) * step_units
        elif mode == "nearest":
            rounded_units = BistPayPriceStep._round_nearest_units(price_units, step_units)
        else:
            raise ValueError('Geçersiz mode. "floor", "ceil" veya "nearest" kullan.')

        return {
            "input": normalized,
            "output": BistPayPriceStep._scaled_int_to_decimal(
                rounded_units,
                BistPayPriceStep.INTERNAL_SCALE,
                2
            ),
            "step": info["step"],
            "stepStr": info["stepStr"],
            "band": info["band"],
            "mode": mode,
        }

    @staticmethod
    def _normalize_input(price: PriceInput) -> str:
        """
        Ondalıklı değeri normalize eder

        Desteklenen örnekler:
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
            raise TypeError("Fiyat str, int veya float olmalı")

        if raw == "":
            raise ValueError("Fiyat boş olamaz.")

        raw = raw.replace("\u00A0", "").replace(" ", "")

        comma_pos = raw.rfind(",")
        dot_pos = raw.rfind(".")

        if comma_pos != -1 and dot_pos != -1:
            # Son görülen ayırıcıyı decimal separator kabul et
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
            raise ValueError(f"Geçersiz fiyat formatı: {raw}")

        parts = raw.split(".", 1)
        int_part = parts[0]
        frac_part = parts[1] if len(parts) > 1 else ""

        int_part = int_part.lstrip("0")
        if int_part == "":
            int_part = "0"

        frac_part = frac_part.rstrip("0")

        normalized = int_part if frac_part == "" else f"{int_part}.{frac_part}"

        if float(normalized) <= 0:
            raise ValueError("Fiyat sıfırdan büyük olmalı")

        return normalized

    @staticmethod
    def _decimal_to_scaled_int(number: str, scale: int) -> int:
        """
        Ondalıklı string değeri sabit ölçekli tam sayıya çevirir

        Örn scale=6:
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
        Sabit ölçekli tam sayıyı ondalıklı string'e çevirir
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
        nearest için yarım ve üzerini yukarı yuvarlar
        """
        quotient = price_units // step_units
        remainder = price_units % step_units

        if (remainder * 2) >= step_units:
            return (quotient + 1) * step_units

        return quotient * step_units


# örneğin "nearest" mod tercihi için..
def bist_calc_fiyat_adim(raw_price: PriceInput) -> str:
    return BistPayPriceStep.round_price_to_step(raw_price, "nearest")["output"]


"""
|--------------------------------------------------------------------------
| Teyit çıktıları:
|--------------------------------------------------------------------------
|
| p1 = bist_calc_fiyat_adim('72.6531')   # "72.65"
| p2 = bist_calc_fiyat_adim('250.26')    # "250.25"
| p3 = bist_calc_fiyat_adim('250.38')    # "250.50"
| p4 = bist_calc_fiyat_adim(1001.49)     # "1001.00"
|
| check = BistPayPriceStep.is_valid_price_step('250.30')
| {
|   'isValid': False,
|   'step': 0.25,
|   'stepStr': '0.250',
|   'band': '250.000 - 499.999',
|   'input': '250.3'
| }
|
"""