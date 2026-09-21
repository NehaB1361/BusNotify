"""
Tests for Depot Request State Machine & Dispatch Workflow (Section 36, 37, 38)
"""
import pytest
from app.services.depot_service import DepotWorkflowService
from app.models.depot import DepotRequest
from app.models.incident import Incident
from app.models.bus import Bus
from app.models.driver import Driver
from app.extensions import db


def test_complete_depot_workflow(app):
    with app.app_context():
        # Setup Incident and Depot Request
        inc = Incident(
            incident_number="INC-TEST-01",
            trip_id=1,
            bus_id=1,
            route_id=1,
            stop_id=2,
            incident_type="Tyre Puncture",
            priority="HIGH",
            affected_passengers=40
        )
        db.session.add(inc)
        db.session.flush()

        req = DepotRequest(
            request_code="DR-TEST-01",
            incident_id=inc.id,
            failed_bus_id=1,
            route_id=1,
            stop_id=2,
            status="PENDING",
            affected_passengers=40
        )
        db.session.add(req)
        db.session.commit()

        req_id = req.id

        # 1. PENDING -> ASSIGNED (Bus 3 = Bus 189, Driver 1 = Rajesh Patil)
        res1 = DepotWorkflowService.assign_resources(req_id, bus_id=3, driver_id=1, eta_minutes=12)
        assert res1["status"] == "ASSIGNED"
        assert res1["replacement_bus_number"] == "189"

        # Verify illegal transition: cannot jump ASSIGNED -> RESOLVED
        with pytest.raises(ValueError):
            DepotWorkflowService.resolve_request(req_id, "Attempted illegal resolve")

        # 2. ASSIGNED -> DISPATCHED
        res2 = DepotWorkflowService.dispatch_bus(req_id)
        assert res2["status"] == "DISPATCHED"

        # 3. DISPATCHED -> ARRIVED
        res3 = DepotWorkflowService.mark_arrived(req_id)
        assert res3["status"] == "ARRIVED"

        # 4. ARRIVED -> PASSENGER_TRANSFER
        # Test boundary violation: transferring > capacity or > affected
        with pytest.raises(ValueError):
            DepotWorkflowService.record_passenger_transfer(req_id, transferred_count=50)

        res4 = DepotWorkflowService.record_passenger_transfer(req_id, transferred_count=40)
        assert res4["status"] == "PASSENGER_TRANSFER"
        assert res4["transferred_passengers"] == 40
        assert res4["remaining_passengers"] == 0

        # 5. PASSENGER_TRANSFER -> RESOLVED
        res5 = DepotWorkflowService.resolve_request(req_id, resolution_notes="Service restored successfully")
        assert res5["status"] == "RESOLVED"
        assert res5["resolved_at"] is not None
