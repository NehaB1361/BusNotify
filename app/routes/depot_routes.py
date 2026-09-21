"""
Depot Operator API Routes
Handles emergency requests, resource allocation, and the 6-stage dispatch state machine:
PENDING -> ASSIGNED -> DISPATCHED -> ARRIVED -> PASSENGER_TRANSFER -> RESOLVED
"""
from flask import Blueprint, request, session
from app.extensions import db
from app.models.depot import DepotRequest
from app.models.bus import Bus
from app.models.driver import Driver
from app.services.depot_service import DepotWorkflowService
from app.utils.response import api_success, api_error

depot_bp = Blueprint("depot_api", __name__, url_prefix="/api/depot")


@depot_bp.route("/dashboard", methods=["GET"])
def get_dashboard():
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
def get_requests():
    status = request.args.get("status")
    query = DepotRequest.query
    if status and status.upper() != "ALL":
        query = query.filter_by(status=status.upper())
    requests_list = query.order_by(DepotRequest.id.desc()).all()
    return api_success(data=[r.to_dict() for r in requests_list])


@depot_bp.route("/requests/<int:request_id>", methods=["GET"])
def get_request_detail(request_id: int):
    req = DepotRequest.query.get(request_id)
    if not req:
        return api_error(code="NOT_FOUND", message="Depot request not found.", status_code=404)
    return api_success(data=req.to_dict())


@depot_bp.route("/assign", methods=["POST"])
def assign():
    data = request.get_json() or {}
    request_id = data.get("request_id")
    bus_id = data.get("bus_id")
    driver_id = data.get("driver_id")
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
def record_transfer():
    data = request.get_json() or {}
    request_id = data.get("request_id")
    transferred_count = data.get("transferred_count")

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
def resolve():
    data = request.get_json() or {}
    request_id = data.get("request_id")
    resolution_notes = data.get("resolution_notes", "All passengers transferred successfully. Trip resumed.")

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
