"""
BusNotify Application Factory
Initializes Flask, database, migrations, blueprints, error handlers, and context processors.
"""
import os
from flask import Flask, render_template, request, session
from werkzeug.exceptions import HTTPException
from app.config import config_by_name
from app.extensions import db, migrate, cors
from app.utils.response import api_error


def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(
        __name__,
        template_folder="../frontend/templates",
        static_folder="../frontend/static"
    )
    app.config.from_object(config_by_name.get(config_name, config_by_name["default"]))

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    # Register blueprints
    from app.routes import (
        auth_bp,
        passenger_bp,
        driver_bp,
        depot_bp,
        admin_bp,
        notification_bp,
        system_bp,
        view_bp,
    )

    app.register_blueprint(auth_bp)
    app.register_blueprint(passenger_bp)
    app.register_blueprint(driver_bp)
    app.register_blueprint(depot_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(system_bp)
    app.register_blueprint(view_bp)

    # Context processor for global templates
    @app.context_processor
    def inject_global_vars():
        return {
            "current_user_id": session.get("user_id"),
            "current_username": session.get("username", "Guest"),
            "current_role": session.get("role", "passenger"),
            "preferred_language": session.get("preferred_language", "en"),
            "system_name": "BusNotify",
            "tagline": "Know your bus. Know your time.",
        }

    # Centralized HTTP & Exception Error Handlers
    @app.errorhandler(400)
    def bad_request_error(error):
        if request.path.startswith("/api/"):
            return api_error(code="BAD_REQUEST", message="Invalid request parameters or payload.", status_code=400)
        return render_template("auth/404.html"), 400

    @app.errorhandler(401)
    def unauthorized_error(error):
        if request.path.startswith("/api/"):
            return api_error(code="UNAUTHORIZED", message="Authentication is required to access this resource.", status_code=401)
        return render_template("auth/unauthorized.html"), 401

    @app.errorhandler(403)
    def forbidden_error(error):
        if request.path.startswith("/api/"):
            return api_error(code="FORBIDDEN", message="You do not have permission to perform this action.", status_code=403)
        return render_template("auth/unauthorized.html"), 403

    @app.errorhandler(404)
    def not_found_error(error):
        if request.path.startswith("/api/"):
            return api_error(code="NOT_FOUND", message="The requested resource or endpoint was not found.", status_code=404)
        return render_template("auth/404.html"), 404

    @app.errorhandler(405)
    def method_not_allowed_error(error):
        if request.path.startswith("/api/"):
            return api_error(code="METHOD_NOT_ALLOWED", message=f"HTTP method {request.method} is not allowed on this endpoint.", status_code=405)
        return render_template("auth/404.html"), 405

    @app.errorhandler(422)
    def unprocessable_error(error):
        if request.path.startswith("/api/"):
            return api_error(code="UNPROCESSABLE_ENTITY", message="Unable to process the contained instructions.", status_code=422)
        return render_template("auth/404.html"), 422

    @app.errorhandler(500)
    def internal_server_error(error):
        db.session.rollback()
        if request.path.startswith("/api/"):
            return api_error(code="SERVER_ERROR", message="An internal server error occurred.", details=str(error), status_code=500)
        return render_template("auth/500.html"), 500

    @app.errorhandler(Exception)
    def unhandled_exception_error(error):
        if isinstance(error, HTTPException):
            if request.path.startswith("/api/"):
                return api_error(code=error.name.upper().replace(" ", "_"), message=error.description, status_code=error.code)
            return render_template("auth/500.html"), error.code

        db.session.rollback()
        app.logger.exception(f"Unhandled Exception: {error}")
        if request.path.startswith("/api/"):
            return api_error(code="UNHANDLED_EXCEPTION", message="An unexpected server error occurred.", details=str(error), status_code=500)
        return render_template("auth/500.html"), 500

    # Auto-create tables if not already present
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            app.logger.warning(f"Note: db.create_all() notice: {e}")

    return app
