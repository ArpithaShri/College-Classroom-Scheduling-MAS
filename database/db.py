"""Database instance and session management.

Provides Flask-SQLAlchemy extension instance and standalone SQLite session helpers.
"""

from typing import Optional
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, declarative_base

from config import Config

# Flask-SQLAlchemy extension instance
db = SQLAlchemy()

# Standalone declarative base for direct SQLAlchemy usage if needed
Base = declarative_base()


def get_engine(database_uri: Optional[str] = None):
    """Create and return a SQLAlchemy engine."""
    uri = database_uri or Config.SQLALCHEMY_DATABASE_URI
    return create_engine(uri, echo=False)


def get_session_factory(database_uri: Optional[str] = None):
    """Create and return a scoped sessionmaker."""
    engine = get_engine(database_uri)
    return scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))


def init_db(app=None, database_uri: Optional[str] = None):
    """Initialize database tables for the given Flask app or standalone engine."""
    if app:
        db.init_app(app)
        with app.app_context():
            db.create_all()
    else:
        engine = get_engine(database_uri)
        db.metadata.create_all(bind=engine)
