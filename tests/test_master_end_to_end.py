"""
BusNotify Master End-to-End Workflow Integration Test
Executes the full 16-step transit operational flow:
1.  Passenger registration/login
2.  Passenger dashboard & search
3.  Driver login
4.  Driver starts trip
5.  Driver submits GPS update
6.  Driver reports Emergency / Tyre Puncture
7.  Incident creation verified (INC-xxx, status OPEN)
8.  Passenger notification generated
9.  Alternative bus recommendations fetched
10. Depot request created (DRxxx, status PENDING)
11. Depot Operator login
12. Replacement assignment (Bus & Driver, status ASSIGNED)
13. Dispatch replacement bus (status DISPATCHED)
14. Replacement bus arrival recorded (status ARRIVED)
15. Passenger transfer recorded (status PASSENGER_TRANSFER)
16. Incident resolved (status RESOLVED) & service-restored notification verified
"""
import pytest
from app.models.incident import Incident
from app.models.depot import DepotRequest
from app.models.notification import Notification
from app.models.trip import Trip, LiveGPS


def test_complete_master_flow(client, app):
    # -------------------------------------------------------------
    # 1. PASSENGER REGISTRATION & LOGIN
    # -------------------------------------------------------------
    reg_res = client.post('/api/auth/register', json={
        "username": "master_passenger",
        "email": "master_pax@test.com",
        "password": "Password123!",
        "role": "passenger",
        "mobile": "9998887771"
    })
    assert reg_res.status_code == 201
    assert reg_res.get_json()["success"] is True

    login_res = client.post('/api/auth/login', json={
        "identifier": "master_pax@test.com",
        "password": "Password123!"
    })
    assert login_res.status_code == 200
    assert login_res.get_json()["success"] is True

    # -------------------------------------------------------------
    # 2. PASSENGER DASHBOARD & SEARCH
    # -------------------------------------------------------------
    search_res = client.get('/api/passenger/search?q=123')
    assert search_res.status_code == 200
    search_data = search_res.get_json()
    assert search_data["success"] is True
    assert len(search_data["data"]) >= 1
    assert search_data["data"][0]["bus_number"] == "123"

    bus_detail_res = client.get('/api/passenger/bus/123')
    assert bus_detail_res.status_code == 200
    assert bus_detail_res.get_json()["data"]["statistics"]["label"] == "Historical statistical estimate"

    # Logout passenger
    client.post('/api/auth/logout')

    # -------------------------------------------------------------
    # 3. DRIVER LOGIN
    # -------------------------------------------------------------
    drv_login = client.post('/api/auth/login', json={
        "identifier": "drv@test.com",
        "password": "Password123!"
    })
    assert drv_login.status_code == 200
    assert drv_login.get_json()["data"]["role"] == "driver"

    # -------------------------------------------------------------
    # 4. DRIVER STARTS TRIP
    # -------------------------------------------------------------
    start_res = client.post('/api/driver/trip/start', json={
        "bus_id": 1,
        "route_id": 1,
        "starting_stop_id": 1,
        "passenger_count": 40
    })
    assert start_res.status_code == 201
    trip_data = start_res.get_json()["data"]
    trip_id = trip_data["id"]
    assert trip_data["status"] == "RUNNING"
    assert trip_data["passenger_count"] == 40

    # -------------------------------------------------------------
    # 5. GPS UPDATE
    # -------------------------------------------------------------
    gps_res = client.post('/api/driver/trip/gps', json={
        "trip_id": trip_id,
        "latitude": 18.5134,
        "longitude": 73.9242,
        "speed_kmh": 22.5,
        "source": "GPS"
    })
    assert gps_res.status_code == 200
    assert gps_res.get_json()["success"] is True

    # Also progress to Magarpatta (stop 2)
    stop_res = client.post('/api/driver/trip/stop-update', json={
        "trip_id": trip_id,
        "stop_id": 2,
        "passenger_count": 40
    })
    assert stop_res.status_code == 200

    # -------------------------------------------------------------
    # 6. EMERGENCY / TYRE PUNCTURE REPORTING
    # -------------------------------------------------------------
    emg_res = client.post('/api/driver/trip/emergency', json={
        "trip_id": trip_id,
        "incident_type": "Tyre Puncture",
        "affected_passengers": 40,
        "description": "Rear tyre punctured near Magarpatta junction.",
        "priority": "HIGH",
        "stop_id": 2
    })
    assert emg_res.status_code == 200
    emg_data = emg_res.get_json()["data"]

    # -------------------------------------------------------------
    # 7. INCIDENT CREATION VERIFIED
    # -------------------------------------------------------------
    incident_info = emg_data["incident"]
    incident_id = incident_info["id"]
    assert incident_info["status"] == "OPEN"
    assert incident_info["incident_type"] == "Tyre Puncture"
    assert incident_info["affected_passengers"] == 40

    # -------------------------------------------------------------
    # 8. PASSENGER NOTIFICATION GENERATED
    # -------------------------------------------------------------
    with app.app_context():
        p_notif = Notification.query.filter(
            Notification.target_role.in_(["passenger", "all"]),
            Notification.related_entity_id == incident_id
        ).first()
        assert p_notif is not None
        assert "Tyre Puncture" in p_notif.title or "Emergency" in p_notif.title

    # -------------------------------------------------------------
    # 9. ALTERNATIVE BUS RECOMMENDATIONS
    # -------------------------------------------------------------
    alt_res = client.get(f'/api/passenger/alternatives/{incident_id}')
    assert alt_res.status_code == 200
    alt_data = alt_res.get_json()["data"]
    assert "alternatives" in alt_data
    assert alt_data["affected_passengers"] == 40

    # -------------------------------------------------------------
    # 10. DEPOT REQUEST CREATED (status: PENDING)
    # -------------------------------------------------------------
    depot_req_info = emg_data["depot_request"]
    depot_req_id = depot_req_info["id"]
    assert depot_req_info["status"] == "PENDING"
    assert depot_req_info["affected_passengers"] == 40

    # Logout driver
    client.post('/api/auth/logout')

    # -------------------------------------------------------------
    # 11. DEPOT OPERATOR LOGIN
    # -------------------------------------------------------------
    depot_login = client.post('/api/auth/login', json={
        "identifier": "depot@test.com",
        "password": "Password123!"
    })
    assert depot_login.status_code == 200
    assert depot_login.get_json()["data"]["role"] == "depot_operator"

    # -------------------------------------------------------------
    # 12. REPLACEMENT ASSIGNMENT (Bus 3 = 189, Driver 2 = D105 Available)
    # -------------------------------------------------------------
    assign_res = client.post('/api/depot/assign', json={
        "request_id": depot_req_id,
        "bus_id": 3,
        "driver_id": 2,
        "eta_minutes": 12
    })
    assert assign_res.status_code == 200
    assert assign_res.get_json()["data"]["status"] == "ASSIGNED"

    # -------------------------------------------------------------
    # 13. DISPATCH REPLACEMENT BUS
    # -------------------------------------------------------------
    dispatch_res = client.post('/api/depot/dispatch', json={
        "request_id": depot_req_id
    })
    assert dispatch_res.status_code == 200
    assert dispatch_res.get_json()["data"]["status"] == "DISPATCHED"

    # -------------------------------------------------------------
    # 14. REPLACEMENT BUS ARRIVAL
    # -------------------------------------------------------------
    arrive_res = client.post('/api/depot/arrive', json={
        "request_id": depot_req_id
    })
    assert arrive_res.status_code == 200
    assert arrive_res.get_json()["data"]["status"] == "ARRIVED"

    # -------------------------------------------------------------
    # 15. PASSENGER TRANSFER RECORDED
    # -------------------------------------------------------------
    transfer_res = client.post('/api/depot/transfer', json={
        "request_id": depot_req_id,
        "transferred_count": 40
    })
    assert transfer_res.status_code == 200
    t_data = transfer_res.get_json()["data"]
    assert t_data["status"] == "PASSENGER_TRANSFER"
    assert t_data["transferred_passengers"] == 40
    assert t_data["remaining_passengers"] == 0

    # -------------------------------------------------------------
    # 16. INCIDENT RESOLVED & SERVICE-RESTORED NOTIFICATION
    # -------------------------------------------------------------
    resolve_res = client.post('/api/depot/resolve', json={
        "request_id": depot_req_id,
        "resolution_notes": "All 40 passengers safely transferred. Service restored."
    })
    assert resolve_res.status_code == 200
    res_data = resolve_res.get_json()["data"]
    assert res_data["status"] == "RESOLVED"

    # Verify database state & service-restored notification
    with app.app_context():
        final_req = DepotRequest.query.get(depot_req_id)
        assert final_req.status == "RESOLVED"

        final_inc = Incident.query.get(incident_id)
        assert final_inc.status == "RESOLVED"

        # Check for service-restored notification sent to passengers
        restored_notif = Notification.query.filter(
            Notification.target_role.in_(["passenger", "all"]),
            Notification.notification_type == "SERVICE_RESTORED"
        ).first()
        assert restored_notif is not None
        assert "Service Restored" in restored_notif.title
