"""
BusNotify - Synthetic Seed Data Generator
Generates realistic Pune transit network data for testing and demonstrations:
- 10 Routes
- 30 Stops with genuine Pune coordinates
- 50 Buses (including Bus 123, 156, 178, 189)
- 20 Drivers (including Rajesh Patil D104)
- 4 Preset Users (Passenger, Driver, Depot Operator, Admin)
- 90 Days of Historical Delay Observations
- Pre-configured main acceptance scenario (Bus 123, Magarpatta, Tyre Puncture)
- Synthetic demonstration data notice
"""
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import random
from datetime import datetime, timedelta, date
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.transit import Route, Stop, RouteStop, RouteConnectivity
from app.models.bus import Bus, BusCapacity, Driver
from app.models.trip import Trip, LiveGPS, PassengerCount
from app.models.delay import HistoricalDelay
from app.models.incident import Incident, AlternativeRecommendation
from app.models.depot import DepotRequest, ReplacementBus, PassengerTransfer
from app.models.notification import Notification
from app.models.audit import AuditLog

app = create_app()

# Pune Transit Stop Coordinates
STOPS_DATA = [
    {"code": "STP-PUN", "name": "Pune Station", "name_mr": "पुणे स्टेशन", "lat": 18.5284, "lon": 73.8744, "landmark": "Railway Station Main Gate"},
    {"code": "STP-RUB", "name": "Ruby Hall", "name_mr": "रुबी हॉल", "lat": 18.5325, "lon": 73.8812, "landmark": "Ruby Hall Clinic"},
    {"code": "STP-BND", "name": "Bund Garden", "name_mr": "बंड गार्डन", "lat": 18.5368, "lon": 73.8865, "landmark": "Yerawada Bridge"},
    {"code": "STP-YER", "name": "Yerwada", "name_mr": "येरवडा", "lat": 18.5529, "lon": 73.8891, "landmark": "Gunjan Chowk"},
    {"code": "STP-KOR", "name": "Koregaon Park", "name_mr": "कोरेगाव पार्क", "lat": 18.5362, "lon": 73.8940, "landmark": "North Main Road"},
    {"code": "STP-KAL", "name": "Kalyani Nagar", "name_mr": "कल्याणी नगर", "lat": 18.5463, "lon": 73.9034, "landmark": "Bishop's School"},
    {"code": "STP-VIM", "name": "Viman Nagar", "name_mr": "विमान नगर", "lat": 18.5679, "lon": 73.9143, "landmark": "Phoenix Marketcity"},
    {"code": "STP-MAG", "name": "Magarpatta", "name_mr": "मगरपट्टा", "lat": 18.5134, "lon": 73.9242, "landmark": "Cybercity Main Gate"},
    {"code": "STP-HAD", "name": "Hadapsar", "name_mr": "हडपसर", "lat": 18.5089, "lon": 73.9260, "landmark": "Gadital Bus Stand"},
    {"code": "STP-SWA", "name": "Swargate", "name_mr": "स्वारगेट", "lat": 18.5018, "lon": 73.8586, "landmark": "Swargate ST Stand"},
    {"code": "STP-KAT", "name": "Katraj", "name_mr": "कात्रज", "lat": 18.4575, "lon": 73.8677, "landmark": "Katraj Snake Park"},
    {"code": "STP-KOT", "name": "Kothrud", "name_mr": "कोथरूड", "lat": 18.5074, "lon": 73.8077, "landmark": "Karve Statue"},
    {"code": "STP-DEC", "name": "Deccan Gymkhana", "name_mr": "डेक्कन जिमखाना", "lat": 18.5173, "lon": 73.8415, "landmark": "Goodluck Chowk"},
    {"code": "STP-SHI", "name": "Shivajinagar", "name_mr": "शिवाजीनगर", "lat": 18.5314, "lon": 73.8446, "landmark": "Shimla Office"},
    {"code": "STP-AUN", "name": "Aundh", "name_mr": "औंध", "lat": 18.5580, "lon": 73.8074, "landmark": "Bremen Chowk"},
    {"code": "STP-BAN", "name": "Baner", "name_mr": "बाणेर", "lat": 18.5590, "lon": 73.7868, "landmark": "Baner Road High Street"},
    {"code": "STP-HIN", "name": "Hinjewadi Phase 1", "name_mr": "हिंजवडी फेज १", "lat": 18.5913, "lon": 73.7389, "landmark": "Infosys Circle"},
    {"code": "STP-WAK", "name": "Wakad", "name_mr": "वाकड", "lat": 18.5987, "lon": 73.7631, "landmark": "Dange Chowk"},
    {"code": "STP-PIM", "name": "Pimpri", "name_mr": "पिंपरी", "lat": 18.6279, "lon": 73.8009, "landmark": "Dr. D.Y. Patil Hospital"},
    {"code": "STP-CHI", "name": "Chinchwad", "name_mr": "चिंचवड", "lat": 18.6364, "lon": 73.7915, "landmark": "Chinchwad Station"},
    {"code": "STP-BHO", "name": "Bhosari", "name_mr": "भोसरी", "lat": 18.6256, "lon": 73.8465, "landmark": "Landewadi Chowk"},
    {"code": "STP-NIG", "name": "Nigdi", "name_mr": "निगडी", "lat": 18.6534, "lon": 73.7707, "landmark": "Bhakti Shakti"},
    {"code": "STP-FAT", "name": "Fatima Nagar", "name_mr": "फातिमा नगर", "lat": 18.5029, "lon": 73.8967, "landmark": "Inox Junction"},
    {"code": "STP-WAD", "name": "Wadgaon Sheri", "name_mr": "वडगाव शेरी", "lat": 18.5501, "lon": 73.9168, "landmark": "Somnath Nagar"},
    {"code": "STP-KHA", "name": "Kharadi", "name_mr": "खराडी", "lat": 18.5514, "lon": 73.9421, "landmark": "EON IT Park"},
    {"code": "STP-MUN", "name": "Mundhwa", "name_mr": "मुंढवा", "lat": 18.5312, "lon": 73.9214, "landmark": "Mundhwa Chowk"},
    {"code": "STP-WAR", "name": "Warje", "name_mr": "वारजे", "lat": 18.4812, "lon": 73.8012, "landmark": "Mai Mangeshkar Hospital"},
    {"code": "STP-SIN", "name": "Sinhagad Road", "name_mr": "सिंहगड रोड", "lat": 18.4891, "lon": 73.8291, "landmark": "Pu La Deshpande Garden"},
    {"code": "STP-BIB", "name": "Bibvewadi", "name_mr": "बिबवेवाडी", "lat": 18.4734, "lon": 73.8612, "landmark": "Chintamani Nagar"},
    {"code": "STP-DHN", "name": "Dhankawadi", "name_mr": "धनकवडी", "lat": 18.4623, "lon": 73.8534, "landmark": "KK Market"},
]

ROUTES_DATA = [
    {
        "number": "101",
        "name": "Pune Station to Hadapsar",
        "name_mr": "पुणे स्टेशन ते हडपसर",
        "source": "Pune Station",
        "destination": "Hadapsar",
        "distance": 12.5,
        "duration": 45,
        "stop_codes": ["STP-PUN", "STP-RUB", "STP-BND", "STP-KOR", "STP-MAG", "STP-HAD"]
    },
    {
        "number": "102",
        "name": "Swargate to Katraj",
        "name_mr": "स्वारगेट ते कात्रज",
        "source": "Swargate",
        "destination": "Katraj",
        "distance": 8.0,
        "duration": 30,
        "stop_codes": ["STP-SWA", "STP-BIB", "STP-DHN", "STP-KAT"]
    },
    {
        "number": "103",
        "name": "Kothrud to Viman Nagar",
        "name_mr": "कोथरूड ते विमान नगर",
        "source": "Kothrud",
        "destination": "Viman Nagar",
        "distance": 16.0,
        "duration": 55,
        "stop_codes": ["STP-KOT", "STP-DEC", "STP-SHI", "STP-YER", "STP-KAL", "STP-VIM"]
    },
    {
        "number": "104",
        "name": "Hinjewadi to Pune Station",
        "name_mr": "हिंजवडी ते पुणे स्टेशन",
        "source": "Hinjewadi Phase 1",
        "destination": "Pune Station",
        "distance": 21.0,
        "duration": 65,
        "stop_codes": ["STP-HIN", "STP-WAK", "STP-BAN", "STP-AUN", "STP-SHI", "STP-PUN"]
    },
    {
        "number": "105",
        "name": "Deccan to Pimpri",
        "name_mr": "डेक्कन ते पिंपरी",
        "source": "Deccan Gymkhana",
        "destination": "Pimpri",
        "distance": 18.0,
        "duration": 50,
        "stop_codes": ["STP-DEC", "STP-SHI", "STP-AUN", "STP-CHI", "STP-PIM"]
    },
    {
        "number": "106",
        "name": "Swargate to Hadapsar",
        "name_mr": "स्वारगेट ते हडपसर",
        "source": "Swargate",
        "destination": "Hadapsar",
        "distance": 10.5,
        "duration": 40,
        "stop_codes": ["STP-SWA", "STP-FAT", "STP-MAG", "STP-HAD"]
    },
    {
        "number": "107",
        "name": "Hadapsar to Kharadi",
        "name_mr": "हडपसर ते खराडी",
        "source": "Hadapsar",
        "destination": "Kharadi",
        "distance": 9.0,
        "duration": 35,
        "stop_codes": ["STP-HAD", "STP-MAG", "STP-MUN", "STP-KHA"]
    },
    {
        "number": "108",
        "name": "Katraj to Shivajinagar",
        "name_mr": "कात्रज ते शिवाजीनगर",
        "source": "Katraj",
        "destination": "Shivajinagar",
        "distance": 12.0,
        "duration": 45,
        "stop_codes": ["STP-KAT", "STP-DHN", "STP-SWA", "STP-DEC", "STP-SHI"]
    },
    {
        "number": "109",
        "name": "Bhosari to Swargate",
        "name_mr": "भोसरी ते स्वारगेट",
        "source": "Bhosari",
        "destination": "Swargate",
        "distance": 15.0,
        "duration": 50,
        "stop_codes": ["STP-BHO", "STP-YER", "STP-BND", "STP-PUN", "STP-SWA"]
    },
    {
        "number": "110",
        "name": "Warje to Viman Nagar",
        "name_mr": "वारजे ते विमान नगर",
        "source": "Warje",
        "destination": "Viman Nagar",
        "distance": 19.0,
        "duration": 60,
        "stop_codes": ["STP-WAR", "STP-SIN", "STP-DEC", "STP-BND", "STP-KAL", "STP-VIM"]
    },
]


def seed_database():
    with app.app_context():
        print("Initializing BusNotify database seeding...")
        db.create_all()

        # Check if already seeded
        if User.query.filter_by(username="passenger").first():
            print("Database already contains seed data. Refreshing scenario state...")
            return

        # 1. Create Core Users
        print("1. Creating role-based user accounts...")
        users_config = [
            {"username": "passenger", "email": "passenger@busnotify.com", "role": "passenger", "lang": "en"},
            {"username": "driver", "email": "driver@busnotify.com", "role": "driver", "lang": "en"},
            {"username": "depot", "email": "depot@busnotify.com", "role": "depot_operator", "lang": "en"},
            {"username": "admin", "email": "admin@busnotify.com", "role": "admin", "lang": "en"},
        ]
        created_users = {}
        for uc in users_config:
            u = User(
                username=uc["username"],
                email=uc["email"],
                role=uc["role"],
                preferred_language=uc["lang"]
            )
            u.set_password("Password123!")
            db.session.add(u)
            created_users[uc["role"]] = u
        db.session.commit()

        # 2. Create 30 Stops
        print("2. Creating 30 Pune Transit Stops...")
        stops_map = {}
        for s_data in STOPS_DATA:
            stop = Stop(
                stop_code=s_data["code"],
                name=s_data["name"],
                name_mr=s_data["name_mr"],
                latitude=s_data["lat"],
                longitude=s_data["lon"],
                landmark=s_data["landmark"]
            )
            db.session.add(stop)
            stops_map[s_data["code"]] = stop
        db.session.commit()

        # 3. Create 10 Routes and RouteStops
        print("3. Creating 10 Routes with sequence stops...")
        routes_map = {}
        for r_data in ROUTES_DATA:
            route = Route(
                route_number=r_data["number"],
                name=r_data["name"],
                name_mr=r_data["name_mr"],
                source=r_data["source"],
                destination=r_data["destination"],
                total_distance_km=r_data["distance"],
                estimated_duration_min=r_data["duration"]
            )
            db.session.add(route)
            db.session.flush()
            routes_map[r_data["number"]] = route

            for idx, scode in enumerate(r_data["stop_codes"]):
                stop_obj = stops_map[scode]
                rs = RouteStop(
                    route_id=route.id,
                    stop_id=stop_obj.id,
                    sequence_order=idx + 1,
                    distance_from_prev_km=round(r_data["distance"] / len(r_data["stop_codes"]), 1),
                    avg_travel_time_min=round(r_data["duration"] / len(r_data["stop_codes"]))
                )
                db.session.add(rs)
        db.session.commit()

        # 4. Route Connectivity (Section 44)
        print("4. Creating Route Connectivity links...")
        # Route 101 connects with Route 106 at Magarpatta (STP-MAG)
        rc1 = RouteConnectivity(
            from_route_id=routes_map["101"].id,
            to_route_id=routes_map["106"].id,
            transfer_stop_id=stops_map["STP-MAG"].id,
            is_connected=True
        )
        rc2 = RouteConnectivity(
            from_route_id=routes_map["101"].id,
            to_route_id=routes_map["107"].id,
            transfer_stop_id=stops_map["STP-MAG"].id,
            is_connected=True
        )
        db.session.add_all([rc1, rc2])
        db.session.commit()

        # 5. Create 50 Buses
        print("5. Creating 50 Buses...")
        buses_map = {}
        # Key demonstration buses
        special_buses = [
            {"number": "123", "reg": "MH-12-RN-1234", "cap": 40, "route": "101", "status": "RUNNING"},
            {"number": "156", "reg": "MH-12-RN-5678", "cap": 40, "route": "106", "status": "RUNNING"},
            {"number": "178", "reg": "MH-12-RN-9012", "cap": 40, "route": "107", "status": "DELAYED"},
            {"number": "189", "reg": "MH-12-RN-3456", "cap": 40, "route": "101", "status": "AVAILABLE"},
        ]

        for sb in special_buses:
            b = Bus(
                bus_number=sb["number"],
                registration_number=sb["reg"],
                capacity=sb["cap"],
                current_status=sb["status"],
                assigned_route_id=routes_map[sb["route"]].id if sb.get("route") else None,
                depot_name="Pune Central Depot"
            )
            db.session.add(b)
            db.session.flush()
            buses_map[sb["number"]] = b
            # Add capacity entry
            db.session.add(BusCapacity(bus_id=b.id, total_capacity=40, seated_capacity=32, standing_capacity=8))

        # Additional buses up to 50
        for i in range(5, 60):
            b_num = f"{100 + i}"
            if b_num in buses_map:
                continue
            if len(buses_map) >= 50:
                break
            assigned_r = random.choice(list(routes_map.values()))
            b = Bus(
                bus_number=b_num,
                registration_number=f"MH-12-RN-{2000 + i}",
                capacity=40,
                current_status=random.choice(["RUNNING", "RUNNING", "DELAYED", "AVAILABLE", "AVAILABLE"]),
                assigned_route_id=assigned_r.id,
                depot_name="Pune Central Depot"
            )
            db.session.add(b)
            db.session.flush()
            buses_map[b_num] = b
            db.session.add(BusCapacity(bus_id=b.id, total_capacity=40, seated_capacity=32, standing_capacity=8))
        db.session.commit()

        # 6. Create 20 Drivers
        print("6. Creating 20 Drivers...")
        # Main driver: Rajesh Patil (D104)
        rajesh_user = created_users["driver"]
        rajesh = Driver(
            user_id=rajesh_user.id,
            driver_code="D104",
            full_name="Rajesh Patil",
            mobile_number="+91 98765 43210",
            license_number="MH-12-2015-0044521",
            status="AVAILABLE",
            assigned_bus_id=buses_map["123"].id
        )
        db.session.add(rajesh)

        # Other 19 drivers
        driver_names = [
            "Suresh Jadhav", "Anil Shinde", "Santosh More", "Prakash Kadam", "Ganesh Gaikwad",
            "Vijay Pawar", "Ramesh Chavan", "Nitin Salunkhe", "Sachin Deshmukh", "Sunil Joshi",
            "Amol Jagtap", "Mahesh Thorat", "Kailas Bhise", "Deepak Mohite", "Prashant Kale",
            "Sandip Landge", "Vikram Mane", "Yogesh Sonawane", "Tushar Ghorpade"
        ]
        for idx, name in enumerate(driver_names):
            d_code = f"D{105 + idx}"
            u_driver = User(
                username=f"driver_{d_code.lower()}",
                email=f"driver_{d_code.lower()}@busnotify.com",
                role="driver"
            )
            u_driver.set_password("Password123!")
            db.session.add(u_driver)
            db.session.flush()

            d = Driver(
                user_id=u_driver.id,
                driver_code=d_code,
                full_name=name,
                mobile_number=f"+91 98765 {50000 + idx}",
                license_number=f"MH-12-2016-{10000 + idx}",
                status="AVAILABLE"
            )
            db.session.add(d)
        db.session.commit()

        # 7. Create Active Trips & GPS for Demonstration
        print("7. Setting up demonstration trips (Bus 123, 156, 178)...")
        now = datetime.utcnow()
        # Bus 123 Trip: Pune Station -> Hadapsar, currently at Magarpatta (Section 42)
        trip_123 = Trip(
            trip_code="TRIP-123-DEMO",
            bus_id=buses_map["123"].id,
            driver_id=rajesh.id,
            route_id=routes_map["101"].id,
            scheduled_start_time=now - timedelta(minutes=35),
            actual_start_time=now - timedelta(minutes=32),
            current_stop_id=stops_map["STP-MAG"].id,
            next_stop_id=stops_map["STP-HAD"].id,
            status="RUNNING",
            passenger_count=40  # 40 passengers on board
        )
        db.session.add(trip_123)
        db.session.flush()

        gps_123 = LiveGPS(
            trip_id=trip_123.id,
            bus_id=buses_map["123"].id,
            latitude=stops_map["STP-MAG"].latitude,
            longitude=stops_map["STP-MAG"].longitude,
            speed_kmh=0.0,
            source="MANUAL_STOP",
            timestamp=now - timedelta(minutes=2)
        )
        db.session.add(gps_123)

        # Alternative Bus 156 Trip (Passing Magarpatta with 15 seats available, 25 occupied)
        trip_156 = Trip(
            trip_code="TRIP-156-DEMO",
            bus_id=buses_map["156"].id,
            route_id=routes_map["106"].id,
            scheduled_start_time=now - timedelta(minutes=20),
            actual_start_time=now - timedelta(minutes=18),
            current_stop_id=stops_map["STP-FAT"].id,
            next_stop_id=stops_map["STP-MAG"].id,
            status="RUNNING",
            passenger_count=25  # 40 - 25 = 15 available seats (Section 42)
        )
        db.session.add(trip_156)
        db.session.flush()

        gps_156 = LiveGPS(
            trip_id=trip_156.id,
            bus_id=buses_map["156"].id,
            latitude=stops_map["STP-FAT"].latitude,
            longitude=stops_map["STP-FAT"].longitude,
            speed_kmh=28.0,
            source="GPS",
            timestamp=now - timedelta(seconds=30)
        )
        db.session.add(gps_156)

        # Alternative Bus 178 Trip (Passing Magarpatta with 30 seats available, 10 occupied)
        trip_178 = Trip(
            trip_code="TRIP-178-DEMO",
            bus_id=buses_map["178"].id,
            route_id=routes_map["107"].id,
            scheduled_start_time=now - timedelta(minutes=15),
            actual_start_time=now - timedelta(minutes=10),
            current_stop_id=stops_map["STP-HAD"].id,
            next_stop_id=stops_map["STP-MAG"].id,
            status="DELAYED",
            passenger_count=10  # 40 - 10 = 30 available seats (Section 42)
        )
        db.session.add(trip_178)
        db.session.flush()

        gps_178 = LiveGPS(
            trip_id=trip_178.id,
            bus_id=buses_map["178"].id,
            latitude=stops_map["STP-HAD"].latitude,
            longitude=stops_map["STP-HAD"].longitude,
            speed_kmh=15.0,
            source="GPS",
            timestamp=now - timedelta(seconds=45)
        )
        db.session.add(gps_178)

        # 8. Generate 90 Days of Historical Delay Records
        print("8. Generating 90 days of synthetic historical delay observations...")
        start_date = date.today() - timedelta(days=90)
        delays_to_insert = []

        # Ensure Route 101 Magarpatta has statistically exact metrics (Section 42):
        # Average: 14 min, Min: 5 min, Max: 28 min, Range: 10-18 min
        mag_stop_id = stops_map["STP-MAG"].id
        r101_id = routes_map["101"].id

        # Target sample set with mean ~ 14, min=5, max=28
        exact_delays = [
            14.0, 13.0, 15.0, 14.0, 12.0, 16.0, 14.0, 13.5, 14.5, 11.0,
            17.0, 10.0, 18.0, 14.0, 15.0, 13.0, 12.0, 16.0, 14.0, 14.0,
            5.0, 28.0, 14.0, 13.0, 15.0, 14.0, 12.0, 16.0, 14.0, 13.0,
            14.0, 15.0, 12.0, 16.0, 14.0, 13.0, 15.0, 14.0, 11.0, 17.0
        ]
        for idx, d_val in enumerate(exact_delays):
            sample_d = start_date + timedelta(days=idx % 90)
            delays_to_insert.append(HistoricalDelay(
                route_id=r101_id,
                stop_id=mag_stop_id,
                bus_id=buses_map["123"].id,
                weekday=sample_d.weekday(),
                hour_of_day=17,  # 5 PM rush hour
                delay_minutes=d_val,
                delay_reason="TYRE_PUNCTURE" if idx < 10 else "TRAFFIC",
                sample_date=sample_d
            ))

        # Populate other stops and routes across 90 days
        all_routes = list(routes_map.values())
        for day_offset in range(90):
            cur_date = start_date + timedelta(days=day_offset)
            wday = cur_date.weekday()
            for r in all_routes:
                for rs in r.route_stops:
                    # Random delay around 4-15 minutes
                    delay_m = round(random.choice([0, 2, 4, 6, 8, 10, 12, 15, 18, 22]), 1)
                    reason = "NONE" if delay_m <= 3 else random.choice(["TRAFFIC", "TRAFFIC", "WEATHER", "PASSENGER_SURGE", "BREAKDOWN"])
                    delays_to_insert.append(HistoricalDelay(
                        route_id=r.id,
                        stop_id=rs.stop_id,
                        weekday=wday,
                        hour_of_day=random.randint(7, 21),
                        delay_minutes=delay_m,
                        delay_reason=reason,
                        sample_date=cur_date
                    ))

        # Bulk insert historical delays in batches
        print(f"   Inserting {len(delays_to_insert)} historical delay records...")
        db.session.bulk_save_objects(delays_to_insert)
        db.session.commit()

        # 9. Audit log
        db.session.add(AuditLog(
            action="DATABASE_SEEDED",
            entity_type="system",
            details="Seeded complete 10 routes, 30 stops, 50 buses, 20 drivers, and 90 days historical delays."
        ))
        db.session.commit()

        print("Seeding completed successfully!")
        print("Default Accounts:")
        print("  Passenger:      passenger@busnotify.com  / Password123!")
        print("  Driver:         driver@busnotify.com     / Password123!")
        print("  Depot Operator: depot@busnotify.com      / Password123!")
        print("  Admin:          admin@busnotify.com      / Password123!")


if __name__ == "__main__":
    seed_database()
