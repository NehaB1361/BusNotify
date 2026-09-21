"""
Driver API Routes
Supports trip initiation, live stop progression, passenger count validation,
GPS updates, and emergency incident reporting.
"""
import json
from datetime import datetime
from flask import Blueprint, request, session, g
from app.extensions import db
from app.models.driver import Driver
from app.models.bus import Bus
from app.models.trip import Trip, LiveGPS, PassengerCount
from app.models.transit import Route, Stop, RouteStop
from app.models.audit import AuditLog
from app.services.incident_service import IncidentService
from app.utils.decorators import login_required, role_required
from app.utils.response import api_success, api_error

driver_bp = Blueprint("driver_api", __name__, url_prefix="/api/driver")


@driver_bp.route("/dashboard", methods=["GET"])
def get_driver_dashboard():
    user_id = session.get("user_id")
    # For demo ease, if no user session or not logged in as driver, fallback to default driver Rajesh Patil (D104)
    driver = Driver.query.filter_by(user_id=user_id).first() if user_id else None
    if not driver:
        driver = Driver.query.filter_by(driver_code="D104").first()
    if not driver:
        driver = Driver.query.first()

    if not driver:
        return api_error(code="NOT_FOUND", message="No driver profile found.", status_code=404)

    # Active or latest trip
    active_trip = Trip.query.filter(
        Trip.driver_id == driver.id,
        Trip.status.in_(["RUNNING", "DELAYED", "PUNCTURED", "BREAKDOWN", "SCHEDULED"])
    ).order_by(Trip.id.desc()).first()

    if not active_trip and driver.assigned_bus_id:
        active_trip = Trip.query.filter_by(bus_id=driver.assigned_bus_id).order_by(Trip.id.desc()).first()

    assigned_bus = driver.assigned_bus or (active_trip.bus if active_trip else None)
    assigned_route = (assigned_bus.assigned_route if assigned_bus else None) or (active_trip.route if active_trip else None)

    # All stops along the route for manual stop selection
    route_stops = []
    if assigned_route:
        for rs in assigned_route.route_stops:
            route_stops.append(rs.stop.to_dict())

    return api_success(data={
        "driver": driver.to_dict(),
        "assigned_bus": assigned_bus.to_dict() if assigned_bus else None,
        "assigned_route": assigned_route.to_dict() if assigned_route else None,
        "trip": active_trip.to_dict() if active_trip else None,
        "route_stops": route_stops,
        "available_seats": active_trip.available_seats if active_trip else (assigned_bus.capacity if assigned_bus else 40)
    })


@driver_bp.route("/trip/start", methods=["POST"])
def start_trip():
    data = request.get_json() or {}
    bus_id = data.get("bus_id")
    route_id = data.get("route_id")
    starting_stop_id = data.get("starting_stop_id")
    initial_passenger_count = int(data.get("passenger_count", 0))

    user_id = session.get("user_id")
    driver = Driver.query.filter_by(user_id=user_id).first() if user_id else None
    if not driver:
        driver = Driver.query.filter_by(driver_code="D104").first() or Driver.query.first()

    bus = Bus.query.get(bus_id) if bus_id else (driver.assigned_bus if driver else None)
    if not bus:
        return api_error(code="VALIDATION_ERROR", message="Bus not found or not assigned.", status_code=400)

    route = Route.query.get(route_id) if route_id else bus.assigned_route
    if not route:
        return api_error(code="VALIDATION_ERROR", message="Route not found.", status_code=400)

    # First stop
    if not starting_stop_id and route.route_stops:
        starting_stop_id = route.route_stops[0].stop_id

    # Check capacity constraints
    if initial_passenger_count > bus.capacity:
        return api_error(code="CAPACITY_EXCEEDED", message=f"Passenger count ({initial_passenger_count}) exceeds bus capacity ({bus.capacity}).", status_code=400)

    trip_count = Trip.query.count() + 1
    trip_code = f"TRIP-{bus.bus_number}-{trip_count:03d}"

    trip = Trip(
        trip_code=trip_code,
        bus_id=bus.id,
        driver_id=driver.id if driver else None,
        route_id=route.id,
        scheduled_start_time=datetime.utcnow(),
        actual_start_time=datetime.utcnow(),
        current_stop_id=starting_stop_id,
        status="RUNNING",
        passenger_count=initial_passenger_count
    )
    db.session.add(trip)
    bus.current_status = "RUNNING"
    if driver:
        driver.status = "ON_TRIP"

    db.session.commit()

    return api_success(data=trip.to_dict(), message="Trip started successfully", status_code=201)


@driver_bp.route("/trip/stop-update", methods=["POST"])
@driver_bp.route("/trip/stop", methods=["POST"])
@driver_bp.route("/trip/passengers", methods=["POST"])
def update_stop():
    data = request.get_json() or {}
    trip_id = data.get("trip_id")
    stop_id = data.get("stop_id")
    passenger_count = data.get("passenger_count")

    trip = Trip.query.get(trip_id)
    if not trip:
        return api_error(code="NOT_FOUND", message="Trip not found.", status_code=404)

    stop = Stop.query.get(stop_id) if stop_id else trip.current_stop
    if not stop:
        return api_error(code="NOT_FOUND", message="Stop not found.", status_code=404)

    trip.current_stop_id = stop.id

    # Update next stop
    route_stops = RouteStop.query.filter_by(route_id=trip.route_id).order_by(RouteStop.sequence_order).all()
    current_idx = next((i for i, rs in enumerate(route_stops) if rs.stop_id == stop.id), -1)
    if current_idx >= 0 and current_idx + 1 < len(route_stops):
        trip.next_stop_id = route_stops[current_idx + 1].stop_id
    else:
        trip.next_stop_id = None

    if passenger_count is not None:
        p_count = int(passenger_count)
        if p_count < 0 or p_count > trip.bus.capacity:
            return api_error(code="INVALID_PASSENGER_COUNT", message=f"Passenger count must be between 0 and bus capacity ({trip.bus.capacity}).", status_code=400)
        old_count = trip.passenger_count or 0
        trip.passenger_count = p_count

        # Log passenger count in historical table
        pax_log = PassengerCount(
            trip_id=trip.id,
            stop_id=stop.id,
            boarding_count=max(0, p_count - old_count),
            alighting_count=max(0, old_count - p_count),
            current_passenger_count=p_count,
            recorded_at=datetime.utcnow()
        )
        db.session.add(pax_log)

    # Record GPS for this stop
    gps = LiveGPS(
        trip_id=trip.id,
        bus_id=trip.bus_id,
        latitude=stop.latitude,
        longitude=stop.longitude,
        speed_kmh=24.0,
        source="MANUAL_STOP",
        timestamp=datetime.utcnow()
    )
    db.session.add(gps)
    db.session.commit()

    return api_success(data=trip.to_dict(), message=f"Updated current stop to {stop.name}")


@driver_bp.route("/trip/gps", methods=["POST"])
def update_gps():
    data = request.get_json() or {}
    trip_id = data.get("trip_id")
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    speed = float(data.get("speed_kmh", 0.0))
    source = data.get("source", "GPS")

    trip = Trip.query.get(trip_id)
    if not trip:
        return api_error(code="NOT_FOUND", message="Trip not found.", status_code=404)

    if latitude is None or longitude is None:
        return api_error(code="VALIDATION_ERROR", message="Latitude and longitude are required.", status_code=400)

    gps = LiveGPS(
        trip_id=trip.id,
        bus_id=trip.bus_id,
        latitude=float(latitude),
        longitude=float(longitude),
        speed_kmh=speed,
        source=source,
        timestamp=datetime.utcnow()
    )
    db.session.add(gps)
    db.session.commit()

    return api_success(data=gps.to_dict(), message="GPS coordinates updated")


@driver_bp.route("/gps", methods=["POST"])
@role_required("driver")
def update_driver_gps():
    """
    Secure GPS endpoint for driver mobile browsers (Section GPS-1).

    - Derives trip_id and bus_id from the authenticated session — never trusts
      any value sent by the frontend.
    - Validates coordinate ranges server-side.
    - Sets source = DRIVER_MOBILE.
    - Logs every update to audit_logs.
    """
    # --- Identify authenticated driver from session ---
    user_id = session.get("user_id")
    driver = Driver.query.filter_by(user_id=user_id).first()
    if not driver:
        return api_error(
            code="DRIVER_NOT_FOUND",
            message="No driver profile associated with this account.",
            status_code=400
        )

    # --- Find active trip owned by this driver ---
    ACTIVE_STATUSES = ["RUNNING", "DELAYED", "PUNCTURED", "BREAKDOWN"]
    active_trip = Trip.query.filter(
        Trip.driver_id == driver.id,
        Trip.status.in_(ACTIVE_STATUSES)
    ).order_by(Trip.id.desc()).first()

    if not active_trip:
        return api_error(
            code="NO_ACTIVE_TRIP",
            message="You do not have an active trip. Start a trip before sharing GPS.",
            status_code=400
        )

    # --- Validate assigned bus ---
    bus = Bus.query.get(active_trip.bus_id)
    if not bus or not bus.is_active:
        return api_error(
            code="BUS_NOT_ACTIVE",
            message="Assigned bus is not available or inactive.",
            status_code=400
        )

    # --- Parse and validate payload ---
    data = request.get_json(silent=True) or {}
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    speed_raw = data.get("speed")
    timestamp_raw = data.get("timestamp")

    if latitude is None or longitude is None:
        return api_error(
            code="VALIDATION_ERROR",
            message="latitude and longitude are required fields.",
            status_code=400
        )

    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (ValueError, TypeError):
        return api_error(
            code="VALIDATION_ERROR",
            message="latitude and longitude must be numeric values.",
            status_code=400
        )

    if not (-90.0 <= latitude <= 90.0):
        return api_error(
            code="VALIDATION_ERROR",
            message=f"latitude must be between -90 and 90. Received: {latitude}",
            status_code=400
        )
    if not (-180.0 <= longitude <= 180.0):
        return api_error(
            code="VALIDATION_ERROR",
            message=f"longitude must be between -180 and 180. Received: {longitude}",
            status_code=400
        )

    # Speed: optional; default 0.0; reject negative values
    speed_kmh = 0.0
    if speed_raw is not None:
        try:
            speed_kmh = float(speed_raw)
        except (ValueError, TypeError):
            return api_error(
                code="VALIDATION_ERROR",
                message="speed must be a numeric value.",
                status_code=400
            )
        if speed_kmh < 0:
            return api_error(
                code="VALIDATION_ERROR",
                message="speed cannot be negative.",
                status_code=400
            )

    # Timestamp: optional; use server UTC if absent or unparsable
    gps_timestamp = datetime.utcnow()
    if timestamp_raw:
        try:
            gps_timestamp = datetime.fromisoformat(str(timestamp_raw).replace("Z", "+00:00"))
            # Strip tz info to store as UTC-naive (consistent with rest of models)
            gps_timestamp = gps_timestamp.replace(tzinfo=None)
        except (ValueError, TypeError):
            gps_timestamp = datetime.utcnow()

    # --- Persist GPS record (trip_id and bus_id come from DB, not frontend) ---
    gps = LiveGPS(
        trip_id=active_trip.id,
        bus_id=bus.id,
        latitude=latitude,
        longitude=longitude,
        speed_kmh=speed_kmh,
        source="DRIVER_MOBILE",
        timestamp=gps_timestamp
    )
    db.session.add(gps)

    # --- Audit log ---
    try:
        audit = AuditLog(
            user_id=user_id,
            action="GPS_UPDATE",
            entity_type="live_gps",
            entity_id=str(active_trip.id),
            details=json.dumps({
                "trip_code": active_trip.trip_code,
                "bus_number": bus.bus_number,
                "latitude": latitude,
                "longitude": longitude,
                "speed_kmh": speed_kmh,
            }),
            ip_address=request.remote_addr
        )
        db.session.add(audit)
    except Exception:
        pass  # Audit failures must not break GPS persistence

    db.session.commit()

    return api_success(
        data=gps.to_dict(),
        message="GPS location updated successfully."
    )



@driver_bp.route("/trip/emergency", methods=["POST"])
def report_emergency():
    """
    Submits an emergency report (Section 25 & 42).
    Generates INC-001, DR001, alternative suggestions, notifications.
    """
    data = request.get_json() or {}
    trip_id = data.get("trip_id")
    incident_type = data.get("incident_type", "Tyre Puncture")
    affected_passengers = int(data.get("affected_passengers", 40))
    description = data.get("description", "Tyre puncture occurred en route.")
    priority = data.get("priority", "HIGH")
    stop_id = data.get("stop_id")

    if not trip_id:
        return api_error(code="VALIDATION_ERROR", message="Trip ID is required.", status_code=400)

    try:
        user_id = session.get("user_id")
        result = IncidentService.report_emergency(
            trip_id=int(trip_id),
            incident_type=incident_type,
            affected_passengers=affected_passengers,
            description=description,
            priority=priority,
            current_stop_id=int(stop_id) if stop_id else None,
            user_id=user_id
        )
        return api_success(data=result, message="Emergency reported successfully. System alerts and depot dispatch generated.")
    except Exception as e:
        return api_error(code="EMERGENCY_REPORT_FAILED", message=str(e), status_code=400)


@driver_bp.route("/trip/end", methods=["POST"])
def end_trip():
    data = request.get_json() or {}
    trip_id = data.get("trip_id")

    trip = Trip.query.get(trip_id)
    if not trip:
        return api_error(code="NOT_FOUND", message="Trip not found.", status_code=404)

    trip.status = "COMPLETED"
    trip.actual_end_time = datetime.utcnow()
    if trip.bus:
        trip.bus.current_status = "AVAILABLE"
    if trip.driver:
        trip.driver.status = "AVAILABLE"

    db.session.commit()
    return api_success(data=trip.to_dict(), message="Trip completed successfully")
