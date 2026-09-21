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
    res = client.get('/api/driver/dashboard')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["driver"]["driver_code"] == "D104"


def test_admin_dashboard_api(client):
    res = client.get('/api/admin/dashboard')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["kpis"]["total_buses"] >= 3


def test_depot_dashboard_api(client):
    res = client.get('/api/depot/dashboard')
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "counts" in data["data"]
