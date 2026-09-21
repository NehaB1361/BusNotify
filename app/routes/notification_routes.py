"""
Notification API Routes
/api/notifications/ - List role-filtered notifications
/api/notifications/<id>/read - Mark as read
"""
from flask import Blueprint, request, session
from app.extensions import db
from app.models.notification import Notification
from app.utils.response import api_success, api_error

notification_bp = Blueprint("notification_api", __name__, url_prefix="/api/notifications")


@notification_bp.route("/", methods=["GET"])
def get_notifications():
    user_id = session.get("user_id")
    role = session.get("role", "passenger")

    # Fetch notifications targeted to this user or to their role or 'all'
    query = Notification.query.filter(
        (Notification.target_role.in_(["all", role])) | (Notification.user_id == user_id)
    ).order_by(Notification.id.desc()).limit(30)

    notifs = query.all()
    unread_count = sum(1 for n in notifs if not n.is_read)

    return api_success(data={
        "unread_count": unread_count,
        "notifications": [n.to_dict() for n in notifs]
    })


@notification_bp.route("/<int:notif_id>/read", methods=["POST"])
def mark_read(notif_id: int):
    notif = Notification.query.get(notif_id)
    if not notif:
        return api_error(code="NOT_FOUND", message="Notification not found.", status_code=404)
    notif.is_read = True
    db.session.commit()
    return api_success(message="Notification marked as read.")
