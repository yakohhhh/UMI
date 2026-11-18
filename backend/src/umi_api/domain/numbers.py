"""Rounding that matches the web app.

Every figure the API returns used to be computed in TypeScript with
Math.round, which rounds halves up. Python's round() rounds halves to even, so
porting a formula with it would shift some values by one unit.
"""

import math


def js_round(value: float) -> int:
    """Math.round(value)."""
    return math.floor(value + 0.5)


def round_to(value: float, decimals: int) -> float:
    """Math.round(value * 10^decimals) / 10^decimals."""
    factor = 10.0**decimals
    return js_round(value * factor) / factor


def js_number(value: float) -> str:
    """A number as a JavaScript template literal prints it: 7, 7.5, -3 (never 7.0)."""
    return str(int(value)) if float(value).is_integer() else repr(float(value))
