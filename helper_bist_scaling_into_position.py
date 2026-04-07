import math
from typing import Any
from helper_bist_price_steps import BistPayPriceStep
from helper_bist_price_steps import example_normalize_price_steps
from helper_bist_price_steps import PriceInput

class BistScalingIntoPosition:
    """
    BIST Pay Market – Scale into a position with stepped limit orders.

    Generates a downward or upward price ladder from a starting price and
    distributes a total budget equally across every step.
    """

    # -----------------------------------------------------------------------
    # Single-step navigation helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def one_step_down(price: PriceInput) -> str:
        """
        Returns the next valid BIST price one step below the given price.

        Examples:
            20.70  -> 20.68
            20.00  -> 19.99
            250.00 -> 249.90
        """
        current = BistPayPriceStep.round_price_to_step(price, "nearest")["output"]
        probe = float(current) - 0.001

        if probe <= 0:
            raise RuntimeError(
                "Cannot calculate one step down: price would reach or go below zero."
            )

        return BistPayPriceStep.round_price_to_step(probe, "floor")["output"]

    @staticmethod
    def one_step_up(price: PriceInput) -> str:
        """
        Returns the next valid BIST price one step above the given price.

        Examples:
            20.70  -> 20.72
            19.99  -> 20.00
            249.90 -> 250.00
        """
        current = BistPayPriceStep.round_price_to_step(price, "nearest")["output"]
        info = BistPayPriceStep.get_price_step(current)

        next_probe = float(current) + float(info["step"])
        next_price = BistPayPriceStep.round_price_to_step(next_probe, "ceil")["output"]

        if float(next_price) <= float(current):
            raise RuntimeError("Cannot calculate one step up: price did not increase.")

        return next_price

    # -----------------------------------------------------------------------
    # Scaled order builders
    # -----------------------------------------------------------------------

    @staticmethod
    def scale_orders_down(
        symbol: str,
        limit_price: PriceInput,
        budget: float,
        max_drop_pct: float = 1.25,
    ) -> dict[str, Any]:
        """
        Builds a downward price ladder of buy orders starting from a limit price.

        Behaviour:
        - Normalises the starting price to a valid BIST step
        - Calculates the lower boundary price using max_drop_pct
        - The lower boundary is rounded UP to the nearest valid step so it
          is never breached
        - Generates every downward step from the top price to the boundary
        - Divides the total budget equally across all steps
        - Calculates integer lot quantities per step
        - Returns a summary dict; call your own order-placement method per entry

        Note:
        - The actual per-step amount may differ slightly from the target
          because lot quantities must be whole numbers.

        Args:
            symbol:       Ticker symbol (e.g. "EXMPL")
            limit_price:  Starting (top) price of the ladder
            budget:       Total budget to distribute across all steps
            max_drop_pct: Maximum downward range as a percentage (default 1.25 %)

        Returns:
            {
                'symbol':              str,
                'top_price':           str,
                'bottom_raw_price':    str,   # raw boundary before rounding
                'bottom_price':        str,   # boundary after ceil rounding
                'max_drop_pct':        float,
                'step_count':          int,
                'target_step_budget':  str,
                'actual_total_budget': str,
                'remaining_budget':    str,
                'total_quantity':      int,
                'orders': [
                    {
                        'price':               str,
                        'quantity':            int,
                        'target_step_budget':  str,
                        'actual_step_budget':  str,
                    },
                    ...
                ]
            }
        """
        symbol = symbol.strip()

        if not symbol:
            raise ValueError("Symbol cannot be empty.")
        if budget <= 0:
            raise ValueError("Budget must be greater than zero.")
        if max_drop_pct < 0:
            raise ValueError("max_drop_pct cannot be negative.")

        # Normalise the starting price to a valid BIST step
        top_price = example_normalize_price_steps(limit_price)
        top_price_float = float(top_price)

        # Calculate the raw lower boundary
        bottom_raw_price = top_price_float * (1 - (max_drop_pct / 100))

        if bottom_raw_price <= 0:
            raise RuntimeError("Lower boundary price evaluated to an invalid value.")

        # Round the lower boundary UP so we never breach it
        bottom_price = BistPayPriceStep.round_price_to_step(bottom_raw_price, "ceil")["output"]
        bottom_price_float = float(bottom_price)

        # Generate all price steps from top down to the boundary
        prices: list[str] = []
        current = top_price

        while float(current) >= bottom_price_float:
            prices.append(current)
            next_price = BistScalingIntoPosition.one_step_down(current)

            # Safety brake: price must strictly decrease on every iteration
            if float(next_price) >= float(current):
                raise RuntimeError(
                    "Price did not decrease during step generation. Loop aborted."
                )

            current = next_price

        if not prices:
            raise RuntimeError("No price steps could be generated.")

        step_count = len(prices)
        target_step_budget = budget / step_count

        # If even the first (most expensive) step cannot buy 1 lot, the plan is invalid
        if target_step_budget < top_price_float:
            raise RuntimeError(
                "Budget is insufficient to buy at least 1 lot at every generated step."
            )

        orders: list[dict[str, Any]] = []
        total_quantity = 0
        actual_total_budget = 0.0

        for price in prices:
            price_float = float(price)
            quantity = int(math.floor(target_step_budget / price_float))

            if quantity < 1:
                raise RuntimeError(
                    f"Step budget is not enough to buy 1 lot at price {price}."
                )

            actual_step_budget = quantity * price_float

            # Place your async buy order here:
            # buy_async(symbol, quantity, price)

            total_quantity += quantity
            actual_total_budget += actual_step_budget

            orders.append(
                {
                    "price": price,
                    "quantity": quantity,
                    "target_step_budget": f"{target_step_budget:.2f}",
                    "actual_step_budget": f"{actual_step_budget:.2f}",
                }
            )

        return {
            "symbol": symbol,
            "top_price": top_price,
            "bottom_raw_price": f"{bottom_raw_price:.4f}",
            "bottom_price": bottom_price,
            "max_drop_pct": max_drop_pct,
            "step_count": step_count,
            "target_step_budget": f"{target_step_budget:.2f}",
            "actual_total_budget": f"{actual_total_budget:.2f}",
            "remaining_budget": f"{budget - actual_total_budget:.2f}",
            "total_quantity": total_quantity,
            "orders": orders,
        }

    @staticmethod
    def scale_orders_up(
        symbol: str,
        limit_price: PriceInput,
        budget: float,
        max_rise_pct: float = 0.4,
    ) -> dict[str, Any]:
        """
        Builds an upward price ladder of buy orders starting from a limit price.

        Behaviour:
        - Normalises the starting price to a valid BIST step
        - Calculates the upper boundary price using max_rise_pct
        - The upper boundary is rounded DOWN to the nearest valid step so it
          is never breached
        - Generates every upward step from the bottom price to the boundary
        - Divides the total budget equally across all steps
        - Calculates integer lot quantities per step
        - Returns a summary dict; call your own order-placement method per entry

        Note:
        - The actual per-step amount may differ slightly from the target
          because lot quantities must be whole numbers.

        Args:
            symbol:       Ticker symbol (e.g. "EXMPL")
            limit_price:  Starting (bottom) price of the ladder
            budget:       Total budget to distribute across all steps
            max_rise_pct: Maximum upward range as a percentage (default 0.4 %)

        Returns:
            {
                'symbol':              str,
                'bottom_price':        str,
                'top_raw_price':       str,   # raw boundary before rounding
                'top_price':           str,   # boundary after floor rounding
                'max_rise_pct':        float,
                'step_count':          int,
                'target_step_budget':  str,
                'actual_total_budget': str,
                'remaining_budget':    str,
                'total_quantity':      int,
                'orders': [
                    {
                        'price':               str,
                        'quantity':            int,
                        'target_step_budget':  str,
                        'actual_step_budget':  str,
                    },
                    ...
                ]
            }
        """
        symbol = symbol.strip()

        if not symbol:
            raise ValueError("Symbol cannot be empty.")
        if budget <= 0:
            raise ValueError("Budget must be greater than zero.")
        if max_rise_pct < 0:
            raise ValueError("max_rise_pct cannot be negative.")

        # Normalise the starting price to a valid BIST step
        bottom_price = example_normalize_price_steps(limit_price)
        bottom_price_float = float(bottom_price)

        # Calculate the raw upper boundary
        top_raw_price = bottom_price_float * (1 + (max_rise_pct / 100))

        if top_raw_price <= 0:
            raise RuntimeError("Upper boundary price evaluated to an invalid value.")

        # Round the upper boundary DOWN so we never breach it
        top_price = BistPayPriceStep.round_price_to_step(top_raw_price, "floor")["output"]
        top_price_float = float(top_price)

        # Generate all price steps from bottom up to the boundary
        prices: list[str] = []
        current = bottom_price

        while float(current) <= top_price_float:
            prices.append(current)
            next_price = BistScalingIntoPosition.one_step_up(current)

            # Safety brake: price must strictly increase on every iteration
            if float(next_price) <= float(current):
                raise RuntimeError(
                    "Price did not increase during step generation. Loop aborted."
                )

            current = next_price

        if not prices:
            raise RuntimeError("No price steps could be generated.")

        step_count = len(prices)
        target_step_budget = budget / step_count

        # If even the last (most expensive) step cannot buy 1 lot, the plan is invalid
        if target_step_budget < top_price_float:
            raise RuntimeError(
                "Budget is insufficient to buy at least 1 lot at every generated step."
            )

        orders: list[dict[str, Any]] = []
        total_quantity = 0
        actual_total_budget = 0.0

        for price in prices:
            price_float = float(price)
            quantity = int(math.floor(target_step_budget / price_float))

            if quantity < 1:
                raise RuntimeError(
                    f"Step budget is not enough to buy 1 lot at price {price}."
                )

            actual_step_budget = quantity * price_float

            # Place your async buy order here:
            # buy_async(symbol, quantity, price)

            total_quantity += quantity
            actual_total_budget += actual_step_budget

            orders.append(
                {
                    "price": price,
                    "quantity": quantity,
                    "target_step_budget": f"{target_step_budget:.2f}",
                    "actual_step_budget": f"{actual_step_budget:.2f}",
                }
            )

        return {
            "symbol": symbol,
            "bottom_price": bottom_price,
            "top_raw_price": f"{top_raw_price:.4f}",
            "top_price": top_price,
            "max_rise_pct": max_rise_pct,
            "step_count": step_count,
            "target_step_budget": f"{target_step_budget:.2f}",
            "actual_total_budget": f"{actual_total_budget:.2f}",
            "remaining_budget": f"{budget - actual_total_budget:.2f}",
            "total_quantity": total_quantity,
            "orders": orders,
        }


"""
|--------------------------------------------------------------------------
| Verification outputs:
|--------------------------------------------------------------------------
|
| down = BistScalingIntoPosition.scale_orders_down("EXMPL", "20.70", 10000)
| # Ladder steps downward from 20.70, spread over ~1.25 % range
|
| up = BistScalingIntoPosition.scale_orders_up("EXMPL", "20.70", 10000)
| # Ladder steps upward from 20.70, spread over ~0.40 % range
|
| one_down = BistScalingIntoPosition.one_step_down("20.70")   # "20.68"
| one_up   = BistScalingIntoPosition.one_step_up("20.70")     # "20.72"
|
| one_down_band = BistScalingIntoPosition.one_step_down("20.00")   # "19.99"
| one_up_band   = BistScalingIntoPosition.one_step_up("19.99")     # "20.00"
|
"""
