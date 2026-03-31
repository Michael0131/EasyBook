# Import time object to convert string inputs into time values
from datetime import time

# wraps preserves original function metadata (important for Flask routing)
from functools import wraps

# Flask utilities for session management and redirects
from flask import redirect, session, url_for


# -----------------------------
# ROLE-BASED ACCESS DECORATOR
# -----------------------------
def require_role(*roles):
    """
    Restricts access to a route based on user roles.

    Example:
        @require_role("admin")
        @require_role("user", "business")

    If the current user's role is not in the allowed roles,
    they are redirected to the login page.
    """

    def decorator(view_func):
        @wraps(view_func)  # Keeps original function name (important for Flask)
        def wrapper(*args, **kwargs):

            # Get current user's role from session
            role = session.get("role")

            # If user is not authorized, redirect to login
            if role not in roles:
                return redirect(url_for("login"))

            # Otherwise, allow access to the original route
            return view_func(*args, **kwargs)

        return wrapper

    return decorator


# -----------------------------
# TIME PARSING HELPER
# -----------------------------
def parse_time_or_none(value: str):
    """
    Converts a string in "HH:MM" format into a Python time object.

    Returns:
        time object if valid input
        None if input is empty or invalid

    Example:
        "09:30" -> time(9, 30)
        "" or invalid -> None

    Used for safely handling form input where time fields may be empty.
    """

    # Validate input format
    if not value or ":" not in value:
        return None

    # Split hours and minutes
    h, m = value.split(":")

    # Convert to integers and return time object
    return time(int(h), int(m))