from datetime import datetime, timedelta

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import func

from src.database import db
from src.models import ActivityLog, Task, TimerSession, User

user_bp = Blueprint("user", __name__, url_prefix="")

# ── Helpers ──

_DEFAULT_USER_ID = 1  # placeholder until auth is implemented


def _format_duration(seconds):
    """Convert seconds to a readable duration string."""
    if seconds is None:
        return "0m"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _relative_time(dt):
    """Convert a datetime to a relative time string (e.g. '2h ago')."""
    if dt is None:
        return ""
    now = datetime.utcnow()
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    days = seconds // 86400
    if days < 7:
        return f"{days}d ago"
    return dt.strftime("%b %d")


def _log_icon(action_type):
    """Return an emoji icon for a given log action type."""
    icons = {
        "task_completed": "✅",
        "task_created": "📝",
        "timer_completed": "⏱️",
        "project_created": "📁",
        "subproject_created": "📂",
    }
    return icons.get(action_type, "🔵")


# ── Jinja2 filters / globals ──


@user_bp.app_template_filter("reltime")
def reltime_filter(dt):
    return _relative_time(dt)


@user_bp.app_template_global()
def log_icon(action_type):
    return _log_icon(action_type)


# ── Helpers: user & stats ──


def _get_or_create_default_user():
    """Return the default user, creating it if it doesn't exist."""
    user = db.session.get(User, _DEFAULT_USER_ID)
    if not user:
        user = User(
            id=_DEFAULT_USER_ID,
            name="Default User",
            nickname="default",
            email="user@smorch.app",
            password_hash="",
        )
        db.session.add(user)
        db.session.commit()
    return user


def _compute_user_stats(user_id):
    """Return a dict of aggregated statistics for a given user."""
    today = datetime.utcnow().date()

    # Total tasks completed (all time)
    tasks_completed_total = Task.query.filter(Task.completed.is_(True)).count()

    # Tasks completed today
    tasks_completed_today = (
        Task.query.filter(
            Task.completed.is_(True), func.date(Task.updated_at) == today
        ).count()
    )

    # Total time tracked
    total_time_seconds = (
        db.session.query(func.sum(TimerSession.actual_seconds))
        .filter(
            TimerSession.user_id == user_id,
            TimerSession.status == "completed",
        )
        .scalar()
        or 0
    )

    # Time tracked today
    time_today_seconds = (
        db.session.query(func.sum(TimerSession.actual_seconds))
        .filter(
            TimerSession.user_id == user_id,
            TimerSession.status == "completed",
            func.date(TimerSession.start_time) == today,
        )
        .scalar()
        or 0
    )

    # Current streak: consecutive days with at least 1 completed task
    streak = 0
    check_date = today
    while True:
        count = (
            Task.query.filter(
                Task.completed.is_(True), func.date(Task.updated_at) == check_date
            ).count()
        )
        if count > 0:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break

    # Total timer sessions
    timer_sessions_total = (
        TimerSession.query.filter(
            TimerSession.user_id == user_id,
            TimerSession.status == "completed",
        ).count()
    )

    # Total tasks
    total_tasks = Task.query.count()

    return {
        "tasks_completed_total": tasks_completed_total,
        "tasks_completed_today": tasks_completed_today,
        "time_tracked_total": _format_duration(total_time_seconds),
        "time_tracked_total_seconds": total_time_seconds,
        "time_tracked_today": _format_duration(time_today_seconds),
        "time_tracked_today_seconds": time_today_seconds,
        "current_streak": streak,
        "timer_sessions_total": timer_sessions_total,
        "total_tasks": total_tasks,
    }


# ── Page route ──


@user_bp.route("/profile")
def profile():
    """Render the user profile page with edit form and statistics."""
    user = _get_or_create_default_user()

    stats = _compute_user_stats(_DEFAULT_USER_ID)

    log_entries = (
        ActivityLog.query.filter(ActivityLog.user_id == _DEFAULT_USER_ID)
        .order_by(ActivityLog.created_at.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        log_entries=log_entries,
    )


# ── API: Profile ──


@user_bp.route("/api/user/profile", methods=["GET"])
def api_profile_get():
    """Return current user profile data as JSON."""
    user = _get_or_create_default_user()

    return jsonify(
        {
            "id": user.id,
            "name": user.name,
            "nickname": user.nickname,
            "email": user.email,
            "created_dttm": user.created_dttm.isoformat(),
        }
    )


@user_bp.route("/api/user/profile", methods=["PUT"])
def api_profile_update():
    """Update current user profile fields."""
    data = request.get_json(silent=True) or {}
    user = _get_or_create_default_user()

    name = data.get("name", "").strip()
    nickname = data.get("nickname", "").strip()
    email = data.get("email", "").strip()

    # Validate required fields
    if not name:
        return jsonify({"error": "Name is required"}), 400
    if not nickname:
        return jsonify({"error": "Nickname is required"}), 400
    if not email:
        return jsonify({"error": "Email is required"}), 400

    # Check unique nickname
    existing_nickname = User.query.filter(
        User.nickname == nickname, User.id != _DEFAULT_USER_ID
    ).first()
    if existing_nickname:
        return jsonify({"error": f'Nickname "{nickname}" is already taken'}), 409

    # Check unique email
    existing_email = User.query.filter(
        User.email == email, User.id != _DEFAULT_USER_ID
    ).first()
    if existing_email:
        return jsonify({"error": f'Email "{email}" is already registered'}), 409

    user.name = name
    user.nickname = nickname
    user.email = email
    db.session.commit()

    return jsonify(
        {
            "id": user.id,
            "name": user.name,
            "nickname": user.nickname,
            "email": user.email,
            "created_dttm": user.created_dttm.isoformat(),
        }
    )


# ── API: User Stats ──


@user_bp.route("/api/user/stats")
def api_user_stats():
    """Return aggregated statistics for the current user."""
    stats = _compute_user_stats(_DEFAULT_USER_ID)
    return jsonify(stats)