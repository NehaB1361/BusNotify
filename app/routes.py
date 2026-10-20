"""
BusNotify - Application Routes & Endpoints
Clean, modular Flask routes for Passenger, Driver, Depot Operator, and Admin.
Includes:
  - Standard JSON response format
  - Authentication REST APIs
  - Role-specific operational APIs
  - System health and monitoring endpoints
  - Frontend template view controllers
"""
import sys
import json
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse
from flask import Blueprint, request, session, redirect, url_for, jsonify, render_template, Response, g
from sqlalchemy import or_, text, func
from sqlalchemy.orm import joinedload, selectinload

from app.models import (
    db,
    User, Route, Stop, RouteStop, Bus, Driver,
    Trip, LiveGPS, PassengerCount, HistoricalDelay,
    Incident, AlternativeRecommendation,
    DepotRequest, ReplacementBus, PassengerTransfer,
    Notification, AuditLog
)
from app.auth import AuthService, login_required, role_required
from app.services import (
    DelayStatisticsService,
    IncidentService,
    AlternativeBusService,
    DepotWorkflowService,
    CSVService
)


# ===========================================================================
# STANDARDIZED API RESPONSE HELPERS
# ===========================================================================
def api_success(data=None, message="Operation completed successfully", status_code=200):
    response = {
        "success": True,
        "data": data if data is not None else {},
        "message": message
    }
    return jsonify(response), status_code


def api_error(code="ERROR", message="An error occurred", details=None, status_code=400):
    response = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details if details is not None else {}
        }
    }
    return jsonify(response), status_code


# ===========================================================================
# 1. AUTHENTICATION API ROUTES (/api/auth)
# ===========================================================================
auth_bp = Blueprint("auth_api", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    role = data.get("role", "passenger")
    mobile = data.get("mobile")

    if not username or not email or not password:
        return api_error(code="VALIDATION_ERROR", message="Username, email, and password are required.", status_code=400)

    try:
        user_data = AuthService.register_user(
            username=username,
            email=email,
            password=password,
            role=role,
            mobile=mobile
        )
        return api_success(data=user_data, message="User registered successfully", status_code=201)
    except ValueError as e:
        return api_error(code="REGISTRATION_FAILED", message=str(e), status_code=400)


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    identifier = data.get("identifier") or data.get("email") or data.get("username")
    password = data.get("password")

    if not identifier or not password:
        return api_error(code="VALIDATION_ERROR", message="Email/mobile and password are required.", status_code=400)

    try:
        user_data = AuthService.authenticate_user(
            identifier=identifier,
            password=password,
            ip_address=request.remote_addr
        )
        return api_success(data=user_data, message="Login successful")
    except ValueError as e:
        return api_error(code="AUTH_FAILED", message=str(e), status_code=401)


@auth_bp.route("/logout", methods=["POST", "GET"])
def logout():
    AuthService.logout_user()
    if request.method == "GET":
        return redirect(url_for("views.login_page"))
    return api_success(message="Logged out successfully")


@auth_bp.route("/me", methods=["GET"])
def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return api_error(code="UNAUTHORIZED", message="Not authenticated", status_code=401)
    
    user = User.query.get(user_id)
    if not user:
        return api_error(code="NOT_FOUND", message="User not found", status_code=404)
    
    return api_success(data=user.to_dict())


# ===========================================================================
# 2. PASSENGER API ROUTES (/api/passenger)
# ===========================================================================
passenger_bp = Blueprint("passenger_api", __name__, url_prefix="/api/passenger")


@passenger_bp.route("/search", methods=["GET"])
def search_buses():
    query_str = request.args.get("q", "").strip()
    source = request.args.get("source", "").strip()
    destination = request.args.get("destination", "").strip()
    status_filter = request.args.get("status", "all").strip().upper()
    limit = min(int(request.args.get("limit", 100)), 300)

    ACTIVE_STATUSES = ["RUNNING", "DELAYED", "PUNCTURED", "BREAKDOWN", "DISPATCHED", "SCHEDULED"]

    buses_query = Bus.query.options(
        joinedload(Bus.assigned_route)
    ).filter(Bus.is_active == True)

    if query_str:
        bus_filter_conditions = [
            Bus.bus_number.ilike(f"%{query_str}%"),
            Bus.registration_number.ilike(f"%{query_str}%")
        ]
        if query_str.isdigit():
            bus_filter_conditions.append(Bus.id == int(query_str))

        route_matches = Route.query.filter(
            or_(
                Route.route_number.ilike(f"%{query_str}%"),
                Route.name.ilike(f"%{query_str}%"),
                Route.source.ilike(f"%{query_str}%"),
                Route.destination.ilike(f"%{query_str}%")
            )
        ).all()
        matching_route_ids = [r.id for r in route_matches]

        active_trips_on_routes = Trip.query.filter(
            Trip.status.in_(ACTIVE_STATUSES),
            Trip.route_id.in_(matching_route_ids)
        ).all() if matching_route_ids else []
        route_bus_ids = [t.bus_id for t in active_trips_on_routes]

        buses_query = buses_query.filter(
            or_(
                *bus_filter_conditions,
                Bus.assigned_route_id.in_(matching_route_ids),
                Bus.id.in_(route_bus_ids)
            )
        )

    if source or destination:
        route_q = Route.query
        if source:
            route_q = route_q.filter(
                or_(
                    Route.source.ilike(f"%{source}%"),
                    Route.route_stops.any(RouteStop.stop.has(Stop.name.ilike(f"%{source}%")))
                )
            )
        if destination:
            route_q = route_q.filter(
                or_(
                    Route.destination.ilike(f"%{destination}%"),
                    Route.route_stops.any(RouteStop.stop.has(Stop.name.ilike(f"%{destination}%")))
                )
            )
        src_dest_routes = route_q.all()
        src_dest_route_ids = [r.id for r in src_dest_routes]

        active_trips_src_dest = Trip.query.filter(
            Trip.status.in_(ACTIVE_STATUSES),
            Trip.route_id.in_(src_dest_route_ids)
        ).all() if src_dest_route_ids else []
        src_dest_bus_ids = [t.bus_id for t in active_trips_src_dest]

        buses_query = buses_query.filter(
            or_(
                Bus.id.in_(src_dest_bus_ids),
                Bus.assigned_route_id.in_(src_dest_route_ids)
            )
        )

    candidate_buses = buses_query.order_by(Bus.id.asc()).limit(limit * 2).all()

    results = []
    stats_cache = {}
    now = datetime.utcnow()

    for bus in candidate_buses:
        # Fetch current active trip for THIS specific bus ID
        active_trip = Trip.query.filter(
            Trip.bus_id == bus.id,
            Trip.status.in_(ACTIVE_STATUSES)
        ).order_by(Trip.id.desc()).first()

        effective_status = active_trip.status if active_trip else bus.current_status
        if not active_trip and effective_status == "RUNNING":
            effective_status = "AVAILABLE"

        # Apply status filter
        if status_filter != "ALL":
            if status_filter == "ON TIME":
                if effective_status != "RUNNING":
                    continue
            else:
                if effective_status != status_filter:
                    continue
        elif not (query_str or source or destination):
            # Default browse view: prioritize active buses/trips
            if not active_trip and effective_status not in ["RUNNING", "DELAYED", "PUNCTURED", "BREAKDOWN", "DISPATCHED"]:
                continue

        # Route priority: active trip route selected by driver; idle buses have no active route
        route = active_trip.route if active_trip else None

        expected_delay = 0.0
        stats = {}
        if active_trip and route:
            stop_id = active_trip.current_stop_id or (route.route_stops[0].stop_id if route.route_stops else 1)
            cache_key = (route.id, stop_id)
            if cache_key not in stats_cache:
                stats_cache[cache_key] = DelayStatisticsService.get_stop_delay_stats(
                    route_id=route.id,
                    stop_id=stop_id
                )
            stats = stats_cache[cache_key]
            expected_delay = stats.get("expected_delay", 0.0)

        # GPS & Freshness
        latest_gps = active_trip.gps_records.first() if active_trip else None
        if latest_gps and latest_gps.timestamp:
            delta_s = max(0, int((now - latest_gps.timestamp).total_seconds()))
            last_update_str = f"{delta_s}s ago" if delta_s < 60 else (f"{delta_s // 60}m ago" if delta_s < 3600 else f"{delta_s // 3600}h ago")
        else:
            last_update_str = "Just now" if active_trip else "Depot"

        if active_trip:
            if active_trip.scheduled_start_time:
                est_arrival_time = active_trip.scheduled_start_time + timedelta(minutes=int(35 + expected_delay))
                expected_arrival_str = est_arrival_time.strftime("%I:%M %p")
            else:
                est_arrival_time = now + timedelta(minutes=int(15 + expected_delay))
                expected_arrival_str = est_arrival_time.strftime("%I:%M %p")
            current_stop_name = active_trip.current_stop.name if active_trip.current_stop else "In Transit"
            next_stop_name = active_trip.next_stop.name if active_trip.next_stop else "Terminus"
            avail_seats = active_trip.available_seats
        else:
            expected_arrival_str = "—"
            depot_name = bus.depot_name or "Depot"
            current_stop_name = f"Stationed at {depot_name}"
            next_stop_name = "—"
            avail_seats = bus.capacity

        depot_location = bus.depot_name or "Depot"
        results.append({
            "trip_id": active_trip.id if active_trip else None,
            "bus_id": bus.id,
            "bus_number": bus.bus_number,
            "registration_number": bus.registration_number,
            "route_id": route.id if route else None,
            "route_number": route.route_number if route else ("Express" if active_trip else "—"),
            "route_name": route.name if route else ("In Transit" if active_trip else "Not currently on an active trip"),
            "source": route.source if route else depot_location,
            "destination": route.destination if route else depot_location,
            "status": effective_status,
            "current_stop": current_stop_name,
            "next_stop": next_stop_name,
            "available_seats": avail_seats,
            "capacity": bus.capacity,
            "historical_average_delay": expected_delay,
            "delay_label": stats.get("label", "On Schedule" if active_trip else "Stationary"),
            "delay_disclaimer": stats.get("disclaimer", "Verified from past trip arrival logs" if active_trip else "Vehicle not in active service"),
            "expected_arrival": expected_arrival_str,
            "last_update": last_update_str,
            "is_active_trip": bool(active_trip),
        })

        if len(results) >= limit:
            break

    return api_success(data=results)


@passenger_bp.route("/routes", methods=["GET"])
def get_passenger_routes():
    """List all transit routes with stop count, active bus count, and distance."""
    q_str = request.args.get("q", "").strip().lower()
    source = request.args.get("source", "").strip().lower()
    destination = request.args.get("destination", "").strip().lower()
    limit = min(int(request.args.get("limit", 100)), 500)

    # Subquery for stops count per route
    stops_sub = db.session.query(
        RouteStop.route_id,
        func.count(RouteStop.id).label("stops_count")
    ).group_by(RouteStop.route_id).subquery()

    # Subquery for active buses/trips count per route
    trips_sub = db.session.query(
        Trip.route_id,
        func.count(Trip.id).label("active_buses_count")
    ).filter(Trip.status.in_(["RUNNING", "DELAYED", "PUNCTURED", "BREAKDOWN", "DISPATCHED"])).group_by(Trip.route_id).subquery()

    query = db.session.query(
        Route,
        func.coalesce(stops_sub.c.stops_count, 0),
        func.coalesce(trips_sub.c.active_buses_count, 0)
    ).outerjoin(stops_sub, Route.id == stops_sub.c.route_id)\
     .outerjoin(trips_sub, Route.id == trips_sub.c.route_id)\
     .filter(Route.is_active == True)

    if q_str:
        query = query.filter(
            or_(
                Route.route_number.ilike(f"%{q_str}%"),
                Route.name.ilike(f"%{q_str}%"),
                Route.source.ilike(f"%{q_str}%"),
                Route.destination.ilike(f"%{q_str}%")
            )
        )
    if source:
        query = query.filter(
            or_(
                Route.source.ilike(f"%{source}%"),
                Route.route_stops.any(RouteStop.stop.has(Stop.name.ilike(f"%{source}%")))
            )
        )
    if destination:
        query = query.filter(
            or_(
                Route.destination.ilike(f"%{destination}%"),
                Route.route_stops.any(RouteStop.stop.has(Stop.name.ilike(f"%{destination}%")))
            )
        )

    results = query.order_by(Route.id.asc()).limit(limit).all()

    data = []
    for r, stops_cnt, buses_cnt in results:
        data.append({
            "id": r.id,
            "route_number": r.route_number,
            "name": r.name,
            "name_mr": r.name_mr or r.name,
            "source": r.source,
            "destination": r.destination,
            "total_distance_km": r.total_distance_km,
            "estimated_duration_min": r.estimated_duration_min,
            "is_active": r.is_active,
            "stops_count": int(stops_cnt),
            "active_buses_count": int(buses_cnt),
            "status": "OPERATIONAL" if r.is_active else "INACTIVE"
        })

    return api_success(data=data)


@passenger_bp.route("/routes/<route_identifier>", methods=["GET"])
def get_passenger_route_detail(route_identifier: str):
    """Fetch complete route details including ordered stops sequence, live buses, and delay statistics."""
    route = None
    if str(route_identifier).isdigit():
        route = Route.query.get(int(route_identifier))
    if not route:
        route = Route.query.filter(
            or_(
                Route.route_number == str(route_identifier),
                Route.route_number.ilike(str(route_identifier))
            )
        ).first()

    if not route:
        return api_error(code="NOT_FOUND", message=f"Route '{route_identifier}' not found", status_code=404)

    route_stops = RouteStop.query.filter_by(route_id=route.id)\
        .order_by(RouteStop.sequence_order)\
        .options(joinedload(RouteStop.stop))\
        .all()

    stops_data = []
    for rs in route_stops:
        if rs.stop:
            stops_data.append({
                "sequence_order": rs.sequence_order,
                "stop_id": rs.stop.id,
                "stop_code": rs.stop.stop_code,
                "stop_name": rs.stop.name,
                "stop_name_mr": rs.stop.name_mr or rs.stop.name,
                "latitude": rs.stop.latitude,
                "longitude": rs.stop.longitude,
                "distance_from_prev_km": rs.distance_from_prev_km,
                "avg_travel_time_min": rs.avg_travel_time_min,
                "landmark": rs.stop.landmark
            })

    active_trips = Trip.query.filter(
        Trip.route_id == route.id,
        Trip.status.in_(["RUNNING", "DELAYED", "PUNCTURED", "BREAKDOWN", "DISPATCHED"])
    ).options(
        joinedload(Trip.bus),
        joinedload(Trip.current_stop),
        joinedload(Trip.next_stop)
    ).all()

    active_buses = []
    for t in active_trips:
        latest_gps = t.gps_records.first()
        active_buses.append({
            "trip_id": t.id,
            "bus_id": t.bus.id if t.bus else None,
            "bus_number": t.bus.bus_number if t.bus else "Unknown",
            "registration_number": t.bus.registration_number if t.bus else "",
            "status": t.status,
            "current_stop": t.current_stop.name if t.current_stop else "En route",
            "next_stop": t.next_stop.name if t.next_stop else "Terminus",
            "available_seats": t.available_seats,
            "capacity": t.bus.capacity if t.bus else 40,
            "latitude": latest_gps.latitude if latest_gps else (route_stops[0].stop.latitude if route_stops and route_stops[0].stop else None),
            "longitude": latest_gps.longitude if latest_gps else (route_stops[0].stop.longitude if route_stops and route_stops[0].stop else None),
            "speed_kmh": latest_gps.speed_kmh if latest_gps else 0.0
        })

    first_stop_id = stops_data[0]["stop_id"] if stops_data else 1
    stats = DelayStatisticsService.get_stop_delay_stats(
        route_id=route.id,
        stop_id=first_stop_id
    )

    return api_success(data={
        "route": route.to_dict(),
        "stops": stops_data,
        "stops_count": len(stops_data),
        "active_buses": active_buses,
        "active_buses_count": len(active_buses),
        "statistics": stats
    })


@passenger_bp.route("/bus/<bus_identifier>", methods=["GET"])
def get_bus_details(bus_identifier: str):
    ACTIVE_STATUSES = ["RUNNING", "DELAYED", "PUNCTURED", "BREAKDOWN", "SCHEDULED", "DISPATCHED"]
    bus = None

    if bus_identifier.isdigit():
        bus = Bus.query.get(int(bus_identifier))

    if not bus:
        matching_buses = Bus.query.filter_by(bus_number=bus_identifier).all()
        if matching_buses:
            active_bus = None
            for mb in matching_buses:
                t = Trip.query.filter(
                    Trip.bus_id == mb.id,
                    Trip.status.in_(ACTIVE_STATUSES)
                ).first()
                if t:
                    active_bus = mb
                    break
            bus = active_bus or matching_buses[0]

    if not bus:
        return api_error(code="NOT_FOUND", message=f"Bus '{bus_identifier}' not found.", status_code=404)

    active_trip = Trip.query.filter(
        Trip.bus_id == bus.id,
        Trip.status.in_(ACTIVE_STATUSES)
    ).order_by(Trip.id.desc()).first()

    # Route priority: fetch actual active trip route selected by driver; do NOT use default static route
    route = active_trip.route if active_trip else None

    stats = {}
    if route:
        stop_id = active_trip.current_stop_id if active_trip and active_trip.current_stop_id else (
            route.route_stops[0].stop_id if route.route_stops else None
        )
        if stop_id:
            stats = DelayStatisticsService.get_stop_delay_stats(route.id, stop_id)
        else:
            stats = DelayStatisticsService.calculate_stats([])

    if not stats:
        stats = {
            "expected_delay": 0.0,
            "mean": 0.0,
            "count": 0,
            "label": "Historical statistical estimate",
            "disclaimer": "Based on historical trip observations." if active_trip else "Not currently on an active trip."
        }

    active_incident = None
    depot_req = None
    if active_trip:
        active_incident = Incident.query.filter_by(trip_id=active_trip.id, status="OPEN").first()
        if not active_incident:
            active_incident = Incident.query.filter_by(bus_id=bus.id).order_by(Incident.id.desc()).first()
        if active_incident and active_incident.depot_request:
            depot_req = active_incident.depot_request.to_dict()

    route_timeline = []
    if route:
        current_seq = None
        if active_trip and active_trip.current_stop_id:
            for rs in route.route_stops:
                if rs.stop_id == active_trip.current_stop_id:
                    current_seq = rs.sequence_order
                    break

        for rs in route.route_stops:
            is_cur = bool(active_trip and active_trip.current_stop_id == rs.stop.id)
            is_pas = bool(current_seq is not None and rs.sequence_order < current_seq)
            route_timeline.append({
                "sequence": rs.sequence_order,
                "stop_id": rs.stop.id,
                "stop_name": rs.stop.name,
                "latitude": rs.stop.latitude,
                "longitude": rs.stop.longitude,
                "is_current": is_cur,
                "is_passed": is_pas
            })

    now = datetime.utcnow()
    latest_gps = active_trip.gps_records.first() if active_trip else None
    if latest_gps and latest_gps.timestamp:
        delta_s = max(0, int((now - latest_gps.timestamp).total_seconds()))
        last_update_str = f"{delta_s}s ago" if delta_s < 60 else (f"{delta_s // 60}m ago" if delta_s < 3600 else f"{delta_s // 3600}h ago")
    else:
        last_update_str = "Just now" if active_trip else f"Stationed at {bus.depot_name}"

    exp_delay = stats.get("expected_delay", 0.0) if stats else 0.0
    if active_trip and active_trip.scheduled_start_time:
        sch_arrival = active_trip.scheduled_start_time.strftime("%I:%M %p")
        exp_arrival = (active_trip.scheduled_start_time + timedelta(minutes=int(30 + exp_delay))).strftime("%I:%M %p")
    elif active_trip:
        sch_arrival = (now - timedelta(minutes=15)).strftime("%I:%M %p")
        exp_arrival = (now + timedelta(minutes=int(15 + exp_delay))).strftime("%I:%M %p")
    else:
        sch_arrival = "—"
        exp_arrival = "—"

    data = {
        "bus": bus.to_dict(),
        "trip": active_trip.to_dict() if active_trip else None,
        "route": route.to_dict() if route else None,
        "is_active_trip": bool(active_trip),
        "trip_message": "Active trip in progress" if active_trip else "Not currently on an active trip.",
        "message": "Active trip in progress" if active_trip else "Not currently on an active trip.",
        "statistics": stats,
        "timeline": route_timeline,
        "incident": active_incident.to_dict() if active_incident else None,
        "depot_request": depot_req,
        "scheduled_arrival": sch_arrival,
        "expected_arrival": exp_arrival,
        "last_update": last_update_str,
    }
    return api_success(data=data, message="Active trip in progress" if active_trip else "Not currently on an active trip.")


@passenger_bp.route("/live-status", methods=["GET"])
def get_live_status():
    """Returns active buses with real GPS coordinates for the passenger map."""
    ACTIVE_STATUSES = ["RUNNING", "DELAYED", "PUNCTURED", "BREAKDOWN"]
    trips = Trip.query.filter(Trip.status.in_(ACTIVE_STATUSES)).all()

    results = []
    now = datetime.utcnow()

    for trip in trips:
        bus = trip.bus
        route = trip.route
        latest_gps = trip.gps_records.first()

        if not latest_gps:
            continue

        delta_seconds = max(0, int((now - latest_gps.timestamp).total_seconds()))

        results.append({
            "trip_id": trip.id,
            "trip_code": trip.trip_code,
            "bus_id": bus.id,
            "bus_number": bus.bus_number,
            "route_number": route.route_number if route else None,
            "route_name": route.name if route else None,
            "source": route.source if route else None,
            "destination": route.destination if route else None,
            "status": trip.status,
            "current_stop": trip.current_stop.name if trip.current_stop else "In Transit",
            "next_stop": trip.next_stop.name if trip.next_stop else None,
            "available_seats": trip.available_seats,
            "capacity": bus.capacity,
            "latitude": latest_gps.latitude,
            "longitude": latest_gps.longitude,
            "speed_kmh": latest_gps.speed_kmh,
            "gps_source": latest_gps.source,
            "recorded_at": latest_gps.timestamp.isoformat() if latest_gps.timestamp else None,
            "seconds_ago": delta_seconds,
            "freshness": latest_gps.freshness_status,
            "driver_name": trip.driver.full_name if trip.driver else None,
        })

    return api_success(data=results)


@passenger_bp.route("/alternatives/<int:incident_id>", methods=["GET"])
def get_alternatives(incident_id: int):
    incident = Incident.query.get(incident_id)
    if not incident:
        return api_error(code="NOT_FOUND", message="Incident not found", status_code=404)

    alternatives = AlternativeBusService.find_alternatives_for_incident(incident)
    depot_req = incident.depot_request
    replacement_info = None

    if depot_req and depot_req.replacement_bus:
        replacement_info = {
            "bus_number": depot_req.replacement_bus.bus_number,
            "capacity": depot_req.replacement_bus.capacity,
            "status": depot_req.status,
            "eta_minutes": depot_req.eta_minutes,
            "driver_name": depot_req.replacement_driver.full_name if depot_req.replacement_driver else None,
            "allocated_passengers": max(0, incident.affected_passengers - sum(a.get("allocated_passengers", 0) for a in alternatives))
        }

    return api_success(data={
        "incident": incident.to_dict(),
        "affected_passengers": incident.affected_passengers,
        "alternatives": alternatives,
        "replacement_bus": replacement_info,
        "depot_request": depot_req.to_dict() if depot_req else None
    })


@passenger_bp.route("/replacement/<string:request_identifier>", methods=["GET"])
@passenger_bp.route("/replacement/<int:request_identifier>", methods=["GET"])
def get_replacement_status(request_identifier):
    req = None
    if isinstance(request_identifier, int) or str(request_identifier).isdigit():
        req = DepotRequest.query.get(int(request_identifier))
    if not req:
        req = DepotRequest.query.filter_by(request_code=str(request_identifier)).first()
    if not req:
        return api_error(code="NOT_FOUND", message=f"Depot request '{request_identifier}' not found", status_code=404)
    return api_success(data=req.to_dict())



@passenger_bp.route("/summary", methods=["GET"])
def get_passenger_summary():
    """Live network overview metrics for passenger dashboard/home."""
    active_buses = Bus.query.filter(Bus.current_status.in_(["RUNNING", "DELAYED", "PUNCTURED"])).count()
    delayed_buses = Bus.query.filter_by(current_status="DELAYED").count()
    open_incidents = Incident.query.filter_by(status="OPEN").count()
    total_buses = Bus.query.count()

    total_records = db.session.query(func.count(HistoricalDelay.id)).scalar() or 0
    on_time_records = db.session.query(func.count(HistoricalDelay.id)).filter(HistoricalDelay.delay_minutes <= 5.0).scalar() or 0
    on_time_rate = round((on_time_records / total_records) * 100.0, 1) if total_records > 0 else 87.4

    avg_delay_result = db.session.query(func.avg(HistoricalDelay.delay_minutes)).scalar()
    avg_delay = round(float(avg_delay_result), 1) if avg_delay_result is not None else 10.5

    return api_success(data={
        "active_buses": active_buses,
        "delayed_buses": delayed_buses,
        "open_incidents": open_incidents,
        "total_buses": total_buses,
        "on_time_percentage": on_time_rate,
        "average_delay_min": avg_delay
    })


@passenger_bp.route("/incidents/active", methods=["GET"])
def get_active_incident():
    """Returns latest open emergency incident with ranked alternatives and depot state."""
    incident = Incident.query.filter_by(status="OPEN").order_by(Incident.id.desc()).first()
    if not incident:
        return api_success(data=None, message="No active emergency incidents.")

    alternatives = AlternativeBusService.find_alternatives_for_incident(incident)
    depot_req = incident.depot_request
    replacement_info = None

    if depot_req and depot_req.replacement_bus:
        replacement_info = {
            "bus_number": depot_req.replacement_bus.bus_number,
            "capacity": depot_req.replacement_bus.capacity,
            "status": depot_req.status,
            "eta_minutes": depot_req.eta_minutes,
            "driver_name": depot_req.replacement_driver.full_name if depot_req.replacement_driver else None,
            "allocated_passengers": max(0, incident.affected_passengers - sum(a.get("allocated_passengers", 0) for a in alternatives))
        }

    return api_success(data={
        "incident": incident.to_dict(),
        "affected_passengers": incident.affected_passengers,
        "alternatives": alternatives,
        "replacement_bus": replacement_info,
        "depot_request": depot_req.to_dict() if depot_req else None
    })


# ===========================================================================
# 3. DRIVER API ROUTES (/api/driver)
# ===========================================================================
driver_bp = Blueprint("driver_api", __name__, url_prefix="/api/driver")


@driver_bp.route("/dashboard", methods=["GET"])
@role_required("driver", "admin")
def get_driver_dashboard():
    user_id = session.get("user_id")
    user = User.query.get(user_id) if user_id else None
    driver = Driver.query.filter_by(user_id=user_id).first() if user_id else None
    if not driver:
        if user and user.role == "admin":
            driver = Driver.query.first()
        else:
            return api_error(code="NOT_FOUND", message="No driver profile found.", status_code=404)

    active_trip = None
    if driver.assigned_bus_id:
        active_trip = Trip.query.filter(
            Trip.driver_id == driver.id,
            Trip.bus_id == driver.assigned_bus_id,
            Trip.status.in_(["RUNNING", "DELAYED", "PUNCTURED", "BREAKDOWN", "SCHEDULED"])
        ).order_by(Trip.id.desc()).first()

    if not active_trip:
        active_trip = Trip.query.filter(
            Trip.driver_id == driver.id,
            Trip.status.in_(["RUNNING", "DELAYED", "PUNCTURED", "BREAKDOWN", "SCHEDULED"])
        ).order_by(Trip.id.desc()).first()

    if not active_trip and driver.assigned_bus_id:
        active_trip = Trip.query.filter(
            Trip.bus_id == driver.assigned_bus_id,
            Trip.status.in_(["RUNNING", "DELAYED", "PUNCTURED", "BREAKDOWN", "SCHEDULED"])
        ).order_by(Trip.id.desc()).first()

    assigned_bus = driver.assigned_bus or (active_trip.bus if active_trip else None)
    assigned_route = (active_trip.route if active_trip else None) or (assigned_bus.assigned_route if assigned_bus else None)

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
@role_required("driver", "admin")
def start_trip():
    data = request.get_json() or {}
    bus_id = data.get("bus_id")
    route_id = data.get("route_id")
    starting_stop_id = data.get("starting_stop_id")
    initial_passenger_count = int(data.get("passenger_count", 0))

    user_id = session.get("user_id")
    user = User.query.get(user_id) if user_id else None
    driver = Driver.query.filter_by(user_id=user_id).first() if user_id else None
    if not driver and user and user.role == "admin":
        driver = Driver.query.first()

    if not driver:
        return api_error(code="NOT_FOUND", message="No driver profile found.", status_code=404)

    bus = Bus.query.get(bus_id) if bus_id else (driver.assigned_bus if driver else None)
    if not bus:
        return api_error(code="VALIDATION_ERROR", message="Bus not found or not assigned.", status_code=400)

    route = Route.query.get(route_id) if route_id else bus.assigned_route
    if not route:
        return api_error(code="VALIDATION_ERROR", message="Route not found.", status_code=400)

    if not starting_stop_id and route.route_stops:
        starting_stop_id = route.route_stops[0].stop_id

    if initial_passenger_count > bus.capacity:
        return api_error(code="CAPACITY_EXCEEDED", message=f"Passenger count ({initial_passenger_count}) exceeds bus capacity ({bus.capacity}).", status_code=400)

    # Complete/supersede any existing active trips for this bus
    active_bus_trips = Trip.query.filter(
        Trip.bus_id == bus.id,
        Trip.status.in_(["RUNNING", "DELAYED", "PUNCTURED", "BREAKDOWN", "SCHEDULED", "DISPATCHED"])
    ).all()
    for ot in active_bus_trips:
        ot.status = "COMPLETED"
        ot.actual_end_time = datetime.utcnow()

    # Complete/supersede any existing active trips for this driver
    if driver:
        active_driver_trips = Trip.query.filter(
            Trip.driver_id == driver.id,
            Trip.status.in_(["RUNNING", "DELAYED", "PUNCTURED", "BREAKDOWN", "SCHEDULED", "DISPATCHED"])
        ).all()
        for odt in active_driver_trips:
            odt.status = "COMPLETED"
            odt.actual_end_time = datetime.utcnow()

    max_id = db.session.query(func.coalesce(func.max(Trip.id), 0)).scalar() or 0
    trip_code = f"TRIP-{bus.id}-{max_id + 1:04d}"
    if Trip.query.filter_by(trip_code=trip_code).first():
        trip_code = f"TRIP-{bus.id}-{max_id + 1:04d}-{int(time.time() * 1000) % 100000:05d}"

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
    bus.assigned_route_id = route.id
    bus.current_status = "RUNNING"
    if driver:
        driver.assigned_bus_id = bus.id
        driver.status = "ON_TRIP"

    db.session.commit()
    return api_success(data=trip.to_dict(), message="Trip started successfully", status_code=201)


@driver_bp.route("/trip/stop-update", methods=["POST"])
@driver_bp.route("/trip/stop", methods=["POST"])
@driver_bp.route("/trip/passengers", methods=["POST"])
@role_required("driver", "admin")
def update_stop():
    data = request.get_json() or {}
    trip_id = data.get("trip_id")
    stop_id = data.get("stop_id")
    passenger_count = data.get("passenger_count")

    trip = Trip.query.get(trip_id)
    if not trip:
        return api_error(code="NOT_FOUND", message="Trip not found.", status_code=404)

    user_id = session.get("user_id")
    user = User.query.get(user_id) if user_id else None
    if user and user.role != "admin":
        driver = Driver.query.filter_by(user_id=user_id).first()
        if not driver or (trip.driver_id and trip.driver_id != driver.id):
            return api_error(code="FORBIDDEN", message="You are not authorized to update this trip.", status_code=403)

    stop = Stop.query.get(stop_id) if stop_id else trip.current_stop
    if not stop:
        return api_error(code="NOT_FOUND", message="Stop not found.", status_code=404)

    trip.current_stop_id = stop.id

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

        pax_log = PassengerCount(
            trip_id=trip.id,
            stop_id=stop.id,
            boarding_count=max(0, p_count - old_count),
            alighting_count=max(0, old_count - p_count),
            current_passenger_count=p_count,
            recorded_at=datetime.utcnow()
        )
        db.session.add(pax_log)

    gps = LiveGPS(
        trip_id=trip.id,
        bus_id=trip.bus_id,
        latitude=stop.latitude,
        longitude=stop.longitude,
        speed_kmh=0.0,
        source="MANUAL_STOP",
        timestamp=datetime.utcnow()
    )
    db.session.add(gps)
    db.session.commit()
    return api_success(data=trip.to_dict(), message=f"Updated current stop to {stop.name}")


@driver_bp.route("/trip/gps", methods=["POST"])
@role_required("driver", "admin")
def update_gps():
    data = request.get_json() or {}
    trip_id = data.get("trip_id")
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    speed = float(data.get("speed_kmh", 0.0))
    source = data.get("source", "GPS")

    user_id = session.get("user_id")
    user = User.query.get(user_id) if user_id else None
    driver = Driver.query.filter_by(user_id=user_id).first() if user_id else None

    trip = None
    if trip_id:
        trip = Trip.query.get(trip_id)
    elif driver:
        trip = Trip.query.filter(
            Trip.driver_id == driver.id,
            Trip.status.in_(["RUNNING", "DELAYED", "PUNCTURED", "BREAKDOWN"])
        ).order_by(Trip.id.desc()).first()

    if not trip:
        return api_error(code="NOT_FOUND", message="Active trip not found.", status_code=404)

    if user and user.role != "admin":
        if not driver or (trip.driver_id and trip.driver_id != driver.id):
            return api_error(code="FORBIDDEN", message="You are not authorized to update this trip.", status_code=403)


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
@role_required("driver", "admin")
def update_driver_gps():
    """Secure endpoint for driver browser watchPosition(). Derives bus and trip from session."""
    user_id = session.get("user_id")
    driver = Driver.query.filter_by(user_id=user_id).first()
    if not driver:
        return api_error(code="DRIVER_NOT_FOUND", message="No driver profile associated with this account.", status_code=400)

    active_trip = None
    if driver.assigned_bus_id:
        active_trip = Trip.query.filter(
            Trip.driver_id == driver.id,
            Trip.bus_id == driver.assigned_bus_id,
            Trip.status.in_(["RUNNING", "DELAYED", "PUNCTURED", "BREAKDOWN"])
        ).order_by(Trip.id.desc()).first()

    if not active_trip:
        active_trip = Trip.query.filter(
            Trip.driver_id == driver.id,
            Trip.status.in_(["RUNNING", "DELAYED", "PUNCTURED", "BREAKDOWN"])
        ).order_by(Trip.id.desc()).first()

    if not active_trip and driver.assigned_bus_id:
        active_trip = Trip.query.filter(
            Trip.bus_id == driver.assigned_bus_id,
            Trip.status.in_(["RUNNING", "DELAYED", "PUNCTURED", "BREAKDOWN"])
        ).order_by(Trip.id.desc()).first()

    if not active_trip:
        return api_error(code="NO_ACTIVE_TRIP", message="You do not have an active trip. Start a trip before sharing GPS.", status_code=400)

    bus = Bus.query.get(active_trip.bus_id)
    if not bus or not bus.is_active:
        return api_error(code="BUS_NOT_ACTIVE", message="Assigned bus is not available or inactive.", status_code=400)

    data = request.get_json(silent=True) or {}
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    speed_raw = data.get("speed")
    timestamp_raw = data.get("timestamp")

    if latitude is None or longitude is None:
        return api_error(code="VALIDATION_ERROR", message="latitude and longitude are required fields.", status_code=400)

    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (ValueError, TypeError):
        return api_error(code="VALIDATION_ERROR", message="latitude and longitude must be numeric values.", status_code=400)

    if not (-90.0 <= latitude <= 90.0) or not (-180.0 <= longitude <= 180.0):
        return api_error(code="VALIDATION_ERROR", message="Coordinates out of valid range.", status_code=400)

    speed_kmh = 0.0
    if speed_raw is not None:
        try:
            speed_kmh = float(speed_raw)
        except (ValueError, TypeError):
            return api_error(code="VALIDATION_ERROR", message="speed must be numeric.", status_code=400)
        if speed_kmh < 0:
            return api_error(code="VALIDATION_ERROR", message="speed cannot be negative.", status_code=400)

    gps_timestamp = datetime.utcnow()
    if timestamp_raw:
        try:
            gps_timestamp = datetime.fromisoformat(str(timestamp_raw).replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            gps_timestamp = datetime.utcnow()

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
        pass

    db.session.commit()
    return api_success(data=gps.to_dict(), message="GPS location updated successfully.")


@driver_bp.route("/trip/emergency", methods=["POST"])
@role_required("driver", "admin")
def report_emergency():
    data = request.get_json() or {}
    trip_id = data.get("trip_id")
    incident_type = data.get("incident_type", "Tyre Puncture")
    affected_passengers = int(data.get("affected_passengers", 40))
    description = data.get("description", "Tyre puncture occurred en route.")
    priority = data.get("priority", "HIGH")
    stop_id = data.get("stop_id")

    if not trip_id:
        return api_error(code="VALIDATION_ERROR", message="Trip ID is required.", status_code=400)

    trip = Trip.query.get(int(trip_id))
    if not trip:
        return api_error(code="NOT_FOUND", message="Trip not found.", status_code=404)

    user_id = session.get("user_id")
    user = User.query.get(user_id) if user_id else None
    if user and user.role != "admin":
        driver = Driver.query.filter_by(user_id=user_id).first()
        if not driver or (trip.driver_id and trip.driver_id != driver.id):
            return api_error(code="FORBIDDEN", message="You are not authorized to report an emergency on this trip.", status_code=403)

    try:
        result = IncidentService.report_emergency(
            trip_id=int(trip_id),
            incident_type=incident_type,
            affected_passengers=affected_passengers,
            description=description,
            priority=priority,
            current_stop_id=int(stop_id) if stop_id else None,
            user_id=user_id
        )
        return api_success(data=result, message="Emergency reported successfully. Depot dispatch initiated.")
    except Exception as e:
        return api_error(code="EMERGENCY_REPORT_FAILED", message=str(e), status_code=400)


@driver_bp.route("/trip/end", methods=["POST"])
@role_required("driver", "admin")
def end_trip():
    data = request.get_json() or {}
    trip_id = data.get("trip_id")

    trip = Trip.query.get(trip_id)
    if not trip:
        return api_error(code="NOT_FOUND", message="Trip not found.", status_code=404)

    user_id = session.get("user_id")
    user = User.query.get(user_id) if user_id else None
    if user and user.role != "admin":
        driver = Driver.query.filter_by(user_id=user_id).first()
        if not driver or (trip.driver_id and trip.driver_id != driver.id):
            return api_error(code="FORBIDDEN", message="You are not authorized to end this trip.", status_code=403)

    trip.status = "COMPLETED"
    trip.actual_end_time = datetime.utcnow()
    if trip.bus:
        trip.bus.current_status = "AVAILABLE"
    if trip.driver:
        trip.driver.status = "AVAILABLE"

    db.session.commit()
    return api_success(data=trip.to_dict(), message="Trip completed successfully")


# ===========================================================================
# 4. DEPOT OPERATOR API ROUTES (/api/depot)
# ===========================================================================
depot_bp = Blueprint("depot_api", __name__, url_prefix="/api/depot")


@depot_bp.route("/dashboard", methods=["GET"])
@role_required("depot_operator", "admin")
def get_depot_dashboard():
    total_reqs = DepotRequest.query.count()
    pending = DepotRequest.query.filter_by(status="PENDING").count()
    assigned = DepotRequest.query.filter_by(status="ASSIGNED").count()
    dispatched = DepotRequest.query.filter_by(status="DISPATCHED").count()
    arrived = DepotRequest.query.filter_by(status="ARRIVED").count()
    passenger_transfer = DepotRequest.query.filter_by(status="PASSENGER_TRANSFER").count()
    resolved = DepotRequest.query.filter_by(status="RESOLVED").count()

    available_buses = Bus.query.filter(
        Bus.is_active == True,
        Bus.current_status.in_(["AVAILABLE", "COMPLETED"])
    ).all()

    available_drivers = Driver.query.filter(
        Driver.status.in_(["AVAILABLE", "OFF_DUTY"])
    ).all()

    active_requests = DepotRequest.query.filter(
        DepotRequest.status.in_(["PENDING", "ASSIGNED", "DISPATCHED", "ARRIVED", "PASSENGER_TRANSFER"])
    ).order_by(DepotRequest.id.desc()).all()

    return api_success(data={
        "counts": {
            "total": total_reqs,
            "pending": pending,
            "assigned": assigned,
            "dispatched": dispatched,
            "arrived": arrived,
            "passenger_transfer": passenger_transfer,
            "resolved": resolved,
            "available_buses": len(available_buses),
            "available_drivers": len(available_drivers),
        },
        "active_requests": [r.to_dict() for r in active_requests],
        "available_buses": [b.to_dict() for b in available_buses],
        "available_drivers": [d.to_dict() for d in available_drivers]
    })


@depot_bp.route("/requests", methods=["GET"])
@role_required("depot_operator", "admin")
def get_requests():
    status = request.args.get("status")
    query = DepotRequest.query
    if status and status.upper() != "ALL":
        query = query.filter_by(status=status.upper())
    requests_list = query.order_by(DepotRequest.id.desc()).all()
    return api_success(data=[r.to_dict() for r in requests_list])


@depot_bp.route("/requests/<int:request_id>", methods=["GET"])
@role_required("depot_operator", "admin")
def get_request_detail(request_id: int):
    req = DepotRequest.query.get(request_id)
    if not req:
        return api_error(code="NOT_FOUND", message="Depot request not found.", status_code=404)
    return api_success(data=req.to_dict())


@depot_bp.route("/assign", methods=["POST"])
@role_required("depot_operator", "admin")
def assign():
    data = request.get_json() or {}
    request_id = data.get("request_id")
    bus_id = data.get("bus_id") or data.get("replacement_bus_id")
    driver_id = data.get("driver_id") or data.get("replacement_driver_id")
    eta_minutes = int(data.get("eta_minutes", 12))

    if not request_id or not bus_id or not driver_id:
        return api_error(code="VALIDATION_ERROR", message="Request ID, Bus ID, and Driver ID are required.", status_code=400)

    try:
        operator_id = session.get("user_id")
        result = DepotWorkflowService.assign_resources(
            request_id=int(request_id),
            bus_id=int(bus_id),
            driver_id=int(driver_id),
            operator_id=operator_id,
            eta_minutes=eta_minutes
        )
        return api_success(data=result, message="Replacement bus and driver assigned successfully.")
    except Exception as e:
        return api_error(code="ASSIGNMENT_FAILED", message=str(e), status_code=400)


@depot_bp.route("/dispatch", methods=["POST"])
@role_required("depot_operator", "admin")
def dispatch():
    data = request.get_json() or {}
    request_id = data.get("request_id")
    if not request_id:
        return api_error(code="VALIDATION_ERROR", message="Request ID is required.", status_code=400)

    try:
        operator_id = session.get("user_id")
        result = DepotWorkflowService.dispatch_bus(int(request_id), operator_id=operator_id)
        return api_success(data=result, message="Replacement bus dispatched successfully.")
    except Exception as e:
        return api_error(code="DISPATCH_FAILED", message=str(e), status_code=400)


@depot_bp.route("/arrive", methods=["POST"])
@role_required("depot_operator", "admin")
def arrive():
    data = request.get_json() or {}
    request_id = data.get("request_id")
    if not request_id:
        return api_error(code="VALIDATION_ERROR", message="Request ID is required.", status_code=400)

    try:
        operator_id = session.get("user_id")
        result = DepotWorkflowService.mark_arrived(int(request_id), operator_id=operator_id)
        return api_success(data=result, message="Replacement bus arrival confirmed.")
    except Exception as e:
        return api_error(code="ARRIVAL_FAILED", message=str(e), status_code=400)


@depot_bp.route("/transfer", methods=["POST"])
@role_required("depot_operator", "admin")
def record_transfer():
    data = request.get_json() or {}
    request_id = data.get("request_id")
    transferred_count = data.get("transferred_count") if data.get("transferred_count") is not None else (data.get("transferred_passengers") if data.get("transferred_passengers") is not None else data.get("passenger_count"))

    if not request_id or transferred_count is None:
        return api_error(code="VALIDATION_ERROR", message="Request ID and transferred count are required.", status_code=400)

    try:
        operator_id = session.get("user_id")
        result = DepotWorkflowService.record_passenger_transfer(
            request_id=int(request_id),
            transferred_count=int(transferred_count),
            operator_id=operator_id
        )
        return api_success(data=result, message="Passenger transfer recorded successfully.")
    except Exception as e:
        return api_error(code="TRANSFER_FAILED", message=str(e), status_code=400)


@depot_bp.route("/resolve", methods=["POST"])
@role_required("depot_operator", "admin")
def resolve():
    data = request.get_json() or {}
    request_id = data.get("request_id")
    resolution_notes = data.get("resolution_notes") or data.get("notes", "All passengers transferred successfully. Trip resumed.")

    if not request_id:
        return api_error(code="VALIDATION_ERROR", message="Request ID is required.", status_code=400)

    try:
        operator_id = session.get("user_id")
        result = DepotWorkflowService.resolve_request(
            request_id=int(request_id),
            resolution_notes=resolution_notes,
            operator_id=operator_id
        )
        return api_success(data=result, message="Depot request marked RESOLVED. Service fully restored.")
    except Exception as e:
        return api_error(code="RESOLUTION_FAILED", message=str(e), status_code=400)


# ===========================================================================
# 5. ADMIN API ROUTES (/api/admin)
# ===========================================================================
admin_bp = Blueprint("admin_api", __name__, url_prefix="/api/admin")


@admin_bp.route("/dashboard", methods=["GET"])
@role_required("admin")
def get_admin_dashboard():
    total_buses = Bus.query.count()
    active_buses = Bus.query.filter(Bus.current_status.in_(["RUNNING", "DELAYED", "PUNCTURED"])).count()
    delayed_buses = Bus.query.filter_by(current_status="DELAYED").count()
    open_incidents = Incident.query.filter_by(status="OPEN").count()
    pending_depot = DepotRequest.query.filter(DepotRequest.status.in_(["PENDING", "ASSIGNED", "DISPATCHED", "ARRIVED"])).count()
    replacement_buses = Bus.query.filter(Bus.current_status.in_(["ASSIGNED", "DISPATCHED"])).count()

    recent_incidents = Incident.query.order_by(Incident.id.desc()).limit(5).all()
    recent_depot = DepotRequest.query.order_by(DepotRequest.id.desc()).limit(5).all()

    avg_delay_result = db.session.query(func.avg(HistoricalDelay.delay_minutes)).scalar()
    avg_delay = round(float(avg_delay_result), 1) if avg_delay_result is not None else 11.4

    total_records = db.session.query(func.count(HistoricalDelay.id)).scalar() or 0
    on_time_records = db.session.query(func.count(HistoricalDelay.id)).filter(HistoricalDelay.delay_minutes <= 5.0).scalar() or 0
    on_time_pct = round((on_time_records / total_records) * 100.0, 1) if total_records > 0 else 82.5

    return api_success(data={
        "kpis": {
            "total_buses": total_buses,
            "active_buses": active_buses,
            "delayed_buses": delayed_buses,
            "open_incidents": open_incidents,
            "pending_depot_requests": pending_depot,
            "replacement_buses": replacement_buses,
            "average_delay_min": avg_delay,
            "on_time_percentage": on_time_pct,
        },
        "recent_incidents": [i.to_dict() for i in recent_incidents],
        "recent_depot_requests": [d.to_dict() for d in recent_depot]
    })


@admin_bp.route("/live-buses", methods=["GET"])
@role_required("admin")
def get_live_buses():
    trips = Trip.query.filter(Trip.status.in_(["RUNNING", "DELAYED", "PUNCTURED", "BREAKDOWN", "SCHEDULED"])).all()
    results = []
    now = datetime.utcnow()

    for trip in trips:
        bus = trip.bus
        route = trip.route
        latest_gps = trip.gps_records.first()

        if latest_gps:
            delta_s = max(0, int((now - latest_gps.timestamp).total_seconds()))
            last_update_label = f"{delta_s}s ago" if delta_s < 60 else (f"{delta_s // 60}m ago" if delta_s < 3600 else f"{delta_s // 3600}h ago")
            freshness = latest_gps.freshness_status
            gps_lat = latest_gps.latitude
            gps_lon = latest_gps.longitude
            speed_kmh = latest_gps.speed_kmh
            recorded_at = latest_gps.timestamp.isoformat()
        else:
            delta_s = None
            last_update_label = "No GPS"
            freshness = "Offline"
            gps_lat = trip.current_stop.latitude if trip.current_stop else 18.5204
            gps_lon = trip.current_stop.longitude if trip.current_stop else 73.8567
            speed_kmh = 0.0
            recorded_at = None

        stats = DelayStatisticsService.get_stop_delay_stats(
            route_id=route.id,
            stop_id=trip.current_stop_id or (route.route_stops[0].stop_id if route and route.route_stops else 1)
        ) if route else {}
        expected_delay = float(stats.get("expected_delay", 0.0))
        if trip.status == "DELAYED" and expected_delay <= 0:
            expected_delay = 8.0
        elif trip.status == "PUNCTURED":
            expected_delay = max(expected_delay, 15.0)
        elif trip.status == "BREAKDOWN":
            expected_delay = max(expected_delay, 25.0)

        results.append({
            "bus_id": bus.id,
            "bus_number": bus.bus_number,
            "registration": bus.registration_number,
            "route_number": route.route_number if route else "N/A",
            "route_name": route.name if route else "N/A",
            "status": trip.status,
            "current_stop": trip.current_stop.name if trip.current_stop else "Depot",
            "delay_min": expected_delay,
            "available_seats": trip.available_seats,
            "capacity": bus.capacity,
            "driver_name": trip.driver.full_name if trip.driver else "Unassigned",
            "driver_code": trip.driver.driver_code if trip.driver else None,
            "latitude": gps_lat,
            "longitude": gps_lon,
            "speed_kmh": speed_kmh,
            "recorded_at": recorded_at,
            "seconds_ago": delta_s,
            "freshness": freshness,
            "last_update": last_update_label,
        })

    return api_success(data=results)


@admin_bp.route("/analytics", methods=["GET"])
@role_required("admin")
def get_analytics():
    # 1. Delay Reasons aggregation from MySQL
    reasons_query = db.session.query(
        HistoricalDelay.delay_reason,
        func.count(HistoricalDelay.id)
    ).filter(HistoricalDelay.delay_reason.isnot(None))\
     .group_by(HistoricalDelay.delay_reason)\
     .order_by(func.count(HistoricalDelay.id).desc()).all()

    if reasons_query:
        reasons_labels = [r[0] for r in reasons_query]
        reasons_values = [int(r[1]) for r in reasons_query]
    else:
        reasons_labels = ["Traffic Congestion", "Tyre Puncture", "Engine Breakdown", "Weather / Rain", "Passenger Surge", "Other Incident"]
        reasons_values = [45, 12, 8, 15, 14, 6]

    # 2. Weekday delays (0=Mon, 6=Sun)
    weekday_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekday_query = db.session.query(
        HistoricalDelay.weekday,
        func.avg(HistoricalDelay.delay_minutes)
    ).filter(HistoricalDelay.weekday.isnot(None))\
     .group_by(HistoricalDelay.weekday).all()

    weekday_map = {w: 0.0 for w in range(7)}
    for row in weekday_query:
        try:
            w_idx = int(row[0])
            if 0 <= w_idx < 7:
                weekday_map[w_idx] = round(float(row[1]), 1)
        except (ValueError, TypeError):
            pass

    weekday_delays = [weekday_map[i] for i in range(7)]
    if all(v == 0.0 for v in weekday_delays):
        weekday_delays = [13.2, 11.5, 12.8, 14.1, 16.5, 9.8, 7.4]

    # 3. Hourly delays (hours 6 to 22)
    hours_labels = [f"{h}:00" for h in range(6, 23)]
    hourly_query = db.session.query(
        HistoricalDelay.hour_of_day,
        func.avg(HistoricalDelay.delay_minutes)
    ).filter(HistoricalDelay.hour_of_day.between(6, 22))\
     .group_by(HistoricalDelay.hour_of_day).all()

    hourly_map = {h: 0.0 for h in range(6, 23)}
    for row in hourly_query:
        try:
            h_val = int(row[0])
            if 6 <= h_val <= 22:
                hourly_map[h_val] = round(float(row[1]), 1)
        except (ValueError, TypeError):
            pass

    hourly_delays = [hourly_map[h] for h in range(6, 23)]
    if all(v == 0.0 for v in hourly_delays):
        hourly_delays = [4.2, 8.5, 14.2, 16.8, 12.1, 9.4, 8.8, 9.2, 11.0, 15.5, 18.2, 17.0, 12.4, 8.0, 5.5, 4.0, 3.2]

    # 4. Route delays (Top routes by average delay)
    route_query = db.session.query(
        Route.route_number,
        Route.name,
        func.avg(HistoricalDelay.delay_minutes)
    ).join(HistoricalDelay, HistoricalDelay.route_id == Route.id)\
     .group_by(Route.id, Route.route_number, Route.name)\
     .order_by(func.avg(HistoricalDelay.delay_minutes).desc())\
     .limit(8).all()

    if route_query:
        route_labels = [f"Route {r[0]} ({r[1]})" for r in route_query]
        route_delays = [round(float(r[2]), 1) for r in route_query]
    else:
        route_labels = ["Route 101 (Pune-Hadapsar)", "Route 102 (Swargate-Katraj)", "Route 103 (Kothrud-Viman)", "Route 104 (Hinjewadi-Pune)", "Route 105 (Deccan-Pimpri)"]
        route_delays = [14.0, 8.2, 11.5, 16.4, 7.8]

    # 5. Overall on-time rate
    total_records = db.session.query(func.count(HistoricalDelay.id)).scalar() or 0
    on_time_records = db.session.query(func.count(HistoricalDelay.id)).filter(HistoricalDelay.delay_minutes <= 5.0).scalar() or 0
    on_time_rate = round((on_time_records / total_records) * 100.0, 1) if total_records > 0 else 82.5

    # 6. On-Time Distribution (On-time <=5m, Moderate 5-15m, Severe >15m)
    moderate_records = db.session.query(func.count(HistoricalDelay.id)).filter(
        HistoricalDelay.delay_minutes > 5.0,
        HistoricalDelay.delay_minutes <= 15.0
    ).scalar() or 0
    severe_records = db.session.query(func.count(HistoricalDelay.id)).filter(
        HistoricalDelay.delay_minutes > 15.0
    ).scalar() or 0

    on_time_dist = {
        "labels": ["On-Time (<= 5 min)", "Moderate Delay (5-15 min)", "Severe Delay (> 15 min)"],
        "values": [int(on_time_records), int(moderate_records), int(severe_records)]
    }

    # 7. Incident Statistics by Category
    incident_rows = db.session.query(
        Incident.incident_type,
        func.count(Incident.id)
    ).group_by(Incident.incident_type).all()

    if incident_rows:
        inc_labels = [row[0] for row in incident_rows]
        inc_values = [int(row[1]) for row in incident_rows]
    else:
        inc_labels = ["Tyre Puncture", "Engine Failure", "Traffic Blockage", "Accident", "Fuel Problem"]
        inc_values = [12, 8, 25, 4, 3]

    incident_stats = {
        "labels": inc_labels,
        "values": inc_values
    }

    # 8. Depot Resolution Statistics by Stage
    depot_stages = ["PENDING", "ASSIGNED", "DISPATCHED", "ARRIVED", "PASSENGER_TRANSFER", "RESOLVED"]
    depot_rows = db.session.query(
        DepotRequest.status,
        func.count(DepotRequest.id)
    ).group_by(DepotRequest.status).all()

    depot_counts_map = {st: 0 for st in depot_stages}
    for row in depot_rows:
        st_name = str(row[0]).upper()
        if st_name in depot_counts_map:
            depot_counts_map[st_name] = int(row[1])

    if sum(depot_counts_map.values()) == 0:
        depot_counts_map = {
            "PENDING": 1,
            "ASSIGNED": 1,
            "DISPATCHED": 2,
            "ARRIVED": 1,
            "PASSENGER_TRANSFER": 1,
            "RESOLVED": 8
        }

    depot_resolution_stats = {
        "labels": ["Pending", "Assigned", "Dispatched", "Arrived", "Transfer", "Resolved"],
        "values": [depot_counts_map[st] for st in depot_stages]
    }

    return api_success(data={
        "delay_reasons": {"labels": reasons_labels, "values": reasons_values},
        "weekday_delays": {"labels": weekday_labels, "values": weekday_delays},
        "hourly_delays": {"labels": hours_labels, "values": hourly_delays},
        "route_delays": {"labels": route_labels, "values": route_delays},
        "on_time_rate": on_time_rate,
        "on_time_distribution": on_time_dist,
        "incident_stats": incident_stats,
        "depot_resolution_stats": depot_resolution_stats
    })


@admin_bp.route("/buses", methods=["GET", "POST"])
@role_required("admin")
def handle_buses():
    if request.method == "POST":
        data = request.get_json() or {}
        num = data.get("bus_number")
        reg = data.get("registration_number")
        cap = int(data.get("capacity", 40))
        route_id = data.get("assigned_route_id")

        if not num or not reg:
            return api_error(code="VALIDATION_ERROR", message="Bus number and registration are required.", status_code=400)

        bus = Bus(bus_number=num, registration_number=reg, capacity=cap, assigned_route_id=route_id)
        db.session.add(bus)
        db.session.commit()
        return api_success(data=bus.to_dict(), message="Bus added successfully", status_code=201)

    buses = Bus.query.all()
    return api_success(data=[b.to_dict() for b in buses])


@admin_bp.route("/buses/<int:bus_id>", methods=["PUT", "DELETE"])
@role_required("admin")
def update_delete_bus(bus_id: int):
    bus = Bus.query.get(bus_id)
    if not bus:
        return api_error(code="NOT_FOUND", message="Bus not found.", status_code=404)

    if request.method == "DELETE":
        db.session.delete(bus)
        db.session.commit()
        return api_success(message="Bus deleted successfully")

    data = request.get_json() or {}
    if "bus_number" in data:
        bus.bus_number = data["bus_number"]
    if "registration_number" in data:
        bus.registration_number = data["registration_number"]
    if "capacity" in data:
        bus.capacity = int(data["capacity"])
    if "is_active" in data:
        bus.is_active = bool(data["is_active"])
    if "assigned_route_id" in data:
        bus.assigned_route_id = data["assigned_route_id"]

    db.session.commit()
    return api_success(data=bus.to_dict(), message="Bus updated successfully")


@admin_bp.route("/routes", methods=["GET", "POST"])
@role_required("admin")
def handle_routes():
    if request.method == "POST":
        data = request.get_json() or {}
        r_num = data.get("route_number")
        name = data.get("name")
        src = data.get("source")
        dest = data.get("destination")
        dist = float(data.get("total_distance_km", 0.0))
        est_duration = int(data.get("estimated_duration_min", 45))

        if not r_num or not name or not src or not dest:
            return api_error(code="VALIDATION_ERROR", message="Route number, name, source, and destination are required.", status_code=400)

        route = Route(route_number=r_num, name=name, source=src, destination=dest, total_distance_km=dist, estimated_duration_min=est_duration)
        db.session.add(route)
        db.session.commit()
        return api_success(data=route.to_dict(), message="Route created successfully", status_code=201)

    include_stops = request.args.get("include_stops", "false").lower() == "true"
    if include_stops:
        routes = Route.query.options(selectinload(Route.route_stops).joinedload(RouteStop.stop)).all()
        return api_success(data=[r.to_dict(include_stops=True) for r in routes])
    routes = Route.query.all()
    return api_success(data=[r.to_dict(include_stops=False) for r in routes])


@admin_bp.route("/routes/<int:route_id>", methods=["PUT", "DELETE"])
@role_required("admin")
def update_delete_route(route_id: int):
    route = Route.query.get(route_id)
    if not route:
        return api_error(code="NOT_FOUND", message="Route not found", status_code=404)
    if request.method == "DELETE":
        route.is_active = False
        db.session.commit()
        return api_success(message=f"Route {route.route_number} deactivated successfully")
    data = request.get_json() or {}
    if "name" in data:
        route.name = data["name"]
    if "source" in data:
        route.source = data["source"]
    if "destination" in data:
        route.destination = data["destination"]
    if "total_distance_km" in data:
        route.total_distance_km = float(data["total_distance_km"])
    if "estimated_duration_min" in data:
        route.estimated_duration_min = int(data["estimated_duration_min"])
    if "is_active" in data:
        route.is_active = bool(data["is_active"])
    db.session.commit()
    return api_success(data=route.to_dict(), message="Route updated successfully")


@admin_bp.route("/stops", methods=["GET", "POST"])
@role_required("admin")
def handle_stops():
    if request.method == "POST":
        data = request.get_json() or {}
        code = data.get("stop_code")
        name = data.get("name")
        name_mr = data.get("name_mr")
        lat = data.get("latitude")
        lon = data.get("longitude")

        if not code or not name or lat is None or lon is None:
            return api_error(code="VALIDATION_ERROR", message="Stop code, name, latitude, and longitude are required.", status_code=400)

        stop = Stop(stop_code=code, name=name, name_mr=name_mr, latitude=float(lat), longitude=float(lon), landmark=data.get("landmark"))
        db.session.add(stop)
        db.session.commit()
        return api_success(data=stop.to_dict(), message="Stop created successfully", status_code=201)

    stops = Stop.query.all()
    return api_success(data=[s.to_dict() for s in stops])


@admin_bp.route("/stops/<int:stop_id>", methods=["PUT", "DELETE"])
@role_required("admin")
def update_delete_stop(stop_id: int):
    stop = Stop.query.get(stop_id)
    if not stop:
        return api_error(code="NOT_FOUND", message="Stop not found", status_code=404)
    if request.method == "DELETE":
        stop.is_active = False
        db.session.commit()
        return api_success(message=f"Stop {stop.stop_code} deactivated successfully")
    data = request.get_json() or {}
    if "name" in data:
        stop.name = data["name"]
    if "name_mr" in data:
        stop.name_mr = data["name_mr"]
    if "latitude" in data:
        stop.latitude = float(data["latitude"])
    if "longitude" in data:
        stop.longitude = float(data["longitude"])
    if "landmark" in data:
        stop.landmark = data["landmark"]
    if "is_active" in data:
        stop.is_active = bool(data["is_active"])
    db.session.commit()
    return api_success(data=stop.to_dict(), message="Stop updated successfully")


@admin_bp.route("/drivers", methods=["GET", "POST"])
@role_required("admin")
def handle_drivers():
    if request.method == "POST":
        data = request.get_json() or {}
        code = data.get("driver_code")
        name = data.get("full_name")
        mob = data.get("mobile_number")
        lic = data.get("license_number")

        if not code or not name or not mob or not lic:
            return api_error(code="VALIDATION_ERROR", message="Driver code, full name, mobile, and license are required.", status_code=400)

        username = f"driver_{code.lower()}"
        user = User.query.filter((User.username == username) | (User.email == f"{username}@busnotify.com")).first()
        if not user:
            user = User(username=username, email=f"{username}@busnotify.com", role="driver")
            user.set_password("Password123!")
            db.session.add(user)
            db.session.flush()

        driver = Driver(user_id=user.id, driver_code=code, full_name=name, mobile_number=mob, license_number=lic)
        db.session.add(driver)
        db.session.commit()
        return api_success(data=driver.to_dict(), message="Driver created successfully", status_code=201)

    drivers = Driver.query.all()
    return api_success(data=[d.to_dict() for d in drivers])


@admin_bp.route("/drivers/<int:driver_id>", methods=["PUT", "DELETE"])
@role_required("admin")
def update_delete_driver(driver_id: int):
    driver = Driver.query.get(driver_id)
    if not driver:
        return api_error(code="NOT_FOUND", message="Driver not found", status_code=404)
    if request.method == "DELETE":
        driver.status = "OFF_DUTY"
        if driver.user:
            driver.user.is_active = False
        db.session.commit()
        return api_success(message=f"Driver {driver.driver_code} deactivated successfully")
    data = request.get_json() or {}
    if "full_name" in data:
        driver.full_name = data["full_name"]
    if "mobile_number" in data:
        driver.mobile_number = data["mobile_number"]
    if "license_number" in data:
        driver.license_number = data["license_number"]
    if "status" in data:
        driver.status = data["status"]
    db.session.commit()
    return api_success(data=driver.to_dict(), message="Driver updated successfully")



@admin_bp.route("/csv-import", methods=["POST"])
@role_required("admin")
def import_csv():
    if "file" not in request.files:
        return api_error(code="FILE_REQUIRED", message="CSV file is required in 'file' form field.", status_code=400)

    table_name = request.form.get("table_name", "routes")
    uploaded_file = request.files["file"]

    try:
        summary = CSVService.import_csv(table_name, uploaded_file)
        return api_success(data=summary, message=f"CSV import completed for {table_name}")
    except Exception as e:
        return api_error(code="IMPORT_ERROR", message=str(e), status_code=400)


@admin_bp.route("/csv-export", methods=["GET"])
@admin_bp.route("/csv-export/<table_name>", methods=["GET"])
@role_required("admin")
def export_csv(table_name: str = None):
    try:
        resolved_table = table_name or request.args.get("type") or request.args.get("table_name", "buses")
        csv_data = CSVService.export_csv(resolved_table)
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-disposition": f"attachment; filename={resolved_table}.csv"}
        )
    except Exception as e:
        return api_error(code="EXPORT_ERROR", message=str(e), status_code=400)


# ===========================================================================
# 6. NOTIFICATION API ROUTES (/api/notifications)
# ===========================================================================
notification_bp = Blueprint("notification_api", __name__, url_prefix="/api/notifications")


@notification_bp.route("/", methods=["GET"])
def get_notifications():
    user_id = session.get("user_id")
    role = session.get("role", "passenger")

    query = Notification.query.filter(
        (Notification.target_role.in_(["all", role])) | (Notification.user_id == user_id)
    ).order_by(Notification.id.desc()).limit(30)

    notifs = query.all()
    unread_count = sum(1 for n in notifs if not n.is_read)

    return api_success(data={
        "unread_count": unread_count,
        "notifications": [n.to_dict() for n in notifs]
    })


@notification_bp.route("/<int:notif_id>/read", methods=["POST"])
def mark_read(notif_id: int):
    notif = Notification.query.get(notif_id)
    if not notif:
        return api_error(code="NOT_FOUND", message="Notification not found.", status_code=404)
    notif.is_read = True
    db.session.commit()
    return api_success(message="Notification marked as read.")


# ===========================================================================
# 7. SYSTEM STATUS & HEALTH ROUTES
# ===========================================================================
system_bp = Blueprint("system_api", __name__)


@system_bp.route("/health", methods=["GET"])
def health_check():
    db_ok = True
    latency_ms = 0.0
    start = time.perf_counter()
    try:
        db.session.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
    except Exception:
        db_ok = False

    engine_name = db.engine.name if hasattr(db, "engine") else "unknown"
    status_code = 200 if db_ok else 503

    return jsonify({
        "status": "UP" if db_ok else "DEGRADED",
        "service": "BusNotify Transit System",
        "database": "CONNECTED" if db_ok else "DISCONNECTED",
        "database_engine": engine_name,
        "database_latency_ms": latency_ms,
        "timestamp": datetime.utcnow().isoformat()
    }), status_code


@system_bp.route("/api/system/status", methods=["GET"])
def system_status():
    return api_success(data={
        "system_name": "BusNotify - Smart Bus Delay Prediction & Passenger Information System",
        "tagline": "Know your bus. Know your time.",
        "server_time": datetime.utcnow().isoformat(),
        "timezone": "Asia/Kolkata",
        "database_engine": db.engine.name,
        "stats": {
            "total_buses": Bus.query.count(),
            "active_trips": Trip.query.filter(Trip.status.in_(["RUNNING", "DELAYED"])).count(),
            "open_incidents": Incident.query.filter_by(status="OPEN").count(),
            "active_depot_requests": DepotRequest.query.filter(DepotRequest.status != "RESOLVED").count(),
        }
    })


@system_bp.route("/api/system/db-test", methods=["GET"])
def database_connection_test():
    start_time = time.perf_counter()
    try:
        result = db.session.execute(text("SELECT 1")).scalar()
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        db_version = "Unknown"
        db_name = "busnotify"
        try:
            if db.engine.name == "mysql":
                db_version = db.session.execute(text("SELECT VERSION()")).scalar()
                db_name = db.session.execute(text("SELECT DATABASE()")).scalar()
            elif db.engine.name == "sqlite":
                db_version = db.session.execute(text("SELECT sqlite_version()")).scalar()
                db_name = "SQLite local file"
        except Exception:
            pass

        return api_success(data={
            "database_status": "CONNECTED",
            "test_query_result": result,
            "engine": db.engine.name,
            "database_name": db_name,
            "database_version": db_version,
            "latency_ms": latency_ms,
            "checked_at": datetime.utcnow().isoformat(),
        }, message="Database connection verified successfully")
    except Exception as e:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return api_error(
            code="DATABASE_CONNECTION_ERROR",
            message="Database connection test failed.",
            details={"error": str(e), "latency_ms": latency_ms},
            status_code=503
        )


@system_bp.route("/api/routes", methods=["GET"])
def system_routes_alias():
    return get_passenger_routes()


@system_bp.route("/api/routes/<route_identifier>", methods=["GET"])
def system_route_detail_alias(route_identifier: str):
    return get_passenger_route_detail(route_identifier)


# ===========================================================================
# 8. HTML VIEW CONTROLLERS (/ ...)
# ===========================================================================
view_bp = Blueprint("views", __name__)


@view_bp.before_request
def require_login_for_frontend():
    if request.path in {"/login", "/register", "/unauthorized"}:
        return None

    user_id = session.get("user_id")
    if not user_id:
        next_url = request.path
        if request.query_string:
            next_url = f"{next_url}?{request.query_string.decode()}"
        return redirect(url_for("views.login_page", next=next_url))

    role = session.get("role")
    if request.path.startswith("/driver") and role not in {"driver", "admin"}:
        return redirect(url_for("views.unauthorized_page"))
    if request.path.startswith("/admin") and role != "admin":
        return redirect(url_for("views.unauthorized_page"))
    if request.path.startswith("/depot") and role not in {"depot_operator", "admin"}:
        return redirect(url_for("views.unauthorized_page"))
    if request.path.startswith("/passenger") and role not in {"passenger", "admin"}:
        return redirect(url_for("views.unauthorized_page"))

    return None


@view_bp.route("/")
def index():
    role = session.get("role")
    if role == "driver":
        return redirect(url_for("views.driver_dashboard"))
    elif role == "depot_operator":
        return redirect(url_for("views.depot_dashboard"))
    elif role == "admin":
        return redirect(url_for("views.admin_dashboard"))
    return redirect(url_for("views.passenger_home"))


@view_bp.route("/login")
def login_page():
    if session.get("user_id"):
        next_url = request.args.get("next")
        if next_url:
            parsed = urlparse(next_url)
            if parsed.scheme == "" and parsed.netloc == "" and next_url.startswith("/"):
                return redirect(next_url)

        role = session.get("role")
        if role == "driver":
            return redirect(url_for("views.driver_dashboard"))
        elif role == "depot_operator":
            return redirect(url_for("views.depot_dashboard"))
        elif role == "admin":
            return redirect(url_for("views.admin_dashboard"))
        return redirect(url_for("views.passenger_home"))

    return render_template("auth/login.html")


@view_bp.route("/register")
def register_page():
    return render_template("auth/register.html")


@view_bp.route("/unauthorized")
def unauthorized_page():
    return render_template("auth/unauthorized.html")


# Passenger Views
@view_bp.route("/passenger")
def passenger_home():
    active_incident = Incident.query.filter_by(status="OPEN").order_by(Incident.id.desc()).first()
    return render_template("passenger/home.html", active_incident=active_incident)


@view_bp.route("/routes")
def routes_redirect():
    return redirect(url_for("views.passenger_routes"))


@view_bp.route("/passenger/routes")
def passenger_routes():
    return render_template("passenger/routes.html")


@view_bp.route("/passenger/route/<route_identifier>")
@view_bp.route("/routes/<route_identifier>")
def passenger_route_detail(route_identifier):
    route = None
    if str(route_identifier).isdigit():
        route = Route.query.get(int(route_identifier))
    if not route:
        route = Route.query.filter(
            or_(
                Route.route_number == str(route_identifier),
                Route.route_number.ilike(str(route_identifier))
            )
        ).first()
    return render_template("passenger/route_detail.html", route_identifier=route_identifier, route=route)


@view_bp.route("/passenger/search")
def passenger_search():
    return render_template("passenger/search.html")


@view_bp.route("/passenger/bus/<bus_identifier>")
def passenger_bus_detail(bus_identifier):
    return render_template("passenger/bus_detail.html", bus_identifier=bus_identifier)


@view_bp.route("/passenger/emergency")
def passenger_emergency():
    incident_id = request.args.get("incident_id")
    incident = Incident.query.get(incident_id) if incident_id else Incident.query.filter_by(status="OPEN").order_by(Incident.id.desc()).first()
    return render_template("passenger/emergency.html", incident=incident)


@view_bp.route("/passenger/replacement/<string:request_identifier>")
@view_bp.route("/passenger/replacement/<int:request_identifier>")
def passenger_replacement(request_identifier):
    depot_req = None
    if isinstance(request_identifier, int) or str(request_identifier).isdigit():
        depot_req = DepotRequest.query.get(int(request_identifier))
    if not depot_req:
        depot_req = DepotRequest.query.filter_by(request_code=str(request_identifier)).first()
    return render_template("passenger/replacement.html", depot_request=depot_req)


@view_bp.route("/passenger/favourites")
def passenger_favourites():
    return render_template("passenger/favourites.html")


@view_bp.route("/passenger/profile")
def passenger_profile():
    return render_template("passenger/profile.html")


# Driver Views
@view_bp.route("/driver")
def driver_dashboard():
    return render_template("driver/dashboard.html")


@view_bp.route("/driver/start-trip")
def driver_start_trip():
    user_id = session.get("user_id")
    driver = Driver.query.filter_by(user_id=user_id).first() if user_id else None

    assigned_bus = driver.assigned_bus if driver and driver.assigned_bus else None
    assigned_route = assigned_bus.assigned_route if assigned_bus else None

    # Fetch active routes, prioritizing assigned route
    routes = Route.query.filter_by(is_active=True).limit(100).all()
    if assigned_route and assigned_route not in routes:
        routes.insert(0, assigned_route)

    # Fetch available buses, prioritizing assigned bus
    buses = Bus.query.filter_by(is_active=True).limit(100).all()
    if assigned_bus and assigned_bus not in buses:
        buses.insert(0, assigned_bus)

    return render_template("driver/start_trip.html", routes=routes, buses=buses, assigned_bus=assigned_bus, assigned_route=assigned_route)



@view_bp.route("/driver/live-trip")
def driver_live_trip():
    return render_template("driver/live_trip.html")


@view_bp.route("/driver/emergency")
def driver_emergency():
    stops = Stop.query.all()
    return render_template("driver/emergency.html", stops=stops)


# Depot Views
@view_bp.route("/depot")
def depot_dashboard():
    return render_template("depot/dashboard.html")


@view_bp.route("/depot/request/<int:request_id>")
def depot_request_detail(request_id):
    req = DepotRequest.query.get(request_id)
    return render_template("depot/request_detail.html", request_id=request_id, depot_req=req)


@view_bp.route("/depot/history")
def depot_history():
    return render_template("depot/history.html")


# Admin Views
@view_bp.route("/admin")
def admin_dashboard():
    return render_template("admin/dashboard.html")


@view_bp.route("/admin/live-buses")
def admin_live_buses():
    return render_template("admin/live_buses.html")


@view_bp.route("/admin/management")
def admin_management():
    return render_template("admin/management.html")


@view_bp.route("/admin/analytics")
def admin_analytics():
    return render_template("admin/analytics.html")


@view_bp.route("/admin/csv-portal")
def admin_csv_portal():
    return render_template("admin/csv_portal.html")


# ===========================================================================
# MODULE ALIASES (Backward Compatibility)
# ===========================================================================
curr_module = sys.modules[__name__]
sys.modules["app.utils.response"] = curr_module
sys.modules["app.routes.auth_routes"] = curr_module
sys.modules["app.routes.passenger_routes"] = curr_module
sys.modules["app.routes.driver_routes"] = curr_module
sys.modules["app.routes.depot_routes"] = curr_module
sys.modules["app.routes.admin_routes"] = curr_module
sys.modules["app.routes.notification_routes"] = curr_module
sys.modules["app.routes.system_routes"] = curr_module
sys.modules["app.routes.view_routes"] = curr_module
