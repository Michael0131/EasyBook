# Import OS module to access environment variables (used to detect production mode)
import os

# Flask utility to abort requests with HTTP status codes
from flask import abort

# Used to securely hash passwords before storing them
from werkzeug.security import generate_password_hash

# Database instance for committing changes
from .extensions import db

# Account model representing users in the system
from .models import Account


# Register development-only utility routes
def init_app(app):

    # -----------------------------
    # DEBUG: WHO IS CURRENT USER
    # -----------------------------
    @app.route("/whoami")
    def whoami():
        """
        Returns basic information about the currently logged-in user.

        Useful for debugging authentication and session issues.

        Disabled in production for security reasons.
        """

        # Prevent access in production environment
        if os.getenv("FLASK_ENV") == "production":
            abort(404)

        # Import session here to avoid unnecessary global import
        from flask import session

        # Return current session data (role + account ID)
        return {
            "role": session.get("role"),
            "account_id": session.get("account_id")
        }


    # -----------------------------
    # DEV TOOL: DATABASE SEEDING
    # -----------------------------
    @app.route("/seed")
    def seed():
        """
        Seeds the database with default admin and business accounts.

        Only runs if the database is empty.
        Disabled in production to prevent unauthorized data creation.
        """

        # Prevent accidental execution in production
        if os.getenv("FLASK_ENV") == "production":
            abort(404)

        # If accounts already exist, do not seed again
        if Account.query.first():
            return "Seed already done."

        # Create default admin account
        admin = Account(
            first_name="Admin",
            last_name="User",
            phone=None,
            email="admin@easybook.com",
            # Always store hashed passwords, never plain text
            password_hash=generate_password_hash("password123"),
            role="admin",
            is_active=True,
        )

        # Create default business account
        business = Account(
            first_name="Business",
            last_name="Owner",
            phone=None,
            email="business@easybook.com",
            password_hash=generate_password_hash("business123"),
            role="business",
            is_active=True,
        )

        # Save both accounts to the database
        db.session.add(admin)
        db.session.add(business)
        db.session.commit()

        return "Seeded admin and business."