"""Phase 1 Foundation Setup & Import Tests.

Verifies that:
1. Python version meets requirements.
2. SPADE framework imports cleanly with core classes.
3. Flask backend framework imports cleanly.
4. SQLAlchemy / Flask-SQLAlchemy imports cleanly.
5. Project configuration loads correctly across environments.
6. Key project directories exist.
"""

import sys
import os
import pytest


def test_python_version():
    """Verify that Python 3.10+ is running."""
    major, minor = sys.version_info.major, sys.version_info.minor
    assert (major, minor) >= (3, 10), f"Python version must be >= 3.10, found {major}.{minor}"


def test_spade_import():
    """Verify that SPADE and its core MAS components import successfully."""
    import spade
    from spade.agent import Agent
    from spade.behaviour import CyclicBehaviour, OneShotBehaviour, PeriodicBehaviour
    from spade.message import Message
    from spade.template import Template

    assert spade is not None
    assert Agent is not None
    assert CyclicBehaviour is not None
    assert OneShotBehaviour is not None
    assert PeriodicBehaviour is not None
    assert Message is not None
    assert Template is not None


def test_flask_import():
    """Verify that Flask imports and initializes a minimal test app."""
    import flask
    from flask import Flask

    assert flask is not None
    app = Flask("test_app")
    assert app.name == "test_app"


def test_sqlalchemy_import():
    """Verify that SQLAlchemy and Flask-SQLAlchemy import successfully."""
    import sqlalchemy
    import flask_sqlalchemy
    from flask_sqlalchemy import SQLAlchemy

    assert sqlalchemy is not None
    assert flask_sqlalchemy is not None
    db = SQLAlchemy()
    assert db is not None


def test_config_import():
    """Verify that project config loads properly."""
    from config import Config, DevelopmentConfig, TestingConfig, ProductionConfig, config_by_name

    assert Config.SECRET_KEY is not None
    assert TestingConfig.TESTING is True
    assert "development" in config_by_name
    assert "testing" in config_by_name
    assert "production" in config_by_name


def test_project_structure():
    """Verify that required directory structure exists."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    required_paths = [
        "README.md",
        ".gitignore",
        "requirements.txt",
        "config.py",
        "run.py",
        "app",
        "app/__init__.py",
        "app/models.py",
        "app/routes",
        "app/routes/__init__.py",
        "app/static",
        "app/templates",
        "agents",
        "agents/__init__.py",
        "scheduler",
        "scheduler/__init__.py",
        "database",
        "database/__init__.py",
        "tests",
        "tests/__init__.py",
        "docs",
    ]

    for rel_path in required_paths:
        full_path = os.path.join(base_dir, rel_path)
        assert os.path.exists(full_path), f"Missing required path: {rel_path}"
