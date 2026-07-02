import pytest

from src.app import create_app
from src.database import db as _db


@pytest.fixture
def app():
    """Create a test app with an in-memory SQLite database."""
    application = create_app("testing")
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.close()
        _db.drop_all()


@pytest.fixture
def client(app):
    """Test client for the app."""
    return app.test_client()
