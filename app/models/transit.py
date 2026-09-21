"""
Transit Models: Route, Stop, RouteStop, RouteConnectivity
"""
from datetime import datetime
from app.extensions import db


class Stop(db.Model):
    __tablename__ = "stops"

    id = db.Column(db.Integer, primary_key=True)
    stop_code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    name_mr = db.Column(db.String(128), nullable=True)  # Marathi translation
    landmark = db.Column(db.String(256), nullable=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    route_stops = db.relationship("RouteStop", back_populates="stop", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "stop_code": self.stop_code,
            "name": self.name,
            "name_mr": self.name_mr or self.name,
            "landmark": self.landmark,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }


class Route(db.Model):
    __tablename__ = "routes"

    id = db.Column(db.Integer, primary_key=True)
    route_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False)
    name_mr = db.Column(db.String(128), nullable=True)
    source = db.Column(db.String(128), nullable=False, index=True)
    destination = db.Column(db.String(128), nullable=False, index=True)
    total_distance_km = db.Column(db.Float, default=0.0)
    estimated_duration_min = db.Column(db.Integer, default=45)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    route_stops = db.relationship("RouteStop", back_populates="route", order_by="RouteStop.sequence_order", cascade="all, delete-orphan")
    buses = db.relationship("Bus", back_populates="assigned_route")
    trips = db.relationship("Trip", back_populates="route")

    def to_dict(self, include_stops=False):
        data = {
            "id": self.id,
            "route_number": self.route_number,
            "name": self.name,
            "name_mr": self.name_mr or self.name,
            "source": self.source,
            "destination": self.destination,
            "total_distance_km": self.total_distance_km,
            "estimated_duration_min": self.estimated_duration_min,
            "is_active": self.is_active,
        }
        if include_stops:
            data["stops"] = [rs.to_dict() for rs in self.route_stops]
        return data


class RouteStop(db.Model):
    __tablename__ = "route_stops"

    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    stop_id = db.Column(db.Integer, db.ForeignKey("stops.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence_order = db.Column(db.Integer, nullable=False)
    distance_from_prev_km = db.Column(db.Float, default=0.0)
    avg_travel_time_min = db.Column(db.Integer, default=5)

    __table_args__ = (
        db.UniqueConstraint("route_id", "sequence_order", name="uq_route_sequence"),
        db.UniqueConstraint("route_id", "stop_id", name="uq_route_stop"),
    )

    route = db.relationship("Route", back_populates="route_stops")
    stop = db.relationship("Stop", back_populates="route_stops")

    def to_dict(self):
        return {
            "id": self.id,
            "route_id": self.route_id,
            "stop_id": self.stop_id,
            "sequence_order": self.sequence_order,
            "distance_from_prev_km": self.distance_from_prev_km,
            "avg_travel_time_min": self.avg_travel_time_min,
            "stop": self.stop.to_dict() if self.stop else None,
        }


class RouteConnectivity(db.Model):
    __tablename__ = "route_connectivity"

    id = db.Column(db.Integer, primary_key=True)
    from_route_id = db.Column(db.Integer, db.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    to_route_id = db.Column(db.Integer, db.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    transfer_stop_id = db.Column(db.Integer, db.ForeignKey("stops.id", ondelete="CASCADE"), nullable=False, index=True)
    is_connected = db.Column(db.Boolean, default=True, nullable=False)

    from_route = db.relationship("Route", foreign_keys=[from_route_id])
    to_route = db.relationship("Route", foreign_keys=[to_route_id])
    transfer_stop = db.relationship("Stop")

    def to_dict(self):
        return {
            "id": self.id,
            "from_route_id": self.from_route_id,
            "to_route_id": self.to_route_id,
            "transfer_stop_id": self.transfer_stop_id,
            "transfer_stop_name": self.transfer_stop.name if self.transfer_stop else None,
            "is_connected": self.is_connected,
        }
