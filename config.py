"""
BusNotify - Application Configuration
Simple, beginner-friendly configuration for Flask and MySQL 8+.
"""
import os
import socket
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def get_active_mysql_port(host, primary_port):
    """
    Checks if primary_port is reachable; if not, checks standard 3306 or 33061.
    Ensures seamless connectivity on local development machines.
    """
    candidates = [int(primary_port)]
    for p in [3306, 33061]:
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
    SECRET_KEY = os.getenv("SECRET_KEY", "busnotify-secret-key-2026")
    
    # Database Configuration - MySQL 8+ ONLY
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "N@ids2024")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    RAW_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "mysql94")

    # Connect to MySQL
    active_port = get_active_mysql_port(DB_HOST, RAW_PORT)
    encoded_password = urllib.parse.quote_plus(DB_PASSWORD) if DB_PASSWORD else ""
    auth_part = f"{DB_USER}:{encoded_password}" if encoded_password else DB_USER

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"mysql+pymysql://{auth_part}@{DB_HOST}:{active_port}/{DB_NAME}?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 280,
        "pool_pre_ping": True,
    }

    # Uploads & app settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload
    UPLOAD_FOLDER = BASE_DIR / "data"
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
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
