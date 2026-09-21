"""
Incident and AlternativeRecommendation Models
"""
from datetime import datetime
from app.extensions import db


class Incident(db.Model):
    __tablename__ = "incidents"

    id = db.Column(db.Integer, primary_key=True)
    incident_number = db.Column(db.String(32), unique=True, nullable=False, index=True)  # e.g., INC-001
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    bus_id = db.Column(db.Integer, db.ForeignKey("buses.id", ondelete="CASCADE"), nullable=False, index=True)
    route_id = db.Column(db.Integer, db.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    stop_id = db.Column(db.Integer, db.ForeignKey("stops.id", ondelete="SET NULL"), nullable=True, index=True)
    
    incident_type = db.Column(
        db.String(64),
        nullable=False,
        index=True
    )  # Tyre Puncture, Engine Failure, Accident, Traffic Blockage, Fuel Problem, Other
    priority = db.Column(
        db.String(16),
        default="HIGH",
        nullable=False,
        index=True
    )  # CRITICAL, HIGH, MEDIUM, LOW
    affected_passengers = db.Column(db.Integer, default=0, nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.String(32),
        default="OPEN",
        nullable=False,
        index=True
    )  # OPEN, ACTION_TAKEN, RESOLVED
    
    reported_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    resolved_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    trip = db.relationship("Trip", back_populates="incidents")
    bus = db.relationship("Bus")
    route = db.relationship("Route")
    stop = db.relationship("Stop")
    depot_request = db.relationship("DepotRequest", back_populates="incident", uselist=False, cascade="all, delete-orphan")
    alternative_recommendations = db.relationship("AlternativeRecommendation", back_populates="incident", order_by="AlternativeRecommendation.rank_order", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "incident_number": self.incident_number,
            "trip_id": self.trip_id,
            "bus_id": self.bus_id,
            "bus_number": self.bus.bus_number if self.bus else None,
            "route_id": self.route_id,
            "route_number": self.route.route_number if self.route else None,
            "route_name": self.route.name if self.route else None,
            "stop_id": self.stop_id,
            "stop_name": self.stop.name if self.stop else "Between Stops",
            "incident_type": self.incident_type,
            "priority": self.priority,
            "affected_passengers": self.affected_passengers,
            "description": self.description,
            "status": self.status,
            "reported_at": self.reported_at.isoformat() if self.reported_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "depot_request_code": self.depot_request.request_code if self.depot_request else None,
        }


class AlternativeRecommendation(db.Model):
    __tablename__ = "alternative_recommendations"

    id = db.Column(db.Integer, primary_key=True)
    incident_id = db.Column(db.Integer, db.ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True)
    recommended_bus_id = db.Column(db.Integer, db.ForeignKey("buses.id", ondelete="CASCADE"), nullable=False)
    direct_route = db.Column(db.Boolean, default=True, nullable=False)
    recommended_stop_id = db.Column(db.Integer, db.ForeignKey("stops.id", ondelete="SET NULL"), nullable=True)
    walking_distance_m = db.Column(db.Integer, default=0)
    eta_minutes = db.Column(db.Integer, nullable=False)
    available_seats = db.Column(db.Integer, nullable=False)
    historical_delay_min = db.Column(db.Float, default=0.0)
    rank_order = db.Column(db.Integer, nullable=False)
    is_recommended = db.Column(db.Boolean, default=False, nullable=False)
    allocated_passengers = db.Column(db.Integer, default=0, nullable=False)

    incident = db.relationship("Incident", back_populates="alternative_recommendations")
    recommended_bus = db.relationship("Bus")
    recommended_stop = db.relationship("Stop")

    def to_dict(self):
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "recommended_bus_id": self.recommended_bus_id,
            "bus_number": self.recommended_bus.bus_number if self.recommended_bus else None,
            "route_number": self.recommended_bus.assigned_route.route_number if (self.recommended_bus and self.recommended_bus.assigned_route) else None,
            "direct_route": self.direct_route,
            "recommended_stop_name": self.recommended_stop.name if self.recommended_stop else None,
            "walking_distance_m": self.walking_distance_m,
            "eta_minutes": self.eta_minutes,
            "available_seats": self.available_seats,
            "historical_delay_min": self.historical_delay_min,
            "rank_order": self.rank_order,
            "is_recommended": self.is_recommended,
            "allocated_passengers": self.allocated_passengers,
            "current_status": self.recommended_bus.current_status if self.recommended_bus else "UNKNOWN",
        }
