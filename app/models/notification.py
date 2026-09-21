"""
Notification Model
Role-aware notifications for Passenger, Driver, Admin, and Depot Operator
"""
from datetime import datetime
from app.extensions import db


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    target_role = db.Column(db.String(32), default="all", nullable=False, index=True)  # all, passenger, driver, admin, depot_operator
    title = db.Column(db.String(128), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(
        db.String(64),
        default="INFO",
        nullable=False,
        index=True
    )  # DELAY, CANCELLATION, PUNCTURE, BREAKDOWN, ALTERNATIVE, REPLACEMENT_ASSIGNED, REPLACEMENT_DISPATCHED, SERVICE_RESTORED, INCIDENT
    priority = db.Column(db.String(16), default="NORMAL", nullable=False)  # NORMAL, HIGH, URGENT
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    related_entity_type = db.Column(db.String(32), nullable=True)  # bus, trip, incident, depot_request
    related_entity_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = db.relationship("User", back_populates="notifications")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "target_role": self.target_role,
            "title": self.title,
            "message": self.message,
            "notification_type": self.notification_type,
            "priority": self.priority,
            "is_read": self.is_read,
            "related_entity_type": self.related_entity_type,
            "related_entity_id": self.related_entity_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
