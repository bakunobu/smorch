from datetime import datetime, timezone

from src.database import db


class ActivityLog(db.Model):
    """Records user actions for the activity log feed."""

    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    action_type = db.Column(
        db.String(50), nullable=False
    )
    # e.g.: task_completed, task_created, timer_completed,
    #        project_created, subproject_created
    description = db.Column(db.String(300), default="")
    related_object_type = db.Column(
        db.String(50), nullable=True
    )  # task | project | subproject
    related_object_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    user = db.relationship(
        "User", backref=db.backref("activity_logs", lazy="dynamic")
    )

    def __repr__(self):
        return (
            f"<ActivityLog {self.id} user={self.user_id} "
            f"action={self.action_type}>"
        )