import os
from functools import wraps
from datetime import datetime, timedelta, time

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import or_
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import joinedload

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "easybook-dev-key")

# -----------------------------
# Database Config
# -----------------------------
# Use DATABASE_URL if set (Supabase/Render). Otherwise use local SQLite in project folder.
# NOTE: If you want instance-based db: "sqlite:///instance/easybook.db"
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///easybook.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# -----------------------------
# Models
# -----------------------------
class Account(db.Model):
    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)

    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(30), nullable=True)

    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(db.String(20), nullable=False)  # user, business, admin
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class Appointment(db.Model):
    __tablename__ = "appointments"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)

    start_at = db.Column(db.DateTime, nullable=False)
    end_at = db.Column(db.DateTime, nullable=False)

    status = db.Column(db.String(20), nullable=False, default="scheduled")
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    # Consistent relationship name: user
    user = db.relationship("Account", backref="appointments")


class BusinessHour(db.Model):
    __tablename__ = "business_hours"

    id = db.Column(db.Integer, primary_key=True)
    weekday = db.Column(db.Integer, nullable=False, unique=True)  # 0=Mon ... 6=Sun
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_closed = db.Column(db.Boolean, nullable=False, default=False)


class AvailabilityOverride(db.Model):
    __tablename__ = "availability_overrides"

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)  # one override per date
    start_time = db.Column(db.Time, nullable=True)          # null if closed
    end_time = db.Column(db.Time, nullable=True)            # null if closed
    is_closed = db.Column(db.Boolean, nullable=False, default=False)

# -----------------------------
# Helpers / Decorators
# -----------------------------
def require_role(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            role = session.get("role")
            if role not in roles:
                return redirect(url_for("login"))
            return view_func(*args, **kwargs)
        return wrapper
    return decorator


def parse_time_or_none(value: str):
    if not value or ":" not in value:
        return None
    h, m = value.split(":")
    return time(int(h), int(m))

# -----------------------------
# Auth Routes
# -----------------------------
@app.route("/")
def home():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        account = Account.query.filter_by(email=email, is_active=True).first()

        if account and check_password_hash(account.password_hash, password):
            session.clear()
            session["role"] = account.role
            session["account_id"] = account.id

            if account.role == "admin":
                return redirect(url_for("admin_dashboard"))
            if account.role == "business":
                return redirect(url_for("business_dashboard"))
            return redirect(url_for("book"))  # user goes straight to booking page

        error = "Invalid email or password."

    return render_template("login.html", error=error)


# --- REGISTER ----- 
@app.route("/register", methods=["GET", "POST"])
def register():
    error = None

    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        phone = request.form.get("phone", "").strip() or None

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not first_name or not last_name:
            error = "First and last name are required."
            return render_template("register.html", error=error)

        existing = Account.query.filter_by(email=email).first()
        if existing:
            error = "That email is already registered. Please log in."
            return render_template("register.html", error=error)

        new_account = Account(
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
            password_hash=generate_password_hash(password),
            role="user",
            is_active=True,
        )
        db.session.add(new_account)
        db.session.commit()

        session.clear()
        session["account_id"] = new_account.id
        session["role"] = new_account.role
        return redirect(url_for("user_home"))

    return render_template("register.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# -----------------------------
# User Area
# -----------------------------

@app.route("/book", methods=["GET", "POST"])
@require_role("user")
def book():
    error = None
    selected_date = request.args.get("date")  # YYYY-MM-DD

    APPT_MINUTES = 30
    SLOT_STEP_MINUTES = 30

    today = datetime.now().date()
    now_dt = datetime.now()

    WINDOW_DAYS = 60
    range_start = today
    range_end = today + timedelta(days=WINDOW_DAYS)

    # -----------------------------
    # Preload data (FAST)
    # -----------------------------
    # Business hours: 7 rows max
    bh_rows = BusinessHour.query.all()
    bh_by_weekday = {bh.weekday: bh for bh in bh_rows}

    # Overrides for date range
    overrides = (
        AvailabilityOverride.query
        .filter(
            AvailabilityOverride.date >= range_start,
            AvailabilityOverride.date <= range_end,
        )
        .all()
    )
    ov_by_date = {ov.date: ov for ov in overrides}

    # Appointments for datetime range (include end day)
    appt_start_dt = datetime.combine(range_start, time(0, 0))
    appt_end_dt = datetime.combine(range_end + timedelta(days=1), time(0, 0))

    appts = (
        Appointment.query
        .filter(
            Appointment.status == "scheduled",
            Appointment.start_at >= appt_start_dt,
            Appointment.start_at < appt_end_dt,
        )
        .all()
    )

    booked_starts_by_date = {}
    for a in appts:
        d = a.start_at.date()
        booked_starts_by_date.setdefault(d, set()).add(a.start_at)

    # -----------------------------
    # Helper: determine if business is open that day
    # -----------------------------
    def is_open_day(day_date):
        ov = ov_by_date.get(day_date)
        if ov:
            # override exists
            if ov.is_closed:
                return False
            if not ov.start_time or not ov.end_time or ov.end_time <= ov.start_time:
                return False
            return True

        bh = bh_by_weekday.get(day_date.weekday())
        if not bh or bh.is_closed:
            return False
        if bh.end_time <= bh.start_time:
            return False
        return True

    # -----------------------------
    # Helper: get open hours for a day (or None)
    # -----------------------------
    def get_day_hours(day_date):
        ov = ov_by_date.get(day_date)
        if ov:
            if ov.is_closed:
                return None
            if not ov.start_time or not ov.end_time or ov.end_time <= ov.start_time:
                return None
            return (ov.start_time, ov.end_time)

        bh = bh_by_weekday.get(day_date.weekday())
        if not bh or bh.is_closed or bh.end_time <= bh.start_time:
            return None
        return (bh.start_time, bh.end_time)

    # -----------------------------
    # Helper: build slots for a day (NO DB)
    # -----------------------------
    def build_slots_for_day(day_date):
        hours = get_day_hours(day_date)
        if not hours:
            return []

        start_t, end_t = hours
        day_start = datetime.combine(day_date, start_t)
        day_end = datetime.combine(day_date, end_t)

        booked_starts = booked_starts_by_date.get(day_date, set())

        slots_local = []
        cur = day_start
        while cur + timedelta(minutes=APPT_MINUTES) <= day_end:
            # Hide past times (esp. today)
            if cur >= now_dt and cur not in booked_starts:
                slots_local.append(cur)
            cur += timedelta(minutes=SLOT_STEP_MINUTES)

        return slots_local

    # -----------------------------
    # POST: book slot
    # -----------------------------
    if request.method == "POST":
        start_str = request.form.get("start_at", "")
        if not start_str:
            return redirect(url_for("book"))

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

        # Server-side safety: block past bookings
        if start_at < datetime.now():
            error = "You cannot book an appointment in the past."
        else:
            end_at = start_at + timedelta(minutes=APPT_MINUTES)

            # Conflict check (DB) - single query
            existing = Appointment.query.filter_by(start_at=start_at, status="scheduled").first()
            if existing:
                error = "Sorry, that slot was just booked. Please choose another."
            else:
                appt = Appointment(
                    user_id=session.get("account_id"),
                    start_at=start_at,
                    end_at=end_at,
                    status="scheduled",
                )
                db.session.add(appt)
                db.session.commit()
                return render_template("booking_success.html", start_at=start_at)

    # -----------------------------
    # Build open_dates and available_dates (NO DB)
    # open_dates: business open (even if fully booked)
    # available_dates: open + has at least 1 slot
    # -----------------------------
    open_dates = []
    available_dates = []

    for i in range(0, WINDOW_DAYS + 1):
        d = today + timedelta(days=i)

        if is_open_day(d):
            open_dates.append(d.isoformat())

            if build_slots_for_day(d):
                available_dates.append(d.isoformat())

    # earliest bookable date (open + has slots)
    soonest_available = available_dates[0] if available_dates else None

    # -----------------------------
    # Determine selected day
    # -----------------------------
    redirected_message = None

    if selected_date:
        try:
            day = datetime.fromisoformat(selected_date).date()
        except ValueError:
            day = today
            selected_date = day.isoformat()

        # No past dates
        if day < today:
            day = today
            selected_date = day.isoformat()

        # If business is closed that day, bounce to soonest available with message
        if soonest_available and selected_date not in open_dates:
            redirected_message = "This business is not open this day. You have returned to the soonest appointment."
            selected_date = soonest_available
            day = datetime.fromisoformat(selected_date).date()

        # If business is open but fully booked, also bounce to soonest available with message
        elif soonest_available and selected_date in open_dates and selected_date not in available_dates:
            redirected_message = "No appointments available for this day. You have returned to the soonest appointment."
            selected_date = soonest_available
            day = datetime.fromisoformat(selected_date).date()

    else:
        # Default to closest day that has availability
        if soonest_available:
            selected_date = soonest_available
            day = datetime.fromisoformat(selected_date).date()
        else:
            day = today
            selected_date = day.isoformat()

    slots = build_slots_for_day(day)

    # Use error slot for the bounce message (so it displays without template changes)
    if redirected_message and not error:
        error = redirected_message

    return render_template(
        "book_slots.html",
        selected_date=selected_date,
        slots=slots,
        error=error,
        today=today.isoformat(),
        # available_dates: open + has slots (for booking)
        available_dates=available_dates,
        # open_dates: open days (for calendar greying-out closed days)
        open_dates=open_dates,
    )

# -----------------------------
# Business Area
# -----------------------------
@app.route("/business")
@require_role("business")
def business_dashboard():
    return render_template("business_dashboard.html")


@app.route("/business/hours", methods=["GET", "POST"])
@require_role("business")
def business_hours():
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    if request.method == "POST":
        for i in range(7):
            closed = request.form.get(f"closed_{i}") == "on"
            start_str = request.form.get(f"start_{i}", "")
            end_str = request.form.get(f"end_{i}", "")

            row = BusinessHour.query.filter_by(weekday=i).first()
            if not row:
                row = BusinessHour(weekday=i, start_time=time(9, 0), end_time=time(17, 0), is_closed=False)
                db.session.add(row)

            if closed:
                row.is_closed = True
            else:
                row.is_closed = False

                st = parse_time_or_none(start_str) or row.start_time or time(9, 0)
                et = parse_time_or_none(end_str) or row.end_time or time(17, 0)

                row.start_time = st
                row.end_time = et

        db.session.commit()
        return redirect(url_for("business_hours"))

    rows = {bh.weekday: bh for bh in BusinessHour.query.all()}
    hours = []

    for i in range(7):
        bh = rows.get(i)
        if not bh:
            default_closed = i in (5, 6)
            bh = BusinessHour(weekday=i, start_time=time(9, 0), end_time=time(17, 0), is_closed=default_closed)
            db.session.add(bh)
            db.session.commit()

        hours.append({"weekday": i, "name": day_names[i], "row": bh})

    return render_template("business_hours.html", hours=hours)


@app.route("/business/overrides", methods=["GET", "POST"])
@require_role("business")
def business_overrides():
    error = None

    if request.method == "POST":
        date_str = request.form.get("date", "").strip()
        closed = request.form.get("is_closed") == "on"
        start_str = request.form.get("start_time", "").strip()
        end_str = request.form.get("end_time", "").strip()

        try:
            override_date = datetime.fromisoformat(date_str).date()
        except ValueError:
            error = "Please select a valid date."
            overrides = AvailabilityOverride.query.order_by(AvailabilityOverride.date.asc()).all()
            return render_template("business_overrides.html", overrides=overrides, error=error)

        row = AvailabilityOverride.query.filter_by(date=override_date).first()
        if not row:
            row = AvailabilityOverride(date=override_date)
            db.session.add(row)

        if closed:
            row.is_closed = True
            row.start_time = None
            row.end_time = None
        else:
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

        if error:
            db.session.rollback()
        else:
            db.session.commit()
            return redirect(url_for("business_overrides"))

    overrides = AvailabilityOverride.query.order_by(AvailabilityOverride.date.asc()).all()
    return render_template("business_overrides.html", overrides=overrides, error=error)

@app.route("/business/overrides/<int:override_id>/delete", methods=["POST"])
@require_role("business")
def delete_override(override_id):
    row = AvailabilityOverride.query.get_or_404(override_id)
    db.session.delete(row)
    db.session.commit()
    return redirect(url_for("business_overrides"))

# -----------------------------
# Admin Area
# -----------------------------
@app.route("/admin")
@require_role("admin")
def admin_dashboard():
    total_accounts = Account.query.count()
    active_accounts = Account.query.filter_by(is_active=True).count()

    me = None
    if session.get("account_id"):
        me = Account.query.get(session["account_id"])

    # IMPORTANT: load the linked Account so name/email shows in templates
    appointments = (
        Appointment.query
        .options(joinedload(Appointment.user))
        .order_by(Appointment.start_at.desc())
        .limit(20)
        .all()
    )

    return render_template(
        "admin_dashboard.html",
        total_accounts=total_accounts,
        active_accounts=active_accounts,
        appointments=appointments,
        me=me,
    )

@app.route("/admin/accounts")
@require_role("admin")
def admin_accounts():
    q = request.args.get("q", "").strip().lower()

    query = Account.query
    if q:
        query = query.filter(
            or_(
                Account.email.ilike(f"%{q}%"),
                Account.role.ilike(f"%{q}%"),
                Account.first_name.ilike(f"%{q}%"),
                Account.last_name.ilike(f"%{q}%"),
            )
        )

    accounts = query.order_by(Account.id.asc()).all()
    return render_template("admin_accounts.html", accounts=accounts, q=q)


@app.route("/admin/accounts/<int:account_id>/toggle", methods=["POST"])
@require_role("admin")
def admin_toggle_account(account_id):
    if session.get("account_id") == account_id:
        return redirect(url_for("admin_accounts"))

    account = Account.query.get_or_404(account_id)
    account.is_active = not account.is_active
    db.session.commit()
    return redirect(url_for("admin_accounts"))


@app.route("/admin/accounts/<int:account_id>/role", methods=["POST"])
@require_role("admin")
def admin_update_role(account_id):
    if session.get("account_id") == account_id:
        return redirect(url_for("admin_accounts"))

    new_role = (request.form.get("role") or "").strip().lower()
    if new_role not in ("user", "business", "admin"):
        return redirect(url_for("admin_accounts"))

    account = Account.query.get_or_404(account_id)
    account.role = new_role
    db.session.commit()
    return redirect(url_for("admin_accounts"))


@app.route("/admin/appointments")
@require_role("admin")
def admin_appointments():
    q = request.args.get("q", "").strip().lower()

    query = Appointment.query.options(joinedload(Appointment.user))

    if q:
        # Search by linked account fields
        query = query.join(Account, Account.id == Appointment.user_id).filter(
            or_(
                Account.email.ilike(f"%{q}%"),
                Account.first_name.ilike(f"%{q}%"),
                Account.last_name.ilike(f"%{q}%"),
            )
        )

    appointments = query.order_by(Appointment.start_at.desc()).all()
    return render_template("admin_appointments.html", appointments=appointments, q=q)


@app.route("/admin/appointments/<int:appointment_id>/cancel", methods=["POST"])
@require_role("admin")
def admin_cancel_appointment(appointment_id):
    appt = Appointment.query.get_or_404(appointment_id)
    db.session.delete(appt)
    db.session.commit()
    return redirect(url_for("admin_appointments"))

# -----------------------------
# Dev-only Utilities (guard these)
# -----------------------------
@app.route("/whoami")
def whoami():
    # Optional: block in production
    if os.getenv("FLASK_ENV") == "production":
        abort(404)
    return {"role": session.get("role"), "account_id": session.get("account_id")}


@app.route("/seed")
def seed():
    # Optional: block in production
    if os.getenv("FLASK_ENV") == "production":
        abort(404)

    # Only seed if no accounts
    if Account.query.first():
        return "Seed already done."

    admin = Account(
        first_name="Admin",
        last_name="User",
        phone=None,
        email="admin@easybook.com",
        password_hash=generate_password_hash("password123"),
        role="admin",
        is_active=True,
    )

    business = Account(
        first_name="Business",
        last_name="Owner",
        phone=None,
        email="business@easybook.com",
        password_hash=generate_password_hash("business123"),
        role="business",
        is_active=True,
    )

    db.session.add(admin)
    db.session.add(business)
    db.session.commit()

    return "Seeded admin and business."

if __name__ == "__main__":
    app.run(debug=True)