"""
BusNotify Routes Package
Registers all blueprints
"""
from app.routes.auth_routes import auth_bp
from app.routes.passenger_routes import passenger_bp
from app.routes.driver_routes import driver_bp
from app.routes.depot_routes import depot_bp
from app.routes.admin_routes import admin_bp
from app.routes.notification_routes import notification_bp
from app.routes.system_routes import system_bp
from app.routes.view_routes import view_bp

__all__ = [
    "auth_bp",
    "passenger_bp",
    "driver_bp",
    "depot_bp",
    "admin_bp",
    "notification_bp",
    "system_bp",
    "view_bp",
]
