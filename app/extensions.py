"""
BusNotify - Extensions module
Initializes SQLAlchemy, Migrate, CORS, etc.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS

db = SQLAlchemy()
migrate = Migrate()
cors = CORS()
