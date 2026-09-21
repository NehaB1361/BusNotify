"""
HistoricalDelay Model
Stores statistical delay observations across routes, stops, buses, weekdays, and hours.
Used exclusively for deterministic descriptive statistics.
"""
from datetime import datetime
from app.extensions import db


class HistoricalDelay(db.Model):
    __tablename__ = "historical_delays"

    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    stop_id = db.Column(db.Integer, db.ForeignKey("stops.id", ondelete="CASCADE"), nullable=False, index=True)
    bus_id = db.Column(db.Integer, db.ForeignKey("buses.id", ondelete="SET NULL"), nullable=True, index=True)
    weekday = db.Column(db.Integer, nullable=False, index=True)  # 0=Monday, 6=Sunday
    hour_of_day = db.Column(db.Integer, nullable=False, index=True)  # 0-23
    delay_minutes = db.Column(db.Float, nullable=False)
    delay_reason = db.Column(
        db.String(64),
        default="TRAFFIC",
        nullable=False,
        index=True
    )  # TRAFFIC, TYRE_PUNCTURE, BREAKDOWN, WEATHER, PASSENGER_SURGE, ACCIDENT, NONE
    sample_date = db.Column(db.Date, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    route = db.relationship("Route")
    stop = db.relationship("Stop")
    bus = db.relationship("Bus")

    def to_dict(self):
        return {
            "id": self.id,
            "route_id": self.route_id,
            "stop_id": self.stop_id,
            "bus_id": self.bus_id,
            "weekday": self.weekday,
            "hour_of_day": self.hour_of_day,
            "delay_minutes": self.delay_minutes,
            "delay_reason": self.delay_reason,
            "sample_date": self.sample_date.isoformat() if self.sample_date else None,
        }
