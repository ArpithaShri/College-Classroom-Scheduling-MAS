"""Configuration settings for College Classroom Scheduling System (MAS)."""

import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-scheduling-mas")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # SQLite Database URI
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'scheduling.db')}"
    )

    # XMPP / SPADE Server Configuration (Default to local or public XMPP server)
    XMPP_SERVER = os.environ.get("XMPP_SERVER", "localhost")
    XMPP_PASSWORD = os.environ.get("XMPP_PASSWORD", "mas_password_2026")


class DevelopmentConfig(Config):
    """Development configuration."""

    DEBUG = True


class TestingConfig(Config):
    """Testing configuration."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    """Production configuration."""

    DEBUG = False


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
