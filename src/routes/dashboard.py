from datetime import datetime

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import func

from src.database import db
from src.models import ActivityLog, Project, Subproject, Task, TimerSession

dashboard_bp = Blueprint("dashboard", __name__)

# ── Helpers ──

_DEFAULT_USER_ID = 1  # placeholder until auth is implemented


def _relative_time(dt):
    """Convert a datetime to a relative time string (e.g. '2h ago')."""
    if dt is None:
        return ""
    # Use naive UTC for comparison (SQLite stores naive datetimes)
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


def _format_duration(seconds):
    """Convert seconds to a readable duration string."""
    if seconds is None:
        return "0m"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


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


# ── Jinja2 filters ──


@dashboard_bp.app_template_filter("reltime")
def reltime_filter(dt):
    return _relative_time(dt)


@dashboard_bp.app_template_global()
def log_icon(action_type):
    return _log_icon(action_type)


# ── Page route ──


@dashboard_bp.route("/dashboard")
def dashboard():
    """Render the main dashboard page with all 3 blocks."""

    # ── Block 1: Projects ──
    projects = Project.query.order_by(Project.title).all()
    project_counts = {}
    for p in projects:
        task_count = (
            Task.query.join(Subproject)
            .filter(Subproject.project_id == p.id)
            .count()
        )
        completed_count = (
            Task.query.join(Subproject)
            .filter(Subproject.project_id == p.id, Task.completed.is_(True))
            .count()
        )
        pct = round((completed_count / task_count * 100)) if task_count > 0 else 0
        project_counts[p.id] = {
            "task_count": task_count,
            "completed_count": completed_count,
            "completed_pct": pct,
        }

    # ── Block 2: Workflow ──
    tasks = (
        Task.query.options(
            db.joinedload(Task.subproject).joinedload(Subproject.project),
            db.joinedload(Task.tags),
        )
        .order_by(Task.priority.desc(), Task.deadline.asc())
        .all()
    )

    # Group tasks by project > subproject
    task_groups = []
    seen = set()
    for task in tasks:
        sub = task.subproject
        proj = sub.project
        key = (proj.id, sub.id)
        if key not in seen:
            seen.add(key)
            task_groups.append(
                {
                    "project": proj.title,
                    "subproject": sub.title,
                    "tasks": [],
                }
            )
        task_groups[-1]["tasks"].append(task)

    # ── Block 3 Stats ──
    today = datetime.utcnow().date()
    tasks_completed_today = (
        Task.query.filter(
            Task.completed.is_(True), func.date(Task.updated_at) == today
        ).count()
    )
    total_time_today = (
        db.session.query(func.sum(TimerSession.actual_seconds))
        .filter(
            TimerSession.status == "completed",
            func.date(TimerSession.start_time) == today,
        )
        .scalar()
        or 0
    )

    # Simple streak: count consecutive days with at least 1 completed task
    streak = 0
    from datetime import timedelta

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

    total_tasks = Task.query.count()

    stats = {
        "tasks_completed_today": tasks_completed_today,
        "time_tracked_today": _format_duration(total_time_today),
        "current_streak": streak,
        "total_tasks": total_tasks,
    }

    # ── Block 3 Log ──
    log_entries = (
        ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(20).all()
    )

    # All tasks for timer dropdown
    all_tasks = Task.query.order_by(Task.title).all()

    return render_template(
        "dashboard.html",
        projects=projects,
        project_counts=project_counts,
        task_groups=task_groups,
        stats=stats,
        log_entries=log_entries,
        all_tasks=all_tasks,
    )


# ── API: Projects ──


@dashboard_bp.route("/api/projects")
def api_projects():
    """Return all projects with subproject/task counts."""
    projects = Project.query.order_by(Project.title).all()
    result = []
    for p in projects:
        task_count = (
            Task.query.join(Subproject)
            .filter(Subproject.project_id == p.id)
            .count()
        )
        completed_count = (
            Task.query.join(Subproject)
            .filter(Subproject.project_id == p.id, Task.completed.is_(True))
            .count()
        )
        result.append(
            {
                "id": p.id,
                "title": p.title,
                "task_count": task_count,
                "completed_count": completed_count,
                "is_private": p.is_private,
            }
        )
    return jsonify(result)


# ── API: Tasks ──


@dashboard_bp.route("/api/tasks")
def api_tasks():
    """Return all tasks grouped by project/subproject."""
    tasks = (
        Task.query.options(
            db.joinedload(Task.subproject).joinedload(Subproject.project),
            db.joinedload(Task.tags),
        )
        .order_by(Task.priority.desc(), Task.deadline.asc())
        .all()
    )
    result = []
    for task in tasks:
        result.append(
            {
                "id": task.id,
                "title": task.title,
                "completed": task.completed,
                "priority": task.priority,
                "complexity": task.complexity,
                "deadline": task.deadline.isoformat() if task.deadline else None,
                "project": task.subproject.project.title,
                "subproject": task.subproject.title,
                "tags": [t.name for t in task.tags],
            }
        )
    return jsonify(result)


# ── API: Stats ──


@dashboard_bp.route("/api/stats")
def api_stats():
    """Return today's stats as JSON."""
    today = datetime.utcnow().date()
    tasks_completed_today = (
        Task.query.filter(
            Task.completed.is_(True), func.date(Task.updated_at) == today
        ).count()
    )
    total_time_today = (
        db.session.query(func.sum(TimerSession.actual_seconds))
        .filter(
            TimerSession.status == "completed",
            func.date(TimerSession.start_time) == today,
        )
        .scalar()
        or 0
    )

    streak = 0
    from datetime import timedelta

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

    total_tasks = Task.query.count()

    return jsonify(
        {
            "tasks_completed_today": tasks_completed_today,
            "time_tracked_today": _format_duration(total_time_today),
            "time_tracked_seconds": total_time_today,
            "current_streak": streak,
            "total_tasks": total_tasks,
        }
    )


# ── API: Log ──


@dashboard_bp.route("/api/log")
def api_log():
    """Return recent activity log entries."""
    entries = (
        ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(20).all()
    )
    return jsonify(
        [
            {
                "id": e.id,
                "action_type": e.action_type,
                "description": e.description,
                "icon": _log_icon(e.action_type),
                "created_at": e.created_at.isoformat(),
                "relative_time": _relative_time(e.created_at),
            }
            for e in entries
        ]
    )


# ── API: Timer ──


@dashboard_bp.route("/api/timer/start", methods=["POST"])
def api_timer_start():
    """Start a new timer session."""
    data = request.get_json(silent=True) or {}
    task_id = data.get("task_id")
    duration = data.get("duration", 1500)  # default 25 min in seconds

    # Stop any existing active timer
    active = (
        TimerSession.query.filter(
            TimerSession.user_id == _DEFAULT_USER_ID,
            TimerSession.status.in_(["active", "paused"]),
        )
        .order_by(TimerSession.start_time.desc())
        .first()
    )
    if active:
        active.status = "cancelled"
        active.end_time = datetime.utcnow()

    session = TimerSession(
        task_id=task_id,
        user_id=_DEFAULT_USER_ID,
        duration_seconds=duration,
        status="active",
    )
    db.session.add(session)
    db.session.commit()

    return jsonify(
        {
            "id": session.id,
            "task_id": session.task_id,
            "duration": session.duration_seconds,
            "status": session.status,
            "start_time": session.start_time.isoformat(),
        }
    ), 201


@dashboard_bp.route("/api/timer/stop", methods=["POST"])
def api_timer_stop():
    """Stop the current active timer session."""
    data = request.get_json(silent=True) or {}
    session = (
        TimerSession.query.filter(
            TimerSession.user_id == _DEFAULT_USER_ID,
            TimerSession.status.in_(["active", "paused"]),
        )
        .order_by(TimerSession.start_time.desc())
        .first()
    )
    if not session:
        return jsonify({"error": "No active timer session"}), 404

    now = datetime.utcnow()
    session.end_time = now
    elapsed = data.get("actual_seconds", int((now - session.start_time).total_seconds()))
    session.actual_seconds = elapsed
    session.status = "completed"

    # Create activity log entry
    task_info = ""
    if session.task_id:
        task = Task.query.get(session.task_id)
        if task:
            task_info = f" on «{task.title}»"
    log_entry = ActivityLog(
        user_id=_DEFAULT_USER_ID,
        action_type="timer_completed",
        description=f"Timer completed{task_info} ({_format_duration(elapsed)})",
        related_object_type="task" if session.task_id else None,
        related_object_id=session.task_id,
    )
    db.session.add(log_entry)
    db.session.commit()

    return jsonify(
        {
            "id": session.id,
            "actual_seconds": elapsed,
            "status": session.status,
        }
    )


@dashboard_bp.route("/api/timer/status")
def api_timer_status():
    """Return the current active timer session, if any."""
    session = (
        TimerSession.query.filter(
            TimerSession.user_id == _DEFAULT_USER_ID,
            TimerSession.status.in_(["active", "paused"]),
        )
        .order_by(TimerSession.start_time.desc())
        .first()
    )
    if not session:
        return jsonify({"active": False})

    elapsed = int((datetime.utcnow() - session.start_time).total_seconds())
    return jsonify(
        {
            "active": True,
            "id": session.id,
            "task_id": session.task_id,
            "duration": session.duration_seconds,
            "elapsed": elapsed,
            "remaining": max(0, session.duration_seconds - elapsed),
            "status": session.status,
            "start_time": session.start_time.isoformat(),
        }
    )
