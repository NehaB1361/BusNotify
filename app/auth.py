"""
BusNotify - Authentication & Authorization Module
Simple, session-based authentication and role-based access control (RBAC).
Roles:
  - passenger: Default public transit passenger
  - driver: Bus operator broadcasting stops & GPS
  - depot_operator: Fleet & replacement bus dispatcher
  - admin: System supervisor with full CRUD & analytics
"""
import sys
from functools import wraps
from typing import Dict, Any, Optional
from flask import session, request, redirect, url_for, g, jsonify
from app.models import db, User, AuditLog


def api_error(code="ERROR", message="An error occurred", details=None, status_code=400):
    response = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details if details is not None else {}
        }
    }
    return jsonify(response), status_code


def api_success(data=None, message="Operation completed successfully", status_code=200):
    response = {
        "success": True,
        "data": data if data is not None else {},
        "message": message
    }
    return jsonify(response), status_code


# ==========================================
# AUTHENTICATION SERVICE
# ==========================================
class AuthService:

    @classmethod
    def register_user(
        cls,
        username: str,
        email: str,
        password: str,
        role: str = "passenger",
        mobile: Optional[str] = None,
        preferred_language: str = "en"
    ) -> Dict[str, Any]:
        """Registers a new user with password hashing."""
        username = username.strip()
        email = email.strip().lower()

        if User.query.filter_by(username=username).first():
            raise ValueError("Username already taken.")
        if User.query.filter_by(email=email).first():
            raise ValueError("Email already registered.")
        if mobile and User.query.filter_by(mobile=mobile).first():
            raise ValueError("Mobile number already registered.")

        if role not in ["passenger", "driver", "admin", "depot_operator"]:
            role = "passenger"

        user = User(
            username=username,
            email=email,
            mobile=mobile,
            role=role,
            preferred_language=preferred_language
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        # Audit log registration
        db.session.add(AuditLog(
            user_id=user.id,
            action="USER_REGISTERED",
            entity_type="user",
            entity_id=str(user.id),
            details=f"New user registered with role {role}"
        ))
        db.session.commit()

        return user.to_dict()

    @classmethod
    def authenticate_user(
        cls,
        identifier: str,
        password: str,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Verifies credentials and sets user session."""
        identifier = identifier.strip().lower()
        
        user = User.query.filter(
            (User.email == identifier) | (User.username == identifier) | (User.mobile == identifier)
        ).first()

        if not user or not user.check_password(password):
            db.session.add(AuditLog(
                action="LOGIN_FAILED",
                entity_type="user",
                entity_id=identifier,
                details="Invalid credentials attempt",
                ip_address=ip_address
            ))
            db.session.commit()
            raise ValueError("Invalid email/mobile or password.")

        if not user.is_active:
            raise ValueError("This account has been deactivated.")

        # Store user details in session
        session["user_id"] = user.id
        session["username"] = user.username
        session["role"] = user.role
        session["preferred_language"] = user.preferred_language

        # Audit log login
        db.session.add(AuditLog(
            user_id=user.id,
            action="LOGIN_SUCCESS",
            entity_type="user",
            entity_id=str(user.id),
            details=f"User {user.username} logged in as {user.role}",
            ip_address=ip_address
        ))
        db.session.commit()

        user_data = user.to_dict()
        if user.role == "driver" and user.driver_profile:
            user_data["driver_profile"] = user.driver_profile.to_dict()

        return user_data

    @classmethod
    def logout_user(cls) -> None:
        """Clears user session and logs logout event."""
        user_id = session.get("user_id")
        if user_id:
            db.session.add(AuditLog(
                user_id=user_id,
                action="LOGOUT",
                entity_type="user",
                entity_id=str(user_id),
                details="User logged out"
            ))
            db.session.commit()
        session.clear()


# ==========================================
# ACCESS CONTROL DECORATORS
# ==========================================
def login_required(f):
    """Enforces that the user is logged in and active."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get("user_id")
        if not user_id:
            if request.path.startswith("/api/"):
                return api_error(code="UNAUTHORIZED", message="Authentication required. Please log in.", status_code=401)
            return redirect(url_for("views.login_page", next=request.path))

        user = User.query.get(user_id)
        if not user:
            session.clear()
            if request.path.startswith("/api/"):
                return api_error(code="UNAUTHORIZED", message="User account not found.", status_code=401)
            return redirect(url_for("views.login_page"))

        if not user.is_active:
            session.clear()
            if request.path.startswith("/api/"):
                return api_error(code="ACCOUNT_INACTIVE", message="Your account is inactive or disabled.", status_code=403)
            return redirect(url_for("views.login_page"))

        g.current_user = user
        return f(*args, **kwargs)
    return decorated_function


def role_required(*allowed_roles):
    """Enforces that the user is logged in and has one of the allowed roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get("user_id")
            if not user_id:
                if request.path.startswith("/api/"):
                    return api_error(code="UNAUTHORIZED", message="Authentication required. Please log in.", status_code=401)
                return redirect(url_for("views.login_page", next=request.path))

            user = User.query.get(user_id)
            if not user:
                session.clear()
                if request.path.startswith("/api/"):
                    return api_error(code="UNAUTHORIZED", message="User account not found.", status_code=401)
                return redirect(url_for("views.login_page"))

            if not user.is_active:
                session.clear()
                if request.path.startswith("/api/"):
                    return api_error(code="ACCOUNT_INACTIVE", message="Your account is inactive or disabled.", status_code=403)
                return redirect(url_for("views.login_page"))

            if user.role not in allowed_roles:
                if request.path.startswith("/api/"):
                    return api_error(
                        code="FORBIDDEN",
                        message=f"Access denied. Required role: {', '.join(allowed_roles)}. Your role: {user.role}",
                        status_code=403
                    )
                return redirect(url_for("views.unauthorized_page"))

            g.current_user = user
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ==========================================
# MODULE ALIASES (Backward Compatibility)
# ==========================================
curr_module = sys.modules[__name__]
sys.modules["app.services.auth_service"] = curr_module
sys.modules["app.utils.decorators"] = curr_module
