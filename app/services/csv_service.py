"""
CSV Import and Export Service
Validates CSV files, checks headers, types, constraints, foreign keys,
and returns structured summaries with row-level error logs (Section 48).
"""
import io
import csv
from datetime import datetime
from typing import Dict, Any, List, Tuple
from app.extensions import db
from app.models.transit import Route, Stop, RouteStop, RouteConnectivity
from app.models.bus import Bus, BusCapacity, Driver
from app.models.trip import Trip, LiveGPS
from app.models.delay import HistoricalDelay
from app.models.incident import Incident
from app.models.depot import DepotRequest, ReplacementBus


class CSVService:

    SCHEMAS = {
        "routes": {
            "required_headers": ["route_number", "name", "source", "destination", "total_distance_km", "estimated_duration_min"],
            "model": Route
        },
        "stops": {
            "required_headers": ["stop_code", "name", "latitude", "longitude"],
            "model": Stop
        },
        "buses": {
            "required_headers": ["bus_number", "registration_number", "capacity", "depot_name"],
            "model": Bus
        },
        "drivers": {
            "required_headers": ["driver_code", "full_name", "mobile_number", "license_number"],
            "model": Driver
        },
        "historical_delays": {
            "required_headers": ["route_number", "stop_code", "weekday", "hour_of_day", "delay_minutes", "delay_reason", "sample_date"],
            "model": HistoricalDelay
        },
        "bus_capacity": {
            "required_headers": ["bus_number", "capacity", "available_seats"],
            "model": BusCapacity
        },
        "depot_requests": {
            "required_headers": ["request_id", "incident_id", "failed_bus_number", "problem", "affected_passengers", "priority", "status"],
            "model": DepotRequest
        }
    }

    @classmethod
    def import_csv(cls, table_name: str, file_stream) -> Dict[str, Any]:
        """
        Validates and imports a CSV file stream into the database.
        """
        if table_name not in cls.SCHEMAS:
            raise ValueError(f"Unsupported table '{table_name}' for CSV import.")

        schema = cls.SCHEMAS[table_name]
        required_headers = schema["required_headers"]

        # Read CSV content
        stream = io.StringIO(file_stream.read().decode("utf-8-sig"), newline=None)
        reader = csv.DictReader(stream)

        # Validate headers
        if not reader.fieldnames:
            raise ValueError("Empty CSV file or missing headers.")

        missing_headers = [h for h in required_headers if h not in reader.fieldnames]
        if missing_headers:
            raise ValueError(f"Missing required CSV headers: {', '.join(missing_headers)}")

        successful_rows = 0
        failed_rows = 0
        errors: List[Dict[str, Any]] = []

        row_num = 1
        for row in reader:
            row_num += 1
            try:
                cls._process_row(table_name, row)
                successful_rows += 1
            except Exception as e:
                failed_rows += 1
                errors.append({
                    "row": row_num,
                    "data": row,
                    "error": str(e)
                })

        db.session.commit()

        return {
            "table": table_name,
            "total_processed": successful_rows + failed_rows,
            "successful_rows": successful_rows,
            "failed_rows": failed_rows,
            "errors": errors[:50]  # Cap error list
        }

    @classmethod
    def _process_row(cls, table_name: str, row: Dict[str, str]):
        if table_name == "routes":
            num = row["route_number"].strip()
            existing = Route.query.filter_by(route_number=num).first()
            if existing:
                raise ValueError(f"Route '{num}' already exists.")
            route = Route(
                route_number=num,
                name=row["name"].strip(),
                source=row["source"].strip(),
                destination=row["destination"].strip(),
                total_distance_km=float(row.get("total_distance_km", 0.0)),
                estimated_duration_min=int(row.get("estimated_duration_min", 45))
            )
            db.session.add(route)

        elif table_name == "stops":
            code = row["stop_code"].strip()
            existing = Stop.query.filter_by(stop_code=code).first()
            if existing:
                raise ValueError(f"Stop code '{code}' already exists.")
            stop = Stop(
                stop_code=code,
                name=row["name"].strip(),
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                landmark=row.get("landmark", "")
            )
            db.session.add(stop)

        elif table_name == "buses":
            b_num = row["bus_number"].strip()
            existing = Bus.query.filter_by(bus_number=b_num).first()
            if existing:
                raise ValueError(f"Bus '{b_num}' already exists.")
            
            route_id = None
            if "assigned_route_id" in row and row["assigned_route_id"].strip():
                r_val = row["assigned_route_id"].strip()
                r_obj = Route.query.filter((Route.route_number == r_val) | (Route.id == r_val if r_val.isdigit() else False)).first()
                if r_obj:
                    route_id = r_obj.id

            bus = Bus(
                bus_number=b_num,
                registration_number=row.get("registration_number", f"MH-12-{b_num}").strip(),
                capacity=int(row.get("capacity", 40)),
                depot_name=row.get("depot_name", "Pune Central Depot"),
                current_status=row.get("current_status", "ACTIVE" if row.get("status") == "ACTIVE" else "AVAILABLE").strip().upper(),
                assigned_route_id=route_id
            )
            db.session.add(bus)
            db.session.flush()

            # Create or update BusCapacity
            cap = int(row.get("capacity", 40))
            db.session.add(BusCapacity(
                bus_id=bus.id,
                total_capacity=cap,
                seated_capacity=int(cap * 0.8),
                standing_capacity=cap - int(cap * 0.8)
            ))

        elif table_name == "bus_capacity":
            b_num = row["bus_number"].strip()
            bus = Bus.query.filter_by(bus_number=b_num).first()
            if not bus:
                raise ValueError(f"Foreign key error: Bus '{b_num}' not found.")
            cap = int(row.get("capacity", bus.capacity or 40))
            avail = int(row.get("available_seats", cap))
            occ = int(row.get("current_occupancy", cap - avail))
            
            bc = BusCapacity.query.filter_by(bus_id=bus.id).first()
            if not bc:
                bc = BusCapacity(bus_id=bus.id, total_capacity=cap, seated_capacity=int(cap * 0.8), standing_capacity=cap - int(cap * 0.8))
                db.session.add(bc)
            else:
                bc.total_capacity = cap

            # Also update current trip passenger count if active trip exists
            from app.models.trip import Trip
            trip = Trip.query.filter_by(bus_id=bus.id).order_by(Trip.id.desc()).first()
            if trip:
                trip.passenger_count = occ

        elif table_name == "depot_requests":
            req_code = row["request_id"].strip()
            existing = DepotRequest.query.filter_by(request_code=req_code).first()
            if existing:
                raise ValueError(f"Depot request '{req_code}' already exists.")

            failed_bus = Bus.query.filter_by(bus_number=row["failed_bus_number"].strip()).first()
            if not failed_bus:
                raise ValueError(f"Bus '{row['failed_bus_number']}' not found.")

            route = None
            if "route_id" in row and row["route_id"].strip():
                route = Route.query.filter_by(route_number=row["route_id"].strip()).first()
            if not route and failed_bus.assigned_route:
                route = failed_bus.assigned_route

            stop = None
            if "location_stop_id" in row and row["location_stop_id"].strip():
                st_code = row["location_stop_id"].strip()
                stop = Stop.query.filter((Stop.stop_code == st_code) | (Stop.name.ilike(f"%{st_code}%"))).first()

            # Create Incident first
            inc_code = row.get("incident_id", f"INC-{req_code}").strip()
            inc = Incident.query.filter_by(incident_code=inc_code).first()
            if not inc:
                inc = Incident(
                    incident_code=inc_code,
                    bus_id=failed_bus.id,
                    route_id=route.id if route else None,
                    stop_id=stop.id if stop else None,
                    incident_type=row.get("problem", "TYRE_PUNCTURE").strip().upper(),
                    affected_passengers=int(row.get("affected_passengers", 40)),
                    severity="HIGH" if row.get("priority") == "CRITICAL" else "MEDIUM",
                    status="OPEN"
                )
                db.session.add(inc)
                db.session.flush()

            # Replacement bus assignment
            rep_bus_id = None
            if "assigned_replacement_bus" in row and row["assigned_replacement_bus"].strip():
                rb = Bus.query.filter_by(bus_number=row["assigned_replacement_bus"].strip()).first()
                if rb:
                    rep_bus_id = rb.id

            depot_req = DepotRequest(
                request_code=req_code,
                incident_id=inc.id,
                failed_bus_id=failed_bus.id,
                route_id=route.id if route else None,
                stop_id=stop.id if stop else None,
                affected_passengers=int(row.get("affected_passengers", 40)),
                assigned_replacement_bus_id=rep_bus_id,
                status=row.get("status", "PENDING").strip().upper()
            )
            db.session.add(depot_req)

        elif table_name == "historical_delays":
            route = Route.query.filter_by(route_number=row["route_number"].strip()).first()
            if not route:
                raise ValueError(f"Foreign key error: Route '{row['route_number']}' not found.")
            stop = Stop.query.filter_by(stop_code=row["stop_code"].strip()).first()
            if not stop:
                raise ValueError(f"Foreign key error: Stop '{row['stop_code']}' not found.")
            
            sample_d = datetime.strptime(row["sample_date"].strip(), "%Y-%m-%d").date()
            record = HistoricalDelay(
                route_id=route.id,
                stop_id=stop.id,
                weekday=int(row["weekday"]),
                hour_of_day=int(row["hour_of_day"]),
                delay_minutes=float(row["delay_minutes"]),
                delay_reason=row.get("delay_reason", "TRAFFIC").strip().upper(),
                sample_date=sample_d
            )
            db.session.add(record)

    @classmethod
    def export_csv(cls, table_name: str) -> str:
        """
        Exports database rows to CSV string format.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        if table_name == "routes":
            writer.writerow(["route_number", "name", "source", "destination", "total_distance_km", "estimated_duration_min"])
            for r in Route.query.all():
                writer.writerow([r.route_number, r.name, r.source, r.destination, r.total_distance_km, r.estimated_duration_min])

        elif table_name == "stops":
            writer.writerow(["stop_code", "name", "latitude", "longitude", "landmark"])
            for s in Stop.query.all():
                writer.writerow([s.stop_code, s.name, s.latitude, s.longitude, s.landmark or ""])

        elif table_name == "buses":
            writer.writerow(["bus_number", "registration_number", "capacity", "depot_name", "current_status"])
            for b in Bus.query.all():
                writer.writerow([b.bus_number, b.registration_number, b.capacity, b.depot_name, b.current_status])

        return output.getvalue()
