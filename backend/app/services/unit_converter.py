"""Unit conversion between kg, t (tonnes), and lb (pounds)."""

CONVERSIONS = {
    ("kg", "t"): 0.001,
    ("kg", "lb"): 2.20462,
    ("t", "kg"): 1000,
    ("t", "lb"): 2204.62,
    ("lb", "kg"): 0.453592,
    ("lb", "t"): 0.000453592,
}


def convert_unit(value: float, from_unit: str, to_unit: str) -> float:
    """Convert a mass quantity from one unit to another."""
    if from_unit == to_unit:
        return value
    key = (from_unit.lower(), to_unit.lower())
    if key not in CONVERSIONS:
        raise ValueError(f"Unknown unit conversion: {from_unit} -> {to_unit}")
    return value * CONVERSIONS[key]


def convert_price_per_unit(value: float, from_unit: str, to_unit: str) -> float:
    """Convert a price-per-unit. $3/t -> $0.003/kg (inverse of mass conversion)."""
    if from_unit == to_unit:
        return value
    key = (from_unit.lower(), to_unit.lower())
    if key not in CONVERSIONS:
        raise ValueError(f"Unknown unit conversion: {from_unit} -> {to_unit}")
    # Price per unit is inversely proportional to mass conversion
    # If 1t = 1000kg, then $3/t = $3/1000kg = $0.003/kg
    factor = CONVERSIONS[key]
    if factor == 0:
        return value
    return value / factor
