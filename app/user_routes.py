# Import datetime utilities for working with dates and time calculations
from datetime import datetime, timedelta

# Flask utilities for request handling, sessions, redirects, and templates
from flask import abort, redirect, render_template, request, session, url_for

# Custom decorator for role-based access control
from .decorators import require_role

# Database instance for committing changes
from .extensions import db

# Appointment model for querying and creating bookings
from .models import Appointment

# Booking logic helpers (separated for cleaner code and reuse)
from .services.booking_service import (
    APPT_MINUTES,
    build_calendar_data,
    build_slots_for_day,
    get_booking_context,
)


# Register user-related routes
def init_app(app):

    # -----------------------------
    # VIEW USER'S UPCOMING APPOINTMENTS
    # -----------------------------
    @app.route("/my-appointments")
    @require_role("user")
    def my_appointments():

        # Query future scheduled appointments for the logged-in user
        appointments = (
            Appointment.query.filter(
                Appointment.user_id == session.get("account_id"),
                Appointment.status == "scheduled",
                Appointment.start_at >= datetime.now(),
            )
            .order_by(Appointment.start_at.asc())
            .all()
        )

        return render_template("my_appointments.html", appointments=appointments)


    # -----------------------------
    # CANCEL USER APPOINTMENT
    # -----------------------------
    @app.route("/appointments/<int:appointment_id>/cancel", methods=["POST"])
    @require_role("user")
    def cancel_appointment(appointment_id):

        # Retrieve appointment or return 404 if not found
        appt = Appointment.query.get_or_404(appointment_id)

        # Prevent user from cancelling someone else's appointment
        if appt.user_id != session.get("account_id"):
            abort(403)

        # Mark appointment as cancelled (soft delete)
        appt.status = "cancelled"
        db.session.commit()

        return redirect(url_for("my_appointments"))


    # -----------------------------
    # BOOK APPOINTMENT
    # -----------------------------
    @app.route("/book", methods=["GET", "POST"])
    @require_role("user")
    def book():

        error = None

        # Selected date from query string (YYYY-MM-DD)
        selected_date = request.args.get("date")

        # Preload booking-related data (performance optimization)
        context = get_booking_context()
        today = context["today"]
        now_dt = context["now_dt"]
        bh_by_weekday = context["bh_by_weekday"]
        ov_by_date = context["ov_by_date"]
        booked_starts_by_date = context["booked_starts_by_date"]

        # -----------------------------
        # HANDLE BOOKING FORM SUBMISSION
        # -----------------------------
        if request.method == "POST":

            start_str = request.form.get("start_at", "")

            # If no time selected, reload page
            if not start_str:
                return redirect(url_for("book"))

            # Convert string to datetime
            try:
                start_at = datetime.fromisoformat(start_str)
            except ValueError:
                return render_template(
                    "book_slots.html",
                    selected_date=(selected_date or today.isoformat()),
                    slots=[],
                    error="Invalid time selected.",
                    today=today.isoformat(),
                    available_dates=[],
                    open_dates=[],
                )

            # Prevent booking in the past
            if start_at < datetime.now():
                error = "You cannot book an appointment in the past."
            else:
                # Calculate end time based on fixed appointment duration
                end_at = start_at + timedelta(minutes=APPT_MINUTES)

                # Check for conflicts (double-booking prevention)
                existing = Appointment.query.filter_by(
                    start_at=start_at,
                    status="scheduled"
                ).first()

                if existing:
                    error = "Sorry, that slot was just booked. Please choose another."
                else:
                    # Create new appointment
                    appt = Appointment(
                        user_id=session.get("account_id"),
                        start_at=start_at,
                        end_at=end_at,
                        status="scheduled",
                    )
                    db.session.add(appt)
                    db.session.commit()

                    # Show confirmation page
                    return render_template("booking_success.html", start_at=start_at)

        # -----------------------------
        # BUILD CALENDAR DATA
        # -----------------------------
        open_dates, available_dates = build_calendar_data(
            today, bh_by_weekday, ov_by_date, booked_starts_by_date, now_dt
        )

        # Earliest available booking date
        soonest_available = available_dates[0] if available_dates else None
        redirected_message = None

        # -----------------------------
        # HANDLE DATE SELECTION LOGIC
        # -----------------------------
        if selected_date:
            try:
                day = datetime.fromisoformat(selected_date).date()
            except ValueError:
                day = today
                selected_date = day.isoformat()

            # Prevent selecting past dates
            if day < today:
                day = today
                selected_date = day.isoformat()

            # If business is closed → redirect to next available date
            if soonest_available and selected_date not in open_dates:
                redirected_message = "This business is not open this day. You have returned to the soonest appointment."
                selected_date = soonest_available
                day = datetime.fromisoformat(selected_date).date()

            # If open but fully booked → also redirect
            elif soonest_available and selected_date in open_dates and selected_date not in available_dates:
                redirected_message = "No appointments available for this day. You have returned to the soonest appointment."
                selected_date = soonest_available
                day = datetime.fromisoformat(selected_date).date()

        else:
            # Default: pick first available date
            if soonest_available:
                selected_date = soonest_available
                day = datetime.fromisoformat(selected_date).date()
            else:
                day = today
                selected_date = day.isoformat()

        # -----------------------------
        # GENERATE TIME SLOTS
        # -----------------------------
        slots = build_slots_for_day(
            day,
            bh_by_weekday,
            ov_by_date,
            booked_starts_by_date,
            now_dt
        )

        # Show redirect message as error (reuses UI space)
        if redirected_message and not error:
            error = redirected_message

        return render_template(
            "book_slots.html",
            selected_date=selected_date,
            slots=slots,
            error=error,
            today=today.isoformat(),
            available_dates=available_dates,
            open_dates=open_dates,
        )