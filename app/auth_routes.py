# Flask utilities for rendering templates, handling requests, sessions, and redirects
from flask import render_template, request, redirect, url_for, session

# Werkzeug utilities for securely hashing and verifying passwords
from werkzeug.security import check_password_hash, generate_password_hash

# Database instance for saving new users
from .extensions import db

# Account model representing users in the database
from .models import Account


# Register authentication-related routes with the Flask app
def init_app(app):

    # -----------------------------
    # HOME ROUTE
    # -----------------------------
    @app.route("/")
    def home():
        # Redirect root URL to login page
        return redirect(url_for("login"))


    # -----------------------------
    # LOGIN
    # -----------------------------
    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None

        # Handle form submission
        if request.method == "POST":

            # Get and normalize user input
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            # Look up active account with matching email
            account = Account.query.filter_by(email=email, is_active=True).first()

            # Verify password hash matches stored password
            if account and check_password_hash(account.password_hash, password):

                # Clear any previous session data
                session.clear()

                # Store user identity and role in session
                session["role"] = account.role
                session["account_id"] = account.id

                # Redirect user based on role (role-based navigation)
                if account.role == "admin":
                    return redirect(url_for("admin_dashboard"))
                if account.role == "business":
                    return redirect(url_for("business_dashboard"))

                # Default: normal user goes to booking page
                return redirect(url_for("book"))

            # If login fails, show error message
            error = "Invalid email or password."

        # Render login page (GET request or failed login)
        return render_template("login.html", error=error)


    # -----------------------------
    # REGISTER NEW USER
    # -----------------------------
    @app.route("/register", methods=["GET", "POST"])
    def register():
        error = None

        if request.method == "POST":

            # Collect and clean user input
            first_name = request.form.get("first_name", "").strip()
            last_name = request.form.get("last_name", "").strip()
            phone = request.form.get("phone", "").strip() or None
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            # Basic validation: require first and last name
            if not first_name or not last_name:
                error = "First and last name are required."
                return render_template("register.html", error=error)

            # Check if email is already registered
            existing = Account.query.filter_by(email=email).first()
            if existing:
                error = "That email is already registered. Please log in."
                return render_template("register.html", error=error)

            # Create new user account
            new_account = Account(
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                email=email,
                # Store hashed password (never store plain text passwords)
                password_hash=generate_password_hash(password),
                role="user",  # Default role for new accounts
                is_active=True,
            )

            # Save to database
            db.session.add(new_account)
            db.session.commit()

            # Automatically log user in after registration
            session.clear()
            session["account_id"] = new_account.id
            session["role"] = new_account.role

            # Redirect to booking page
            return redirect(url_for("book"))

        # Render registration form
        return render_template("register.html", error=error)


    # -----------------------------
    # LOGOUT
    # -----------------------------
    @app.route("/logout")
    def logout():

        # Clear all session data (log user out)
        session.clear()

        # Redirect back to login page
        return redirect(url_for("login"))