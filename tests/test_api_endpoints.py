"""
Integration Tests for REST APIs across all 4 User Roles and System Health
"""
def test_health_endpoint(client):
    res = client.get('/health')
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "UP"
    assert data["database"] == "CONNECTED"


def test_system_status_api(client):
    res = client.get('/api/system/status')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "BusNotify" in data["data"]["system_name"]


def test_passenger_search_api(client):
    res = client.get('/api/passenger/search?q=123')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert len(data["data"]) >= 1
    assert data["data"][0]["bus_number"] == "123"


def test_passenger_bus_details_api(client):
    res = client.get('/api/passenger/bus/123')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["bus"]["bus_number"] == "123"
    assert data["data"]["statistics"]["label"] == "Historical statistical estimate"


def test_driver_dashboard_api(client):
    # Unauthenticated should fail with 401
    unauth_res = client.get('/api/driver/dashboard')
    assert unauth_res.status_code == 401

    # Authenticate as driver
    login_res = client.post('/api/auth/login', json={
        "identifier": "drv@test.com",
        "password": "Password123!"
    })
    assert login_res.status_code == 200

    res = client.get('/api/driver/dashboard')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["driver"]["driver_code"] == "D104"
    client.post('/api/auth/logout')


def test_admin_dashboard_api(client):
    # Unauthenticated should fail with 401
    unauth_res = client.get('/api/admin/dashboard')
    assert unauth_res.status_code == 401

    # Authenticate as admin
    login_res = client.post('/api/auth/login', json={
        "identifier": "admin@test.com",
        "password": "Password123!"
    })
    assert login_res.status_code == 200

    res = client.get('/api/admin/dashboard')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["kpis"]["total_buses"] >= 3
    client.post('/api/auth/logout')


def test_depot_dashboard_api(client):
    # Unauthenticated should fail with 401
    unauth_res = client.get('/api/depot/dashboard')
    assert unauth_res.status_code == 401

    # Authenticate as depot operator
    login_res = client.post('/api/auth/login', json={
        "identifier": "depot@test.com",
        "password": "Password123!"
    })
    assert login_res.status_code == 200

    res = client.get('/api/depot/dashboard')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "counts" in data["data"]
    client.post('/api/auth/logout')


def test_passenger_intermediate_stop_search_api(client):
    # Search for intermediate stop 'Magarpatta' (not terminal Pune Station or Hadapsar)
    res = client.get('/api/passenger/search?source=Magarpatta')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert len(data["data"]) >= 1
    assert data["data"][0]["bus_number"] == "123"

    # Search as destination
    res_dest = client.get('/api/passenger/search?destination=Magarpatta')
    assert res_dest.status_code == 200
    data_dest = res_dest.get_json()
    assert data_dest["success"] is True
    assert len(data_dest["data"]) >= 1


def test_passenger_summary_api(client):
    res = client.get('/api/passenger/summary')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    summary = data["data"]
    assert "active_buses" in summary
    assert "delayed_buses" in summary
    assert "on_time_percentage" in summary
    assert "open_incidents" in summary
    assert "total_buses" in summary
    assert summary["total_buses"] >= 3


def test_passenger_replacement_alphanumeric_lookup(client, app):
    from app.models.depot import DepotRequest
    from app.models.incident import Incident
    from app.extensions import db

    with app.app_context():
        inc = Incident(
            incident_number="INC-ALPHA-01",
            trip_id=1,
            bus_id=1,
            route_id=1,
            stop_id=2,
            incident_type="TYRE_PUNCTURE",
            affected_passengers=40
        )
        db.session.add(inc)
        db.session.flush()

        req = DepotRequest(
            request_code="DR-ALPHA-999",
            incident_id=inc.id,
            failed_bus_id=1,
            route_id=1,
            stop_id=2,
            status="PENDING",
            affected_passengers=40
        )
        db.session.add(req)
        db.session.commit()

    # Query by alphanumeric code via API
    res = client.get('/api/passenger/replacement/DR-ALPHA-999')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["request_code"] == "DR-ALPHA-999"

    # Log in as passenger to view frontend page
    login_res = client.post('/api/auth/login', json={
        "identifier": "pax@test.com",
        "password": "Password123!"
    })
    assert login_res.status_code == 200

    # Query view route by alphanumeric code
    view_res = client.get('/passenger/replacement/DR-ALPHA-999')
    assert view_res.status_code == 200
    assert b"DR-ALPHA-999" in view_res.data
    client.post('/api/auth/logout')



def test_driver_gps_auto_fallback(client):
    # Authenticate as driver
    login_res = client.post('/api/auth/login', json={
        "identifier": "drv@test.com",
        "password": "Password123!"
    })
    assert login_res.status_code == 200

    # Post GPS telemetry without providing trip_id
    gps_res = client.post('/api/driver/trip/gps', json={
        "latitude": 18.5204,
        "longitude": 73.8567,
        "speed_kmh": 28.5
    })
    assert gps_res.status_code == 200
    gps_data = gps_res.get_json()
    assert gps_data["success"] is True
    assert gps_data["data"]["latitude"] == 18.5204
    assert gps_data["data"]["longitude"] == 73.8567

    client.post('/api/auth/logout')


def test_admin_crud_endpoints(client):
    # Authenticate as admin
    login_res = client.post('/api/auth/login', json={
        "identifier": "admin@test.com",
        "password": "Password123!"
    })
    assert login_res.status_code == 200

    # Create Stop
    stop_res = client.post('/api/admin/stops', json={
        "stop_code": "STP-CRUD-1",
        "name": "Deccan Corner",
        "latitude": 18.5170,
        "longitude": 73.8420,
        "landmark": "Near FC Road"
    })
    assert stop_res.status_code == 201
    stop_id = stop_res.get_json()["data"]["id"]

    # Deactivate Stop (DELETE)
    del_stop_res = client.delete(f'/api/admin/stops/{stop_id}')
    assert del_stop_res.status_code == 200

    # Create Driver
    drv_res = client.post('/api/admin/drivers', json={
        "driver_code": "D999",
        "full_name": "Mahesh More",
        "mobile_number": "9812345678",
        "license_number": "MH12-99999"
    })
    assert drv_res.status_code == 201
    drv_id = drv_res.get_json()["data"]["id"]

    # Deactivate Driver (DELETE)
    del_drv_res = client.delete(f'/api/admin/drivers/{drv_id}')
    assert del_drv_res.status_code == 200

    # Deactivate Route (DELETE)
    del_route_res = client.delete('/api/admin/routes/1')
    assert del_route_res.status_code == 200

    client.post('/api/auth/logout')


def test_passenger_routes_endpoints(client):
    # Log in as passenger
    login_res = client.post('/api/auth/login', json={
        "identifier": "pax@test.com",
        "password": "Password123!"
    })
    assert login_res.status_code == 200

    # 1. Test listing routes API
    routes_res = client.get('/api/passenger/routes?limit=10')
    assert routes_res.status_code == 200
    routes_data = routes_res.get_json()
    assert routes_data["success"] is True
    assert isinstance(routes_data["data"], list)
    assert len(routes_data["data"]) > 0

    # 2. Test route detail API by number and by ID
    first_route = routes_data["data"][0]
    detail_res = client.get(f'/api/passenger/routes/{first_route["route_number"]}')
    assert detail_res.status_code == 200
    detail_data = detail_res.get_json()["data"]
    assert "route" in detail_data
    assert "stops" in detail_data
    assert "active_buses" in detail_data
    assert "statistics" in detail_data

    # 3. Test global API aliases
    alias_res = client.get('/api/routes?limit=5')
    assert alias_res.status_code == 200
    alias_detail_res = client.get(f'/api/routes/{first_route["route_number"]}')
    assert alias_detail_res.status_code == 200

    # 4. Test Route frontend pages
    view_list_res = client.get('/passenger/routes')
    assert view_list_res.status_code == 200
    assert b"Transit Routes Directory" in view_list_res.data

    view_detail_res = client.get(f'/passenger/route/{first_route["route_number"]}')
    assert view_detail_res.status_code == 200
    assert b"Stop Sequence &amp; Itinerary" in view_detail_res.data or b"Stop Sequence & Itinerary" in view_detail_res.data

    # 5. Test root /routes redirect
    redirect_res = client.get('/routes')
    assert redirect_res.status_code in (200, 302)

    client.post('/api/auth/logout')


