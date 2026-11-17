"""Thin wrappers around the free APIs we use: Photon (geocoding), OSRM (routes), Open-Meteo (weather)."""
import hashlib
import math
import time
from datetime import datetime, timezone

import requests
from django.conf import settings
from django.core.cache import cache

session = requests.Session()
session.headers["User-Agent"] = f"truck-weather-routing ({settings.APP_CONTACT})"


class ProviderError(Exception):
    pass


def _get(url, params, timeout=20):
    host = url.split("/")[2]
    try:
        resp = session.get(url, params=params, timeout=timeout)
        if resp.status_code == 429:  # rate limited: wait a moment and try once more
            time.sleep(3)
            resp = session.get(url, params=params, timeout=timeout)
    except requests.RequestException as exc:
        raise ProviderError(f"Could not reach {host}") from exc
    if resp.status_code == 429:
        raise ProviderError(f"{host} is rate limiting us (free tier). Please try again in a minute.")
    if resp.status_code != 200:
        raise ProviderError(f"{url.split('/')[2]} returned {resp.status_code}")
    return resp.json()


# ---- geocoding ----

def search_places(query, limit=5):
    key = "geo:" + hashlib.md5(f"{query.lower()}:{limit}".encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return cached

    data = _get("https://photon.komoot.io/api/", {"q": query, "limit": limit, "lang": "en"})
    places = []
    for feature in data.get("features", []):
        props = feature["properties"]
        lon, lat = feature["geometry"]["coordinates"]
        parts = [props.get("name"), props.get("city"), props.get("state"), props.get("country")]
        label = ", ".join(dict.fromkeys(p for p in parts if p))
        places.append({"label": label, "lat": lat, "lon": lon})

    cache.set(key, places, 24 * 3600)
    return places


# ---- routing ----

def _osrm_route(coords, alternatives=False):
    path = ";".join(f"{lon},{lat}" for lat, lon in coords)
    data = _get(
        f"{settings.OSRM_URL}/route/v1/driving/{path}",
        {
            "alternatives": "3" if alternatives else "false",
            "overview": "full",
            "geometries": "geojson",
            "annotations": "distance,duration",
            "steps": "false",
        },
        timeout=30,
    )
    if data.get("code") != "Ok":
        raise ProviderError(data.get("message") or "No route found between these places")
    return [_parse_route(r) for r in data["routes"]]


def _parse_route(raw):
    points = [(lat, lon) for lon, lat in raw["geometry"]["coordinates"]]
    seg_dist, seg_time = [], []
    for leg in raw["legs"]:
        seg_dist += leg["annotation"]["distance"]
        seg_time += leg["annotation"]["duration"]

    # With several legs the via point appears twice in the geometry; drop exact duplicates
    # so the point list lines up with the per-segment annotations.
    if len(points) != len(seg_dist) + 1:
        points = [p for i, p in enumerate(points) if i == 0 or p != points[i - 1]]
    if len(points) != len(seg_dist) + 1:
        seg_dist = [haversine_m(points[i], points[i + 1]) for i in range(len(points) - 1)]
        scale = raw["duration"] / max(sum(seg_dist), 1)
        seg_time = [d * scale for d in seg_dist]

    return {
        "points": points,
        "seg_dist": seg_dist,
        "seg_time": seg_time,
        "distance_m": raw["distance"],
        "duration_s": raw["duration"],
    }


# Two routes count as the same choice if most of one runs along the other.
MAX_SHARED = 0.7
CELL = 0.02  # degrees, about 2 km


def _cells(route):
    """Small grid cells the route passes through (long segments are filled in every 1 km)."""
    if "cells" not in route:
        cells = set()
        points = route["points"]
        for a, b, dist in zip(points, points[1:], route["seg_dist"]):
            steps = max(1, int(dist // 1000))
            for k in range(steps):
                f = k / steps
                lat = a[0] + f * (b[0] - a[0])
                lon = a[1] + f * (b[1] - a[1])
                cells.add((round(lat / CELL), round(lon / CELL)))
        route["cells"] = cells
    return route["cells"]


def shared_share(a, b):
    """Share of route a that runs within about 2 km of route b."""
    a_cells, b_cells = _cells(a), _cells(b)
    near = sum(1 for r, c in a_cells if any((r + i, c + j) in b_cells for i in (-1, 0, 1) for j in (-1, 0, 1)))
    return near / len(a_cells)


def _too_similar(route, others):
    return any(shared_share(route, o) > MAX_SHARED or shared_share(o, route) > MAX_SHARED for o in others)


def get_routes(origin, destination, wanted=3):
    """origin/destination are (lat, lon). Returns up to `wanted` clearly different routes, fastest first."""
    routes = []
    for route in _osrm_route([origin, destination], alternatives=True):
        if not _too_similar(route, routes):
            routes.append(route)

    # The public OSRM server often gives only 1-2 useful alternatives. To still offer a real choice
    # we ask for detours through points pushed sideways from the trip (at 1/2, 1/3 and 2/3 of it).
    if len(routes) < wanted:
        routes += get_detours(origin, destination, routes, (0.08, 0.15, 0.25, 0.35), 1.5, limit=wanted - len(routes))

    routes.sort(key=lambda r: r["duration_s"])
    return routes[:wanted]


def get_detours(origin, destination, existing, shares, max_ratio, limit=None):
    """Routes through via points pushed sideways by `shares` of the trip length.

    Detours longer than `max_ratio` times the fastest existing route, or mostly on the same roads
    as a route we already have, are skipped.
    """
    fastest = min(existing, key=lambda r: r["duration_s"])
    found = []
    for via in _side_points(origin, destination, shares):
        if limit is not None and len(found) >= limit:
            break
        try:
            candidate = _osrm_route([origin, via, destination])[0]
        except ProviderError:
            continue
        too_long = (
            candidate["distance_m"] > fastest["distance_m"] * max_ratio
            or candidate["duration_s"] > fastest["duration_s"] * max_ratio
        )
        if not too_long and not _too_similar(candidate, existing + found):
            found.append(candidate)
    return found


def _side_points(origin, destination, shares):
    """Points pushed sideways from the line between origin and destination, nearest first."""
    (lat1, lon1), (lat2, lon2) = origin, destination
    for share in shares:
        for t in (0.5, 0.33, 0.67):
            lat, lon = lat1 + t * (lat2 - lat1), lon1 + t * (lon2 - lon1)
            # work in a locally "flat" frame so the offset is perpendicular on the map
            k = math.cos(math.radians(lat))
            dx, dy = (lon2 - lon1) * k, lat2 - lat1
            for side in (1, -1):
                yield (lat + side * dx * share, lon - side * dy * share / k)


def haversine_m(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


# ---- weather ----

FORECAST_DAYS = 8
GRID = 0.25  # degrees, about the resolution of the forecast models


def snap(lat, lon):
    return round(round(lat / GRID) * GRID, 2), round(round(lon / GRID) * GRID, 2)


def get_forecasts(points):
    """Hourly forecast for each (lat, lon). Returns a list in the same order as `points`.

    Points are snapped to a 0.25 degree grid, so nearby checkpoints and heatmap cells share one
    lookup. Open-Meteo counts every location as a call, so this keeps the request count low.
    Each item: {"start": epoch hour of first value, "wind": [...mph], "rain": [...in/h], "snow": [...in/h]}
    """
    cells = [snap(lat, lon) for lat, lon in points]
    unique = list(dict.fromkeys(cells))
    keys = {cell: f"wx:{cell[0]:.2f},{cell[1]:.2f}" for cell in unique}
    found = cache.get_many(list(keys.values()))

    missing = [cell for cell in unique if keys[cell] not in found]
    for start in range(0, len(missing), 100):
        batch = missing[start:start + 100]
        data = _get(
            "https://api.open-meteo.com/v1/forecast",
            {
                "latitude": ",".join(f"{lat:.2f}" for lat, _ in batch),
                "longitude": ",".join(f"{lon:.2f}" for _, lon in batch),
                "hourly": "wind_speed_10m,rain,snowfall",
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
                "timezone": "GMT",
                "forecast_days": FORECAST_DAYS,
            },
            timeout=30,
        )
        if isinstance(data, dict):
            data = [data]
        fresh = {}
        for cell, item in zip(batch, data):
            hourly = item["hourly"]
            first = datetime.fromisoformat(hourly["time"][0]).replace(tzinfo=timezone.utc)
            fresh[keys[cell]] = {
                "start": int(first.timestamp() // 3600),
                "wind": [v or 0 for v in hourly["wind_speed_10m"]],
                "rain": [v or 0 for v in hourly["rain"]],
                "snow": [v or 0 for v in hourly["snowfall"]],
            }
        cache.set_many(fresh, 60 * 60)
        found.update(fresh)

    return [found[keys[cell]] for cell in cells]


def weather_at(forecast, when):
    """Values for the forecast hour closest to `when` (aware datetime). None if outside the forecast."""
    index = round(when.timestamp() / 3600) - forecast["start"]
    if not 0 <= index < len(forecast["wind"]):
        return None
    return forecast["wind"][index], forecast["rain"][index], forecast["snow"][index]
