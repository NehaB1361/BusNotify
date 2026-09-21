"""
DepotRequest, ReplacementBus, and PassengerTransfer Models
"""
from datetime import datetime
from app.extensions import db


class DepotRequest(db.Model):
    __tablename__ = "depot_requests"

    id = db.Column(db.Integer, primary_key=True)
    request_code = db.Column(db.String(32), unique=True, nullable=False, index=True)  # e.g., DR001
    incident_id = db.Column(db.Integer, db.ForeignKey("incidents.id", ondelete="CASCADE"), unique=True, nullable=False)
    failed_bus_id = db.Column(db.Integer, db.ForeignKey("buses.id", ondelete="CASCADE"), nullable=False, index=True)
    route_id = db.Column(db.Integer, db.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False)
    stop_id = db.Column(db.Integer, db.ForeignKey("stops.id", ondelete="SET NULL"), nullable=True)
    
    replacement_bus_id = db.Column(db.Integer, db.ForeignKey("buses.id", ondelete="SET NULL"), nullable=True)
    replacement_driver_id = db.Column(db.Integer, db.ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True)
    operator_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    status = db.Column(
        db.String(32),
        default="PENDING",
        nullable=False,
        index=True
    )  # PENDING, ASSIGNED, DISPATCHED, ARRIVED, PASSENGER_TRANSFER, RESOLVED, CANCELLED
    
    affected_passengers = db.Column(db.Integer, default=0, nullable=False)
    transferred_passengers = db.Column(db.Integer, default=0, nullable=False)
    priority = db.Column(db.String(16), default="HIGH", nullable=False)
    
    eta_minutes = db.Column(db.Integer, default=12)
    resolution_notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    assigned_at = db.Column(db.DateTime, nullable=True)
    dispatched_at = db.Column(db.DateTime, nullable=True)
    arrived_at = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    incident = db.relationship("Incident", back_populates="depot_request")
    failed_bus = db.relationship("Bus", foreign_keys=[failed_bus_id])
    replacement_bus = db.relationship("Bus", foreign_keys=[replacement_bus_id])
    replacement_driver = db.relationship("Driver", foreign_keys=[replacement_driver_id])
    route = db.relationship("Route")
    stop = db.relationship("Stop")
    operator = db.relationship("User", foreign_keys=[operator_id])
    transfers = db.relationship("PassengerTransfer", back_populates="depot_request", cascade="all, delete-orphan")

    @property
    def remaining_passengers(self):
        return max(0, self.affected_passengers - self.transferred_passengers)

    def to_dict(self):
        return {
            "id": self.id,
            "request_code": self.request_code,
            "incident_id": self.incident_id,
            "incident_number": self.incident.incident_number if self.incident else None,
            "incident_type": self.incident.incident_type if self.incident else None,
            "failed_bus_id": self.failed_bus_id,
            "failed_bus_number": self.failed_bus.bus_number if self.failed_bus else None,
            "route_id": self.route_id,
            "route_number": self.route.route_number if self.route else None,
            "route_name": self.route.name if self.route else None,
            "source": self.route.source if self.route else None,
            "destination": self.route.destination if self.route else None,
            "stop_id": self.stop_id,
            "stop_name": self.stop.name if self.stop else "Between Stops",
            "replacement_bus_id": self.replacement_bus_id,
            "replacement_bus_number": self.replacement_bus.bus_number if self.replacement_bus else None,
            "replacement_bus_capacity": self.replacement_bus.capacity if self.replacement_bus else None,
            "replacement_driver_id": self.replacement_driver_id,
            "replacement_driver_name": self.replacement_driver.full_name if self.replacement_driver else None,
            "replacement_driver_code": self.replacement_driver.driver_code if self.replacement_driver else None,
            "status": self.status,
            "priority": self.priority,
            "affected_passengers": self.affected_passengers,
            "transferred_passengers": self.transferred_passengers,
            "remaining_passengers": self.remaining_passengers,
            "eta_minutes": self.eta_minutes,
            "resolution_notes": self.resolution_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
            "dispatched_at": self.dispatched_at.isoformat() if self.dispatched_at else None,
            "arrived_at": self.arrived_at.isoformat() if self.arrived_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class ReplacementBus(db.Model):
    __tablename__ = "replacement_buses"

    id = db.Column(db.Integer, primary_key=True)
    depot_request_id = db.Column(db.Integer, db.ForeignKey("depot_requests.id", ondelete="CASCADE"), nullable=False)
    bus_id = db.Column(db.Integer, db.ForeignKey("buses.id", ondelete="CASCADE"), nullable=False)
    driver_id = db.Column(db.Integer, db.ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True)
    eta_minutes = db.Column(db.Integer, default=12)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    bus = db.relationship("Bus")
    driver = db.relationship("Driver")


class PassengerTransfer(db.Model):
    __tablename__ = "passenger_transfers"

    id = db.Column(db.Integer, primary_key=True)
    depot_request_id = db.Column(db.Integer, db.ForeignKey("depot_requests.id", ondelete="CASCADE"), nullable=False)
    failed_bus_id = db.Column(db.Integer, db.ForeignKey("buses.id", ondelete="CASCADE"), nullable=False)
    target_bus_id = db.Column(db.Integer, db.ForeignKey("buses.id", ondelete="CASCADE"), nullable=False)
    passengers_transferred = db.Column(db.Integer, nullable=False)
    transfer_stop_id = db.Column(db.Integer, db.ForeignKey("stops.id", ondelete="SET NULL"), nullable=True)
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    depot_request = db.relationship("DepotRequest", back_populates="transfers")
    failed_bus = db.relationship("Bus", foreign_keys=[failed_bus_id])
    target_bus = db.relationship("Bus", foreign_keys=[target_bus_id])
    transfer_stop = db.relationship("Stop")

    def to_dict(self):
        return {
            "id": self.id,
            "depot_request_id": self.depot_request_id,
            "failed_bus_number": self.failed_bus.bus_number if self.failed_bus else None,
            "target_bus_number": self.target_bus.bus_number if self.target_bus else None,
            "passengers_transferred": self.passengers_transferred,
            "transfer_stop_name": self.transfer_stop.name if self.transfer_stop else None,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
        }
