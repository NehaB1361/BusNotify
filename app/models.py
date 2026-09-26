"""
BusNotify - Database Models
Simple, clean, beginner-friendly MySQL database models using Flask-SQLAlchemy.
Tables:
  - users: Authentication, passwords, and role assignment
  - routes: Bus route details (source, destination, distance)
  - stops: Physical bus stops with latitude/longitude
  - route_stops: Ordered stop sequence for each route
  - route_connectivity: Interchange connections between routes
  - buses: Fleet inventory with capacity and operational status
  - bus_capacity: Detailed seated vs standing capacity
  - drivers: Driver profile linked to user account and bus assignment
  - trips: Scheduled and live bus trips
  - live_gps: Real-time GPS coordinate telemetry from driver mobile browsers
  - passenger_counts: Onboard passenger logs per stop
  - historical_delays: Historical delay observations for statistics calculation
  - incidents: Emergency incident reports (tyre puncture, breakdown, etc.)
  - alternative_recommendations: Recommended alternate buses for passengers
  - depot_requests: Depot replacement dispatch state machine (DR001)
  - replacement_buses: Assigned replacement bus record
  - passenger_transfers: Logs of passengers transferred between buses
  - notifications: Role-targeted passenger, driver, and depot alerts
  - audit_logs: System activity and security audit trail
"""
import sys
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS

db = SQLAlchemy()
migrate = Migrate()
cors = CORS()


# ==========================================
# 1. USER & AUTHENTICATION
# ==========================================
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    mobile = db.Column(db.String(20), unique=True, nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(
        db.Enum("passenger", "driver", "admin", "depot_operator", name="user_roles"),
        nullable=False,
        default="passenger",
        index=True
    )
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    preferred_language = db.Column(db.String(10), default="en", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    driver_profile = db.relationship("Driver", back_populates="user", uselist=False, cascade="all, delete-orphan")
    notifications = db.relationship("Notification", back_populates="user", lazy="dynamic", cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "mobile": self.mobile,
            "role": self.role,
            "is_active": self.is_active,
            "preferred_language": self.preferred_language,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ==========================================
# 2. TRANSIT NETWORK (Routes, Stops, Sequence)
# ==========================================
class Stop(db.Model):
    __tablename__ = "stops"

    id = db.Column(db.Integer, primary_key=True)
    stop_code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    name = db.Column(db.String(128), nullable=False, index=True)
    name_mr = db.Column(db.String(128), nullable=True)
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


# ==========================================
# 3. BUS FLEET & DRIVERS
# ==========================================
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


# ==========================================
# 4. TRIPS, LIVE GPS & OCCUPANCY
# ==========================================
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
    )  # GPS, MANUAL_STOP, DRIVER_MOBILE
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    trip = db.relationship("Trip", back_populates="gps_records")
    bus = db.relationship("Bus")

    @property
    def freshness_status(self):
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


# ==========================================
# 5. HISTORICAL DELAYS (Pure Statistics)
# ==========================================
class HistoricalDelay(db.Model):
    __tablename__ = "historical_delays"

    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    stop_id = db.Column(db.Integer, db.ForeignKey("stops.id", ondelete="CASCADE"), nullable=False, index=True)
    weekday = db.Column(db.Integer, nullable=False, index=True)
    hour_of_day = db.Column(db.Integer, nullable=False, index=True)
    delay_minutes = db.Column(db.Float, nullable=False)
    delay_reason = db.Column(db.String(64), default="TRAFFIC", nullable=False)
    recorded_date = db.Column(db.Date, nullable=False, index=True)
    sample_date = db.synonym("recorded_date")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    route = db.relationship("Route")
    stop = db.relationship("Stop")

    def __init__(self, **kwargs):
        if "sample_date" in kwargs and "recorded_date" not in kwargs:
            kwargs["recorded_date"] = kwargs.pop("sample_date")
        super().__init__(**kwargs)

    def to_dict(self):
        return {
            "id": self.id,
            "route_id": self.route_id,
            "route_number": self.route.route_number if self.route else None,
            "stop_id": self.stop_id,
            "stop_name": self.stop.name if self.stop else None,
            "weekday": self.weekday,
            "hour_of_day": self.hour_of_day,
            "delay_minutes": self.delay_minutes,
            "delay_reason": self.delay_reason,
            "recorded_date": self.recorded_date.isoformat() if self.recorded_date else None,
        }


# ==========================================
# 6. INCIDENTS & ALTERNATIVE RECOMMENDATIONS
# ==========================================
class Incident(db.Model):
    __tablename__ = "incidents"

    id = db.Column(db.Integer, primary_key=True)
    incident_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    bus_id = db.Column(db.Integer, db.ForeignKey("buses.id", ondelete="CASCADE"), nullable=False, index=True)
    route_id = db.Column(db.Integer, db.ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True)
    stop_id = db.Column(db.Integer, db.ForeignKey("stops.id", ondelete="SET NULL"), nullable=True, index=True)
    
    incident_type = db.Column(db.String(64), nullable=False, index=True)
    priority = db.Column(db.String(16), default="HIGH", nullable=False, index=True)
    affected_passengers = db.Column(db.Integer, default=0, nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(32), default="OPEN", nullable=False, index=True)  # OPEN, ACTION_TAKEN, RESOLVED
    
    reported_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    resolved_at = db.Column(db.DateTime, nullable=True)

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


# ==========================================
# 7. DEPOT WORKFLOW & REPLACEMENTS
# ==========================================
class DepotRequest(db.Model):
    __tablename__ = "depot_requests"

    id = db.Column(db.Integer, primary_key=True)
    request_code = db.Column(db.String(32), unique=True, nullable=False, index=True)
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
    )  # PENDING -> ASSIGNED -> DISPATCHED -> ARRIVED -> PASSENGER_TRANSFER -> RESOLVED
    
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


# ==========================================
# 8. NOTIFICATIONS & AUDIT LOGS
# ==========================================
class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    target_role = db.Column(db.String(32), default="all", nullable=False, index=True)
    title = db.Column(db.String(128), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(32), default="INFO", nullable=False)
    notification_type = db.synonym("type")
    priority = db.Column(db.String(16), default="HIGH", nullable=True)
    related_entity_type = db.Column(db.String(32), nullable=True)
    related_entity_id = db.Column(db.Integer, nullable=True, index=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = db.relationship("User", back_populates="notifications")

    def __init__(self, **kwargs):
        if "notification_type" in kwargs and "type" not in kwargs:
            kwargs["type"] = kwargs.pop("notification_type")
        super().__init__(**kwargs)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "target_role": self.target_role,
            "title": self.title,
            "message": self.message,
            "type": self.type,
            "priority": self.priority,
            "related_entity_type": self.related_entity_type,
            "related_entity_id": self.related_entity_id,
            "is_read": self.is_read,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = db.Column(db.String(64), nullable=False, index=True)
    entity_type = db.Column(db.String(64), nullable=False)
    entity_id = db.Column(db.String(64), nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "details": self.details,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ==========================================
# MODULE ALIASES (Backward Compatibility)
# ==========================================
# Allows imports like `from app.models.user import User` while having everything in `app.models`
curr_module = sys.modules[__name__]
sys.modules["app.models.user"] = curr_module
sys.modules["app.models.bus"] = curr_module
sys.modules["app.models.driver"] = curr_module
sys.modules["app.models.transit"] = curr_module
sys.modules["app.models.trip"] = curr_module
sys.modules["app.models.delay"] = curr_module
sys.modules["app.models.incident"] = curr_module
sys.modules["app.models.depot"] = curr_module
sys.modules["app.models.notification"] = curr_module
sys.modules["app.models.audit"] = curr_module
sys.modules["app.extensions"] = curr_module
