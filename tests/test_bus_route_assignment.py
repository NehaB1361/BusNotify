"""
Tests for Bus-to-Route Dynamic Assignment and Multiple Buses with Same Bus Number.
Verifies:
1. Treating each bus as a unique database record via bus_id.
2. Saving selected route_id and bus_id to active trip when driver starts a trip.
3. Passenger search returns actual active trip route selected by driver.
4. Multiple buses sharing the same bus_number are distinguished by unique bus_id
   and display their actual active routes separately.
5. Idle buses with no active trip gracefully report 'Not currently on an active trip'.
"""
import pytest
from datetime import datetime
from app.extensions import db
from app.models.transit import Route, Stop, RouteStop
from app.models.bus import Bus, Driver
from app.models.trip import Trip
from app.models.user import User


def test_multiple_buses_same_number_different_routes(client, app):
    with app.app_context():
        # Create two distinct routes
        route_a = Route(route_number="201", name="Pune - Mumbai Express", source="Pune", destination="Mumbai", total_distance_km=150.0)
        route_b = Route(route_number="202", name="Pune - Nashik Highway", source="Pune", destination="Nashik", total_distance_km=210.0)
        db.session.add_all([route_a, route_b])
        db.session.commit()

        # Create two separate bus records sharing the SAME bus_number "555"
        bus_a = Bus(
            bus_number="555",
            registration_number="MH-12-AA-5555",
            capacity=45,
            current_status="RUNNING",
            assigned_route_id=route_a.id
        )
        bus_b = Bus(
            bus_number="555",
            registration_number="MH-12-BB-5555",
            capacity=45,
            current_status="RUNNING",
            assigned_route_id=route_b.id
        )
        # Create an idle bus with no active trip
        bus_idle = Bus(
            bus_number="777",
            registration_number="MH-12-IDLE-777",
            capacity=35,
            current_status="AVAILABLE"
        )
        db.session.add_all([bus_a, bus_b, bus_idle])
        db.session.commit()

        # Create active trips for both buses with different drivers and routes
        trip_a = Trip(
            trip_code="TRIP-555-A",
            bus_id=bus_a.id,
            route_id=route_a.id,
            scheduled_start_time=datetime.utcnow(),
            status="RUNNING",
            passenger_count=30
        )
        trip_b = Trip(
            trip_code="TRIP-555-B",
            bus_id=bus_b.id,
            route_id=route_b.id,
            scheduled_start_time=datetime.utcnow(),
            status="RUNNING",
            passenger_count=25
        )
        db.session.add_all([trip_a, trip_b])
        db.session.commit()

        bus_a_id = bus_a.id
        bus_b_id = bus_b.id
        bus_idle_id = bus_idle.id

    # 1. Passenger searches for "555"
    search_res = client.get('/api/passenger/search?q=555')
    assert search_res.status_code == 200
    search_json = search_res.get_json()
    assert search_json["success"] is True

    results = search_json["data"]
    # Should return both buses
    assert len(results) >= 2
    buses_555 = [b for b in results if b["bus_number"] == "555"]
    assert len(buses_555) == 2

    ids = {b["bus_id"] for b in buses_555}
    assert ids == {bus_a_id, bus_b_id}

    # Verify routes are separate and reflect active trips
    bus_map = {b["bus_id"]: b for b in buses_555}
    assert bus_map[bus_a_id]["route_number"] == "201"
    assert "Mumbai" in bus_map[bus_a_id]["route_name"]
    assert bus_map[bus_a_id]["is_active_trip"] is True

    assert bus_map[bus_b_id]["route_number"] == "202"
    assert "Nashik" in bus_map[bus_b_id]["route_name"]
    assert bus_map[bus_b_id]["is_active_trip"] is True

    # 2. Detailed view by bus_id
    detail_a = client.get(f'/api/passenger/bus/{bus_a_id}')
    assert detail_a.status_code == 200
    data_a = detail_a.get_json()["data"]
    assert data_a["bus"]["id"] == bus_a_id
    assert data_a["bus"]["bus_number"] == "555"
    assert data_a["route"]["route_number"] == "201"
    assert data_a["is_active_trip"] is True

    detail_b = client.get(f'/api/passenger/bus/{bus_b_id}')
    assert detail_b.status_code == 200
    data_b = detail_b.get_json()["data"]
    assert data_b["bus"]["id"] == bus_b_id
    assert data_b["bus"]["bus_number"] == "555"
    assert data_b["route"]["route_number"] == "202"
    assert data_b["is_active_trip"] is True

    # 3. Idle bus test
    detail_idle = client.get(f'/api/passenger/bus/{bus_idle_id}')
    assert detail_idle.status_code == 200
    data_idle = detail_idle.get_json()["data"]
    assert data_idle["bus"]["id"] == bus_idle_id
    assert data_idle["bus"]["bus_number"] == "777"
    assert data_idle["is_active_trip"] is False
    assert data_idle["route"] is None
    assert "Not currently on an active trip" in data_idle["message"]

    # 4. Search for idle bus
    search_idle = client.get('/api/passenger/search?q=777')
    assert search_idle.status_code == 200
    idle_results = [b for b in search_idle.get_json()["data"] if b["bus_number"] == "777"]
    assert len(idle_results) == 1
    assert idle_results[0]["is_active_trip"] is False
    assert idle_results[0]["route_name"] == "Not currently on an active trip"


def test_driver_start_trip_binds_route_and_bus_to_active_trip(client, app):
    # Driver logs in
    drv_login = client.post('/api/auth/login', json={
        "identifier": "drv@test.com",
        "password": "Password123!"
    })
    assert drv_login.status_code == 200

    # Fetch driver dashboard to verify current state
    dash_res = client.get('/api/driver/dashboard')
    assert dash_res.status_code == 200

    with app.app_context():
        # Create a new route
        special_route = Route(
            route_number="999X",
            name="Swargate - Hinjawadi Special",
            source="Swargate",
            destination="Hinjawadi",
            total_distance_km=25.0
        )
        db.session.add(special_route)
        db.session.commit()
        special_route_id = special_route.id

    # Start trip on special route
    start_res = client.post('/api/driver/trip/start', json={
        "bus_id": 1,
        "route_id": special_route_id,
        "passenger_count": 35
    })
    assert start_res.status_code == 201
    start_json = start_res.get_json()
    assert start_json["success"] is True
    assert start_json["data"]["route_id"] == special_route_id
    assert start_json["data"]["bus_id"] == 1

    # Check that passenger bus details reflect the newly started trip's route, NOT the default
    detail_res = client.get('/api/passenger/bus/1')
    assert detail_res.status_code == 200
    detail_json = detail_res.get_json()["data"]
    assert detail_json["route"]["id"] == special_route_id
    assert detail_json["route"]["route_number"] == "999X"
    assert "Hinjawadi" in detail_json["route"]["destination"]
