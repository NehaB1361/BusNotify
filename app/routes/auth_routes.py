"""
Authentication API Routes
/api/auth/register, /api/auth/login, /api/auth/logout, /api/auth/me
"""
from flask import Blueprint, request, session, redirect, url_for
from app.services.auth_service import AuthService
from app.utils.response import api_success, api_error

auth_bp = Blueprint("auth_api", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    role = data.get("role", "passenger")
    mobile = data.get("mobile")

    if not username or not email or not password:
        return api_error(code="VALIDATION_ERROR", message="Username, email, and password are required.", status_code=400)

    try:
        user_data = AuthService.register_user(
            username=username,
            email=email,
            password=password,
            role=role,
            mobile=mobile
        )
        return api_success(data=user_data, message="User registered successfully", status_code=201)
    except ValueError as e:
        return api_error(code="REGISTRATION_FAILED", message=str(e), status_code=400)


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    identifier = data.get("identifier") or data.get("email") or data.get("username")
    password = data.get("password")

    if not identifier or not password:
        return api_error(code="VALIDATION_ERROR", message="Email/mobile and password are required.", status_code=400)

    try:
        user_data = AuthService.authenticate_user(
            identifier=identifier,
            password=password,
            ip_address=request.remote_addr
        )
        return api_success(data=user_data, message="Login successful")
    except ValueError as e:
        return api_error(code="AUTH_FAILED", message=str(e), status_code=401)


@auth_bp.route("/logout", methods=["POST", "GET"])
def logout():
    AuthService.logout_user()
    if request.method == "GET":
        return redirect(url_for("views.login_page"))
    return api_success(message="Logged out successfully")


@auth_bp.route("/me", methods=["GET"])
def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return api_error(code="UNAUTHORIZED", message="Not authenticated", status_code=401)
    
    from app.models.user import User
    user = User.query.get(user_id)
    if not user:
        return api_error(code="NOT_FOUND", message="User not found", status_code=404)
    
    return api_success(data=user.to_dict())
