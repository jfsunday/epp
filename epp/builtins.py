"""Built-in functions for E++: say, ask, random_between."""

import random as _random


def format_value(value: object) -> str:
    """Format a value for Say output."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        if value == int(value):
            return str(int(value))
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(format_value(v) for v in value) + "]"
    if isinstance(value, dict):
        entries = ", ".join(f"{k}: {format_value(v)}" for k, v in value.items())
        return "{" + entries + "}"
    return str(value)


def ask_auto_detect(prompt: str, *, input_fn=None) -> object:
    """Ask the user for input; auto-detect number vs text."""
    if input_fn is None:
        input_fn = input
    raw = input_fn(prompt)
    # Try to parse as number
    try:
        if '.' in raw:
            return float(raw)
        return float(int(raw))  # store as float for consistency
    except ValueError:
        return raw


def random_between(low: float, high: float) -> float:
    """Return a random integer between low and high (inclusive)."""
    return float(_random.randint(int(low), int(high)))
