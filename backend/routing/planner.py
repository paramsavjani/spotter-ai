import math
from bisect import bisect_left
from datetime import datetime, timedelta, timezone

from . import providers
from .risk import HIGH, LEVEL_NAMES, NO_TRAVEL, SEVERE, checkpoint_risk, heat_value

METERS_PER_MILE = 1609.344
HEATMAP_HOURS = 48  # never more than this, even for very long trips
MAX_DEPARTURE_DAYS = 5  # forecast range we accept for a departure
MAX_WAIT_HOURS = 72  # how far ahead we look for a safe departure


def plan(origin, destination, departure, load_lbs, interval_miles):
    start = (origin["lat"], origin["lon"])
    end = (destination["lat"], destination["lon"])
    routes = providers.get_routes(start, end)
    summaries, forecasts = score_routes(routes, departure, load_lbs, interval_miles)

    # A route with a No Travel checkpoint can't be driven. If every route is blocked,
    # look for the earliest departure time at which one of them is clear.
    all_blocked = all(s["blocked"] for s in summaries)
    earliest = find_earliest_departure(summaries, forecasts, departure, load_lbs) if all_blocked else None

    best, reason = recommend(summaries)
    for s in summaries:
        s["recommended"] = best is not None and s["id"] == best["id"]

    return {
        "origin": origin,
        "destination": destination,
        "departure": departure.isoformat(),
        "load_lbs": load_lbs,
        "interval_miles": interval_miles,
        "routes": summaries,
        "recommended_id": best["id"] if best else None,
        "recommendation_reason": reason,
        "all_blocked": all_blocked,
        "earliest_departure": earliest,
        "heatmap": build_heatmap(routes, departure, load_lbs),
    }


def score_routes(routes, departure, load_lbs, interval_miles):
    """Checkpoints, weather and risk for each route.

    Also returns the forecast of every checkpoint so we can re-check other departure times later.
    """
    all_checkpoints = [make_checkpoints(r, departure, interval_miles) for r in routes]
    flat = [cp for cps in all_checkpoints for cp in cps]
    flat_forecasts = providers.get_forecasts([(cp["lat"], cp["lon"]) for cp in flat])
    for cp, forecast in zip(flat, flat_forecasts):
        add_weather(cp, forecast, load_lbs)

    summaries, forecasts = [], []
    pos = 0
    for i, (route, checkpoints) in enumerate(zip(routes, all_checkpoints)):
        forecasts.append(flat_forecasts[pos:pos + len(checkpoints)])
        pos += len(checkpoints)
        summaries.append({
            "id": i,
            "distance_miles": round(route["distance_m"] / METERS_PER_MILE, 1),
            "duration_hours": round(route["duration_s"] / 3600, 2),
            "arrival": (departure + timedelta(seconds=route["duration_s"])).isoformat(),
            "path": [[round(lat, 5), round(lon, 5)] for lat, lon in simplify(route["points"])],
            "checkpoints": checkpoints,
            **risk_summary(checkpoints),
        })
    return summaries, forecasts


def find_earliest_departure(summaries, forecasts, departure, load_lbs, latest=None):
    """First hour after `departure` at which one of the routes has no No Travel checkpoint.

    Route geometry and travel times stay the same; only the clock moves, so every checkpoint is
    looked up again in the forecast we already have.
    """
    if latest is None:
        latest = datetime.now(timezone.utc) + timedelta(days=MAX_DEPARTURE_DAYS)

    for wait in range(1, MAX_WAIT_HOURS + 1):
        leave = departure + timedelta(hours=wait)
        if leave > latest:
            break
        options = []
        for summary, route_forecasts in zip(summaries, forecasts):
            checkpoints = shift_checkpoints(summary["checkpoints"], route_forecasts, wait, load_lbs)
            risk = risk_summary(checkpoints)
            if not risk["blocked"] and not risk["missing_forecast"]:
                options.append({**summary, **risk})
        if options:
            best = min(options, key=ranking_key)
            return {
                "departure": leave.isoformat(),
                "wait_hours": wait,
                "route_id": best["id"],
                "arrival": (datetime.fromisoformat(best["arrival"]) + timedelta(hours=wait)).isoformat(),
                "severe_miles": best["severe_miles"],
                "high_miles": best["high_miles"],
            }
    return None


def shift_checkpoints(checkpoints, forecasts, hours, load_lbs):
    shifted = []
    for cp, forecast in zip(checkpoints, forecasts):
        eta = datetime.fromisoformat(cp["eta"]) + timedelta(hours=hours)
        new = {"lat": cp["lat"], "lon": cp["lon"], "mile": cp["mile"], "eta": eta.isoformat()}
        add_weather(new, forecast, load_lbs)
        shifted.append(new)
    return shifted


def make_checkpoints(route, departure, interval_miles):
    """Checkpoints every `interval_miles` along the route (plus the destination), with ETAs."""
    cum_dist, cum_time = [0.0], [0.0]
    for d, t in zip(route["seg_dist"], route["seg_time"]):
        cum_dist.append(cum_dist[-1] + d)
        cum_time.append(cum_time[-1] + t)

    total = cum_dist[-1]
    step = interval_miles * METERS_PER_MILE
    marks = [n * step for n in range(int(total // step) + 1)]
    if total - marks[-1] > step * 0.2 or len(marks) == 1:
        marks.append(total)
    else:
        marks[-1] = total  # a tiny last stretch is merged into the previous checkpoint

    checkpoints = []
    points = route["points"]
    for mark in marks:
        i = min(max(bisect_left(cum_dist, mark), 1), len(cum_dist) - 1)
        seg = cum_dist[i] - cum_dist[i - 1]
        f = (mark - cum_dist[i - 1]) / seg if seg else 0
        lat = points[i - 1][0] + f * (points[i][0] - points[i - 1][0])
        lon = points[i - 1][1] + f * (points[i][1] - points[i - 1][1])
        seconds = cum_time[i - 1] + f * (cum_time[i] - cum_time[i - 1])
        checkpoints.append({
            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "mile": round(mark / METERS_PER_MILE, 1),
            "eta": (departure + timedelta(seconds=seconds)).isoformat(),
        })
    return checkpoints


def add_weather(cp, forecast, load_lbs):
    values = providers.weather_at(forecast, datetime.fromisoformat(cp["eta"]))
    if values is None:
        cp.update(wind_mph=None, rain_in=None, snow_in=None, level=None, level_name="No forecast", cause=None)
        return
    wind, rain, snow = values
    level, cause = checkpoint_risk(wind, rain, snow, load_lbs)
    cp.update(
        wind_mph=round(wind, 1),
        rain_in=round(rain, 2),
        snow_in=round(snow, 2),
        level=level,
        level_name=LEVEL_NAMES[level],
        cause=cause if level > 0 else None,
    )


def risk_summary(checkpoints):
    """Miles at each level. The stretch between two checkpoints counts at the worse of the two."""
    miles = [0.0] * len(LEVEL_NAMES)
    weighted = 0.0
    covered = 0.0
    for a, b in zip(checkpoints, checkpoints[1:]):
        levels = [cp["level"] for cp in (a, b) if cp["level"] is not None]
        if not levels:
            continue
        stretch = b["mile"] - a["mile"]
        level = max(levels)
        miles[level] += stretch
        weighted += level * stretch
        covered += stretch

    known = [cp for cp in checkpoints if cp["level"] is not None]
    stop = next((cp for cp in checkpoints if cp["level"] == NO_TRAVEL), None)
    return {
        "blocked": stop is not None,
        "blocked_at": stop,
        "miles_by_level": {LEVEL_NAMES[i]: round(m, 1) for i, m in enumerate(miles)},
        "no_travel_miles": round(miles[NO_TRAVEL], 1),
        "severe_miles": round(miles[SEVERE], 1),
        "high_miles": round(miles[HIGH], 1),
        "avg_risk": round(weighted / covered, 2) if covered else None,
        "worst_level": LEVEL_NAMES[max(cp["level"] for cp in known)] if known else None,
        "missing_forecast": len(known) < len(checkpoints),
    }


def ranking_key(route):
    # Blocked routes are removed before this, so the order is the one from the brief.
    return (
        route["severe_miles"],
        route["high_miles"],
        route["avg_risk"] if route["avg_risk"] is not None else 99,
        route["duration_hours"],
    )


def recommend(routes):
    usable = [r for r in routes if not r["blocked"]]
    if not usable:
        return None, "Every route crosses a No Travel zone at this departure time."

    ordered = sorted(usable, key=ranking_key)
    best = ordered[0]
    if len(ordered) == 1:
        if len(routes) > 1:
            return best, "The other routes cross a No Travel zone."
        return best, "Only one route was found."

    runner_up = ordered[1]
    reasons = ["fewer Severe miles", "fewer High-risk miles", "lower average risk", "shortest travel time"]
    for reason, a, b in zip(reasons, ranking_key(best), ranking_key(runner_up)):
        if a != b:
            return best, f"Picked for {reason}."
    return best, "All routes look the same, picked the fastest."


def simplify(points, every_m=800):
    """Drop points closer than `every_m` to the previous kept one. Keeps the payload small."""
    kept = [points[0]]
    for p in points[1:-1]:
        if providers.haversine_m(kept[-1], p) >= every_m:
            kept.append(p)
    kept.append(points[-1])
    return kept


def build_heatmap(routes, departure, load_lbs):
    """Weather intensity on a grid around the routes for each hour from departure until the
    slowest route arrives (at most 48 h)."""
    longest = max(r["distance_m"] for r in routes) / METERS_PER_MILE
    # Degrees; multiples of the 0.25 forecast grid so cells share cached lookups with checkpoints.
    # Every cell is one Open-Meteo call, so the grid stays coarse; the map blurs it smoothly.
    cell = 0.5 if longest < 800 else 1.0
    spread = 1

    cells = set()
    for route in routes:
        for lat, lon in route["points"][::10]:
            r, c = round(lat / cell), round(lon / cell)
            for dr in range(-spread, spread + 1):
                for dc in range(-spread, spread + 1):
                    cells.add((r + dr, c + dc))

    grid = sorted((r * cell, c * cell) for r, c in cells)
    forecasts = providers.get_forecasts(grid)

    start_hour = int(departure.timestamp() // 3600)
    last_arrival = departure.timestamp() + max(r["duration_s"] for r in routes)
    hours = min(math.ceil(last_arrival / 3600) - start_hour, HEATMAP_HOURS)
    frames = []
    for h in range(hours + 1):
        frame = []
        for fc in forecasts:
            i = start_hour + h - fc["start"]
            if 0 <= i < len(fc["wind"]):
                frame.append(heat_value(fc["wind"][i], fc["rain"][i], fc["snow"][i], load_lbs))
            else:
                frame.append(0)
        frames.append(frame)

    return {
        "points": [[round(lat, 3), round(lon, 3)] for lat, lon in grid],
        "cell_deg": cell,
        "start": departure.replace(minute=0, second=0, microsecond=0).isoformat(),
        "frames": frames,
    }
