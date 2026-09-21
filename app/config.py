"""
BusNotify - Configuration module
Supports MySQL 8+ with automated connection fallback and .env management.
"""
import os
import socket
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def get_active_mysql_port(host, primary_port):
    """
    Checks if primary_port is reachable; if not, checks standard 3306 or 33061.
    """
    candidates = [int(primary_port)]
    for p in [33061, 3306]:
        if p not in candidates:
            candidates.append(p)

    for p in candidates:
        try:
            with socket.create_connection((host, p), timeout=0.5):
                return p
        except (socket.timeout, ConnectionRefusedError, OSError):
            continue
    return int(primary_port)


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "busnotify-production-transit-flow-secret-key-2026")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "busnotify-jwt-secret-key-2026")
    
    # Database configuration
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    RAW_PORT = os.getenv("DB_PORT", "33061")
    DB_NAME = os.getenv("DB_NAME", "busnotify")
    USE_SQLITE = os.getenv("USE_SQLITE", "false").lower() in ("true", "1", "yes")

    if USE_SQLITE:
        SQLALCHEMY_DATABASE_URI = os.getenv(
            "DATABASE_URL",
            f"sqlite:///{BASE_DIR / 'busnotify.db'}"
        )
    else:
        active_port = get_active_mysql_port(DB_HOST, RAW_PORT)
        encoded_password = urllib.parse.quote_plus(DB_PASSWORD) if DB_PASSWORD else ""
        if encoded_password:
            auth_part = f"{DB_USER}:{encoded_password}"
        else:
            auth_part = DB_USER

        SQLALCHEMY_DATABASE_URI = os.getenv(
            "DATABASE_URL",
            f"mysql+pymysql://{auth_part}@{DB_HOST}:{active_port}/{DB_NAME}?charset=utf8mb4"
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 280,
        "pool_pre_ping": True,
    }

    # Application settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    UPLOAD_FOLDER = BASE_DIR / "uploads"
    TIMEZONE = "Asia/Kolkata"
    DEBUG = False
    TESTING = False


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
