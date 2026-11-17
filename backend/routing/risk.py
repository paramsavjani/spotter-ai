LOW, MODERATE, HIGH, SEVERE, NO_TRAVEL = range(5)
LEVEL_NAMES = ["Low", "Moderate", "High", "Severe", "No Travel"]


def wind_level(mph):
    if mph >= 55:
        return NO_TRAVEL
    if mph >= 45:
        return SEVERE
    if mph >= 35:
        return HIGH
    if mph >= 25:
        return MODERATE
    return LOW


def rain_level(inches_per_hour):
    if inches_per_hour > 1.0:
        return NO_TRAVEL
    if inches_per_hour >= 0.5:
        return SEVERE
    if inches_per_hour >= 0.25:
        return HIGH
    if inches_per_hour >= 0.1:
        return MODERATE
    return LOW


def snow_level(inches_per_hour):
    if inches_per_hour > 3.0:
        return NO_TRAVEL
    if inches_per_hour >= 2.0:
        return SEVERE
    if inches_per_hour >= 1.0:
        return HIGH
    if inches_per_hour >= 0.5:
        return MODERATE
    return LOW


def wind_level_for_load(mph, load_lbs):
    level = wind_level(mph)
    if 45 <= mph < 55 and load_lbs > 30000:
        level = NO_TRAVEL
    elif 35 <= mph < 45 and load_lbs > 40000:
        level = SEVERE
    return level


def checkpoint_risk(wind_mph, rain_in, snow_in, load_lbs):
    """Returns the overall level and which condition caused it."""
    levels = {
        "wind": wind_level_for_load(wind_mph, load_lbs),
        "rain": rain_level(rain_in),
        "snow": snow_level(snow_in),
    }
    cause = max(levels, key=levels.get)
    return levels[cause], cause


def heat_value(wind_mph, rain_in, snow_in, load_lbs):
    """0..1 intensity for the heatmap, where 1 means the No Travel threshold is reached."""
    wind_limit = 45 if load_lbs > 30000 else 55
    value = max(wind_mph / wind_limit, rain_in / 1.0, snow_in / 3.0)
    return round(min(value, 1.0), 2)
