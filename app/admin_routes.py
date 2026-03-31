# Import datetime to compare appointment times (past vs future)
from datetime import datetime

# Flask utilities for routing, templates, form data, sessions, and redirects
from flask import redirect, render_template, request, session, url_for

# SQLAlchemy helpers for building more complex queries
from sqlalchemy import or_

# joinedload allows eager loading of related data to avoid extra queries
from sqlalchemy.orm import joinedload

# Custom decorator used to restrict routes to specific roles (admin here)
from .decorators import require_role

# Database instance used for committing changes
from .extensions import db

# Database models used in this file
from .models import Account, Appointment


# This function registers all admin routes to the Flask app
def init_app(app):

    # -----------------------------
    # ADMIN DASHBOARD
    # -----------------------------
    @app.route("/admin")
    @require_role("admin")  # Only admins can access this route
    def admin_dashboard():

        # Total number of accounts in the system
        total_accounts = Account.query.count()

        # Number of active accounts (not disabled)
        active_accounts = Account.query.filter_by(is_active=True).count()

        # Get the currently logged-in admin user
        me = Account.query.get(session["account_id"]) if session.get("account_id") else None

        # Load the 20 most recent appointments
        # joinedload loads the associated user in the same query (performance optimization)
        appointments = Appointment.query.options(joinedload(Appointment.user)) \
            .order_by(Appointment.start_at.desc()) \
            .limit(20) \
            .all()

        # Render the admin dashboard page
        return render_template(
            "admin_dashboard.html",
            total_accounts=total_accounts,
            active_accounts=active_accounts,
            appointments=appointments,
            me=me,
        )


    # -----------------------------
    # ADMIN ACCOUNT MANAGEMENT
    # -----------------------------
    @app.route("/admin/accounts")
    @require_role("admin")
    def admin_accounts():

        # Get optional search query from URL parameters
        q = request.args.get("q", "").strip().lower()

        # Start with base query for accounts
        query = Account.query

        # If a search query exists, filter accounts by email, role, or name
        if q:
            query = query.filter(
                or_(
                    Account.email.ilike(f"%{q}%"),
                    Account.role.ilike(f"%{q}%"),
                    Account.first_name.ilike(f"%{q}%"),
                    Account.last_name.ilike(f"%{q}%"),
                )
            )

        # Retrieve accounts sorted by ID
        accounts = query.order_by(Account.id.asc()).all()

        # Render account management page
        return render_template("admin_accounts.html", accounts=accounts, q=q)


    # -----------------------------
    # ENABLE / DISABLE ACCOUNTS
    # -----------------------------
    @app.route("/admin/accounts/<int:account_id>/toggle", methods=["POST"])
    @require_role("admin")
    def admin_toggle_account(account_id):

        # Prevent admin from disabling their own account
        if session.get("account_id") == account_id:
            return redirect(url_for("admin_accounts"))

        # Retrieve the account or return 404 if it doesn't exist
        account = Account.query.get_or_404(account_id)

        # Toggle account active state
        account.is_active = not account.is_active

        # Save change to database
        db.session.commit()

        return redirect(url_for("admin_accounts"))


    # -----------------------------
    # CHANGE ACCOUNT ROLE
    # -----------------------------
    @app.route("/admin/accounts/<int:account_id>/role", methods=["POST"])
    @require_role("admin")
    def admin_update_role(account_id):

        # Prevent admin from changing their own role accidentally
        if session.get("account_id") == account_id:
            return redirect(url_for("admin_accounts"))

        # Get new role from submitted form
        new_role = (request.form.get("role") or "").strip().lower()

        # Validate role value
        if new_role not in ("user", "business", "admin"):
            return redirect(url_for("admin_accounts"))

        # Update role in database
        account = Account.query.get_or_404(account_id)
        account.role = new_role
        db.session.commit()

        return redirect(url_for("admin_accounts"))


    # -----------------------------
    # VIEW UPCOMING APPOINTMENTS
    # -----------------------------
    @app.route("/admin/appointments")
    @require_role("admin")
    def admin_appointments():

        # Optional search filter
        q = request.args.get("q", "").strip().lower()

        # Base query: future appointments only
        query = Appointment.query.options(joinedload(Appointment.user)) \
            .filter(Appointment.start_at >= datetime.now())

        # Apply search filter if provided
        if q:
            query = query.join(Account, Account.id == Appointment.user_id).filter(
                or_(
                    Account.email.ilike(f"%{q}%"),
                    Account.first_name.ilike(f"%{q}%"),
                    Account.last_name.ilike(f"%{q}%"),
                )
            )

        # Order appointments chronologically
        appointments = query.order_by(Appointment.start_at.asc()).all()

        # Group appointments by day to make the UI easier to read
        grouped_appointments = {}
        for appt in appointments:
            day = appt.start_at.date()
            grouped_appointments.setdefault(day, []).append(appt)

        # Render page showing grouped appointments
        return render_template(
            "admin_appointments.html",
            grouped_appointments=grouped_appointments,
            q=q
        )


    # -----------------------------
    # VIEW PAST APPOINTMENTS (ARCHIVE)
    # -----------------------------
    @app.route("/admin/appointments/archive")
    @require_role("admin")
    def admin_appointments_archive():

        # Optional search filter
        q = request.args.get("q", "").strip().lower()

        # Query only past appointments
        query = Appointment.query.options(joinedload(Appointment.user)) \
            .filter(Appointment.start_at < datetime.now())

        # Apply search filtering
        if q:
            query = query.join(Account, Account.id == Appointment.user_id).filter(
                or_(
                    Account.email.ilike(f"%{q}%"),
                    Account.first_name.ilike(f"%{q}%"),
                    Account.last_name.ilike(f"%{q}%"),
                )
            )

        # Order by newest past appointment first
        appointments = query.order_by(Appointment.start_at.desc()).all()

        return render_template(
            "admin_appointments_archive.html",
            appointments=appointments,
            q=q
        )


    # -----------------------------
    # CANCEL AN APPOINTMENT
    # -----------------------------
    @app.route("/admin/appointments/<int:appointment_id>/cancel", methods=["POST"])
    @require_role("admin")
    def admin_cancel_appointment(appointment_id):

        # Find appointment or return 404
        appt = Appointment.query.get_or_404(appointment_id)

        # If appointment is already in the past, redirect to archive instead
        if appt.start_at < datetime.now():
            return redirect(url_for("admin_appointments_archive"))

        # Delete the appointment from the database
        db.session.delete(appt)
        db.session.commit()

        # Redirect back to the upcoming appointments page
        return redirect(url_for("admin_appointments"))