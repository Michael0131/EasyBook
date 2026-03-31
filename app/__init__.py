import os

from dotenv import load_dotenv
from flask import Flask

from .admin_routes import init_app as init_admin_routes
from .auth_routes import init_app as init_auth_routes
from .business_routes import init_app as init_business_routes
from .extensions import db, migrate
from .misc_routes import init_app as init_misc_routes
from .user_routes import init_app as init_user_routes


def create_app():
    load_dotenv()

    app = Flask(__name__, template_folder="../templates")
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "easybook-dev-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///easybook.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    migrate.init_app(app, db)

    # Import models so Flask-Migrate sees metadata.
    from . import models  # noqa: F401

    init_auth_routes(app)
    init_user_routes(app)
    init_business_routes(app)
    init_admin_routes(app)
    init_misc_routes(app)

    return app
