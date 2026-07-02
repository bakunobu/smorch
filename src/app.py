import os

from dotenv import load_dotenv
from flask import Flask

from src.config import config_by_name
from src.database import db, init_db
from src.routes import health_bp

load_dotenv()


def create_app(config_name=None):
    """Application factory."""
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_by_name.get(config_name, config_by_name["default"]))

    # Initialize extensions
    init_db(app)

    # Register blueprints
    app.register_blueprint(health_bp)

    return app
