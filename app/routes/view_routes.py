"""
View Routes for BusNotify
Serves server-rendered HTML templates for all roles and shared shells.
"""
from urllib.parse import urlparse

from flask import Blueprint, render_template, session, redirect, url_for, request
from app.models.bus import Bus
from app.models.transit import Route, Stop
from app.models.trip import Trip
from app.models.incident import Incident
from app.models.depot import DepotRequest
from app.utils.decorators import login_required, role_required

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

    # Cross-role protection: reject unauthorized portal access
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


# ---------------- PASSENGER PORTAL ----------------

@view_bp.route("/passenger")
def passenger_home():
    routes = Route.query.filter_by(is_active=True).all()
    stops = Stop.query.all()
    # Check for active emergency alert (e.g. Bus 123)
    active_incident = Incident.query.filter_by(status="OPEN").order_by(Incident.id.desc()).first()
    return render_template("passenger/home.html", routes=routes, stops=stops, active_incident=active_incident)


@view_bp.route("/passenger/search")
def passenger_search():
    return render_template("passenger/search.html")


@view_bp.route("/passenger/bus/<bus_identifier>")
def passenger_bus_detail(bus_identifier):
    return render_template("passenger/bus_detail.html", bus_identifier=bus_identifier)


@view_bp.route("/passenger/emergency")
def passenger_emergency():
    # If no specific incident queried, pick the latest open incident or INC-001
    incident_id = request.args.get("incident_id")
    incident = Incident.query.get(incident_id) if incident_id else Incident.query.filter_by(status="OPEN").order_by(Incident.id.desc()).first()
    return render_template("passenger/emergency.html", incident=incident)


@view_bp.route("/passenger/replacement/<int:request_id>")
def passenger_replacement(request_id):
    depot_req = DepotRequest.query.get(request_id)
    return render_template("passenger/replacement.html", depot_request=depot_req)


@view_bp.route("/passenger/favourites")
def passenger_favourites():
    return render_template("passenger/favourites.html")


@view_bp.route("/passenger/profile")
def passenger_profile():
    return render_template("passenger/profile.html")


# ---------------- DRIVER PORTAL ----------------

@view_bp.route("/driver")
def driver_dashboard():
    return render_template("driver/dashboard.html")


@view_bp.route("/driver/start-trip")
def driver_start_trip():
    routes = Route.query.filter_by(is_active=True).all()
    buses = Bus.query.filter_by(is_active=True).all()
    return render_template("driver/start_trip.html", routes=routes, buses=buses)


@view_bp.route("/driver/live-trip")
def driver_live_trip():
    return render_template("driver/live_trip.html")


@view_bp.route("/driver/emergency")
def driver_emergency():
    stops = Stop.query.all()
    return render_template("driver/emergency.html", stops=stops)


# ---------------- DEPOT OPERATOR PORTAL ----------------

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


# ---------------- ADMIN PORTAL ----------------

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
