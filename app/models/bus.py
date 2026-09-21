"""
Bus, BusCapacity, and Driver Models
"""
from datetime import datetime
from app.extensions import db


class Bus(db.Model):
    __tablename__ = "buses"

    id = db.Column(db.Integer, primary_key=True)
    bus_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    registration_number = db.Column(db.String(32), unique=True, nullable=False)
    depot_name = db.Column(db.String(64), default="Pune Central Depot", nullable=False)
    capacity = db.Column(db.Integer, default=40, nullable=False)
    current_status = db.Column(
        db.String(32),
        default="AVAILABLE",
        nullable=False,
        index=True
    )  # RUNNING, DELAYED, CANCELLED, PUNCTURED, BREAKDOWN, COMPLETED, AVAILABLE, DISPATCHED
    assigned_route_id = db.Column(db.Integer, db.ForeignKey("routes.id", ondelete="SET NULL"), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    assigned_route = db.relationship("Route", back_populates="buses")
    capacity_detail = db.relationship("BusCapacity", back_populates="bus", uselist=False, cascade="all, delete-orphan")
    trips = db.relationship("Trip", back_populates="bus", lazy="dynamic")
    active_driver = db.relationship("Driver", back_populates="assigned_bus", uselist=False)

    def to_dict(self):
        return {
            "id": self.id,
            "bus_number": self.bus_number,
            "registration_number": self.registration_number,
            "depot_name": self.depot_name,
            "capacity": self.capacity,
            "current_status": self.current_status,
            "assigned_route_id": self.assigned_route_id,
            "route_number": self.assigned_route.route_number if self.assigned_route else None,
            "route_name": self.assigned_route.name if self.assigned_route else None,
            "is_active": self.is_active,
        }


class BusCapacity(db.Model):
    __tablename__ = "bus_capacity"

    id = db.Column(db.Integer, primary_key=True)
    bus_id = db.Column(db.Integer, db.ForeignKey("buses.id", ondelete="CASCADE"), unique=True, nullable=False)
    total_capacity = db.Column(db.Integer, default=40, nullable=False)
    seated_capacity = db.Column(db.Integer, default=32, nullable=False)
    standing_capacity = db.Column(db.Integer, default=8, nullable=False)

    bus = db.relationship("Bus", back_populates="capacity_detail")

    def to_dict(self):
        return {
            "bus_id": self.bus_id,
            "total_capacity": self.total_capacity,
            "seated_capacity": self.seated_capacity,
            "standing_capacity": self.standing_capacity,
        }


class Driver(db.Model):
    __tablename__ = "drivers"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    driver_code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(128), nullable=False)
    mobile_number = db.Column(db.String(20), nullable=False)
    license_number = db.Column(db.String(64), unique=True, nullable=False)
    status = db.Column(
        db.String(32),
        default="AVAILABLE",
        nullable=False,
        index=True
    )  # AVAILABLE, ON_TRIP, OFF_DUTY
    assigned_bus_id = db.Column(db.Integer, db.ForeignKey("buses.id", ondelete="SET NULL"), nullable=True)

    user = db.relationship("User", back_populates="driver_profile")
    assigned_bus = db.relationship("Bus", back_populates="active_driver")
    trips = db.relationship("Trip", back_populates="driver", lazy="dynamic")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "driver_code": self.driver_code,
            "full_name": self.full_name,
            "mobile_number": self.mobile_number,
            "license_number": self.license_number,
            "status": self.status,
            "assigned_bus_id": self.assigned_bus_id,
            "assigned_bus_number": self.assigned_bus.bus_number if self.assigned_bus else None,
        }
