from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash
from werkzeug.security import check_password_hash
from datetime import time, datetime, timedelta

import os

app = Flask(__name__, instance_relative_config=True)
app.secret_key = "easybook-dev-key"

db_path = os.path.join(app.instance_path, "easybook.db")
os.makedirs(app.instance_path, exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_path}"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

class Account(db.Model):
    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # "user", "business", "admin"
    is_active = db.Column(db.Boolean, default=True, nullable=False)


class Appointment(db.Model):
    __tablename__ = "appointments"

    id = db.Column(db.Integer, primary_key=True)

    # Which user booked it
    user_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)

    start_at = db.Column(db.DateTime, nullable=False)
    end_at = db.Column(db.DateTime, nullable=False)

    status = db.Column(db.String(20), nullable=False, default="scheduled")
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    user = db.relationship("Account", backref="appointments")

class BusinessHour(db.Model):
    __tablename__ = "business_hours"

    id = db.Column(db.Integer, primary_key=True)
    weekday = db.Column(db.Integer, nullable=False, unique=True)  # 0=Mon ... 6=Sun
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    is_closed = db.Column(db.Boolean, nullable=False, default=False)



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


@app.route("/")
def home():
    # Default entry point = sign in
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
            if account.role == "user":
                return redirect(url_for("user_home"))

            error = "Account role is not configured."
        else:
            error = "Invalid email or password."

    return render_template("login.html", error=error)

# Debug, can be deleted whenever - MUST BE DELETED BEFORE PRODUCTION
@app.route("/whoami")
def whoami():
    return {
        "role": session.get("role"),
        "account_id": session.get("account_id")
    }

# --- REGISTER ----- 
@app.route("/register", methods=["GET", "POST"])
def register():
    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            error = "Email and password are required."
            return render_template("register.html", error=error)

        existing = Account.query.filter_by(email=email).first()
        if existing:
            error = "That email is already registered."
            return render_template("register.html", error=error)

        user = Account(
            email=email,
            password_hash=generate_password_hash(password),
            role="user",
            is_active=True
        )
        db.session.add(user)
        db.session.commit()

        # Log the new user in immediately
        session.clear()
        session["role"] = "user"
        session["account_id"] = user.id

        return redirect(url_for("user_home"))

    return render_template("register.html", error=error)

@app.route("/business/hours", methods=["GET", "POST"])
@require_role("business")
def business_hours():
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    def parse_time_or_none(value: str):
        if not value or ":" not in value:
            return None
        h, m = value.split(":")
        return time(int(h), int(m))

    if request.method == "POST":
        for i in range(7):
            closed = request.form.get(f"closed_{i}") == "on"
            start_str = request.form.get(f"start_{i}", "")
            end_str = request.form.get(f"end_{i}", "")

            row = BusinessHour.query.filter_by(weekday=i).first()
            if not row:
                # default row if missing
                row = BusinessHour(
                    weekday=i,
                    start_time=time(9, 0),
                    end_time=time(17, 0),
                    is_closed=False
                )
                db.session.add(row)

            if closed:
                row.is_closed = True
                # times remain as-is (ignored when closed)
            else:
                row.is_closed = False

                parsed_start = parse_time_or_none(start_str)
                parsed_end = parse_time_or_none(end_str)

                # If inputs were missing (disabled previously), keep existing times or defaults
                if parsed_start is None:
                    parsed_start = row.start_time or time(9, 0)
                if parsed_end is None:
                    parsed_end = row.end_time or time(17, 0)

                row.start_time = parsed_start
                row.end_time = parsed_end

        db.session.commit()
        return redirect(url_for("business_hours"))

    # GET: ensure rows exist
    rows = {bh.weekday: bh for bh in BusinessHour.query.all()}
    hours = []
    for i in range(7):
        bh = rows.get(i)
        if not bh:
            default_closed = i in (5, 6)  # Sat/Sun
            bh = BusinessHour(
                weekday=i,
                start_time=time(9, 0),
                end_time=time(17, 0),
                is_closed=default_closed
            )
            db.session.add(bh)
            db.session.commit()

        hours.append({"weekday": i, "name": day_names[i], "row": bh})

    return render_template("business_hours.html", hours=hours)



@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


from datetime import datetime, timedelta, time  # make sure this import exists at top

@app.route("/book", methods=["GET", "POST"])
@require_role("user")
def book():
    error = None
    selected_date = request.args.get("date")  # YYYY-MM-DD

    APPT_MINUTES = 30
    SLOT_STEP_MINUTES = 30

    # -------------------------
    # POST: book a selected slot
    # -------------------------
    if request.method == "POST":
        start_str = request.form.get("start_at", "")
        if not start_str:
            return redirect(url_for("book"))

        try:
            start_at = datetime.fromisoformat(start_str)
        except ValueError:
            error = "Invalid time selected."
            start_at = None

        if start_at:
            end_at = start_at + timedelta(minutes=APPT_MINUTES)

            existing = Appointment.query.filter_by(
                start_at=start_at,
                status="scheduled"
            ).first()

            if existing:
                error = "Sorry, that slot was just booked. Please choose another."
            else:
                user_id = session.get("account_id")
                appt = Appointment(
                    user_id=user_id,
                    start_at=start_at,
                    end_at=end_at,
                    status="scheduled"
                )
                db.session.add(appt)
                db.session.commit()
                return render_template("booking_success.html", start_at=start_at)

    # -------------------------
    # GET: show available slots
    # -------------------------
    if not selected_date:
        selected_date = datetime.now().date().isoformat()

    try:
        day = datetime.fromisoformat(selected_date).date()
    except ValueError:
        day = datetime.now().date()
        selected_date = day.isoformat()

    # 1) Date override check (priority)
    ov = AvailabilityOverride.query.filter_by(date=day).first()
    if ov:
        if ov.is_closed:
            return render_template("book_slots.html", selected_date=selected_date, slots=[], error=None)

        # If override is open, it must have times
        if not ov.start_time or not ov.end_time or ov.end_time <= ov.start_time:
            return render_template(
                "book_slots.html",
                selected_date=selected_date,
                slots=[],
                error="Business override hours are not configured correctly for this date."
            )

        day_start = datetime.combine(day, ov.start_time)
        day_end = datetime.combine(day, ov.end_time)

    else:
        # 2) Fall back to weekly schedule
        weekday = day.weekday()  # 0=Mon ... 6=Sun
        bh = BusinessHour.query.filter_by(weekday=weekday).first()

        if not bh or bh.is_closed:
            return render_template("book_slots.html", selected_date=selected_date, slots=[], error=None)

        day_start = datetime.combine(day, bh.start_time)
        day_end = datetime.combine(day, bh.end_time)

        if day_end <= day_start:
            return render_template(
                "book_slots.html",
                selected_date=selected_date,
                slots=[],
                error="Business hours are not configured correctly for this day."
            )

    # Already booked start times in this window
    booked = Appointment.query.filter(
        Appointment.start_at >= day_start,
        Appointment.start_at < day_end,
        Appointment.status == "scheduled"
    ).all()
    booked_starts = {a.start_at for a in booked}

    # Generate slots
    slots = []
    cur = day_start
    while cur + timedelta(minutes=APPT_MINUTES) <= day_end:
        if cur not in booked_starts:
            slots.append(cur)
        cur += timedelta(minutes=SLOT_STEP_MINUTES)

    return render_template("book_slots.html", selected_date=selected_date, slots=slots, error=error)


@app.route("/business/overrides", methods=["GET", "POST"])
@require_role("business")
def business_overrides():
    error = None

    def parse_time_or_none(value: str):
        if not value or ":" not in value:
            return None
        h, m = value.split(":")
        return time(int(h), int(m))

    if request.method == "POST":
        date_str = request.form.get("date", "").strip()
        closed = request.form.get("is_closed") == "on"
        start_str = request.form.get("start_time", "").strip()
        end_str = request.form.get("end_time", "").strip()

        # Validate date
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


# ---- User Area ----
@app.route("/user")
@require_role("user")
def user_home():
    return render_template("user_home.html")


# ---- Business Area ----
@app.route("/business")
@require_role("business")
def business_dashboard():
    return render_template("business_dashboard.html")


class AvailabilityOverride(db.Model):
    __tablename__ = "availability_overrides"

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)  # one override per date
    start_time = db.Column(db.Time, nullable=True)          # null if closed
    end_time = db.Column(db.Time, nullable=True)            # null if closed
    is_closed = db.Column(db.Boolean, nullable=False, default=False)



# ---- Admin Area ----
@app.route("/admin")
@require_role("admin")
def admin_dashboard():
    return render_template("admin_dashboard.html")





@app.route("/seed")
def seed():
    # Only seed if table is empty to avoid duplicates
    if Account.query.first():
        return "Seed already done."

    admin = Account(
        email="admin@easybook.com",
        password_hash=generate_password_hash("password123"),
        role="admin",
        is_active=True
    )

    business = Account(
        email="business@easybook.com",
        password_hash=generate_password_hash("business123"),
        role="business",
        is_active=True
    )

    db.session.add(admin)
    db.session.add(business)
    db.session.commit()

    return "Seeded admin and business."



if __name__ == "__main__":
    app.run(debug=True)
