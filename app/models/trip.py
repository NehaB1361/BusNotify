"""
Trip, LiveGPS, and PassengerCount Models
"""
from datetime import datetime
from app.extensions import db


class Trip(db.Model):
    __tablename__ = "trips"

    id = db.Column(db.Integer, primary_key=True)
    trip_code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    bus_id = db.Column(db.Integer, db.ForeignKey("buses.id", ondelete="CASCADE"), nullable=False, index=True)
    driver_id = db.Column(db.Integer, db.ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True, index=True)
    route_id = db.Column(db.Integer, db.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    
    scheduled_start_time = db.Column(db.DateTime, nullable=False)
    actual_start_time = db.Column(db.DateTime, nullable=True)
    actual_end_time = db.Column(db.DateTime, nullable=True)
    
    current_stop_id = db.Column(db.Integer, db.ForeignKey("stops.id", ondelete="SET NULL"), nullable=True)
    next_stop_id = db.Column(db.Integer, db.ForeignKey("stops.id", ondelete="SET NULL"), nullable=True)
    
    status = db.Column(
        db.String(32),
        default="SCHEDULED",
        nullable=False,
        index=True
    )  # SCHEDULED, RUNNING, DELAYED, CANCELLED, PUNCTURED, BREAKDOWN, COMPLETED
    
    passenger_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    bus = db.relationship("Bus", back_populates="trips")
    driver = db.relationship("Driver", back_populates="trips")
    route = db.relationship("Route", back_populates="trips")
    current_stop = db.relationship("Stop", foreign_keys=[current_stop_id])
    next_stop = db.relationship("Stop", foreign_keys=[next_stop_id])
    gps_records = db.relationship("LiveGPS", back_populates="trip", order_by="desc(LiveGPS.timestamp)", cascade="all, delete-orphan", lazy="dynamic")
    incidents = db.relationship("Incident", back_populates="trip", lazy="dynamic")

    @property
    def available_seats(self):
        capacity = self.bus.capacity if self.bus else 40
        return max(0, capacity - self.passenger_count)

    def to_dict(self):
        latest_gps = self.gps_records.first()
        return {
            "id": self.id,
            "trip_code": self.trip_code,
            "bus_id": self.bus_id,
            "bus_number": self.bus.bus_number if self.bus else None,
            "driver_id": self.driver_id,
            "driver_name": self.driver.full_name if self.driver else None,
            "driver_code": self.driver.driver_code if self.driver else None,
            "route_id": self.route_id,
            "route_number": self.route.route_number if self.route else None,
            "route_name": self.route.name if self.route else None,
            "source": self.route.source if self.route else None,
            "destination": self.route.destination if self.route else None,
            "current_stop_id": self.current_stop_id,
            "current_stop_name": self.current_stop.name if self.current_stop else "Depot",
            "next_stop_id": self.next_stop_id,
            "next_stop_name": self.next_stop.name if self.next_stop else None,
            "status": self.status,
            "passenger_count": self.passenger_count,
            "available_seats": self.available_seats,
            "capacity": self.bus.capacity if self.bus else 40,
            "scheduled_start_time": self.scheduled_start_time.isoformat() if self.scheduled_start_time else None,
            "actual_start_time": self.actual_start_time.isoformat() if self.actual_start_time else None,
            "latest_gps": latest_gps.to_dict() if latest_gps else None,
        }


class LiveGPS(db.Model):
    __tablename__ = "live_gps"

    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    bus_id = db.Column(db.Integer, db.ForeignKey("buses.id", ondelete="CASCADE"), nullable=False, index=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    speed_kmh = db.Column(db.Float, default=0.0)
    source = db.Column(
        db.String(32),
        default="GPS",
        nullable=False
    )  # GPS, MANUAL_STOP, SIMULATED
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    trip = db.relationship("Trip", back_populates="gps_records")
    bus = db.relationship("Bus")

    @property
    def freshness_status(self):
        """Returns: Fresh, Delayed Update, Stale, Offline (Section 46)"""
        delta = (datetime.utcnow() - self.timestamp).total_seconds()
        if delta <= 60:
            return "Fresh"
        elif delta <= 180:
            return "Delayed Update"
        elif delta <= 600:
            return "Stale"
        else:
            return "Offline"

    def to_dict(self):
        return {
            "id": self.id,
            "trip_id": self.trip_id,
            "bus_id": self.bus_id,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "speed_kmh": self.speed_kmh,
            "source": self.source,
            "freshness": self.freshness_status,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class PassengerCount(db.Model):
    __tablename__ = "passenger_counts"

    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    stop_id = db.Column(db.Integer, db.ForeignKey("stops.id", ondelete="CASCADE"), nullable=False)
    boarding_count = db.Column(db.Integer, default=0, nullable=False)
    alighting_count = db.Column(db.Integer, default=0, nullable=False)
    current_passenger_count = db.Column(db.Integer, default=0, nullable=False)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    trip = db.relationship("Trip")
    stop = db.relationship("Stop")

    def to_dict(self):
        return {
            "id": self.id,
            "trip_id": self.trip_id,
            "stop_id": self.stop_id,
            "stop_name": self.stop.name if self.stop else None,
            "boarding_count": self.boarding_count,
            "alighting_count": self.alighting_count,
            "current_passenger_count": self.current_passenger_count,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
        }
