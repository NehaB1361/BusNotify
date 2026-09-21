"""
Tests for Historical Descriptive Delay Statistics (Section 3 & 14)
Strictly verifies that descriptive statistics (mean, median, range, std dev) are used,
sample count < 5 fallback occurs, and explicit statistical labeling & disclaimer are present.
"""
from app.services.stats_service import DelayStatisticsService, LABEL_TEXT, DISCLAIMER_TEXT


def test_statistics_calculation_accuracy():
    sample_delays = [10.0, 12.0, 14.0, 16.0, 18.0]
    stats = DelayStatisticsService.calculate_stats(sample_delays)

    assert stats["count"] == 5
    assert stats["mean"] == 14.0
    assert stats["median"] == 14.0
    assert stats["min"] == 10.0
    assert stats["max"] == 18.0
    assert stats["expected_delay"] == 14.0
    assert stats["label"] == LABEL_TEXT
    assert stats["disclaimer"] == DISCLAIMER_TEXT
    assert stats["limited_data"] is False
    assert stats["expected_range_min"] <= 14.0
    assert stats["expected_range_max"] >= 14.0


def test_statistics_small_sample_fallback(app):
    with app.app_context():
        # Query stop with 0/less than 5 samples -> should return fallback
        stats = DelayStatisticsService.get_stop_delay_stats(route_id=1, stop_id=1)
        assert stats["limited_data"] is True
        assert "Limited historical data" in stats["message"]
        assert stats["label"] == LABEL_TEXT


def test_bus_123_magarpatta_statistics(app):
    with app.app_context():
        # Stop 2 has 10 delay records of 14.0
        stats = DelayStatisticsService.get_stop_delay_stats(route_id=1, stop_id=2)
        assert stats["count"] >= 10
        assert stats["expected_delay"] == 14.0
        assert stats["limited_data"] is False
