"""Project volumes forward using flat or seasonal methods."""


def project_volumes(
    actuals: dict[tuple[int, int], float],
    method: str,
    periods: list[tuple[int, int]],
) -> dict[tuple[int, int], tuple[float, bool]]:
    """
    Given actual volumes and a list of periods, return volumes for all periods.
    Returns dict of (year, quarter) -> (volume, is_projected).
    """
    result = {}

    # Find the last period with actual data
    last_actual_period = None
    last_actual_volume = 0.0
    for p in periods:
        if p in actuals:
            last_actual_period = p
            last_actual_volume = actuals[p]

    for year, quarter in periods:
        key = (year, quarter)
        if key in actuals:
            result[key] = (actuals[key], False)
        else:
            projected = _project_single(actuals, method, year, quarter, last_actual_volume)
            result[key] = (projected, True)

    return result


def _project_single(
    actuals: dict[tuple[int, int], float],
    method: str,
    year: int,
    quarter: int,
    last_actual_volume: float,
) -> float:
    if method == "seasonal":
        # Same quarter in the previous year
        prev_key = (year - 1, quarter)
        if prev_key in actuals:
            return actuals[prev_key]
        # Fall back to flat if no prior year data
        return last_actual_volume
    else:
        # Flat: repeat the last known volume
        return last_actual_volume
