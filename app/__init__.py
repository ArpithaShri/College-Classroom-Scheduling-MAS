"""Flask Application Package Factory."""

import os
from flask import Flask

from config import config_by_name
from database.db import db


def create_app(config_name: str = "development") -> Flask:
    """Application factory for the College Classroom Scheduling System."""
    app = Flask(__name__)

    # Load configuration
    cfg = config_by_name.get(config_name, config_by_name["default"])
    app.config.from_object(cfg)

    # Ensure instance directory exists for SQLite storage
    os.makedirs(app.instance_path, exist_ok=True)

    # Initialize extensions
    db.init_app(app)

    return app
