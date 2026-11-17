import json
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import planner, providers

ALLOWED_INTERVALS = (10, 25, 50)
MAX_LOAD_LBS = 80000


@require_GET
def geocode(request):
    query = request.GET.get("q", "").strip()
    if len(query) < 3:
        return JsonResponse({"results": []})
    try:
        return JsonResponse({"results": providers.search_places(query)})
    except providers.ProviderError as exc:
        return JsonResponse({"error": str(exc)}, status=502)


@csrf_exempt
@require_POST
def plan_trip(request):
    try:
        body = json.loads(request.body)
        origin = _place(body.get("origin"), "origin")
        destination = _place(body.get("destination"), "destination")
        departure = _departure(body.get("departure"))
        load_lbs = float(body.get("load_lbs", 0))
        interval = int(body.get("interval_miles", 25))
    except (ValueError, TypeError, KeyError) as exc:
        return JsonResponse({"error": str(exc) if isinstance(exc, ValueError) else "Invalid request"}, status=400)

    if not 0 < load_lbs <= MAX_LOAD_LBS:
        return JsonResponse({"error": f"Load must be between 1 and {MAX_LOAD_LBS:,} lb"}, status=400)
    if interval not in ALLOWED_INTERVALS:
        return JsonResponse({"error": "Checkpoint interval must be 10, 25 or 50 miles"}, status=400)

    try:
        result = planner.plan(origin, destination, departure, load_lbs, interval)
    except providers.ProviderError as exc:
        return JsonResponse({"error": str(exc)}, status=502)
    return JsonResponse(result)


def _place(value, name):
    if not isinstance(value, dict):
        raise ValueError(f"Missing {name}")
    lat, lon = float(value["lat"]), float(value["lon"])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"Bad coordinates for {name}")
    return {"label": str(value.get("label", ""))[:200], "lat": lat, "lon": lon}


def _departure(value):
    if not value:
        return datetime.now(timezone.utc).replace(microsecond=0)
    when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if when < now - timedelta(hours=1):
        raise ValueError("Departure time is in the past")
    if when > now + timedelta(days=planner.MAX_DEPARTURE_DAYS):
        raise ValueError("Departure must be within the next 5 days (weather forecast range)")
    return when.replace(microsecond=0)


def frontend(request):
    index = settings.FRONTEND_DIR / "index.html"
    if not index.exists():
        return HttpResponse("Frontend not built. Run the React dev server (see README).", status=404)
    return HttpResponse(index.read_text(), content_type="text/html")
