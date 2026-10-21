"""
Tests for Passenger Directional Search and Typo Tolerance
Verifies:
1. Searching 'Pune to Kolhapur' returns ONLY Pune to Kolhapur buses, never Kolhapur to Pune.
2. Searching 'Kolhapur to Pune' returns ONLY Kolhapur to Pune buses, never Pune to Kolhapur.
3. Typo tolerance: 'pune to kolhapppur' correctly matches 'Pune to Kolhapur'.
4. Query string parsing: 'q=pune to kolhapur' correctly resolves to source=Pune and destination=Kolhapur.
"""
import pytest
from app.models.transit import Route, Stop, RouteStop
from app.models.bus import Bus
from app.models.trip import Trip
from app.extensions import db


def test_directional_search_pune_to_kolhapur_strict(client, app):
    with app.app_context():
        # Setup stops
        s_pune = Stop.query.filter_by(name="Pune Station").first()
        s_kolhapur = Stop(stop_code="STP-KOL", name="Kolhapur Central", latitude=16.7050, longitude=74.2433)
        db.session.add(s_kolhapur)
        db.session.commit()

        # Route 1: Pune -> Kolhapur
        r_forward = Route(
            route_number="PUNE-KOL-109",
            name="109 - Pune to Kolhapur",
            source="Pune",
            destination="Kolhapur",
            total_distance_km=230.0
        )
        # Route 2: Kolhapur -> Pune (Reverse)
        r_reverse = Route(
            route_number="KOL-PUNE-110",
            name="110 - Kolhapur to Pune",
            source="Kolhapur",
            destination="Pune",
            total_distance_km=230.0
        )
        db.session.add_all([r_forward, r_reverse])
        db.session.commit()

        # Stops for forward
        rs_f1 = RouteStop(route_id=r_forward.id, stop_id=s_pune.id, sequence_order=1)
        rs_f2 = RouteStop(route_id=r_forward.id, stop_id=s_kolhapur.id, sequence_order=2)
        # Stops for reverse
        rs_r1 = RouteStop(route_id=r_reverse.id, stop_id=s_kolhapur.id, sequence_order=1)
        rs_r2 = RouteStop(route_id=r_reverse.id, stop_id=s_pune.id, sequence_order=2)
        db.session.add_all([rs_f1, rs_f2, rs_r1, rs_r2])

        # Bus A: Forward
        bus_forward = Bus(
            bus_number="BUS-PK-1",
            registration_number="MH-12-PK01",
            capacity=45,
            current_status="RUNNING",
            assigned_route_id=r_forward.id
        )
        # Bus B: Reverse
        bus_reverse = Bus(
            bus_number="BUS-KP-1",
            registration_number="MH-12-KP01",
            capacity=45,
            current_status="RUNNING",
            assigned_route_id=r_reverse.id
        )
        db.session.add_all([bus_forward, bus_reverse])
        db.session.commit()

        from datetime import datetime
        # Active trip for forward
        trip_forward = Trip(
            trip_code="TRIP-PK-100",
            bus_id=bus_forward.id,
            route_id=r_forward.id,
            driver_id=1,
            status="RUNNING",
            scheduled_start_time=datetime.utcnow()
        )
        # Active trip for reverse
        trip_reverse = Trip(
            trip_code="TRIP-KP-200",
            bus_id=bus_reverse.id,
            route_id=r_reverse.id,
            driver_id=2,
            status="RUNNING",
            scheduled_start_time=datetime.utcnow()
        )
        db.session.add_all([trip_forward, trip_reverse])
        db.session.commit()

    # 1. Search Pune to Kolhapur: ONLY forward bus must be returned
    res = client.get('/api/passenger/search?source=Pune&destination=Kolhapur')
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert len(data) == 1
    assert data[0]["bus_number"] == "BUS-PK-1"
    assert data[0]["route_name"] == "109 - Pune to Kolhapur"
    assert data[0]["source"] == "Pune"
    assert data[0]["destination"] == "Kolhapur"

    # 2. Search Kolhapur to Pune: ONLY reverse bus must be returned
    res_rev = client.get('/api/passenger/search?source=Kolhapur&destination=Pune')
    assert res_rev.status_code == 200
    data_rev = res_rev.get_json()["data"]
    assert len(data_rev) == 1
    assert data_rev[0]["bus_number"] == "BUS-KP-1"
    assert data_rev[0]["route_name"] == "110 - Kolhapur to Pune"
    assert data_rev[0]["source"] == "Kolhapur"
    assert data_rev[0]["destination"] == "Pune"

    # 3. Typo tolerance: 'pune to kolhapppur' (with 3 p's)
    res_typo = client.get('/api/passenger/search?source=pune&destination=kolhapppur')
    assert res_typo.status_code == 200
    data_typo = res_typo.get_json()["data"]
    assert len(data_typo) == 1
    assert data_typo[0]["bus_number"] == "BUS-PK-1"
    assert data_typo[0]["route_name"] == "109 - Pune to Kolhapur"

    # 4. Search via single 'q' query parameter: 'q=pune to kolhapppur'
    res_q = client.get('/api/passenger/search?q=pune to kolhapppur')
    assert res_q.status_code == 200
    data_q = res_q.get_json()["data"]
    assert len(data_q) == 1
    assert data_q[0]["bus_number"] == "BUS-PK-1"
    assert data_q[0]["route_name"] == "109 - Pune to Kolhapur"
