# Import datetime utilities for working with dates and times
from datetime import datetime, time

# Flask utilities for rendering templates, handling requests, and redirects
from flask import redirect, render_template, request, url_for

# Used to efficiently load related user data with appointments
from sqlalchemy.orm import joinedload

# Custom helpers: role-based access control and time parsing
from .decorators import parse_time_or_none, require_role

# Database instance for committing changes
from .extensions import db

# Database models used in this module
from .models import Appointment, AvailabilityOverride, BusinessHour


# Register all business-related routes to the Flask app
def init_app(app):

    # -----------------------------
    # BUSINESS DASHBOARD (WEEKLY HOURS)
    # -----------------------------
    @app.route("/business", methods=["GET", "POST"])
    @require_role("business")  # Only business users can access this page
    def business_dashboard():

        # Names of days for display in UI
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        # Handle form submission (updating weekly hours)
        if request.method == "POST":

            # Loop through all 7 days of the week
            for i in range(7):
                closed = request.form.get(f"closed_{i}") == "on"
                start_str = request.form.get(f"start_{i}", "")
                end_str = request.form.get(f"end_{i}", "")

                # Get existing row or create a new one if missing
                row = BusinessHour.query.filter_by(weekday=i).first()
                if not row:
                    row = BusinessHour(
                        weekday=i,
                        start_time=time(9, 0),
                        end_time=time(17, 0),
                        is_closed=False,
                    )
                    db.session.add(row)

                # Update closed/open status
                if closed:
                    row.is_closed = True
                else:
                    row.is_closed = False

                    # Parse input times; fallback to existing/default values
                    row.start_time = parse_time_or_none(start_str) or row.start_time or time(9, 0)
                    row.end_time = parse_time_or_none(end_str) or row.end_time or time(17, 0)

            # Save all updates at once
            db.session.commit()

            # Redirect to refresh page and prevent resubmission
            return redirect(url_for("business_dashboard"))

        # -----------------------------
        # LOAD CURRENT HOURS FOR DISPLAY
        # -----------------------------
        rows = {bh.weekday: bh for bh in BusinessHour.query.all()}
        hours = []

        # Ensure all 7 days exist in database
        for i in range(7):
            bh = rows.get(i)
            if not bh:
                # Default: weekends closed, weekdays open
                default_closed = i in (5, 6)

                bh = BusinessHour(
                    weekday=i,
                    start_time=time(9, 0),
                    end_time=time(17, 0),
                    is_closed=default_closed,
                )
                db.session.add(bh)
                db.session.commit()

            # Prepare data for template
            hours.append({
                "weekday": i,
                "name": day_names[i],
                "row": bh
            })

        return render_template("business_dashboard.html", hours=hours)


    # -----------------------------
    # DATE-SPECIFIC OVERRIDES
    # -----------------------------
    @app.route("/business/overrides", methods=["GET", "POST"])
    @require_role("business")
    def business_overrides():
        error = None

        if request.method == "POST":

            # Get form input
            date_str = request.form.get("date", "").strip()
            closed = request.form.get("is_closed") == "on"
            start_str = request.form.get("start_time", "").strip()
            end_str = request.form.get("end_time", "").strip()

            # Validate date input
            try:
                override_date = datetime.fromisoformat(date_str).date()
            except ValueError:
                error = "Please select a valid date."
                overrides = AvailabilityOverride.query.order_by(AvailabilityOverride.date.asc()).all()
                return render_template("business_overrides.html", overrides=overrides, error=error)

            # Get or create override row for that date
            row = AvailabilityOverride.query.filter_by(date=override_date).first()
            if not row:
                row = AvailabilityOverride(date=override_date)
                db.session.add(row)

            # Handle closed day override
            if closed:
                row.is_closed = True
                row.start_time = None
                row.end_time = None
            else:
                # Validate and set custom hours
                st = parse_time_or_none(start_str)
                et = parse_time_or_none(end_str)

                if st is None or et is None:
                    error = "Start and end times are required unless the day is closed."
                elif et <= st:
                    error = "End time must be after start time."
                else:
                    row.is_closed = False
                    row.start_time = st
                    row.end_time = et

            # Rollback if validation failed, otherwise commit changes
            if error:
                db.session.rollback()
            else:
                db.session.commit()
                return redirect(url_for("business_overrides"))

        # Load all overrides sorted by date
        overrides = AvailabilityOverride.query.order_by(AvailabilityOverride.date.asc()).all()
        return render_template("business_overrides.html", overrides=overrides, error=error)


    # -----------------------------
    # DELETE AN OVERRIDE
    # -----------------------------
    @app.route("/business/overrides/<int:override_id>/delete", methods=["POST"])
    @require_role("business")
    def delete_override(override_id):

        # Find override or return 404
        row = AvailabilityOverride.query.get_or_404(override_id)

        # Delete and save
        db.session.delete(row)
        db.session.commit()

        return redirect(url_for("business_overrides"))


    # -----------------------------
    # VIEW UPCOMING APPOINTMENTS
    # -----------------------------
    @app.route("/business/appointments")
    @require_role("business")
    def business_appointments():

        # Query upcoming scheduled appointments
        appointments = (
            Appointment.query.options(joinedload(Appointment.user))
            .filter(
                Appointment.status == "scheduled",
                Appointment.start_at >= datetime.now()
            )
            .order_by(Appointment.start_at.asc())
            .all()
        )

        # Group appointments by day for easier UI display
        grouped_appointments = {}
        for appt in appointments:
            day = appt.start_at.date()
            grouped_appointments.setdefault(day, []).append(appt)

        return render_template(
            "business_appointments.html",
            grouped_appointments=grouped_appointments
        )


    # -----------------------------
    # VIEW PAST APPOINTMENTS (ARCHIVE)
    # -----------------------------
    @app.route("/business/appointments/archive")
    @require_role("business")
    def business_appointments_archive():

        # Query past appointments
        appointments = (
            Appointment.query.options(joinedload(Appointment.user))
            .filter(
                Appointment.status == "scheduled",
                Appointment.start_at < datetime.now()
            )
            .order_by(Appointment.start_at.desc())
            .all()
        )

        return render_template(
            "business_appointments_archive.html",
            appointments=appointments
        )


    # -----------------------------
    # CANCEL APPOINTMENT
    # -----------------------------
    @app.route("/business/appointments/<int:appointment_id>/cancel", methods=["GET", "POST"])
    @require_role("business")
    def business_cancel_appointment(appointment_id):

        # Prevent cancellation via GET request (force POST for safety)
        if request.method == "GET":
            return redirect(url_for("business_appointments"))

        # Retrieve appointment or return 404
        appt = Appointment.query.get_or_404(appointment_id)

        # If appointment is already in the past, redirect to archive
        if appt.start_at < datetime.now():
            return redirect(url_for("business_appointments_archive"))

        # Delete appointment from database
        db.session.delete(appt)
        db.session.commit()

        return redirect(url_for("business_appointments"))