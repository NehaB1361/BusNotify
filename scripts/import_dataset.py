"""
BusNotify - Complete Dataset Import Script
Imports the full transit dataset from data/csv_templates/*.csv into MySQL 8+ (mysql94):
- stops.csv (451 stops + BANGALORE_STATION)
- routes.csv (1,017 routes + 60 inter-city routes)
- route_stops.csv (4,198 route stop sequences)
- depot_operators.csv (330 operators -> users)
- drivers.csv (4,006 drivers -> users & driver records)
- buses.csv & replacement_buses.csv (fleet of active & standby buses)
- bus_capacity.csv (capacity & occupancy details)
- route_connectivity.csv (34,773 route connections)
- live_gps.csv (3,116 real-time GPS tracking snapshots + active trips)
- incidents.csv (3,162 incident records + trips)
- depot_requests.csv (1,936 depot replacement requests)
- historical_delays.csv (61,616 statistical delay observations)

Preserves baseline acceptance accounts and scenarios:
- admin@busnotify.com, driver@busnotify.com, depot@busnotify.com, passenger@busnotify.com, snehal@gmail.com
- Bus 123, 156, 178, 189 & SHIVNERI_101
- Driver D104 (Rajesh Patil)
- Magarpatta Stop
"""

import os
import sys
import csv
from datetime import datetime, date, timedelta
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from werkzeug.security import generate_password_hash
from sqlalchemy import text
from app import create_app, db
from app.models import (
    User, Stop, Route, RouteStop, RouteConnectivity,
    Bus, BusCapacity, Driver, Trip, LiveGPS,
    Incident, DepotRequest, HistoricalDelay, AuditLog
)

DATA_DIR = BASE_DIR / "data" / "csv_templates"


def clean_str(val):
    if val is None:
        return ""
    return str(val).strip()


def parse_dt(dt_str):
    if not dt_str:
        return datetime.utcnow()
    dt_str = dt_str.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            pass
    return datetime.utcnow()


def parse_date(d_str):
    if not d_str:
        return date.today()
    d_str = d_str.strip()
    try:
        return datetime.strptime(d_str, "%Y-%m-%d").date()
    except ValueError:
        return date.today()


def run_import():
    app = create_app()
    with app.app_context():
        print("=" * 60)
        print("BusNotify - Commencing Full Dataset Import into MySQL 8+")
        print(f"Database: {app.config.get('DB_NAME', 'mysql94')} on {app.config.get('DB_HOST', 'localhost')}:{app.config.get('DB_PORT', '3306')}")
        print(f"Data Source Directory: {DATA_DIR}")
        print("=" * 60)

        # 1. Temporarily disable foreign keys and truncate tables
        print("\n1. Truncating existing tables...")
        db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        
        tables_to_truncate = [
            "alternative_recommendations",
            "passenger_transfers",
            "replacement_buses",
            "depot_requests",
            "incidents",
            "live_gps",
            "passenger_counts",
            "historical_delays",
            "trips",
            "bus_capacity",
            "buses",
            "drivers",
            "route_connectivity",
            "route_stops",
            "routes",
            "stops",
            "notifications",
            "audit_logs",
            "users"
        ]
        for t in tables_to_truncate:
            db.session.execute(text(f"TRUNCATE TABLE {t};"))
        db.session.commit()
        print("   All tables truncated cleanly.")

        # Single pre-computed bcrypt hash for lightning-fast account generation
        print("\n2. Generating master password hash for 'Password123!'...")
        pwd_hash = generate_password_hash("Password123!")

        # 3. Create Core Demo Users
        print("\n3. Creating baseline demo users...")
        baseline_users = [
            User(id=1, username="passenger", email="passenger@busnotify.com", role="passenger", password_hash=pwd_hash),
            User(id=2, username="driver", email="driver@busnotify.com", role="driver", password_hash=pwd_hash),
            User(id=3, username="depot", email="depot@busnotify.com", role="depot_operator", password_hash=pwd_hash),
            User(id=4, username="admin", email="admin@busnotify.com", role="admin", password_hash=pwd_hash),
            User(id=5, username="snehal", email="snehal@gmail.com", role="passenger", password_hash=pwd_hash),
        ]
        db.session.add_all(baseline_users)
        db.session.commit()
        print(f"   Created {len(baseline_users)} core demo accounts.")

        # 4. Import Stops
        print("\n4. Importing stops from stops.csv...")
        stops_file = DATA_DIR / "stops.csv"
        stop_code_to_id = {}
        stops_to_add = []
        
        with open(stops_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                scode = clean_str(row["stop_id"])
                sname = clean_str(row["stop_name"])
                lat = float(row["latitude"])
                lon = float(row["longitude"])
                stop_obj = Stop(
                    stop_code=scode,
                    name=sname,
                    latitude=lat,
                    longitude=lon
                )
                stops_to_add.append(stop_obj)

        # Add Bangalore Station if not present
        if not any(s.stop_code == "BANGALORE_STATION" for s in stops_to_add):
            stops_to_add.append(Stop(
                stop_code="BANGALORE_STATION",
                name="Bangalore Station",
                latitude=12.9716,
                longitude=77.5946
            ))

        # Add STP-MAG alias / fallback if needed
        if not any(s.stop_code == "STP-MAG" for s in stops_to_add):
            stops_to_add.append(Stop(
                stop_code="STP-MAG",
                name="Magarpatta",
                latitude=18.5204,
                longitude=73.8567
            ))

        db.session.add_all(stops_to_add)
        db.session.commit()

        # Build lookup
        all_stops = Stop.query.all()
        for s in all_stops:
            stop_code_to_id[s.stop_code] = s.id
        print(f"   Imported {len(all_stops)} stops.")

        # 5. Import Routes
        print("\n5. Importing routes from routes.csv...")
        routes_file = DATA_DIR / "routes.csv"
        route_num_to_id = {}
        routes_to_add = []
        added_route_codes = set()

        with open(routes_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                r_id = clean_str(row["route_id"])
                r_short = clean_str(row["route_short_name"])
                r_name = clean_str(row["route_name"])
                dist = float(row["distance_km"]) if row.get("distance_km") else 10.0
                dur = int(row["scheduled_duration_min"]) if row.get("scheduled_duration_min") else 45

                if " to " in r_name:
                    parts = r_name.split(" to ")
                    src = parts[0].strip()
                    dst = parts[1].strip()
                else:
                    words = r_name.split()
                    src = words[0] if words else "Source"
                    dst = words[-1] if len(words) > 1 else "Destination"

                display_name = f"{r_short} - {r_name}" if r_short else r_name
                route_obj = Route(
                    route_number=r_id,
                    name=display_name[:128],
                    source=src[:128],
                    destination=dst[:128],
                    total_distance_km=dist,
                    estimated_duration_min=dur,
                    is_active=True
                )
                routes_to_add.append(route_obj)
                added_route_codes.add(r_id)

        # Scan for any missing routes from buses.csv, incidents.csv, live_gps.csv
        missing_routes_needed = set()
        for fn in ["buses.csv", "replacement_buses.csv", "incidents.csv", "live_gps.csv"]:
            p = DATA_DIR / fn
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        rid = clean_str(row.get("route_id"))
                        if rid and rid not in added_route_codes and rid not in missing_routes_needed:
                            missing_routes_needed.add(rid)

        for rid in missing_routes_needed:
            name_parts = rid.replace("_", " ").title()
            if " To " in name_parts:
                src, dst = name_parts.split(" To ")
            else:
                parts = name_parts.split()
                src = parts[0] if parts else "Origin"
                dst = parts[-1] if len(parts) > 1 else "Destination"
            routes_to_add.append(Route(
                route_number=rid,
                name=f"{name_parts} Express",
                source=src[:128],
                destination=dst[:128],
                total_distance_km=150.0,
                estimated_duration_min=180,
                is_active=True
            ))
            added_route_codes.add(rid)

        # Ensure Route 101 exists for legacy acceptance scenario
        if "101" not in added_route_codes:
            routes_to_add.append(Route(
                route_number="101",
                name="101 - Pune Station to Hadapsar",
                source="Pune Station",
                destination="Hadapsar",
                total_distance_km=12.5,
                estimated_duration_min=45,
                is_active=True
            ))
            added_route_codes.add("101")

        db.session.add_all(routes_to_add)
        db.session.commit()

        all_routes = Route.query.all()
        for r in all_routes:
            route_num_to_id[r.route_number] = r.id
        print(f"   Imported {len(all_routes)} routes (including {len(missing_routes_needed)} inter-city routes).")

        # 6. Import Route Stops
        print("\n6. Importing route_stops from route_stops.csv...")
        route_stops_file = DATA_DIR / "route_stops.csv"
        route_stops_to_add = []
        with open(route_stops_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rid = clean_str(row["route_id"])
                sid = clean_str(row["stop_id"])
                seq = int(row["stop_sequence"])
                if rid in route_num_to_id and sid in stop_code_to_id:
                    route_stops_to_add.append(RouteStop(
                        route_id=route_num_to_id[rid],
                        stop_id=stop_code_to_id[sid],
                        sequence_order=seq
                    ))

        # Add Route 101 stops for compatibility
        if "101" in route_num_to_id and "MAGARPATTA" in stop_code_to_id and "PUNE_STATION" in stop_code_to_id:
            route_stops_to_add.append(RouteStop(route_id=route_num_to_id["101"], stop_id=stop_code_to_id["PUNE_STATION"], sequence_order=1))
            route_stops_to_add.append(RouteStop(route_id=route_num_to_id["101"], stop_id=stop_code_to_id["MAGARPATTA"], sequence_order=2))

        # Batch insert route stops
        for i in range(0, len(route_stops_to_add), 1000):
            db.session.add_all(route_stops_to_add[i:i + 1000])
            db.session.flush()
        db.session.commit()
        print(f"   Imported {len(route_stops_to_add)} route_stop entries.")

        # 7. Import Depot Operators -> Users
        print("\n7. Importing depot operators from depot_operators.csv...")
        depot_file = DATA_DIR / "depot_operators.csv"
        depot_users_to_add = []
        with open(depot_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                op_id = clean_str(row["operator_id"])
                op_name = clean_str(row["operator_name"])
                email = clean_str(row["email"]).lower()
                username = f"depot_op_{op_id}"
                depot_users_to_add.append(User(
                    username=username,
                    email=email,
                    role="depot_operator",
                    password_hash=pwd_hash,
                    is_active=True
                ))
        for i in range(0, len(depot_users_to_add), 500):
            db.session.add_all(depot_users_to_add[i:i + 500])
            db.session.flush()
        db.session.commit()
        print(f"   Imported {len(depot_users_to_add)} depot operator user accounts.")

        # 8. Import Drivers -> Users & Driver records
        print("\n8. Importing drivers from drivers.csv...")
        drivers_file = DATA_DIR / "drivers.csv"
        driver_users_to_add = []
        raw_drivers = []
        with open(drivers_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_drivers.append(row)

        # Batch insert driver users
        start_user_id = 1000
        for idx, row in enumerate(raw_drivers):
            d_id = clean_str(row["driver_id"])
            d_phone = clean_str(row["phone"])
            driver_users_to_add.append(User(
                id=start_user_id + idx,
                username=f"drv_{d_id}",
                email=f"driver_{d_id}@busnotify.com",
                mobile=d_phone,
                role="driver",
                password_hash=pwd_hash,
                is_active=True
            ))

        for i in range(0, len(driver_users_to_add), 1000):
            db.session.add_all(driver_users_to_add[i:i + 1000])
            db.session.flush()
        db.session.commit()
        print(f"   Imported {len(driver_users_to_add)} driver user accounts.")

        # Now insert Driver records
        drivers_to_add = []
        for idx, row in enumerate(raw_drivers):
            d_id = clean_str(row["driver_id"])
            d_name = clean_str(row["driver_name"])
            d_phone = clean_str(row["phone"])
            d_lic = clean_str(row["license_number"])
            raw_st = clean_str(row.get("status", "AVAILABLE")).upper()
            if raw_st in ("ACTIVE", "AVAILABLE"):
                d_status = "AVAILABLE"
            elif raw_st in ("INACTIVE", "OFF_DUTY"):
                d_status = "OFF_DUTY"
            elif raw_st in ("ON_LEAVE", "LEAVE"):
                d_status = "LEAVE"
            else:
                d_status = raw_st
            user_id = start_user_id + idx
            
            drivers_to_add.append(Driver(
                user_id=user_id,
                driver_code=f"DRV-{int(d_id):04d}",
                full_name=d_name,
                mobile_number=d_phone,
                license_number=d_lic,
                status=d_status
            ))

        # Core scenario: Rajesh Patil (D104) linked to driver@busnotify.com (user_id=2)
        d104 = Driver(
            user_id=2,
            driver_code="D104",
            full_name="Rajesh Patil",
            mobile_number="9876543210",
            license_number="MH12-12345",
            status="AVAILABLE"
        )
        drivers_to_add.append(d104)

        for i in range(0, len(drivers_to_add), 1000):
            db.session.add_all(drivers_to_add[i:i + 1000])
            db.session.flush()
        db.session.commit()
        print(f"   Imported {len(drivers_to_add)} driver profiles.")

        # 9. Import Buses, Replacement Buses & Capacities
        print("\n9. Importing buses and replacement fleet...")
        buses_dict = {}  # bus_number -> dict of properties
        
        # buses.csv
        buses_file = DATA_DIR / "buses.csv"
        with open(buses_file, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                bnum = clean_str(row["bus_number"])
                rid = clean_str(row["route_id"])
                cap = int(row["capacity"]) if row.get("capacity") else 40
                status = clean_str(row.get("status", "ACTIVE"))
                buses_dict[bnum] = {
                    "bus_number": bnum,
                    "route_id": rid,
                    "capacity": cap,
                    "status": "RUNNING" if status == "ACTIVE" else status,
                    "depot_name": "Pune Central Depot"
                }

        # replacement_buses.csv
        rep_file = DATA_DIR / "replacement_buses.csv"
        with open(rep_file, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                bnum = clean_str(row["bus_number"])
                rid = clean_str(row["route_id"])
                cap = int(row["capacity"]) if row.get("capacity") else 40
                status = clean_str(row.get("status", "AVAILABLE"))
                depot = clean_str(row.get("depot_name", "Pune Depot"))
                if bnum not in buses_dict:
                    buses_dict[bnum] = {
                        "bus_number": bnum,
                        "route_id": rid,
                        "capacity": cap,
                        "status": status,
                        "depot_name": depot
                    }

        # Ensure compatibility demo buses exist: 123, 156, 178, 189
        for bnum, (status, rid) in {
            "123": ("RUNNING", "PUNE_MUM"),
            "156": ("RUNNING", "PUNE_MUM"),
            "178": ("DELAYED", "PUNE_MUM"),
            "189": ("AVAILABLE", "PUNE_MUM")
        }.items():
            if bnum not in buses_dict:
                buses_dict[bnum] = {
                    "bus_number": bnum,
                    "route_id": rid,
                    "capacity": 40,
                    "status": status,
                    "depot_name": "Pune Central Depot"
                }

        bus_num_to_id = {}
        buses_to_add = []
        for idx, (bnum, bdata) in enumerate(buses_dict.items()):
            route_id_fk = route_num_to_id.get(bdata["route_id"])
            reg_no = f"MH-12-{idx + 1000:04d}"
            b_obj = Bus(
                bus_number=bnum,
                registration_number=reg_no,
                depot_name=bdata["depot_name"],
                capacity=bdata["capacity"],
                current_status=bdata["status"],
                assigned_route_id=route_id_fk,
                is_active=True
            )
            buses_to_add.append(b_obj)

        for i in range(0, len(buses_to_add), 1000):
            db.session.add_all(buses_to_add[i:i + 1000])
            db.session.flush()
        db.session.commit()

        all_buses = Bus.query.all()
        for b in all_buses:
            bus_num_to_id[b.bus_number] = b.id
        print(f"   Imported {len(all_buses)} buses.")

        # Assign Bus 123 and SHIVNERI_101 to driver D104
        if "SHIVNERI_101" in bus_num_to_id:
            d104.assigned_bus_id = bus_num_to_id["SHIVNERI_101"]
            db.session.commit()

        # Import Bus Capacities
        print("   Populating bus_capacity details...")
        capacities_to_add = []
        for b in all_buses:
            capacities_to_add.append(BusCapacity(
                bus_id=b.id,
                total_capacity=b.capacity,
                seated_capacity=int(b.capacity * 0.8),
                standing_capacity=int(b.capacity * 0.2)
            ))
        for i in range(0, len(capacities_to_add), 1000):
            db.session.add_all(capacities_to_add[i:i + 1000])
            db.session.flush()
        db.session.commit()
        print(f"   Populated {len(capacities_to_add)} bus capacity records.")

        # 10. Import Route Connectivity
        print("\n10. Importing route_connectivity from route_connectivity.csv...")
        conn_file = DATA_DIR / "route_connectivity.csv"
        conn_to_add = []
        with open(conn_file, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                r1 = clean_str(row["route_id_1"])
                r2 = clean_str(row["route_id_2"])
                sid = clean_str(row["common_stop_id"])
                if r1 in route_num_to_id and r2 in route_num_to_id and sid in stop_code_to_id:
                    conn_to_add.append({
                        "from_route_id": route_num_to_id[r1],
                        "to_route_id": route_num_to_id[r2],
                        "transfer_stop_id": stop_code_to_id[sid],
                        "is_connected": 1
                    })

        # Bulk insert route connectivity using raw batch execute for maximum speed
        print(f"   Executing bulk insert of {len(conn_to_add)} connectivity links...")
        insert_sql = text("""
            INSERT INTO route_connectivity (from_route_id, to_route_id, transfer_stop_id, is_connected)
            VALUES (:from_route_id, :to_route_id, :transfer_stop_id, :is_connected)
        """)
        batch_size = 5000
        for i in range(0, len(conn_to_add), batch_size):
            db.session.execute(insert_sql, conn_to_add[i:i + batch_size])
        db.session.commit()
        print("   Route connectivity imported successfully.")

        # 11. Import Live GPS and Create Active Trips
        print("\n11. Importing live_gps.csv & creating live trips...")
        live_file = DATA_DIR / "live_gps.csv"
        trips_to_add = []
        gps_records_to_add = []
        trip_code_to_id = {}

        now = datetime.utcnow()
        with open(live_file, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                bnum = clean_str(row["bus_number"])
                rid = clean_str(row["route_id"])
                sid = clean_str(row["current_stop_id"])
                lat = float(row["latitude"])
                lon = float(row["longitude"])
                speed = float(row.get("speed_kmph", 35.0))
                status = clean_str(row.get("status", "RUNNING"))
                cap = int(row.get("capacity", 40))
                avail = int(row.get("available_seats", 20))
                pax = max(0, cap - avail)
                updated = parse_dt(row.get("last_updated"))

                if bnum in bus_num_to_id and rid in route_num_to_id:
                    bus_id = bus_num_to_id[bnum]
                    route_id = route_num_to_id[rid]
                    stop_id = stop_code_to_id.get(sid)
                    trip_code = f"TRIP_LIVE_{bnum}"
                    
                    drv_fk = d104.id if bnum in ("SHIVNERI_101", "123") else None
                    trip = Trip(
                        trip_code=trip_code,
                        bus_id=bus_id,
                        driver_id=drv_fk,
                        route_id=route_id,
                        current_stop_id=stop_id,
                        status="RUNNING" if status == "ON_TIME" else status,
                        passenger_count=pax,
                        scheduled_start_time=now - timedelta(hours=1),
                        actual_start_time=now - timedelta(minutes=55)
                    )
                    trips_to_add.append((trip, lat, lon, speed, updated))

        # Add acceptance scenario trips if not present
        for bnum, tcode, status, pax in [
            ("123", "TRIP-123-DEMO", "PUNCTURED", 40),
            ("156", "TRIP-156-DEMO", "RUNNING", 25),
            ("178", "TRIP-178-DEMO", "DELAYED", 10),
        ]:
            if bnum in bus_num_to_id and "101" in route_num_to_id:
                mag_id = stop_code_to_id.get("MAGARPATTA") or stop_code_to_id.get("STP-MAG")
                drv_fk = d104.id if bnum in ("123", "SHIVNERI_101") else None
                trip = Trip(
                    trip_code=tcode,
                    bus_id=bus_num_to_id[bnum],
                    driver_id=drv_fk,
                    route_id=route_num_to_id["101"],
                    current_stop_id=mag_id,
                    status=status,
                    passenger_count=pax,
                    scheduled_start_time=now - timedelta(hours=1),
                    actual_start_time=now - timedelta(minutes=50)
                )
                trips_to_add.append((trip, 18.5204, 73.8567, 0.0 if status == "PUNCTURED" else 30.0, now))

        # Insert Trips first
        for i in range(0, len(trips_to_add), 1000):
            batch = [t[0] for t in trips_to_add[i:i + 1000]]
            db.session.add_all(batch)
            db.session.flush()
        db.session.commit()

        # Retrieve trip IDs and insert LiveGPS records
        for trip_obj, lat, lon, speed, updated in trips_to_add:
            trip_code_to_id[trip_obj.trip_code] = trip_obj.id
            gps_records_to_add.append({
                "trip_id": trip_obj.id,
                "bus_id": trip_obj.bus_id,
                "latitude": lat,
                "longitude": lon,
                "speed_kmh": speed,
                "source": "GPS",
                "timestamp": updated
            })

        print(f"   Inserted {len(trips_to_add)} live trips. Now inserting live GPS snapshots...")
        gps_sql = text("""
            INSERT INTO live_gps (trip_id, bus_id, latitude, longitude, speed_kmh, source, timestamp)
            VALUES (:trip_id, :bus_id, :latitude, :longitude, :speed_kmh, :source, :timestamp)
        """)
        for i in range(0, len(gps_records_to_add), batch_size):
            db.session.execute(gps_sql, gps_records_to_add[i:i + batch_size])
        db.session.commit()
        print("   Live GPS tracking snapshots imported.")

        # 12. Import Incidents & Depot Requests
        print("\n12. Importing incidents from incidents.csv...")
        incidents_file = DATA_DIR / "incidents.csv"
        incident_id_to_db_id = {}
        incidents_to_add = []
        extra_trips_to_add = []

        with open(incidents_file, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                inc_num = clean_str(row["incident_id"])
                t_code = clean_str(row["trip_id"])
                bnum = clean_str(row["bus_number"])
                rid = clean_str(row["route_id"])
                sid = clean_str(row["location_stop_id"])
                itype = clean_str(row["incident_type"])
                priority = clean_str(row.get("priority", "HIGH"))
                pax = int(row.get("affected_passengers", 0))
                status = clean_str(row.get("status", "OPEN"))
                rep_time = parse_dt(row.get("reported_at"))

                bus_id = bus_num_to_id.get(bnum)
                route_id = route_num_to_id.get(rid)
                stop_id = stop_code_to_id.get(sid)

                if bus_id and route_id:
                    # Check if trip already exists
                    if t_code not in trip_code_to_id:
                        trip = Trip(
                            trip_code=t_code,
                            bus_id=bus_id,
                            route_id=route_id,
                            current_stop_id=stop_id,
                            status="PUNCTURED" if "PUNCTURE" in itype else "BREAKDOWN",
                            passenger_count=pax,
                            scheduled_start_time=rep_time - timedelta(minutes=30),
                            actual_start_time=rep_time - timedelta(minutes=25)
                        )
                        extra_trips_to_add.append((t_code, trip))

        # Insert extra trips needed for incidents
        for i in range(0, len(extra_trips_to_add), 1000):
            batch = [item[1] for item in extra_trips_to_add[i:i + 1000]]
            db.session.add_all(batch)
            db.session.flush()
        db.session.commit()

        for t_code, trip_obj in extra_trips_to_add:
            trip_code_to_id[t_code] = trip_obj.id

        # Now insert Incident objects
        with open(incidents_file, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                inc_num = clean_str(row["incident_id"])
                t_code = clean_str(row["trip_id"])
                bnum = clean_str(row["bus_number"])
                rid = clean_str(row["route_id"])
                sid = clean_str(row["location_stop_id"])
                itype = clean_str(row["incident_type"])
                priority = clean_str(row.get("priority", "HIGH"))
                pax = int(row.get("affected_passengers", 0))
                status = clean_str(row.get("status", "OPEN"))
                rep_time = parse_dt(row.get("reported_at"))

                bus_id = bus_num_to_id.get(bnum)
                route_id = route_num_to_id.get(rid)
                stop_id = stop_code_to_id.get(sid)
                trip_id = trip_code_to_id.get(t_code)

                if bus_id and route_id and trip_id:
                    incidents_to_add.append(Incident(
                        incident_number=inc_num,
                        trip_id=trip_id,
                        bus_id=bus_id,
                        route_id=route_id,
                        stop_id=stop_id,
                        incident_type=itype,
                        priority=priority,
                        affected_passengers=pax,
                        description=f"Incident {itype} reported for Bus {bnum}",
                        status=status,
                        reported_at=rep_time
                    ))

        for i in range(0, len(incidents_to_add), 1000):
            db.session.add_all(incidents_to_add[i:i + 1000])
            db.session.flush()
        db.session.commit()

        all_incidents = Incident.query.all()
        for inc in all_incidents:
            incident_id_to_db_id[inc.incident_number] = inc.id
        print(f"   Imported {len(all_incidents)} incidents.")

        # Import Depot Requests
        print("\n13. Importing depot requests from depot_requests.csv...")
        req_file = DATA_DIR / "depot_requests.csv"
        requests_to_add = []
        with open(req_file, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                req_code = clean_str(row["request_id"])
                inc_num = clean_str(row["incident_id"])
                f_bnum = clean_str(row["failed_bus_number"])
                rid = clean_str(row["route_id"])
                sid = clean_str(row["location_stop_id"])
                prob = clean_str(row.get("problem", "BREAKDOWN"))
                aff_pax = int(row.get("affected_passengers", 0))
                tr_pax = int(row.get("transferred_passengers", 0))
                priority = clean_str(row.get("priority", "HIGH"))
                status = clean_str(row.get("status", "PENDING"))
                rep_bnum = clean_str(row.get("assigned_replacement_bus", ""))
                created = parse_dt(row.get("created_at"))

                inc_fk = incident_id_to_db_id.get(inc_num)
                f_bus_fk = bus_num_to_id.get(f_bnum)
                route_fk = route_num_to_id.get(rid)
                stop_fk = stop_code_to_id.get(sid)
                rep_bus_fk = bus_num_to_id.get(rep_bnum) if rep_bnum else None

                if inc_fk and f_bus_fk and route_fk:
                    requests_to_add.append(DepotRequest(
                        request_code=req_code,
                        incident_id=inc_fk,
                        failed_bus_id=f_bus_fk,
                        route_id=route_fk,
                        stop_id=stop_fk,
                        replacement_bus_id=rep_bus_fk,
                        status=status,
                        affected_passengers=aff_pax,
                        transferred_passengers=tr_pax,
                        priority=priority,
                        created_at=created
                    ))

        for i in range(0, len(requests_to_add), 1000):
            db.session.add_all(requests_to_add[i:i + 1000])
            db.session.flush()
        db.session.commit()
        print(f"   Imported {len(requests_to_add)} depot replacement requests.")

        # 14. Import Historical Delays (61,616 records)
        print("\n14. Importing 61,616 historical delay records...")
        hist_file = DATA_DIR / "historical_delays.csv"
        delays_data = []

        with open(hist_file, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rid = clean_str(row["route_id"])
                to_sid = clean_str(row["to_stop_id"])
                
                route_fk = route_num_to_id.get(rid)
                stop_fk = stop_code_to_id.get(to_sid)

                if route_fk and stop_fk:
                    s_date = parse_date(row.get("trip_date"))
                    wday = int(row.get("day_of_week", s_date.weekday()))
                    sched_arr = clean_str(row.get("scheduled_arrival", "09:00:00"))
                    hour = int(sched_arr.split(":")[0]) if ":" in sched_arr else 9
                    d_min = float(row.get("delay_minutes", 0.0))
                    reason = clean_str(row.get("delay_reason", "TRAFFIC"))

                    delays_data.append({
                        "route_id": route_fk,
                        "stop_id": stop_fk,
                        "weekday": wday,
                        "hour_of_day": hour,
                        "delay_minutes": d_min,
                        "delay_reason": reason,
                        "recorded_date": s_date,
                        "created_at": now
                    })

        print(f"   Inserting {len(delays_data)} delay rows via high-speed raw SQL chunks...")
        hist_sql = text("""
            INSERT INTO historical_delays (route_id, stop_id, weekday, hour_of_day, delay_minutes, delay_reason, recorded_date, created_at)
            VALUES (:route_id, :stop_id, :weekday, :hour_of_day, :delay_minutes, :delay_reason, :recorded_date, :created_at)
        """)
        for i in range(0, len(delays_data), batch_size):
            db.session.execute(hist_sql, delays_data[i:i + batch_size])
        db.session.commit()
        print("   Historical delay dataset imported successfully.")

        # 15. Re-enable foreign key checks
        print("\n15. Re-enabling foreign key checks and logging audit record...")
        db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        db.session.add(AuditLog(
            action="DATASET_IMPORTED",
            entity_type="system",
            details=f"Imported complete dataset: {len(all_stops)} stops, {len(all_routes)} routes, {len(all_buses)} buses, {len(delays_data)} historical delays."
        ))
        db.session.commit()

        print("\n" + "=" * 60)
        print("DATASET IMPORT COMPLETE!")
        print("=" * 60)
        print("Summary of Database Counts:")
        print(f"  Stops:               {Stop.query.count():,}")
        print(f"  Routes:              {Route.query.count():,}")
        print(f"  Route Stops:         {RouteStop.query.count():,}")
        print(f"  Users:               {User.query.count():,}")
        print(f"  Drivers:             {Driver.query.count():,}")
        print(f"  Buses:               {Bus.query.count():,}")
        print(f"  Route Connectivity:  {RouteConnectivity.query.count():,}")
        print(f"  Trips:               {Trip.query.count():,}")
        print(f"  Live GPS Snapshots:  {LiveGPS.query.count():,}")
        print(f"  Incidents:           {Incident.query.count():,}")
        print(f"  Depot Requests:      {DepotRequest.query.count():,}")
        print(f"  Historical Delays:   {HistoricalDelay.query.count():,}")
        print("=" * 60)


if __name__ == "__main__":
    run_import()
