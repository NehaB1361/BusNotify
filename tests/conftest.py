"""
Pytest configuration and shared fixtures for BusNotify
"""
import pytest
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.transit import Route, Stop, RouteStop
from app.models.bus import Bus, Driver
from app.models.trip import Trip
from app.models.delay import HistoricalDelay
from datetime import datetime, date


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()

        # Seed minimal baseline for testing
        u_pax = User(username="test_pax", email="pax@test.com", role="passenger")
        u_pax.set_password("Password123!")
        
        u_drv = User(username="test_drv", email="drv@test.com", role="driver")
        u_drv.set_password("Password123!")

        u_drv2 = User(username="test_drv2", email="drv2@test.com", role="driver")
        u_drv2.set_password("Password123!")
        
        u_dep = User(username="test_depot", email="depot@test.com", role="depot_operator")
        u_dep.set_password("Password123!")
        
        u_adm = User(username="test_adm", email="admin@test.com", role="admin")
        u_adm.set_password("Password123!")
        
        db.session.add_all([u_pax, u_drv, u_drv2, u_dep, u_adm])
        db.session.commit()

        # Stops
        s1 = Stop(stop_code="STP-1", name="Pune Station", latitude=18.5284, longitude=73.8744)
        s2 = Stop(stop_code="STP-2", name="Magarpatta", latitude=18.5134, longitude=73.9242)
        s3 = Stop(stop_code="STP-3", name="Hadapsar", latitude=18.5089, longitude=73.9260)
        db.session.add_all([s1, s2, s3])
        db.session.commit()

        # Route
        r = Route(route_number="101", name="Pune-Hadapsar", source="Pune Station", destination="Hadapsar", total_distance_km=12.5)
        db.session.add(r)
        db.session.commit()

        rs1 = RouteStop(route_id=r.id, stop_id=s1.id, sequence_order=1)
        rs2 = RouteStop(route_id=r.id, stop_id=s2.id, sequence_order=2)
        rs3 = RouteStop(route_id=r.id, stop_id=s3.id, sequence_order=3)
        db.session.add_all([rs1, rs2, rs3])

        # Buses
        b123 = Bus(bus_number="123", registration_number="MH-12-1234", capacity=40, current_status="RUNNING", assigned_route_id=r.id)
        b156 = Bus(bus_number="156", registration_number="MH-12-5678", capacity=40, current_status="RUNNING", assigned_route_id=r.id)
        b189 = Bus(bus_number="189", registration_number="MH-12-3456", capacity=40, current_status="AVAILABLE")
        db.session.add_all([b123, b156, b189])
        db.session.commit()

        # Drivers
        d104 = Driver(user_id=u_drv.id, driver_code="D104", full_name="Rajesh Patil", mobile_number="9876543210", license_number="MH12-12345", status="AVAILABLE", assigned_bus_id=b123.id)
        d105 = Driver(user_id=u_drv2.id, driver_code="D105", full_name="Suresh Shinde", mobile_number="9876543211", license_number="MH12-67890", status="AVAILABLE")
        db.session.add_all([d104, d105])
        db.session.commit()

        # Trip
        t = Trip(
            trip_code="TRIP-123-TEST",
            bus_id=b123.id,
            driver_id=d104.id,
            route_id=r.id,
            scheduled_start_time=datetime.utcnow(),
            current_stop_id=s2.id,
            status="RUNNING",
            passenger_count=40
        )
        db.session.add(t)

        # 10 Historical delay observations for stop 2 (Magarpatta)
        for i in range(10):
            db.session.add(HistoricalDelay(
                route_id=r.id,
                stop_id=s2.id,
                weekday=1,
                hour_of_day=17,
                delay_minutes=14.0,
                delay_reason="TYRE_PUNCTURE",
                sample_date=date(2026, 9, 1)
            ))

        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
