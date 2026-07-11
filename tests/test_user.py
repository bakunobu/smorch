"""Tests for user/profile routes and API endpoints."""

import pytest

from src.database import db
from src.models import ActivityLog, TimerSession, User


class TestProfilePage:
    """GET /profile renders the profile page."""

    def test_profile_returns_200(self, client):
        """Profile page loads successfully."""
        resp = client.get("/profile")
        assert resp.status_code == 200

    def test_profile_contains_blocks(self, client):
        """Profile page contains edit form and statistics sections."""
        resp = client.get("/profile")
        html = resp.data.decode()
        assert "Edit Profile" in html
        assert "Your Statistics" in html
        assert "Recent Activity" in html

    def test_profile_creates_default_user(self, client, app):
        """If no user exists, profile page creates the default user."""
        # Make the request first — the route creates the user
        client.get("/profile")

        with app.app_context():
            user = db.session.get(User, 1)
            assert user is not None
            assert user.name == "Default User"
            assert user.nickname == "default"

    def test_profile_shows_user_data(self, client, app):
        """Profile page displays user name and nickname."""
        # Create user first, then check the page shows the data
        with app.app_context():
            user_ = User(
                id=1,
                name="Alice",
                nickname="alice",
                email="alice@test.com",
                password_hash="",
            )
            db.session.add(user_)
            db.session.commit()

        resp = client.get("/profile")
        html = resp.data.decode()
        assert "Alice" in html
        assert "alice" in html
        assert "Member since" in html

        resp = client.get("/profile")
        html = resp.data.decode()
        assert "Alice" in html
        assert "alice" in html
        assert "Member since" in html


class TestProfileAPI:
    """GET/PUT /api/user/profile endpoints."""

    def test_api_profile_get(self, client):
        """GET /api/user/profile returns user data."""
        resp = client.get("/api/user/profile")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "name" in data
        assert "nickname" in data
        assert "email" in data
        assert "created_dttm" in data

    def test_api_profile_update(self, client, app):
        """PUT /api/user/profile updates user fields."""
        resp = client.put(
            "/api/user/profile",
            json={"name": "Bob", "nickname": "bobby", "email": "bob@test.com"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["name"] == "Bob"
        assert data["nickname"] == "bobby"
        assert data["email"] == "bob@test.com"

        # Verify persisted
        with app.app_context():
            user = User.query.get(1)
            assert user.name == "Bob"
            assert user.nickname == "bobby"
            assert user.email == "bob@test.com"

    def test_api_profile_update_missing_name(self, client):
        """PUT /api/user/profile returns 400 when name is missing."""
        resp = client.put(
            "/api/user/profile",
            json={"name": "", "nickname": "bobby", "email": "bob@test.com"},
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_api_profile_update_missing_nickname(self, client):
        """PUT /api/user/profile returns 400 when nickname is missing."""
        resp = client.put(
            "/api/user/profile",
            json={"name": "Bob", "nickname": "", "email": "bob@test.com"},
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_api_profile_update_missing_email(self, client):
        """PUT /api/user/profile returns 400 when email is missing."""
        resp = client.put(
            "/api/user/profile",
            json={"name": "Bob", "nickname": "bobby", "email": ""},
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()


class TestUserStatsAPI:
    """GET /api/user/stats returns aggregated statistics."""

    def test_api_user_stats_structure(self, client):
        """GET /api/user/stats returns all expected fields."""
        resp = client.get("/api/user/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "tasks_completed_total" in data
        assert "tasks_completed_today" in data
        assert "time_tracked_total" in data
        assert "time_tracked_today" in data
        assert "current_streak" in data
        assert "timer_sessions_total" in data
        assert "total_tasks" in data

    def test_api_user_stats_initial_values(self, client):
        """GET /api/user/stats returns zero values when no data exists."""
        resp = client.get("/api/user/stats")
        data = resp.get_json()
        assert data["tasks_completed_total"] == 0
        assert data["tasks_completed_today"] == 0
        assert data["current_streak"] == 0
        assert data["timer_sessions_total"] == 0
        assert data["total_tasks"] == 0

    def test_api_user_stats_with_timer_data(self, client, app):
        """GET /api/user/stats reflects timer session data."""
        with app.app_context():
            session = TimerSession(
                user_id=1,
                duration_seconds=1500,
                actual_seconds=1200,
                status="completed",
            )
            db.session.add(session)
            db.session.commit()

        resp = client.get("/api/user/stats")
        data = resp.get_json()
        assert data["timer_sessions_total"] == 1
        assert data["time_tracked_total_seconds"] == 1200
        assert "20m" in data["time_tracked_total"]  # 1200s = 20m

    def test_api_user_stats_with_activity_log(self, client, app):
        """GET /api/user/stats does NOT include activity log in stats."""
        with app.app_context():
            entry = ActivityLog(
                user_id=1,
                action_type="task_completed",
                description="Test task",
            )
            db.session.add(entry)
            db.session.commit()

        # Activity log doesn't affect stats, just verify no crash
        resp = client.get("/api/user/stats")
        assert resp.status_code == 200


class TestProfileNavLink:
    """The nav link to /profile already exists in base.html."""

    def test_profile_nav_link_in_base(self, client):
        """The base template contains a link to /profile."""
        resp = client.get("/dashboard")
        html = resp.data.decode()
        assert '/profile' in html
        assert 'Profile' in html