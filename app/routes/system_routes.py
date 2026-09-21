"""
System Status, Database Connectivity Test, and Health API Routes
Endpoints:
- /health - Standard health check for monitoring and load balancers
- /api/system/status - High-level system metadata and operational counts
- /api/system/db-test - Detailed database connection verification & latency test
"""
import time
from datetime import datetime
from flask import Blueprint, jsonify, request
from sqlalchemy import text
from app.extensions import db
from app.utils.response import api_success, api_error

system_bp = Blueprint("system_api", __name__)


@system_bp.route("/health", methods=["GET"])
def health_check():
    """
    Health check endpoint: verifies application liveness and database connection.
    """
    db_ok = True
    latency_ms = 0.0
    start = time.perf_counter()
    try:
        db.session.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
    except Exception:
        db_ok = False

    engine_name = db.engine.name if hasattr(db, "engine") else "unknown"
    status_code = 200 if db_ok else 503

    return jsonify({
        "status": "UP" if db_ok else "DEGRADED",
        "service": "BusNotify Transit System",
        "database": "CONNECTED" if db_ok else "DISCONNECTED",
        "database_engine": engine_name,
        "database_latency_ms": latency_ms,
        "timestamp": datetime.utcnow().isoformat()
    }), status_code


@system_bp.route("/api/system/status", methods=["GET"])
def system_status():
    """
    Returns system status and operational counts.
    """
    from app.models.bus import Bus
    from app.models.trip import Trip
    from app.models.incident import Incident
    from app.models.depot import DepotRequest

    return api_success(data={
        "system_name": "BusNotify - Smart Bus Delay Prediction & Passenger Information System",
        "tagline": "Know your bus. Know your time.",
        "server_time": datetime.utcnow().isoformat(),
        "timezone": "Asia/Kolkata",
        "database_engine": db.engine.name,
        "stats": {
            "total_buses": Bus.query.count(),
            "active_trips": Trip.query.filter(Trip.status.in_(["RUNNING", "DELAYED"])).count(),
            "open_incidents": Incident.query.filter_by(status="OPEN").count(),
            "active_depot_requests": DepotRequest.query.filter(DepotRequest.status != "RESOLVED").count(),
        }
    })


@system_bp.route("/api/system/db-test", methods=["GET"])
def database_connection_test():
    """
    Explicit database connectivity test:
    Executes SELECT 1, checks schema, measures response latency, and returns diagnostics.
    """
    start_time = time.perf_counter()
    try:
        result = db.session.execute(text("SELECT 1")).scalar()
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Query database name and version if MySQL
        db_version = "Unknown"
        db_name = "busnotify"
        try:
            if db.engine.name == "mysql":
                db_version = db.session.execute(text("SELECT VERSION()")).scalar()
                db_name = db.session.execute(text("SELECT DATABASE()")).scalar()
            elif db.engine.name == "sqlite":
                db_version = db.session.execute(text("SELECT sqlite_version()")).scalar()
                db_name = "SQLite local file"
        except Exception:
            pass

        return api_success(data={
            "database_status": "CONNECTED",
            "test_query_result": result,
            "engine": db.engine.name,
            "database_name": db_name,
            "database_version": db_version,
            "latency_ms": latency_ms,
            "pool_size": getattr(db.engine.pool, "size", lambda: "N/A")() if hasattr(db.engine.pool, "size") else "N/A",
            "checked_at": datetime.utcnow().isoformat(),
        }, message="Database connection verified successfully")
    except Exception as e:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return api_error(
            code="DATABASE_CONNECTION_ERROR",
            message="Database connection test failed.",
            details={"error": str(e), "latency_ms": latency_ms},
            status_code=503
        )
