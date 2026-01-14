from flask import Flask, render_template, redirect, url_for

app = Flask(__name__)

@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route("/book")
def book():
    return render_template("book.html")

@app.route("/admin")
def admin():
    return render_template("admin.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/ping")
def ping():
    return "pong"


if __name__ == "__main__":
    app.run(debug=True)
