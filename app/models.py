# Import database instance used to define models and tables
from .extensions import db


# -----------------------------
# ACCOUNT MODEL
# -----------------------------
class Account(db.Model):
    """
    Represents a user in the system.

    Roles:
        - user: normal customer booking appointments
        - business: manages availability and appointments
        - admin: system administrator
    """

    __tablename__ = "accounts"

    # Primary key (unique identifier)
    id = db.Column(db.Integer, primary_key=True)

    # Basic user information
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(30), nullable=True)

    # Authentication fields
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)  # hashed password

    # Role-based access control
    role = db.Column(db.String(20), nullable=False)

    # Used to disable accounts without deleting them
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    @property
    def full_name(self):
        """
        Returns the user's full name as a single string.

        Useful for display in templates.
        """
        return f"{self.first_name} {self.last_name}".strip()


# -----------------------------
# APPOINTMENT MODEL
# -----------------------------
class Appointment(db.Model):
    """
    Represents a scheduled appointment.

    Each appointment is linked to a user and has a start/end time.
    """

    __tablename__ = "appointments"

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key linking to Account table
    user_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)

    # Appointment time range
    start_at = db.Column(db.DateTime, nullable=False)
    end_at = db.Column(db.DateTime, nullable=False)

    # Status allows tracking (e.g., scheduled, cancelled)
    status = db.Column(db.String(20), nullable=False, default="scheduled")

    # Timestamp when appointment was created (auto-generated)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

    # Relationship: allows access to the user who owns the appointment
    user = db.relationship("Account", backref="appointments")


# -----------------------------
# BUSINESS HOURS MODEL
# -----------------------------
class BusinessHour(db.Model):
    """
    Represents the default weekly operating hours for the business.

    One row per weekday (0 = Monday, 6 = Sunday).
    """

    __tablename__ = "business_hours"

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Day of week (unique ensures only one row per day)
    weekday = db.Column(db.Integer, nullable=False, unique=True)

    # Opening and closing times for that day
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

    # Indicates if business is closed that day
    is_closed = db.Column(db.Boolean, nullable=False, default=False)


# -----------------------------
# AVAILABILITY OVERRIDE MODEL
# -----------------------------
class AvailabilityOverride(db.Model):
    """
    Represents exceptions to normal business hours for specific dates.

    Example:
        - Holidays (closed)
        - Special extended hours
    """

    __tablename__ = "availability_overrides"

    # Primary key
    id = db.Column(db.Integer, primary_key=True)

    # Specific date this override applies to (unique = one override per day)
    date = db.Column(db.Date, unique=True, nullable=False)

    # Optional custom hours for that date
    # (None if the business is closed)
    start_time = db.Column(db.Time, nullable=True)
    end_time = db.Column(db.Time, nullable=True)

    # Indicates if business is closed for that specific date
    is_closed = db.Column(db.Boolean, nullable=False, default=False)