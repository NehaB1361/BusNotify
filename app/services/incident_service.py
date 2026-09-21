"""
Incident Service
Handles emergency reports from drivers, triggers system notifications,
runs alternative bus recommendations, and generates depot requests.
"""
from datetime import datetime
from typing import Dict, Any, Optional
from app.extensions import db
from app.models.trip import Trip
from app.models.bus import Bus
from app.models.incident import Incident, AlternativeRecommendation
from app.models.depot import DepotRequest
from app.models.notification import Notification
from app.models.audit import AuditLog
from app.services.alternative_service import AlternativeBusService


class IncidentService:

    @classmethod
    def report_emergency(
        cls,
        trip_id: int,
        incident_type: str,
        affected_passengers: int,
        description: str = "",
        priority: str = "HIGH",
        current_stop_id: Optional[int] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Processes driver emergency report (Section 25 & 42):
        1. Updates trip status
        2. Updates bus status
        3. Creates Incident record (e.g. INC-001)
        4. Creates DepotRequest (DR001)
        5. Computes alternative bus recommendations and stores them
        6. Dispatches notifications to passengers and staff
        """
        trip = Trip.query.get(trip_id)
        if not trip:
            raise ValueError(f"Trip with ID {trip_id} not found.")

        bus = trip.bus
        bus_status = "PUNCTURED" if "PUNCTURE" in incident_type.upper() else "BREAKDOWN"
        
        # 1. Update trip & bus status
        trip.status = bus_status
        if current_stop_id:
            trip.current_stop_id = current_stop_id
        bus.current_status = bus_status

        # Generate unique incident number (e.g., INC-001)
        incident_count = Incident.query.count() + 1
        incident_number = f"INC-{incident_count:03d}"

        # 2. Create Incident
        incident = Incident(
            incident_number=incident_number,
            trip_id=trip.id,
            bus_id=bus.id,
            route_id=trip.route_id,
            stop_id=current_stop_id or trip.current_stop_id,
            incident_type=incident_type,
            priority=priority,
            affected_passengers=affected_passengers,
            description=description,
            status="OPEN",
            reported_at=datetime.utcnow(),
        )
        db.session.add(incident)
        db.session.flush()

        # 3. Create Depot Request (DR001)
        depot_req_count = DepotRequest.query.count() + 1
        request_code = f"DR{depot_req_count:03d}"

        depot_request = DepotRequest(
            request_code=request_code,
            incident_id=incident.id,
            failed_bus_id=bus.id,
            route_id=trip.route_id,
            stop_id=incident.stop_id,
            status="PENDING",
            affected_passengers=affected_passengers,
            transferred_passengers=0,
            priority=priority,
            created_at=datetime.utcnow()
        )
        db.session.add(depot_request)

        # 4. Generate & persist alternative recommendations
        alternatives = AlternativeBusService.find_alternatives_for_incident(incident)
        for alt in alternatives:
            rec = AlternativeRecommendation(
                incident_id=incident.id,
                recommended_bus_id=alt["bus_id"],
                direct_route=alt.get("direct_route", True),
                recommended_stop_id=alt.get("recommended_stop_id"),
                walking_distance_m=alt.get("walking_distance_m", 0),
                eta_minutes=alt.get("eta_minutes", 15),
                available_seats=alt.get("available_seats", 0),
                historical_delay_min=alt.get("historical_delay_min", 0.0),
                rank_order=alt.get("rank_order", 1),
                is_recommended=alt.get("is_recommended", False),
                allocated_passengers=alt.get("allocated_passengers", 0),
            )
            db.session.add(rec)

        # 5. Create notifications
        stop_name = incident.stop.name if incident.stop else "en route"
        p_notif = Notification(
            target_role="passenger",
            title=f"Emergency Alert: Bus {bus.bus_number} - {incident_type}",
            message=f"Bus {bus.bus_number} on {trip.route.name} reported {incident_type} at {stop_name}. Alternatives and replacement bus are being coordinated.",
            notification_type="PUNCTURE" if "PUNCTURE" in incident_type.upper() else "BREAKDOWN",
            priority="HIGH",
            related_entity_type="incident",
            related_entity_id=incident.id
        )
        a_notif = Notification(
            target_role="admin",
            title=f"Incident {incident_number}: Bus {bus.bus_number}",
            message=f"New incident reported: {incident_type} at {stop_name}. Depot request {request_code} created.",
            notification_type="INCIDENT",
            priority="HIGH",
            related_entity_type="incident",
            related_entity_id=incident.id
        )
        d_notif = Notification(
            target_role="depot_operator",
            title=f"Urgent Depot Request {request_code}",
            message=f"Bus {bus.bus_number} requires replacement at {stop_name}. {affected_passengers} passengers affected.",
            notification_type="REPLACEMENT_ASSIGNED",
            priority="HIGH",
            related_entity_type="depot_request",
            related_entity_id=depot_request.id
        )
        db.session.add_all([p_notif, a_notif, d_notif])

        # 6. Audit log
        audit = AuditLog(
            user_id=user_id,
            action="REPORT_EMERGENCY",
            entity_type="incident",
            entity_id=incident_number,
            details=f"Reported {incident_type} on Bus {bus.bus_number}. Depot request {request_code} generated."
        )
        db.session.add(audit)
        db.session.commit()

        return {
            "incident": incident.to_dict(),
            "depot_request": depot_request.to_dict(),
            "alternatives": alternatives
        }
