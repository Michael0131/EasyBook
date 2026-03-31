# Import datetime utilities for date math and time range construction
from datetime import datetime, timedelta, time

# Import models needed to read business hours, overrides, and existing appointments
from ..models import Appointment, AvailabilityOverride, BusinessHour


# Fixed appointment length in minutes
APPT_MINUTES = 30

# Time between possible slot start times
# In this project, slots move in 30-minute increments
SLOT_STEP_MINUTES = 30

# Number of future days shown in the booking window
WINDOW_DAYS = 60


def get_booking_context(today=None, now_dt=None):
    """
    Preloads all booking data needed to build the calendar and time slots.

    Returns:
        A dictionary containing:
        - today's date
        - current datetime
        - weekly business hours by weekday
        - date-specific overrides
        - already-booked appointment start times grouped by date

    This reduces repeated database queries when generating availability.
    """

    # Use current date/time unless values were passed in manually
    # (manual values can be helpful for testing)
    today = today or datetime.now().date()
    now_dt = now_dt or datetime.now()

    # Define the booking search window
    range_start = today
    range_end = today + timedelta(days=WINDOW_DAYS)

    # Load weekly business hours and organize them by weekday number
    # Example: 0 = Monday, 6 = Sunday
    bh_rows = BusinessHour.query.all()
    bh_by_weekday = {bh.weekday: bh for bh in bh_rows}

    # Load date-specific overrides only within the booking window
    overrides = (
        AvailabilityOverride.query.filter(
            AvailabilityOverride.date >= range_start,
            AvailabilityOverride.date <= range_end,
        ).all()
    )
    ov_by_date = {ov.date: ov for ov in overrides}

    # Build datetime range for appointment lookup
    # Start at beginning of first day and end at beginning of day after range_end
    appt_start_dt = datetime.combine(range_start, time(0, 0))
    appt_end_dt = datetime.combine(range_end + timedelta(days=1), time(0, 0))

    # Load scheduled appointments within the booking window
    appts = (
        Appointment.query.filter(
            Appointment.status == "scheduled",
            Appointment.start_at >= appt_start_dt,
            Appointment.start_at < appt_end_dt,
        ).all()
    )

    # Group booked appointment start times by date for fast conflict checks
    booked_starts_by_date = {}
    for appt in appts:
        day_date = appt.start_at.date()
        booked_starts_by_date.setdefault(day_date, set()).add(appt.start_at)

    return {
        "today": today,
        "now_dt": now_dt,
        "range_start": range_start,
        "range_end": range_end,
        "bh_by_weekday": bh_by_weekday,
        "ov_by_date": ov_by_date,
        "booked_starts_by_date": booked_starts_by_date,
    }


def is_open_day(day_date, bh_by_weekday, ov_by_date):
    """
    Determines whether the business is open on a given day.

    Priority:
        1. Date-specific override
        2. Default weekly business hours

    Returns:
        True if the business is open on that date
        False otherwise
    """

    # Overrides take priority over normal weekly hours
    override = ov_by_date.get(day_date)
    if override:
        if override.is_closed:
            return False

        # Invalid override hours are treated as closed
        if not override.start_time or not override.end_time or override.end_time <= override.start_time:
            return False

        return True

    # If no override exists, use default weekly hours
    business_hour = bh_by_weekday.get(day_date.weekday())
    if not business_hour or business_hour.is_closed:
        return False

    # Invalid hours also count as closed
    if business_hour.end_time <= business_hour.start_time:
        return False

    return True


def get_day_hours(day_date, bh_by_weekday, ov_by_date):
    """
    Returns the opening and closing times for a given day.

    Priority:
        1. Date-specific override
        2. Default weekly business hours

    Returns:
        (start_time, end_time) tuple if open
        None if closed or invalid
    """

    # Check for date-specific override first
    override = ov_by_date.get(day_date)
    if override:
        if override.is_closed:
            return None

        # Invalid override hours mean the day cannot be booked
        if not override.start_time or not override.end_time or override.end_time <= override.start_time:
            return None

        return override.start_time, override.end_time

    # Otherwise use weekly hours
    business_hour = bh_by_weekday.get(day_date.weekday())
    if not business_hour or business_hour.is_closed or business_hour.end_time <= business_hour.start_time:
        return None

    return business_hour.start_time, business_hour.end_time


def build_slots_for_day(day_date, bh_by_weekday, ov_by_date, booked_starts_by_date, now_dt):
    """
    Builds all available appointment start times for one day.

    Rules:
        - Slots must fit fully inside business hours
        - Slots cannot be in the past
        - Slots cannot already be booked
        - Slots move forward in SLOT_STEP_MINUTES increments

    Returns:
        List of available datetime slot starts
    """

    # Get opening hours for the selected day
    hours = get_day_hours(day_date, bh_by_weekday, ov_by_date)
    if not hours:
        return []

    start_t, end_t = hours

    # Convert opening/closing times into full datetimes
    day_start = datetime.combine(day_date, start_t)
    day_end = datetime.combine(day_date, end_t)

    # Get all already-booked start times for this day
    booked_starts = booked_starts_by_date.get(day_date, set())

    slots = []
    current = day_start

    # Keep generating slots while a full appointment still fits before closing time
    while current + timedelta(minutes=APPT_MINUTES) <= day_end:

        # Only include future, unbooked slots
        if current >= now_dt and current not in booked_starts:
            slots.append(current)

        # Move to next possible slot start
        current += timedelta(minutes=SLOT_STEP_MINUTES)

    return slots


def build_calendar_data(today, bh_by_weekday, ov_by_date, booked_starts_by_date, now_dt):
    """
    Builds booking calendar data for the full booking window.

    Returns:
        open_dates:
            Dates when the business is open
        available_dates:
            Dates that have at least one open booking slot

    This is used to drive the booking calendar UI.
    """

    open_dates = []
    available_dates = []

    # Check each day in the booking window
    for i in range(0, WINDOW_DAYS + 1):
        day_date = today + timedelta(days=i)

        # Add day to open_dates if business is open
        if is_open_day(day_date, bh_by_weekday, ov_by_date):
            iso_date = day_date.isoformat()
            open_dates.append(iso_date)

            # Only add to available_dates if at least one slot exists
            if build_slots_for_day(day_date, bh_by_weekday, ov_by_date, booked_starts_by_date, now_dt):
                available_dates.append(iso_date)

    return open_dates, available_dates