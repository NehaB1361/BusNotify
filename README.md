# BusNotify 🚌

**Smart Bus Delay Prediction and Passenger Information System**  
*"Know your bus. Know your time."*

[![Tests](https://img.shields.io/badge/tests-23%20passing-brightgreen)](tests/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![Flask](https://img.shields.io/badge/flask-3.x-lightgrey)](https://flask.palletsprojects.com)
[![MySQL](https://img.shields.io/badge/database-MySQL%208-orange)](https://mysql.com)
[![Bootstrap](https://img.shields.io/badge/frontend-Bootstrap%205-purple)](https://getbootstrap.com)

---

## Overview

BusNotify is a **full-stack college final-year project** demonstrating real-world software engineering. It provides:

- 🔍 **Live Bus Tracking** — Passengers search buses by route, stop, or bus number
- 📊 **Historical Statistical Estimates** — Descriptive statistics (mean, median, P90) from 90+ days of trip data *(not AI)*
- 🚨 **Emergency Incident Workflow** — Driver reports → Depot assigns replacement → 6-stage state machine
- 🔄 **Alternative Bus Engine** — Deterministic multi-criteria ranking using DSA (priority queue, greedy algorithm)
- 📁 **CSV Bulk Import/Export** — Schema-validated data pipeline for 7 dataset types
- 📈 **Admin Analytics** — Chart.js-powered dashboards (hourly delay, root cause, weekday, route comparison)
- 🔐 **Role-Based Authentication** — 4 roles: Passenger, Driver, Depot Operator, Admin (JWT sessions)

> **Important:** This project uses **Historical Statistical Estimates** only — no AI/ML. All estimates are computed via SQL aggregations and deterministic algorithms.

---

## Quick Start

### Prerequisites
- Python 3.11+
- MySQL 8.0+
- Git

### 1. Clone & Setup Environment

```powershell
git clone <repo-url>
cd BusNotify
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```powershell
copy .env.example .env
# Edit .env with your MySQL credentials:
# DATABASE_URL=mysql+pymysql://root:password@localhost/busnotify
# SECRET_KEY=your-secret-key
# JWT_SECRET_KEY=your-jwt-secret
```

### 3. Initialize Database

```powershell
flask db upgrade
python scripts/seed_data.py
```

### 4. (Optional) Load Intercity Dataset

```powershell
python scripts/load_dataset.py
```

### 5. Run Application

```powershell
python run.py
```

Visit: **http://localhost:5000**

---

## Demo Login Credentials

| Role | Email | Password |
|---|---|---|
| Passenger | passenger@busnotify.com | Password123! |
| Driver (Rajesh Patil) | driver@busnotify.com | Password123! |
| Depot Operator | depot@busnotify.com | Password123! |
| Admin | admin@busnotify.com | Password123! |

---

## Project Structure

```
BusNotify/
├── app/
│   ├── __init__.py          # create_app() application factory & error handlers
│   ├── models.py            # Clean SQLAlchemy MySQL database models
│   ├── routes.py            # REST API endpoints & page controllers
│   ├── services.py          # Delay statistics (pure statistics), incident & depot workflow
│   └── auth.py              # Authentication service, session management & RBAC decorators
├── templates/               # Jinja2 HTML templates for all portals
│   ├── auth_base.html       # Centered layout for login/auth
│   ├── base.html            # Master layout with sidebar
│   ├── auth/                # login, register, unauthorized, 404, 500
│   ├── passenger/           # home, search, bus_detail, emergency, replacement, favourites, profile
│   ├── driver/              # dashboard, start_trip, live_trip, emergency
│   ├── depot/               # dashboard, request_detail, history
│   └── admin/               # dashboard, live_buses, analytics, management, csv_portal
├── static/                  # Static assets
│   ├── css/                 # transit-flow.css & custom styles
│   └── js/                  # api.js & transit-ui.js
├── data/                    # Datasets
│   └── historical_delays.csv # Historical delay observations for statistics
├── scripts/                 # Utility scripts
│   └── seed_data.py         # Database seeder (routes, stops, buses, users)
├── tests/                   # Pytest test suite (28 passing tests)
│   ├── test_api_endpoints.py
│   ├── test_auth.py
│   ├── test_depot_workflow.py
│   ├── test_dsa.py
│   ├── test_master_end_to_end.py
│   └── test_statistics.py
├── .env                     # Environment variables & MySQL connection config
├── requirements.txt         # Python dependencies
├── config.py                # Configuration classes (Development, Testing, Production)
├── run.py                   # Application entrypoint
└── README.md
```

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, Flask 3.x |
| ORM | SQLAlchemy + Flask-Migrate (Alembic) |
| Database | MySQL 8.0+ |
| Auth | Flask-JWT-Extended + Flask-Bcrypt |
| Frontend | Bootstrap 5.3.3 + Vanilla JavaScript |
| Charts | Chart.js 4.x |
| Maps | Leaflet.js 1.9.4 |
| Icons | Bootstrap Icons 1.11.3 |
| Testing | pytest + pytest-flask |

---

## Running Tests

```powershell
.\venv\Scripts\pytest -v tests/
# Expected: 23 passed
```

---

## Key Features by Role

### 🧑 Passenger
- Search buses by route, stop, or bus number
- View live bus status, ETA, occupancy
- Historical Statistical Estimates (mean, median, P90)
- Emergency alternatives when bus breaks down
- Save favourite routes
- Manage profile

### 🚌 Driver
- Start/end trips with route and bus assignment
- Submit GPS location updates
- Update passenger counts at each stop
- Report emergencies (tyre puncture, engine failure, accident)
- View live trip telemetry

### 🏭 Depot Operator
- View incoming breakdown requests sorted by priority
- Assign replacement buses (greedy algorithm from available fleet)
- Track 6-stage workflow: PENDING → ASSIGNED → DISPATCHED → ARRIVED → PASSENGER_TRANSFER → RESOLVED
- View audit history of all requests

### 🛡️ Admin
- Fleet-wide KPI dashboard (8 metrics)
- Live bus monitoring (table + map view)
- Analytics: Hourly delay, Root causes (doughnut), Weekday trends, Route comparison
- CRUD management for buses, routes, stops, drivers
- CSV bulk import and export

---

## Data Flow: Emergency Workflow

```
1. Driver: POST /api/driver/trip/emergency
   → Creates Incident + updates Trip/Bus status

2. System: AlternativeService ranks substitute buses
   → DSA: Priority Queue (by severity) + Greedy redistribution

3. Depot: Assigns replacement → dispatches → arrives
   → 6-stage DepotRequest state machine

4. Passengers: Notified at each stage
   → NotificationService fans out to all affected passengers

5. Admin: Full audit trail in AuditLog table
```

---

## CSV Import Schemas

| Dataset | Required Columns |
|---|---|
| routes | route_number, name, source, destination, total_distance_km, estimated_duration_min |
| stops | stop_code, name, latitude, longitude, landmark |
| buses | bus_number, registration_number, capacity, assigned_route_id, current_status |
| drivers | driver_code, full_name, mobile_number, license_number |
| historical_delays | route_number, stop_code, weekday, hour_of_day, delay_minutes, delay_reason, sample_date |
| bus_capacity | bus_number, capacity, available_seats |
| depot_requests | request_id, incident_id, failed_bus_number, problem, affected_passengers, priority, status |

---

## Academic Subject Mapping

See [`docs/SUBJECT_MAPPING.md`](docs/SUBJECT_MAPPING.md) for complete mapping of:
- DSA concepts → implementation files
- DBMS concepts → schema/query files
- Statistics → `stats_service.py`
- OOP/Software Engineering → architecture patterns

---

## License

This project is a college academic submission. All code is original work for educational purposes.

*BusNotify v1.0.0 — September 2026*
