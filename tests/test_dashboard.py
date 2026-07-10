"""Tests for TimerSession, ActivityLog models and dashboard routes."""

from datetime import datetime, timezone, timedelta

import pytest

from src.database import db
from src.models.log import ActivityLog
from src.models.timer import TimerSession
from src.models.base import Project, Subproject, Task


# ── Model Tests ──


class TestTimerSessionModel:
    """TimerSession model creation and defaults."""

    def test_create_timer_session(self, app):
        """A TimerSession can be created with default values."""
        with app.app_context():
            session = TimerSession(
                user_id=1,
                duration_seconds=1500,
                status="active",
            )
            db.session.add(session)
            db.session.commit()

            assert session.id is not None
            assert session.user_id == 1
            assert session.duration_seconds == 1500
            assert session.status == "active"
            assert session.actual_seconds == 0
            assert session.start_time is not None
            assert session.end_time is None
            assert session.task_id is None

    def test_timer_session_with_task(self, app):
        """A TimerSession can be linked to a Task."""
        with app.app_context():
            proj = Project(title="Test Project")
            sub = Subproject(title="Test Sub", project=proj)
            task = Task(title="Test Task", subproject=sub)
            db.session.add_all([proj, sub, task])
            db.session.flush()

            session = TimerSession(
                task_id=task.id,
                user_id=1,
                duration_seconds=3000,
                status="active",
            )
            db.session.add(session)
            db.session.commit()

            assert session.task_id == task.id
            assert session.task.title == "Test Task"

    def test_timer_session_repr(self, app):
        """TimerSession __repr__ returns meaningful info."""
        with app.app_context():
            session = TimerSession(user_id=1, status="completed", actual_seconds=120)
            db.session.add(session)
            db.session.commit()
            rep = repr(session)
            assert "TimerSession" in rep
            assert "completed" in rep
            assert "120" in rep


class TestActivityLogModel:
    """ActivityLog model creation and defaults."""

    def test_create_activity_log(self, app):
        """An ActivityLog entry can be created."""
        with app.app_context():
            entry = ActivityLog(
                user_id=1,
                action_type="task_completed",
                description="Test task completed",
            )
            db.session.add(entry)
            db.session.commit()

            assert entry.id is not None
            assert entry.user_id == 1
            assert entry.action_type == "task_completed"
            assert entry.description == "Test task completed"
            assert entry.created_at is not None
            assert entry.related_object_type is None
            assert entry.related_object_id is None

    def test_activity_log_with_relation(self, app):
        """ActivityLog can store related object references."""
        with app.app_context():
            entry = ActivityLog(
                user_id=1,
                action_type="timer_completed",
                description="Timer done",
                related_object_type="task",
                related_object_id=42,
            )
            db.session.add(entry)
            db.session.commit()

            assert entry.related_object_type == "task"
            assert entry.related_object_id == 42

    def test_activity_log_repr(self, app):
        """ActivityLog __repr__ returns meaningful info."""
        with app.app_context():
            entry = ActivityLog(user_id=1, action_type="task_created")
            db.session.add(entry)
            db.session.commit()
            rep = repr(entry)
            assert "ActivityLog" in rep
            assert "task_created" in rep


# ── Route Tests ──


class TestDashboardPage:
    """GET /dashboard renders the main page."""

    def test_dashboard_returns_200(self, client):
        """Dashboard page loads successfully."""
        resp = client.get("/dashboard")
        assert resp.status_code == 200

    def test_dashboard_contains_blocks(self, client):
        """Dashboard page contains all three block headings."""
        resp = client.get("/dashboard")
        html = resp.data.decode()
        assert "Projects" in html
        assert "Workflow" in html
        assert "Session" in html  # Block 3 heading


class TestDashboardAPI:
    """Dashboard API endpoints."""

    def test_api_projects_empty(self, client):
        """GET /api/projects returns empty list when no projects exist."""
        resp = client.get("/api/projects")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_api_projects_with_data(self, client, app):
        """GET /api/projects returns project data."""
        with app.app_context():
            proj = Project(title="API Test Project")
            sub = Subproject(title="Sub", project=proj)
            task = Task(title="Task", subproject=sub)
            db.session.add_all([proj, sub, task])
            db.session.commit()

        resp = client.get("/api/projects")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "API Test Project"
        assert data[0]["task_count"] == 1
        assert data[0]["completed_count"] == 0

    def test_api_tasks_empty(self, client):
        """GET /api/tasks returns empty list when no tasks exist."""
        resp = client.get("/api/tasks")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_api_tasks_with_data(self, client, app):
        """GET /api/tasks returns task data with project/subproject info."""
        with app.app_context():
            proj = Project(title="P1")
            sub = Subproject(title="S1", project=proj)
            task = Task(title="T1", subproject=sub, priority=3)
            db.session.add_all([proj, sub, task])
            db.session.commit()

        resp = client.get("/api/tasks")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["title"] == "T1"
        assert data[0]["project"] == "P1"
        assert data[0]["subproject"] == "S1"
        assert data[0]["priority"] == 3

    def test_api_stats(self, client):
        """GET /api/stats returns valid stats structure."""
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "tasks_completed_today" in data
        assert "time_tracked_today" in data
        assert "current_streak" in data
        assert "total_tasks" in data

    def test_api_log_empty(self, client):
        """GET /api/log returns empty list when no activity."""
        resp = client.get("/api/log")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_api_log_with_entry(self, client, app):
        """GET /api/log returns activity log entries."""
        with app.app_context():
            entry = ActivityLog(
                user_id=1,
                action_type="task_completed",
                description="Test completed",
            )
            db.session.add(entry)
            db.session.commit()

        resp = client.get("/api/log")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["action_type"] == "task_completed"
        assert data[0]["description"] == "Test completed"

    def test_api_timer_start(self, client):
        """POST /api/timer/start creates a timer session."""
        resp = client.post(
            "/api/timer/start",
            json={"duration": 1500},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["duration"] == 1500
        assert data["status"] == "active"

    def test_api_timer_start_with_task(self, client, app):
        """POST /api/timer/start with task_id links to task."""
        with app.app_context():
            proj = Project(title="P")
            sub = Subproject(title="S", project=proj)
            task = Task(title="Timer Task", subproject=sub)
            db.session.add_all([proj, sub, task])
            db.session.commit()
            task_id = task.id

        resp = client.post(
            "/api/timer/start",
            json={"task_id": task_id, "duration": 600},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["task_id"] == task_id
        assert data["duration"] == 600

    def test_api_timer_stop_no_active(self, client):
        """POST /api/timer/stop returns 404 when no active session."""
        resp = client.post("/api/timer/stop")
        assert resp.status_code == 404

    def test_api_timer_start_then_stop(self, client):
        """Starting and then stopping a timer works correctly."""
        # Start
        start_resp = client.post("/api/timer/start", json={"duration": 1500})
        assert start_resp.status_code == 201
        session_id = start_resp.get_json()["id"]

        # Stop
        stop_resp = client.post("/api/timer/stop", json={"actual_seconds": 100})
        assert stop_resp.status_code == 200
        stop_data = stop_resp.get_json()
        assert stop_data["id"] == session_id
        assert stop_data["status"] == "completed"
        assert stop_data["actual_seconds"] == 100

    def test_api_timer_status_no_active(self, client):
        """GET /api/timer/status returns active=False when no timer running."""
        resp = client.get("/api/timer/status")
        assert resp.status_code == 200
        assert resp.get_json() == {"active": False}

    def test_api_timer_status_active(self, client):
        """GET /api/timer/status returns active timer data."""
        client.post("/api/timer/start", json={"duration": 3000})
        resp = client.get("/api/timer/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["active"] is True
        assert data["duration"] == 3000
        assert data["status"] == "active"
        assert "remaining" in data
        assert "elapsed" in data