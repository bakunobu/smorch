from datetime import datetime, timezone

from src.database import db


class TimerSession(db.Model):
    """Tracks a work/break timer session linked to a task."""

    __tablename__ = "timer_sessions"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    start_time = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    end_time = db.Column(db.DateTime, nullable=True)
    duration_seconds = db.Column(
        db.Integer, default=1500
    )  # planned duration (default 25 min)
    actual_seconds = db.Column(db.Integer, default=0)  # actual elapsed time
    status = db.Column(
        db.String(20), default="active"
    )  # active | paused | completed | cancelled

    task = db.relationship("Task", backref=db.backref("timer_sessions", lazy="dynamic"))
    user = db.relationship(
        "User", backref=db.backref("timer_sessions", lazy="dynamic")
    )

    def __repr__(self):
        return (
            f"<TimerSession {self.id} task={self.task_id} "
            f"status={self.status} elapsed={self.actual_seconds}s>"
        )