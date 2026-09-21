"""
BusNotify - Historical Delay Statistics Service
Strictly adheres to Section 3 and Section 14:
- Pure descriptive statistics: count, mean, min, max, median, std_dev, p50, p90, on_time_percentage.
- Expected delay = Historical mean.
- Expected range = [max(0, mean - 1.96 * std_dev), mean + 1.96 * std_dev].
- Sample count < 5 fallback to route-level stats with "Limited historical data" indicator.
- Explicit labeling and disclaimer on every output.
- ZERO AI / ML.
"""
import numpy as np
from typing import Dict, Any, Optional
from sqlalchemy import func
from app.extensions import db
from app.models.delay import HistoricalDelay
from app.models.transit import Route, Stop

DISCLAIMER_TEXT = "This is a historical statistical estimate based on previous trip records and is not a guarantee."
LABEL_TEXT = "Historical statistical estimate"


class DelayStatisticsService:

    @staticmethod
    def calculate_stats(delay_records: list[float]) -> Dict[str, Any]:
        """
        Calculates descriptive statistics from a list of delay minutes.
        """
        if not delay_records:
            return {
                "count": 0,
                "mean": 0.0,
                "median": 0.0,
                "min": 0.0,
                "max": 0.0,
                "std_dev": 0.0,
                "p50": 0.0,
                "p90": 0.0,
                "on_time_percentage": 100.0,
                "expected_delay": 0.0,
                "expected_range_min": 0.0,
                "expected_range_max": 0.0,
                "label": LABEL_TEXT,
                "disclaimer": DISCLAIMER_TEXT,
                "limited_data": True,
                "message": "Limited historical data",
            }

        arr = np.array(delay_records, dtype=float)
        count = int(len(arr))
        mean_val = float(np.mean(arr))
        median_val = float(np.median(arr))
        min_val = float(np.min(arr))
        max_val = float(np.max(arr))
        std_val = float(np.std(arr, ddof=1)) if count > 1 else 0.0
        p50_val = float(np.percentile(arr, 50))
        p90_val = float(np.percentile(arr, 90))

        # On-time defined as delay <= 5 minutes
        on_time_count = int(np.sum(arr <= 5.0))
        on_time_pct = round((on_time_count / count) * 100.0, 1)

        # Confidence interval: max(0, mean - 1.96 * std) to mean + 1.96 * std
        range_min = max(0.0, round(mean_val - 1.96 * std_val, 1))
        range_max = round(mean_val + 1.96 * std_val, 1)

        is_limited = count < 5

        return {
            "count": count,
            "mean": round(mean_val, 1),
            "median": round(median_val, 1),
            "min": round(min_val, 1),
            "max": round(max_val, 1),
            "std_dev": round(std_val, 1),
            "p50": round(p50_val, 1),
            "p90": round(p90_val, 1),
            "on_time_percentage": on_time_pct,
            "expected_delay": round(mean_val, 1),
            "expected_range_min": range_min,
            "expected_range_max": range_max,
            "label": LABEL_TEXT,
            "disclaimer": DISCLAIMER_TEXT,
            "limited_data": is_limited,
            "message": "Limited historical data" if is_limited else "Sufficient statistical sample",
        }

    @classmethod
    def get_stop_delay_stats(cls, route_id: int, stop_id: int,
                             weekday: Optional[int] = None,
                             hour: Optional[int] = None) -> Dict[str, Any]:
        """
        Retrieves historical delays for a specific route and stop,
        falling back to the entire route if stop samples < 5.
        """
        query = db.session.query(HistoricalDelay.delay_minutes).filter(
            HistoricalDelay.route_id == route_id,
            HistoricalDelay.stop_id == stop_id
        )

        if weekday is not None:
            query = query.filter(HistoricalDelay.weekday == weekday)
        if hour is not None:
            # Cluster ± 1 hour
            query = query.filter(HistoricalDelay.hour_of_day.between(max(0, hour - 1), min(23, hour + 1)))

        results = [r[0] for r in query.all()]

        if len(results) < 5:
            # Fallback to route-level statistics
            route_query = db.session.query(HistoricalDelay.delay_minutes).filter(
                HistoricalDelay.route_id == route_id
            )
            route_results = [r[0] for r in route_query.all()]
            stats = cls.calculate_stats(route_results)
            stats["is_fallback"] = True
            stats["limited_data"] = True
            stats["message"] = "Limited historical data for this stop; showing route-level statistical average."
            return stats

        stats = cls.calculate_stats(results)
        stats["is_fallback"] = False
        return stats

    @classmethod
    def get_bus_incident_stats(cls, route_id: int, stop_id: int, reason: str = "TYRE_PUNCTURE") -> Dict[str, Any]:
        """
        Specialized delay statistics for emergency incidents (e.g. Tyre Puncture at Magarpatta on Route Pune -> Hadapsar).
        Matches Section 42 specifications:
          Historical average: 14 min
          Historical min: 5 min
          Historical max: 28 min
          Expected range: 10–18 min
        """
        query = db.session.query(HistoricalDelay.delay_minutes).filter(
            HistoricalDelay.route_id == route_id,
            HistoricalDelay.delay_reason == reason
        )
        results = [r[0] for r in query.all()]
        if not results:
            # Check for any incident delay records on this route
            query = db.session.query(HistoricalDelay.delay_minutes).filter(
                HistoricalDelay.route_id == route_id
            )
            results = [r[0] for r in query.all()]

        stats = cls.calculate_stats(results)
        return stats
