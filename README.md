# EasyBook -- Smart Appointment Scheduling System

EasyBook is a full-stack web-based appointment scheduling system that
allows users to book available time slots with a service provider. The
system dynamically generates availability, prevents scheduling
conflicts, and provides role-based dashboards for users, business
owners, and administrators.

This project was developed is Michael Johnson's Senior Capstone Project (CSE 499) to
demonstrate backend scheduling logic, database design, and full-stack
web application development.

------------------------------------------------------------------------

## 🌐 Live Application

https://easybook-66x7.onrender.com/login

------------------------------------------------------------------------

## 🚀 Features

### 👤 User Features

-   Register and log in securely
-   View available dates and time slots
-   Book appointments
-   Cancel upcoming appointments
-   View personal appointment history

### 🏢 Business Features

-   Set weekly operating hours
-   Configure date-specific overrides (holidays, custom hours)
-   View upcoming and past appointments
-   Cancel appointments when needed

### 🛠️ Admin Features

-   Manage all user accounts
-   Enable/disable accounts
-   Change user roles (user, business, admin)
-   View and manage all appointments

### ⚙️ System Features

-   Automatic time slot generation
-   Conflict detection (prevents double-booking)
-   Role-based access control
-   Persistent database storage
-   Clean and responsive UI

------------------------------------------------------------------------

## 🧠 Booking System Logic

The system uses a dynamic scheduling algorithm that:

-   Combines **weekly business hours** with **date-specific overrides**
-   Generates available time slots within a configurable booking window
-   Filters out:
    -   Past times
    -   Already booked slots
    -   Closed days
-   Ensures all appointments:
    -   Fit within business hours
    -   Do not overlap with existing bookings

------------------------------------------------------------------------

## 🏗️ Project Structure

app/
│
├── __init__.py          # App factory and route registration
├── extensions.py        # Database and migration setup
├── models.py            # Database models
├── decorators.py        # Role-based access control
│
├── auth_routes.py       # Login, registration, logout
├── user_routes.py       # Booking and user appointments
├── business_routes.py   # Business dashboard and overrides
├── admin_routes.py      # Admin dashboard and management
├── misc_routes.py       # Dev tools (seed, whoami)
│
└── services/
    └── booking_service.py   # Scheduling and slot generation logic

templates/
│
├── login.html                      # User login page
├── register.html                   # User registration page
├── my_appointments.html            # User appointment list
│
├── book.html                       # Initial booking page (date selection)
├── book_slots.html                 # Available time slots for selected date
├── booking_success.html            # Booking confirmation page
│
├── business_dashboard.html         # Business weekly hours management
├── business_overrides.html         # Date-specific availability overrides
├── business_appointments.html      # Upcoming business appointments
├── business_appointments_archive.html  # Past business appointments
│
├── admin_dashboard.html            # Admin overview dashboard
├── admin_accounts.html             # Account management page
├── admin_appointments.html         # Upcoming appointments (admin view)
├── admin_appointments_archive.html # Archived appointments (admin view)
│
├── admin.html                      # Legacy / placeholder admin page
├── index.html                      # Basic system status page

migrations/                         # Database migration files (Alembic)
app.py                             # Application entry point

------------------------------------------------------------------------

## 🧰 Technology Stack

### Frontend

-   HTML\
-   CSS (Bootstrap)\
-   JavaScript (basic interactivity)

### Backend

-   Python\
-   Flask (web framework)\
-   Jinja2 (templating engine)

### Database

-   SQLite (local development)\
-   PostgreSQL via Supabase (production)

### Deployment

-   Render (cloud hosting)

------------------------------------------------------------------------

## 🔐 Security Features

-   Passwords are securely hashed using Werkzeug
-   Role-based route protection using decorators
-   Session-based authentication
-   Production-only routes are protected (e.g., `/seed`, `/whoami`
    disabled)

------------------------------------------------------------------------

## 🧪 Development Setup

### 1. Clone the repository

``` bash
git clone <your-repo-url>
cd easybook
```

### 2. Activate virtual environment

``` powershell
venv\Scripts\Activate.ps1
```

### 3. Install dependencies

``` bash
pip install -r requirements.txt
```

### 4. Run the application

``` bash
python app.py
```

------------------------------------------------------------------------

## 🌱 Database Seeding (Development Only)

To create default accounts:

    http://localhost:5000/seed

⚠️ Disabled in production for security.

------------------------------------------------------------------------

## 📌 Project Scope

This system is designed for: - A **single service provider** - A
**single time zone** - Fixed appointment durations (30 minutes)

### Not Included

-   Payments or billing systems
-   Multi-provider scheduling
-   External calendar integrations (Google Calendar, etc.)

