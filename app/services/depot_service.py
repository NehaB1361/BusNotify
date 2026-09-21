"""
Depot Service
Enforces the exact dispatch workflow state machine from Section 36:
PENDING -> ASSIGNED -> DISPATCHED -> ARRIVED -> PASSENGER_TRANSFER -> RESOLVED
"""
from datetime import datetime
from typing import Dict, Any, Optional
from app.extensions import db
from app.models.depot import DepotRequest, PassengerTransfer, ReplacementBus
from app.models.bus import Bus
from app.models.driver import Driver
from app.models.incident import Incident
from app.models.notification import Notification
from app.models.audit import AuditLog

# Strict valid transitions
VALID_TRANSITIONS = {
    "PENDING": ["ASSIGNED", "CANCELLED"],
    "ASSIGNED": ["DISPATCHED", "CANCELLED"],
    "DISPATCHED": ["ARRIVED", "CANCELLED"],
    "ARRIVED": ["PASSENGER_TRANSFER", "CANCELLED"],
    "PASSENGER_TRANSFER": ["RESOLVED"],
    "RESOLVED": [],
    "CANCELLED": []
}


class DepotWorkflowService:

    @classmethod
    def assign_resources(
        cls,
        request_id: int,
        bus_id: int,
        driver_id: int,
        operator_id: Optional[int] = None,
        eta_minutes: int = 12
    ) -> Dict[str, Any]:
        """
        Transition: PENDING -> ASSIGNED
        Validates replacement bus & driver availability and capacity.
        """
        req = DepotRequest.query.get(request_id)
        if not req:
            raise ValueError(f"Depot request {request_id} not found.")

        if req.status != "PENDING":
            raise ValueError(f"Cannot assign resources. Current status is '{req.status}', expected 'PENDING'.")

        bus = Bus.query.get(bus_id)
        if not bus or not bus.is_active:
            raise ValueError("Invalid or inactive bus selected.")
        if bus.current_status not in ["AVAILABLE", "COMPLETED"]:
            raise ValueError(f"Bus {bus.bus_number} is currently '{bus.current_status}', not AVAILABLE.")

        driver = Driver.query.get(driver_id)
        if not driver:
            raise ValueError("Invalid driver selected.")
        if driver.status not in ["AVAILABLE", "OFF_DUTY"]:
            raise ValueError(f"Driver {driver.full_name} is currently '{driver.status}', not AVAILABLE.")

        # Update Request
        req.replacement_bus_id = bus.id
        req.replacement_driver_id = driver.id
        req.operator_id = operator_id
        req.status = "ASSIGNED"
        req.assigned_at = datetime.utcnow()
        req.eta_minutes = eta_minutes

        # Update Bus and Driver state
        bus.current_status = "ASSIGNED"
        driver.status = "ON_TRIP"
        driver.assigned_bus_id = bus.id

        # Record ReplacementBus entry
        rep_entry = ReplacementBus(
            depot_request_id=req.id,
            bus_id=bus.id,
            driver_id=driver.id,
            eta_minutes=eta_minutes,
            assigned_at=datetime.utcnow()
        )
        db.session.add(rep_entry)

        # Notify
        db.session.add(Notification(
            target_role="passenger",
            title=f"Replacement Bus Assigned ({bus.bus_number})",
            message=f"Replacement Bus {bus.bus_number} with driver {driver.full_name} has been assigned. ETA: {eta_minutes} mins.",
            notification_type="REPLACEMENT_ASSIGNED",
            priority="HIGH",
            related_entity_type="depot_request",
            related_entity_id=req.id
        ))
        db.session.add(Notification(
            target_role="driver",
            user_id=driver.user_id,
            title="Emergency Trip Assignment",
            message=f"You are assigned to operate Bus {bus.bus_number} for Depot Request {req.request_code} at {req.stop.name if req.stop else 'Location'}.",
            notification_type="REPLACEMENT_ASSIGNED",
            priority="HIGH",
            related_entity_type="depot_request",
            related_entity_id=req.id
        ))

        # Audit log
        db.session.add(AuditLog(
            user_id=operator_id,
            action="ASSIGN_REPLACEMENT",
            entity_type="depot_request",
            entity_id=req.request_code,
            details=f"Assigned Bus {bus.bus_number} and Driver {driver.full_name} (ETA: {eta_minutes}m)"
        ))

        db.session.commit()
        return req.to_dict()

    @classmethod
    def dispatch_bus(cls, request_id: int, operator_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Transition: ASSIGNED -> DISPATCHED
        """
        req = DepotRequest.query.get(request_id)
        if not req:
            raise ValueError(f"Depot request {request_id} not found.")

        if req.status != "ASSIGNED":
            raise ValueError(f"Cannot dispatch. Current status is '{req.status}', expected 'ASSIGNED'.")

        req.status = "DISPATCHED"
        req.dispatched_at = datetime.utcnow()
        if req.replacement_bus:
            req.replacement_bus.current_status = "DISPATCHED"

        # Notify passengers
        db.session.add(Notification(
            target_role="passenger",
            title=f"Replacement Bus {req.replacement_bus.bus_number} Dispatched",
            message=f"Replacement Bus {req.replacement_bus.bus_number} is on the way to {req.stop.name if req.stop else 'pickup location'}. ETA: {req.eta_minutes} min.",
            notification_type="REPLACEMENT_DISPATCHED",
            priority="HIGH",
            related_entity_type="depot_request",
            related_entity_id=req.id
        ))

        db.session.add(AuditLog(
            user_id=operator_id,
            action="DISPATCH_REPLACEMENT",
            entity_type="depot_request",
            entity_id=req.request_code,
            details=f"Dispatched Replacement Bus {req.replacement_bus.bus_number} towards {req.stop.name if req.stop else 'incident location'}."
        ))

        db.session.commit()
        return req.to_dict()

    @classmethod
    def mark_arrived(cls, request_id: int, operator_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Transition: DISPATCHED -> ARRIVED
        """
        req = DepotRequest.query.get(request_id)
        if not req:
            raise ValueError(f"Depot request {request_id} not found.")

        if req.status != "DISPATCHED":
            raise ValueError(f"Cannot mark arrived. Current status is '{req.status}', expected 'DISPATCHED'.")

        req.status = "ARRIVED"
        req.arrived_at = datetime.utcnow()

        db.session.add(Notification(
            target_role="passenger",
            title=f"Replacement Bus {req.replacement_bus.bus_number} Arrived",
            message=f"Replacement Bus {req.replacement_bus.bus_number} has arrived at {req.stop.name if req.stop else 'the stop'}. Please proceed to board.",
            notification_type="REPLACEMENT_ARRIVED",
            priority="HIGH",
            related_entity_type="depot_request",
            related_entity_id=req.id
        ))

        db.session.add(AuditLog(
            user_id=operator_id,
            action="REPLACEMENT_ARRIVED",
            entity_type="depot_request",
            entity_id=req.request_code,
            details=f"Replacement Bus {req.replacement_bus.bus_number} reached incident site."
        ))

        db.session.commit()
        return req.to_dict()

    @classmethod
    def record_passenger_transfer(
        cls,
        request_id: int,
        transferred_count: int,
        operator_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Transition: ARRIVED -> PASSENGER_TRANSFER
        Validates transfer boundaries:
          0 <= transferred <= affected_passengers
          transferred <= replacement_capacity
        """
        req = DepotRequest.query.get(request_id)
        if not req:
            raise ValueError(f"Depot request {request_id} not found.")

        if req.status not in ["ARRIVED", "PASSENGER_TRANSFER"]:
            raise ValueError(f"Cannot record transfer. Current status is '{req.status}', expected 'ARRIVED' or 'PASSENGER_TRANSFER'.")

        if transferred_count < 0:
            raise ValueError("Transferred count cannot be negative.")

        replacement_cap = req.replacement_bus.capacity if req.replacement_bus else 40
        if transferred_count > replacement_cap:
            raise ValueError(f"Transferred count ({transferred_count}) exceeds replacement bus capacity ({replacement_cap}).")

        if transferred_count > req.affected_passengers:
            raise ValueError(f"Transferred count ({transferred_count}) exceeds total affected passengers ({req.affected_passengers}).")

        req.status = "PASSENGER_TRANSFER"
        req.transferred_passengers = transferred_count

        transfer_log = PassengerTransfer(
            depot_request_id=req.id,
            failed_bus_id=req.failed_bus_id,
            target_bus_id=req.replacement_bus_id,
            passengers_transferred=transferred_count,
            transfer_stop_id=req.stop_id,
            recorded_at=datetime.utcnow()
        )
        db.session.add(transfer_log)

        db.session.add(AuditLog(
            user_id=operator_id,
            action="RECORD_TRANSFER",
            entity_type="depot_request",
            entity_id=req.request_code,
            details=f"Recorded transfer of {transferred_count}/{req.affected_passengers} passengers."
        ))

        db.session.commit()
        return req.to_dict()

    @classmethod
    def resolve_request(
        cls,
        request_id: int,
        resolution_notes: str,
        operator_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Transition: PASSENGER_TRANSFER -> RESOLVED
        Closes incident and notifies passengers of full service restoration.
        """
        req = DepotRequest.query.get(request_id)
        if not req:
            raise ValueError(f"Depot request {request_id} not found.")

        if req.status != "PASSENGER_TRANSFER":
            raise ValueError(f"Cannot resolve request. Current status is '{req.status}', expected 'PASSENGER_TRANSFER'.")

        req.status = "RESOLVED"
        req.resolved_at = datetime.utcnow()
        req.resolution_notes = resolution_notes

        # Resolve Incident
        if req.incident:
            req.incident.status = "RESOLVED"
            req.incident.resolved_at = datetime.utcnow()

        # Update Replacement Bus and Driver
        if req.replacement_bus:
            req.replacement_bus.current_status = "RUNNING"
        if req.failed_bus:
            req.failed_bus.current_status = "COMPLETED"

        # Notify
        db.session.add(Notification(
            target_role="passenger",
            title="Service Restored",
            message=f"Passenger transfer completed for Bus {req.failed_bus.bus_number}. Journey continuing via Bus {req.replacement_bus.bus_number}. Service restored.",
            notification_type="SERVICE_RESTORED",
            priority="HIGH",
            related_entity_type="depot_request",
            related_entity_id=req.id
        ))

        db.session.add(AuditLog(
            user_id=operator_id,
            action="RESOLVE_DEPOT_REQUEST",
            entity_type="depot_request",
            entity_id=req.request_code,
            details=f"Request resolved. Notes: {resolution_notes}"
        ))

        db.session.commit()
        return req.to_dict()
