"""
BusNotify - User Dataset Loader
Ingests the official BusNotify Complete Dataset:
- 6 Intercity/City Routes (PUNE_MUM, PUNE_NASHIK, MUM_NAGPUR, PUNE_SOLAPUR, MUM_AHMEDABAD, PUNE_BANGALORE)
- 30 Buses with capacity, current occupancy, and available seats
- Emergency Incidents and Depot Requests (DR001 / INC001, DR002 / INC002)
- Live GPS snapshots and historical delay records for accurate statistical estimates
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta, date
import random

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from app.extensions import db
from app.models.transit import Route, Stop, RouteStop, RouteConnectivity
from app.models.bus import Bus, BusCapacity
from app.models.trip import Trip, LiveGPS
from app.models.incident import Incident
from app.models.depot import DepotRequest
from app.models.delay import HistoricalDelay

DATASET_BUS_CAPACITY = [
    {"bus_number": "SHIVNERI_101", "route_id": "PUNE_MUM", "capacity": 50, "occupancy": 8, "available": 42},
    {"bus_number": "SHIVNERI_102", "route_id": "PUNE_MUM", "capacity": 50, "occupancy": 38, "available": 12},
    {"bus_number": "SHIVNERI_103", "route_id": "PUNE_MUM", "capacity": 50, "occupancy": 17, "available": 33},
    {"bus_number": "SHIVNERI_104", "route_id": "PUNE_MUM", "capacity": 50, "occupancy": 28, "available": 22},
    {"bus_number": "SHIVNERI_105", "route_id": "PUNE_MUM", "capacity": 50, "occupancy": 34, "available": 16},
    {"bus_number": "PUNE_NASHIK_101", "route_id": "PUNE_NASHIK", "capacity": 40, "occupancy": 14, "available": 26},
    {"bus_number": "PUNE_NASHIK_102", "route_id": "PUNE_NASHIK", "capacity": 40, "occupancy": 20, "available": 20},
    {"bus_number": "PUNE_NASHIK_103", "route_id": "PUNE_NASHIK", "capacity": 40, "occupancy": 14, "available": 26},
    {"bus_number": "PUNE_NASHIK_104", "route_id": "PUNE_NASHIK", "capacity": 40, "occupancy": 24, "available": 16},
    {"bus_number": "PUNE_NASHIK_105", "route_id": "PUNE_NASHIK", "capacity": 40, "occupancy": 32, "available": 8},
    {"bus_number": "MUM_NAGPUR_101", "route_id": "MUM_NAGPUR", "capacity": 45, "occupancy": 31, "available": 14},
    {"bus_number": "MUM_NAGPUR_102", "route_id": "MUM_NAGPUR", "capacity": 45, "occupancy": 25, "available": 20},
    {"bus_number": "MUM_NAGPUR_103", "route_id": "MUM_NAGPUR", "capacity": 45, "occupancy": 9, "available": 36},
    {"bus_number": "MUM_NAGPUR_104", "route_id": "MUM_NAGPUR", "capacity": 45, "occupancy": 45, "available": 0},
    {"bus_number": "MUM_NAGPUR_105", "route_id": "MUM_NAGPUR", "capacity": 45, "occupancy": 18, "available": 27},
    {"bus_number": "PUNE_SOLAPUR_101", "route_id": "PUNE_SOLAPUR", "capacity": 40, "occupancy": 31, "available": 9},
    {"bus_number": "PUNE_SOLAPUR_102", "route_id": "PUNE_SOLAPUR", "capacity": 40, "occupancy": 22, "available": 18},
    {"bus_number": "PUNE_SOLAPUR_103", "route_id": "PUNE_SOLAPUR", "capacity": 40, "occupancy": 23, "available": 17},
    {"bus_number": "PUNE_SOLAPUR_104", "route_id": "PUNE_SOLAPUR", "capacity": 40, "occupancy": 15, "available": 25},
    {"bus_number": "PUNE_SOLAPUR_105", "route_id": "PUNE_SOLAPUR", "capacity": 40, "occupancy": 21, "available": 19},
    {"bus_number": "MUM_AHMEDABAD_101", "route_id": "MUM_AHMEDABAD", "capacity": 50, "occupancy": 48, "available": 2},
    {"bus_number": "MUM_AHMEDABAD_102", "route_id": "MUM_AHMEDABAD", "capacity": 50, "occupancy": 43, "available": 7},
    {"bus_number": "MUM_AHMEDABAD_103", "route_id": "MUM_AHMEDABAD", "capacity": 50, "occupancy": 20, "available": 30},
    {"bus_number": "MUM_AHMEDABAD_104", "route_id": "MUM_AHMEDABAD", "capacity": 50, "occupancy": 30, "available": 20},
    {"bus_number": "MUM_AHMEDABAD_105", "route_id": "MUM_AHMEDABAD", "capacity": 50, "occupancy": 20, "available": 30},
    {"bus_number": "PUNE_BANGALORE_101", "route_id": "PUNE_BANGALORE", "capacity": 50, "occupancy": 12, "available": 38},
    {"bus_number": "PUNE_BANGALORE_102", "route_id": "PUNE_BANGALORE", "capacity": 50, "occupancy": 14, "available": 36},
    {"bus_number": "PUNE_BANGALORE_103", "route_id": "PUNE_BANGALORE", "capacity": 50, "occupancy": 17, "available": 33},
    {"bus_number": "PUNE_BANGALORE_104", "route_id": "PUNE_BANGALORE", "capacity": 50, "occupancy": 6, "available": 44},
    {"bus_number": "PUNE_BANGALORE_105", "route_id": "PUNE_BANGALORE", "capacity": 50, "occupancy": 20, "available": 30}
]

ROUTES_CONFIG = {
    "PUNE_MUM": {
        "name": "Pune to Mumbai Shivneri AC Express",
        "name_mr": "पुणे ते मुंबई शिवनेरी एसी एक्सप्रेस",
        "source": "Pune Station",
        "destination": "Dadar Mumbai",
        "distance": 150.0,
        "duration": 210,
        "stops": ["STP-PUN", "STP-SHI", "STP-WAK", "STP-MAG", "STP-HAD"]
    },
    "PUNE_NASHIK": {
        "name": "Pune to Nashik Semi-Luxury",
        "name_mr": "पुणे ते नाशिक सेमी-लक्झरी",
        "source": "Shivajinagar",
        "destination": "Nashik CBS",
        "distance": 210.0,
        "duration": 270,
        "stops": ["STP-SHI", "STP-BHO", "STP-NIG", "STP-PUN"]
    },
    "MUM_NAGPUR": {
        "name": "Mumbai to Nagpur Superfast Express",
        "name_mr": "मुंबई ते नागपूर सुपरफास्ट एक्सप्रेस",
        "source": "Mumbai Central",
        "destination": "Nagpur Mor Bhavan",
        "distance": 820.0,
        "duration": 780,
        "stops": ["STP-PUN", "STP-YER", "STP-KHA"]
    },
    "PUNE_SOLAPUR": {
        "name": "Pune to Solapur Express",
        "name_mr": "पुणे ते सोलापूर एक्सप्रेस",
        "source": "Swargate",
        "destination": "Solapur Bus Stand",
        "distance": 250.0,
        "duration": 300,
        "stops": ["STP-SWA", "STP-FAT", "STP-MAG", "STP-HAD"]
    },
    "MUM_AHMEDABAD": {
        "name": "Mumbai to Ahmedabad Intercity",
        "name_mr": "मुंबई ते अहमदाबाद इंटरसिटी",
        "source": "Borivali Mumbai",
        "destination": "Geeta Mandir Ahmedabad",
        "distance": 530.0,
        "duration": 540,
        "stops": ["STP-DEC", "STP-AUN", "STP-BAN"]
    },
    "PUNE_BANGALORE": {
        "name": "Pune to Bangalore Deluxe Sleeper",
        "name_mr": "पुणे ते बंगलोर डिलक्स स्लीपर",
        "source": "Katraj Pune",
        "destination": "Majestic Bangalore",
        "distance": 840.0,
        "duration": 810,
        "stops": ["STP-KAT", "STP-DHN", "STP-SWA", "STP-BIB"]
    }
}


def load_dataset():
    app = create_app()
    with app.app_context():
        print("Starting dataset ingestion...")

        # 1. Ensure Stops exist
        stops = {s.stop_code: s for s in Stop.query.all()}

        # 2. Ingest or update Routes
        routes_map = {}
        for r_code, r_info in ROUTES_CONFIG.items():
            route = Route.query.filter_by(route_number=r_code).first()
            if not route:
                route = Route(
                    route_number=r_code,
                    name=r_info["name"],
                    name_mr=r_info["name_mr"],
                    source=r_info["source"],
                    destination=r_info["destination"],
                    total_distance_km=r_info["distance"],
                    estimated_duration_min=r_info["duration"]
                )
                db.session.add(route)
                db.session.flush()

                # Add RouteStops
                for idx, scode in enumerate(r_info["stops"]):
                    if scode in stops:
                        rs = RouteStop(
                            route_id=route.id,
                            stop_id=stops[scode].id,
                            sequence_order=idx + 1,
                            distance_from_prev_km=round(r_info["distance"] / len(r_info["stops"]), 1),
                            avg_travel_time_min=round(r_info["duration"] / len(r_info["stops"]))
                        )
                        db.session.add(rs)
            routes_map[r_code] = route
        db.session.commit()
        print(f"Routes synchronized ({len(routes_map)} routes).")

        # 3. Ingest Buses, BusCapacity, and Trips
        now = datetime.utcnow()
        buses_map = {}
        trips_map = {}
        for b_data in DATASET_BUS_CAPACITY:
            b_num = b_data["bus_number"]
            bus = Bus.query.filter_by(bus_number=b_num).first()
            r_obj = routes_map.get(b_data["route_id"])
            
            # Determine initial status
            status = "RUNNING"
            if b_num == "SHIVNERI_101":
                status = "PUNCTURED"
            elif b_num == "PUNE_NASHIK_101":
                status = "BREAKDOWN"
            elif b_num == "PUNE_NASHIK_105":
                status = "DISPATCHED"
            elif b_data["available"] > 30:
                status = "AVAILABLE"
            elif b_data["occupancy"] > 35:
                status = "DELAYED"

            if not bus:
                reg_num = f"MH-12-{b_num[:4]}-{random.randint(1000, 9999)}"
                bus = Bus(
                    bus_number=b_num,
                    registration_number=reg_num,
                    capacity=b_data["capacity"],
                    depot_name="Pune Central Depot",
                    current_status=status,
                    assigned_route_id=r_obj.id if r_obj else None
                )
                db.session.add(bus)
                db.session.flush()
            else:
                bus.capacity = b_data["capacity"]
                bus.current_status = status
                if r_obj:
                    bus.assigned_route_id = r_obj.id

            buses_map[b_num] = bus

            # Update or create BusCapacity
            bc = BusCapacity.query.filter_by(bus_id=bus.id).first()
            if not bc:
                bc = BusCapacity(
                    bus_id=bus.id,
                    total_capacity=b_data["capacity"],
                    seated_capacity=int(b_data["capacity"] * 0.8),
                    standing_capacity=b_data["capacity"] - int(b_data["capacity"] * 0.8)
                )
                db.session.add(bc)
            else:
                bc.total_capacity = b_data["capacity"]

            # Create or update active Trip and LiveGPS for live tracking
            trip = Trip.query.filter_by(bus_id=bus.id).first()
            cur_stop = stops.get("STP-MAG") if b_num == "SHIVNERI_101" else (stops.get("STP-PUN") if b_num == "PUNE_NASHIK_101" else random.choice(list(stops.values())))
            nxt_stop = stops.get("STP-HAD") if b_num == "SHIVNERI_101" else random.choice(list(stops.values()))

            if not trip:
                trip = Trip(
                    trip_code=f"TRIP-{b_num}",
                    bus_id=bus.id,
                    route_id=r_obj.id if r_obj else None,
                    scheduled_start_time=now - timedelta(minutes=45),
                    actual_start_time=now - timedelta(minutes=40),
                    current_stop_id=cur_stop.id if cur_stop else None,
                    next_stop_id=nxt_stop.id if nxt_stop else None,
                    status=status if status in ["RUNNING", "DELAYED", "PUNCTURED", "BREAKDOWN", "DISPATCHED"] else "RUNNING",
                    passenger_count=b_data["occupancy"]
                )
                db.session.add(trip)
                db.session.flush()

                # Live GPS
                lat = cur_stop.latitude + (random.uniform(-0.005, 0.005) if cur_stop else 0)
                lon = cur_stop.longitude + (random.uniform(-0.005, 0.005) if cur_stop else 0)
                gps = LiveGPS(
                    trip_id=trip.id,
                    bus_id=bus.id,
                    latitude=lat,
                    longitude=lon,
                    speed_kmh=0.0 if status in ["PUNCTURED", "BREAKDOWN"] else 34.5,
                    source="GPS",
                    timestamp=now - timedelta(seconds=random.randint(10, 45))
                )
                db.session.add(gps)
            else:
                trip.passenger_count = b_data["occupancy"]
                trip.status = status if status in ["RUNNING", "DELAYED", "PUNCTURED", "BREAKDOWN", "DISPATCHED"] else "RUNNING"
            trips_map[b_num] = trip

        db.session.commit()
        print(f"Buses, capacities, trips and GPS records updated ({len(buses_map)} buses).")

        # 4. Ingest Incidents and Depot Requests (DR001 and DR002)
        mag_stop = Stop.query.filter((Stop.stop_code == "STP-MAG") | (Stop.name == "Magarpatta")).first()
        pun_stop = Stop.query.filter((Stop.stop_code == "STP-PUN") | (Stop.name == "Pune Station")).first()
        r_mum = routes_map.get("PUNE_MUM")
        r_nsk = routes_map.get("PUNE_NASHIK")

        # Incident 1 / DR001
        inc1 = Incident.query.filter_by(incident_number="INC001").first()
        trip_101 = trips_map.get("SHIVNERI_101")
        if not inc1:
            inc1 = Incident(
                incident_number="INC001",
                trip_id=trip_101.id if trip_101 else 1,
                bus_id=buses_map["SHIVNERI_101"].id,
                route_id=r_mum.id if r_mum else None,
                stop_id=mag_stop.id if mag_stop else None,
                incident_type="Tyre Puncture",
                affected_passengers=40,
                priority="HIGH",
                status="OPEN",
                reported_at=datetime(2026, 9, 19, 16, 56, 0)
            )
            db.session.add(inc1)
            db.session.flush()

        dr1 = DepotRequest.query.filter_by(request_code="DR001").first()
        if not dr1:
            dr1 = DepotRequest(
                request_code="DR001",
                incident_id=inc1.id,
                failed_bus_id=buses_map["SHIVNERI_101"].id,
                route_id=r_mum.id if r_mum else None,
                stop_id=mag_stop.id if mag_stop else None,
                affected_passengers=40,
                transferred_passengers=30,
                priority="HIGH",
                status="PENDING",
                created_at=datetime(2026, 9, 19, 16, 56, 0)
            )
            db.session.add(dr1)

        # Incident 2 / DR002
        inc2 = Incident.query.filter_by(incident_number="INC002").first()
        trip_nsk_101 = trips_map.get("PUNE_NASHIK_101")
        if not inc2:
            inc2 = Incident(
                incident_number="INC002",
                trip_id=trip_nsk_101.id if trip_nsk_101 else 1,
                bus_id=buses_map["PUNE_NASHIK_101"].id,
                route_id=r_nsk.id if r_nsk else None,
                stop_id=pun_stop.id if pun_stop else None,
                incident_type="Engine Failure",
                affected_passengers=28,
                priority="CRITICAL",
                status="OPEN",
                reported_at=datetime(2026, 9, 19, 17, 6, 0)
            )
            db.session.add(inc2)
            db.session.flush()

        dr2 = DepotRequest.query.filter_by(request_code="DR002").first()
        if not dr2:
            dr2 = DepotRequest(
                request_code="DR002",
                incident_id=inc2.id,
                failed_bus_id=buses_map["PUNE_NASHIK_101"].id,
                route_id=r_nsk.id if r_nsk else None,
                stop_id=pun_stop.id if pun_stop else None,
                affected_passengers=28,
                transferred_passengers=0,
                priority="CRITICAL",
                replacement_bus_id=buses_map["PUNE_NASHIK_105"].id,
                status="ASSIGNED",
                created_at=datetime(2026, 9, 19, 17, 6, 0)
            )
            db.session.add(dr2)

        # 5. Add historical delay observations for new routes
        start_d = date.today() - timedelta(days=60)
        delay_batch = []
        for r_code, r_obj in routes_map.items():
            for s_code in ROUTES_CONFIG[r_code]["stops"]:
                st_obj = stops.get(s_code)
                if not st_obj:
                    continue
                # Add 10-15 historical records per stop
                for k in range(12):
                    s_date = start_d + timedelta(days=k * 4)
                    delay_m = random.choice([4.0, 6.5, 9.0, 11.5, 14.0, 16.0, 18.5, 22.0])
                    delay_batch.append(HistoricalDelay(
                        route_id=r_obj.id,
                        stop_id=st_obj.id,
                        weekday=s_date.weekday(),
                        hour_of_day=17,
                        delay_minutes=delay_m,
                        delay_reason="TRAFFIC" if delay_m < 15 else "PUNCTURE_OR_BREAKDOWN",
                        sample_date=s_date
                    ))
        db.session.bulk_save_objects(delay_batch)
        db.session.commit()
        print(f"Incidents (DR001, DR002) and {len(delay_batch)} historical delay records ingested successfully!")


if __name__ == "__main__":
    load_dataset()
