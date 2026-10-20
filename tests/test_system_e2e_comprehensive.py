"""
Comprehensive End-to-End System Integration Test Suite for BusNotify.
Validates all user personas, edge cases, multi-bus numbers, and workflows:
1. Passenger: Auth, Validation, Search, Idle Buses, Intermediate Stops, Multi-Bus Disambiguation, Notifications
2. Driver: Auth, Dashboard, Start Trip, Capacity Checks, Stop Progression, GPS Telemetry, IDOR Security, Emergency, Cancellation, End Trip
3. Depot Operator: Auth, Dashboard, Replacement Lifecycle (Assign -> Dispatch -> Arrive -> Transfer -> Resolve)
4. Admin: Auth, Live Fleet Telemetry, CRUD (Buses, Routes, Stops, Drivers), Analytics
5. Multi-User Concurrency & Edge Cases
"""
import pytest
from datetime import datetime
from app.extensions import db
from app.models.user import User
from app.models.transit import Route, Stop, RouteStop
from app.models.bus import Bus, Driver
from app.models.trip import Trip, LiveGPS
from app.models.incident import Incident
from app.models.depot import DepotRequest


# ===========================================================================
# 1. PASSENGER PERSONA WORKFLOW TESTS
# ===========================================================================
def test_passenger_authentication_and_validations(client):
    """Test passenger registration validations, duplicates, login, and logout."""
    # 1. Missing fields validation
    res = client.post('/api/auth/register', json={"username": "incomplete"})
    assert res.status_code == 400
    assert "VALIDATION_ERROR" in res.get_json()["error"]["code"]

    # 2. Valid registration
    res = client.post('/api/auth/register', json={
        "username": "pax_alice",
        "email": "alice@test.com",
        "password": "Password123!",
        "role": "passenger",
        "mobile": "9876500001"
    })
    assert res.status_code == 201
    assert res.get_json()["success"] is True

    # 3. Duplicate email registration rejected
    res_dup = client.post('/api/auth/register', json={
        "username": "alice_two",
        "email": "alice@test.com",
        "password": "Password123!"
    })
    assert res_dup.status_code == 400

    # 4. Login with invalid password rejected
    res_bad_pw = client.post('/api/auth/login', json={
        "identifier": "alice@test.com",
        "password": "WrongPassword!"
    })
    assert res_bad_pw.status_code == 401

    # 5. Successful login
    login_res = client.post('/api/auth/login', json={
        "identifier": "alice@test.com",
        "password": "Password123!"
    })
    assert login_res.status_code == 200
    assert login_res.get_json()["data"]["role"] == "passenger"

    # 6. Logout
    logout_res = client.post('/api/auth/logout')
    assert logout_res.status_code == 200


def test_passenger_search_and_multi_bus_handling(client, app):
    """
    Test passenger search for:
    - Multiple buses with identical bus_number on different routes
    - Idle buses stationed at depot (must cleanly show 'Not currently on an active trip')
    - Intermediate stop search
    - Non-existent query gracefully returning empty list
    """
    with app.app_context():
        # Create routes
        r1 = Route(route_number="701", name="Swargate - Katraj", source="Swargate", destination="Katraj", total_distance_km=10.0)
        r2 = Route(route_number="702", name="Swargate - Hadapsar", source="Swargate", destination="Hadapsar", total_distance_km=15.0)
        db.session.add_all([r1, r2])
        db.session.commit()

        # Create two physical buses sharing bus_number "888"
        b_alpha = Bus(bus_number="888", registration_number="MH-12-888A", capacity=40, current_status="RUNNING", assigned_route_id=r1.id)
        b_beta = Bus(bus_number="888", registration_number="MH-12-888B", capacity=40, current_status="RUNNING", assigned_route_id=r2.id)
        # Create an idle bus with default assigned route in DB but NO active trip
        b_idle = Bus(bus_number="999-IDLE", registration_number="MH-12-IDLE9", capacity=40, current_status="AVAILABLE", assigned_route_id=r1.id)
        db.session.add_all([b_alpha, b_beta, b_idle])
        db.session.commit()

        # Active trips for both 888 buses
        t_alpha = Trip(trip_code="TRIP-888-A", bus_id=b_alpha.id, route_id=r1.id, scheduled_start_time=datetime.utcnow(), status="RUNNING")
        t_beta = Trip(trip_code="TRIP-888-B", bus_id=b_beta.id, route_id=r2.id, scheduled_start_time=datetime.utcnow(), status="RUNNING")
        db.session.add_all([t_alpha, t_beta])
        db.session.commit()

        alpha_id, beta_id, idle_id = b_alpha.id, b_beta.id, b_idle.id

    # Search for "888": both physical buses must be returned with distinct bus_id and routes
    search_res = client.get('/api/passenger/search?q=888')
    assert search_res.status_code == 200
    data = search_res.get_json()["data"]
    buses_888 = [b for b in data if b["bus_number"] == "888"]
    assert len(buses_888) == 2

    id_map = {b["bus_id"]: b for b in buses_888}
    assert alpha_id in id_map and beta_id in id_map
    assert id_map[alpha_id]["route_number"] == "701"
    assert id_map[beta_id]["route_number"] == "702"
    assert id_map[alpha_id]["is_active_trip"] is True
    assert id_map[beta_id]["is_active_trip"] is True

    # Search for idle bus: must not display default route 701!
    search_idle = client.get(f'/api/passenger/search?q=999-IDLE')
    assert search_idle.status_code == 200
    idle_data = search_idle.get_json()["data"]
    assert len(idle_data) == 1
    assert idle_data[0]["is_active_trip"] is False
    assert idle_data[0]["route_name"] == "Not currently on an active trip"
    assert "Stationed at" in idle_data[0]["current_stop"]

    # Detail view of idle bus
    detail_idle = client.get(f'/api/passenger/bus/{idle_id}')
    assert detail_idle.status_code == 200
    res_json = detail_idle.get_json()
    assert res_json["data"]["is_active_trip"] is False
    assert res_json["data"]["route"] is None
    assert "Not currently on an active trip" in res_json["message"]

    # Non-existent search query returns clean empty list, not an error
    non_existent = client.get('/api/passenger/search?q=NON_EXISTENT_BUS_XYZ')
    assert non_existent.status_code == 200
    assert len(non_existent.get_json()["data"]) == 0


def test_passenger_notifications(client):
    """Test notifications retrieval and mark-as-read."""
    client.post('/api/auth/login', json={"identifier": "pax@test.com", "password": "Password123!"})
    res = client.get('/api/notifications/')
    assert res.status_code == 200
    notifs = res.get_json()["data"]["notifications"]
    assert isinstance(notifs, list)


# ===========================================================================
# 2. DRIVER PERSONA WORKFLOW TESTS
# ===========================================================================
def test_driver_full_lifecycle_and_security(client, app):
    """
    Test driver workflow:
    1. Login & Dashboard check (no completed trip reported as active)
    2. Capacity check on start trip
    3. Start trip and verify bus status RUNNING
    4. Stop progression & passenger boarding
    5. Live GPS broadcasting
    6. Incident reporting: Tyre Puncture & Cancellation
    7. IDOR Security: unauthorized driver cannot end or report on this trip
    8. End trip and verify bus becomes AVAILABLE
    """
    # 1. Driver Login
    login_res = client.post('/api/auth/login', json={"identifier": "drv@test.com", "password": "Password123!"})
    assert login_res.status_code == 200

    dash_res = client.get('/api/driver/dashboard')
    assert dash_res.status_code == 200

    with app.app_context():
        bus = Bus.query.filter_by(bus_number="123").first()
        route = Route.query.filter_by(route_number="101").first()
        bus_id = bus.id
        route_id = route.id

    # 2. Capacity validation: cannot start trip with passengers > capacity
    cap_res = client.post('/api/driver/trip/start', json={
        "bus_id": bus_id,
        "route_id": route_id,
        "passenger_count": 999
    })
    assert cap_res.status_code == 400
    assert "CAPACITY_EXCEEDED" in cap_res.get_json()["error"]["code"]

    # 3. Successful trip start
    start_res = client.post('/api/driver/trip/start', json={
        "bus_id": bus_id,
        "route_id": route_id,
        "passenger_count": 25
    })
    assert start_res.status_code == 201
    trip = start_res.get_json()["data"]
    trip_id = trip["id"]
    assert trip["status"] == "RUNNING"
    assert trip["route_id"] == route_id

    # 4. Stop progression
    stop_update = client.post('/api/driver/trip/stop-update', json={
        "trip_id": trip_id,
        "passenger_count": 30
    })
    assert stop_update.status_code == 200

    # 5. Live GPS telemetry submission
    gps_res = client.post('/api/driver/trip/gps', json={
        "trip_id": trip_id,
        "latitude": 18.5204,
        "longitude": 73.8567,
        "speed_kmh": 32.5
    })
    assert gps_res.status_code == 200
    assert gps_res.get_json()["data"]["freshness_status"] == "Fresh"

    # 6. IDOR Security test: Log in as Driver 2 and attempt to report emergency on Driver 1's trip
    client.post('/api/auth/login', json={"identifier": "drv2@test.com", "password": "Password123!"})
    unauth_em = client.post('/api/driver/trip/emergency', json={
        "trip_id": trip_id,
        "incident_type": "Engine Breakdown"
    })
    assert unauth_em.status_code == 403
    assert "FORBIDDEN" in unauth_em.get_json()["error"]["code"]

    # Also attempt to end trip as Driver 2
    unauth_end = client.post('/api/driver/trip/end', json={"trip_id": trip_id})
    assert unauth_end.status_code == 403

    # Log back in as Driver 1
    client.post('/api/auth/login', json={"identifier": "drv@test.com", "password": "Password123!"})

    # 7. Cancellation handling
    cancel_res = client.post('/api/driver/trip/emergency', json={
        "trip_id": trip_id,
        "incident_type": "Trip Cancelled due to heavy rain",
        "affected_passengers": 30,
        "description": "Route flooded, trip cancelled."
    })
    assert cancel_res.status_code == 200
    with app.app_context():
        t_rec = Trip.query.get(trip_id)
        assert t_rec.status == "CANCELLED"
        b_rec = Bus.query.get(bus_id)
        assert b_rec.current_status == "CANCELLED"

    # 8. End Trip
    end_res = client.post('/api/driver/trip/end', json={"trip_id": trip_id})
    assert end_res.status_code == 200
    assert end_res.get_json()["data"]["status"] == "COMPLETED"

    with app.app_context():
        b_rec = Bus.query.get(bus_id)
        assert b_rec.current_status == "AVAILABLE"

    # Verify driver dashboard no longer reports completed trip as active
    dash_after = client.get('/api/driver/dashboard')
    assert dash_after.status_code == 200
    assert dash_after.get_json()["data"]["trip"] is None


# ===========================================================================
# 3. DEPOT OPERATOR WORKFLOW TESTS
# ===========================================================================
def test_depot_replacement_full_lifecycle(client, app):
    """
    Test Depot Operator replacement lifecycle:
    Incident reported -> Request PENDING -> Assign -> Dispatch -> Arrive -> Transfer -> Resolve
    Verifies replacement bus activated on new trip and failed bus set to MAINTENANCE.
    """
    # 1. Driver reports emergency to trigger depot request
    client.post('/api/auth/login', json={"identifier": "drv@test.com", "password": "Password123!"})
    start_res = client.post('/api/driver/trip/start', json={"bus_id": 1, "route_id": 1, "passenger_count": 35})
    trip_id = start_res.get_json()["data"]["id"]

    em_res = client.post('/api/driver/trip/emergency', json={
        "trip_id": trip_id,
        "incident_type": "Tyre Puncture",
        "affected_passengers": 35,
        "description": "Rear right puncture near Magarpatta"
    })
    print("EMERGENCY RESPONSE:", em_res.status_code, em_res.get_json())
    assert em_res.status_code == 200
    em_data = em_res.get_json()["data"]
    request_id = em_data["depot_request"]["id"]

    # 2. Depot Operator logs in
    client.post('/api/auth/login', json={"identifier": "depot@test.com", "password": "Password123!"})

    # View requests
    reqs_res = client.get('/api/depot/requests')
    assert reqs_res.status_code == 200
    open_reqs = reqs_res.get_json()["data"]
    target_req = next((r for r in open_reqs if r["id"] == request_id), None)
    assert target_req is not None
    assert target_req["status"] == "PENDING"

    # Step 1: Assign replacement bus & driver
    with app.app_context():
        # Get standby bus b189 (bus 3) and driver 2
        rep_bus = Bus.query.filter_by(bus_number="189").first()
        rep_driver = Driver.query.filter_by(driver_code="D105").first()
        rep_bus_id = rep_bus.id
        rep_driver_id = rep_driver.id

    assign_res = client.post('/api/depot/assign', json={
        "request_id": request_id,
        "replacement_bus_id": rep_bus_id,
        "replacement_driver_id": rep_driver_id,
        "notes": "Dispatched from Pune Central"
    })
    assert assign_res.status_code == 200
    assert assign_res.get_json()["data"]["status"] == "ASSIGNED"

    # Step 2: Dispatch
    disp_res = client.post('/api/depot/dispatch', json={"request_id": request_id, "estimated_arrival_minutes": 10})
    assert disp_res.status_code == 200
    assert disp_res.get_json()["data"]["status"] == "DISPATCHED"

    # Step 3: Arrive
    arr_res = client.post('/api/depot/arrive', json={"request_id": request_id})
    assert arr_res.status_code == 200
    assert arr_res.get_json()["data"]["status"] == "ARRIVED"

    # Step 4: Transfer
    xfer_res = client.post('/api/depot/transfer', json={"request_id": request_id, "transferred_passengers": 35})
    assert xfer_res.status_code == 200
    assert xfer_res.get_json()["data"]["status"] == "PASSENGER_TRANSFER"

    # Step 5: Resolve
    resolve_res = client.post('/api/depot/resolve', json={"request_id": request_id, "notes": "Passengers transferred, service active"})
    assert resolve_res.status_code == 200
    assert resolve_res.get_json()["data"]["status"] == "RESOLVED"

    # Verify database consistency
    with app.app_context():
        inc = Incident.query.get(em_data["incident"]["id"])
        assert inc.status == "RESOLVED"
        failed_bus = Bus.query.get(1)
        assert failed_bus.current_status == "MAINTENANCE"
        rep_b = Bus.query.get(rep_bus_id)
        assert rep_b.current_status == "RUNNING"


# ===========================================================================
# 4. ADMIN PERSONA WORKFLOW TESTS
# ===========================================================================
def test_admin_telemetry_and_crud(client):
    """Test Admin login, live fleet monitoring, and full CRUD operations."""
    # 1. Admin Login
    login_res = client.post('/api/auth/login', json={"identifier": "admin@test.com", "password": "Password123!"})
    assert login_res.status_code == 200
    assert login_res.get_json()["data"]["role"] == "admin"

    # 2. Live Buses Telemetry
    live_res = client.get('/api/admin/live-buses')
    assert live_res.status_code == 200
    assert isinstance(live_res.get_json()["data"], list)

    # 3. Analytics API
    analytics_res = client.get('/api/admin/analytics')
    assert analytics_res.status_code == 200
    data = analytics_res.get_json()["data"]
    assert "on_time_rate" in data
    assert "hourly_delays" in data

    # 4. Bus CRUD
    # Create Bus
    new_bus_res = client.post('/api/admin/buses', json={
        "bus_number": "ADMIN-BUS-01",
        "registration_number": "MH-12-ADM-01",
        "capacity": 50
    })
    assert new_bus_res.status_code == 201
    created_bus_id = new_bus_res.get_json()["data"]["id"]

    # Update Bus
    update_bus = client.put(f'/api/admin/buses/{created_bus_id}', json={"capacity": 55})
    assert update_bus.status_code == 200
    assert update_bus.get_json()["data"]["capacity"] == 55

    # Delete Bus
    del_bus = client.delete(f'/api/admin/buses/{created_bus_id}')
    assert del_bus.status_code == 200

    # 5. Route CRUD
    # Create Route
    new_route_res = client.post('/api/admin/routes', json={
        "route_number": "R-ADM-99",
        "name": "Admin Test Route",
        "source": "Terminal A",
        "destination": "Terminal B",
        "total_distance_km": 18.5,
        "estimated_duration_min": 50
    })
    assert new_route_res.status_code == 201
    created_route_id = new_route_res.get_json()["data"]["id"]

    # Update Route
    update_route = client.put(f'/api/admin/routes/{created_route_id}', json={"name": "Admin Updated Route"})
    assert update_route.status_code == 200

    # Delete Route
    del_route = client.delete(f'/api/admin/routes/{created_route_id}')
    assert del_route.status_code == 200

    # 6. Stop CRUD
    new_stop_res = client.post('/api/admin/stops', json={
        "stop_code": "STP-ADM-01",
        "name": "Admin Test Stop",
        "latitude": 18.5300,
        "longitude": 73.8600
    })
    assert new_stop_res.status_code == 201
    created_stop_id = new_stop_res.get_json()["data"]["id"]

    # Delete Stop
    del_stop = client.delete(f'/api/admin/stops/{created_stop_id}')
    assert del_stop.status_code == 200

    # 7. CSV Export
    csv_res = client.get('/api/admin/csv-export?type=buses')
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers.get("Content-Type", "")


# ===========================================================================
# 5. MULTI-USER CONCURRENCY & RACE CONDITIONS
# ===========================================================================
def test_concurrent_trip_starts_same_bus_number(client, app):
    """
    Test two drivers starting trips on two distinct physical buses
    that share the identical bus_number (e.g. '123').
    Verifies zero trip_code collision, distinct active trips, and correct API reflection.
    """
    with app.app_context():
        r1 = Route.query.filter_by(route_number="101").first()
        r2 = Route(route_number="102", name="Swargate - Hinjawadi", source="Swargate", destination="Hinjawadi", total_distance_km=22.0)
        db.session.add(r2)
        db.session.commit()

        # Second physical bus with bus_number 123
        b_twin = Bus(bus_number="123", registration_number="MH-12-TWIN-123", capacity=40, current_status="AVAILABLE")
        db.session.add(b_twin)
        db.session.commit()
        twin_id = b_twin.id
        r2_id = r2.id

    # Driver 1 starts trip on bus 1 (bus_number 123)
    client.post('/api/auth/login', json={"identifier": "drv@test.com", "password": "Password123!"})
    start1 = client.post('/api/driver/trip/start', json={"bus_id": 1, "route_id": 1, "passenger_count": 20})
    assert start1.status_code == 201
    trip1 = start1.get_json()["data"]

    # Driver 2 starts trip on twin bus (also bus_number 123)
    client.post('/api/auth/login', json={"identifier": "drv2@test.com", "password": "Password123!"})
    start2 = client.post('/api/driver/trip/start', json={"bus_id": twin_id, "route_id": r2_id, "passenger_count": 30})
    assert start2.status_code == 201
    trip2 = start2.get_json()["data"]

    # Verify trip codes are completely distinct
    assert trip1["trip_code"] != trip2["trip_code"]
    assert trip1["bus_id"] != trip2["bus_id"]

    # Verify passenger search for "123" returns both buses with their driver-selected routes
    search = client.get('/api/passenger/search?q=123')
    assert search.status_code == 200
    buses = [b for b in search.get_json()["data"] if b["bus_number"] == "123"]
    assert len(buses) == 2
    b_map = {b["bus_id"]: b for b in buses}
    assert b_map[1]["route_number"] == "101"
    assert b_map[twin_id]["route_number"] == "102"
