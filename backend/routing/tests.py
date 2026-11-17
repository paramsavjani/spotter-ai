from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from . import planner, providers
from .risk import HIGH, LOW, MODERATE, NO_TRAVEL, SEVERE, checkpoint_risk, rain_level, snow_level, wind_level


class RiskRulesTest(SimpleTestCase):
    def test_wind_thresholds(self):
        self.assertEqual(wind_level(24.9), LOW)
        self.assertEqual(wind_level(25), MODERATE)
        self.assertEqual(wind_level(35), HIGH)
        self.assertEqual(wind_level(45), SEVERE)
        self.assertEqual(wind_level(55), NO_TRAVEL)

    def test_rain_thresholds(self):
        self.assertEqual(rain_level(0.09), LOW)
        self.assertEqual(rain_level(0.1), MODERATE)
        self.assertEqual(rain_level(0.3), HIGH)
        self.assertEqual(rain_level(1.0), SEVERE)
        self.assertEqual(rain_level(1.01), NO_TRAVEL)

    def test_snow_thresholds(self):
        self.assertEqual(snow_level(0.4), LOW)
        self.assertEqual(snow_level(0.5), MODERATE)
        self.assertEqual(snow_level(1.5), HIGH)
        self.assertEqual(snow_level(2.5), SEVERE)
        self.assertEqual(snow_level(3.1), NO_TRAVEL)

    def test_load_rules(self):
        self.assertEqual(checkpoint_risk(50, 0, 0, 30000)[0], SEVERE)
        self.assertEqual(checkpoint_risk(50, 0, 0, 30001)[0], NO_TRAVEL)
        self.assertEqual(checkpoint_risk(40, 0, 0, 40000)[0], HIGH)
        self.assertEqual(checkpoint_risk(40, 0, 0, 40001)[0], SEVERE)
        self.assertEqual(checkpoint_risk(60, 0, 0, 1000)[0], NO_TRAVEL)

    def test_worst_condition_wins(self):
        level, cause = checkpoint_risk(10, 0.6, 0.2, 20000)
        self.assertEqual((level, cause), (SEVERE, "rain"))


def fake_route(miles, hours):
    # a straight line split into 1-mile segments
    n = int(miles)
    return {
        "points": [(40.0, -100 + i * 0.0188) for i in range(n + 1)],
        "seg_dist": [planner.METERS_PER_MILE] * n,
        "seg_time": [hours * 3600 / n] * n,
        "distance_m": miles * planner.METERS_PER_MILE,
        "duration_s": hours * 3600,
    }


class CheckpointTest(SimpleTestCase):
    def test_spacing_and_eta(self):
        start = datetime(2026, 1, 1, 8, tzinfo=timezone.utc)
        cps = planner.make_checkpoints(fake_route(100, 2), start, 25)
        self.assertEqual([cp["mile"] for cp in cps], [0, 25, 50, 75, 100])
        self.assertEqual(cps[2]["eta"], "2026-01-01T09:00:00+00:00")

    def test_short_tail_is_merged(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        cps = planner.make_checkpoints(fake_route(102, 2), start, 25)
        self.assertEqual([cp["mile"] for cp in cps], [0, 25, 50, 75, 102])


def summary(**kw):
    base = {"blocked": False, "severe_miles": 0, "high_miles": 0, "avg_risk": 0.5, "duration_hours": 10}
    return {**base, **kw}


class RecommendationTest(SimpleTestCase):
    def test_severe_miles_beat_travel_time(self):
        fast = summary(id=0, severe_miles=20, duration_hours=8)
        slow = summary(id=1, duration_hours=11)
        best, reason = planner.recommend([fast, slow])
        self.assertEqual(best["id"], 1)
        self.assertIn("Severe", reason)

    def test_order_of_criteria(self):
        a = summary(id=0, high_miles=10, avg_risk=0.2)
        b = summary(id=1, high_miles=5, avg_risk=1.5)
        self.assertEqual(planner.recommend([a, b])[0]["id"], 1)

    def test_falls_back_to_time(self):
        a = summary(id=0, duration_hours=12)
        b = summary(id=1, duration_hours=9)
        self.assertEqual(planner.recommend([a, b])[0]["id"], 1)

    def test_risk_summary_uses_worse_end(self):
        cps = [
            {"mile": 0, "level": LOW},
            {"mile": 25, "level": SEVERE},
            {"mile": 50, "level": LOW},
        ]
        result = planner.risk_summary(cps)
        self.assertEqual(result["severe_miles"], 50)
        self.assertEqual(result["avg_risk"], 3)

    def test_blocked_route_is_never_recommended(self):
        blocked = summary(id=0, blocked=True, duration_hours=6)
        stormy = summary(id=1, severe_miles=40, duration_hours=9)
        best, reason = planner.recommend([blocked, stormy])
        self.assertEqual(best["id"], 1)
        self.assertIn("No Travel", reason)

    def test_all_blocked_gives_no_recommendation(self):
        routes = [summary(id=i, blocked=True) for i in range(3)]
        best, reason = planner.recommend(routes)
        self.assertIsNone(best)
        self.assertIn("No Travel", reason)

    def test_one_no_travel_checkpoint_blocks_the_route(self):
        cps = [{"mile": 0, "level": LOW}, {"mile": 25, "level": NO_TRAVEL}, {"mile": 50, "level": LOW}]
        result = planner.risk_summary(cps)
        self.assertTrue(result["blocked"])
        self.assertEqual(result["blocked_at"]["mile"], 25)


class EarliestDepartureTest(SimpleTestCase):
    def test_waits_until_the_wind_drops(self):
        departure = datetime(2026, 1, 1, 8, tzinfo=timezone.utc)
        checkpoints = planner.make_checkpoints(fake_route(100, 2), departure, 25)
        # 60 mph wind everywhere until 13:00, calm afterwards
        start = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp() // 3600)
        wind = [60] * 13 + [10] * 60
        forecast = {"start": start, "wind": wind, "rain": [0] * 73, "snow": [0] * 73}
        forecasts = [forecast] * len(checkpoints)
        for cp in checkpoints:
            planner.add_weather(cp, forecast, 20000)

        route = {"id": 0, "duration_hours": 2, "arrival": "2026-01-01T10:00:00+00:00",
                 "checkpoints": checkpoints, **planner.risk_summary(checkpoints)}
        self.assertTrue(route["blocked"])

        found = planner.find_earliest_departure([route], [forecasts], departure, 20000, latest=departure + timedelta(days=5))
        # leaving 13:00 means the first checkpoint is already in the calm hours
        self.assertEqual(found["wait_hours"], 5)
        self.assertEqual(found["departure"], "2026-01-01T13:00:00+00:00")
        self.assertEqual(found["arrival"], "2026-01-01T15:00:00+00:00")

    def test_none_when_it_never_clears(self):
        departure = datetime(2026, 1, 1, 8, tzinfo=timezone.utc)
        checkpoints = planner.make_checkpoints(fake_route(50, 1), departure, 25)
        start = int(departure.timestamp() // 3600)
        forecast = {"start": start, "wind": [70] * 100, "rain": [0] * 100, "snow": [0] * 100}
        for cp in checkpoints:
            planner.add_weather(cp, forecast, 20000)
        route = {"id": 0, "duration_hours": 1, "arrival": "2026-01-01T09:00:00+00:00",
                 "checkpoints": checkpoints, **planner.risk_summary(checkpoints)}
        found = planner.find_earliest_departure([route], [[forecast] * len(checkpoints)], departure, 20000,
                                                latest=departure + timedelta(days=5))
        self.assertIsNone(found)


class RouteOverlapTest(SimpleTestCase):
    def test_same_road_is_too_similar(self):
        road = fake_route(100, 2)
        almost_same = fake_route(100, 2)
        almost_same["points"] = [(lat + 0.005, lon) for lat, lon in almost_same["points"]]  # ~0.5 km apart
        other_road = fake_route(100, 2)
        other_road["points"] = [(lat + 0.5, lon) for lat, lon in other_road["points"]]  # ~55 km apart

        self.assertGreater(providers.shared_share(almost_same, road), 0.9)
        self.assertEqual(providers.shared_share(other_road, road), 0)
        self.assertTrue(providers._too_similar(almost_same, [road]))
        self.assertFalse(providers._too_similar(other_road, [road]))
