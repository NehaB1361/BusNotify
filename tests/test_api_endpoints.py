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
