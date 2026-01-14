from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = "easybook-dev-key"


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
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        # Temporary hardcoded accounts (replace with DB later)
        if username == "admin" and password == "password123":
            session.clear()
            session["role"] = "admin"
            return redirect(url_for("admin_dashboard"))

        if username == "business" and password == "business123":
            session.clear()
            session["role"] = "business"
            return redirect(url_for("business_dashboard"))

        if username == "user" and password == "user123":
            session.clear()
            session["role"] = "user"
            return redirect(url_for("user_home"))

        error = "Invalid username or password."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/book")
def book():
    return render_template("book.html")


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


# ---- Admin Area ----
@app.route("/admin")
@require_role("admin")
def admin_dashboard():
    return render_template("admin_dashboard.html")


if __name__ == "__main__":
    app.run(debug=True)
