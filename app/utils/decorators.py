"""
Authentication and Role-Based Authorization Decorators for BusNotify
Enforces:
- Login requirement
- Active user status (rejects deactivated/inactive users)
- Role-based authorization across Passenger, Driver, Admin, and Depot Operator
- Rejection of cross-role / unauthorized access with 403 Forbidden
"""
from functools import wraps
from flask import session, request, redirect, url_for, g
from app.utils.response import api_error
from app.models.user import User


def login_required(f):
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
    """
    Ensures user is logged in, active, and has one of the allowed roles.
    Supported roles: 'passenger', 'driver', 'admin', 'depot_operator'
    """
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
