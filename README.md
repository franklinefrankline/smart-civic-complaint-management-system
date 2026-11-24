# Smart Civic Complaint Management and Tracking System
### *A Multilingual Web Portal for Transparent Complaint Resolution*

A production-ready full-stack civic governance and municipal grievance redressal web application built with **Python Flask**, **MySQL**, **Leaflet.js OpenStreetMap**, **Chart.js**, and **Vanilla JavaScript**.

---

## System Overview

The **Smart Civic Complaint Management and Tracking System** connects citizens, municipal department officers, field maintenance crews, and central administrators into a unified, accountable, real-time grievance redressal ecosystem.

### Key Pillars
1. **Four Independent Role Portals**:
   - **Citizen**: File complaints, pin GPS location on map, view lifecycle history, track status, give star ratings, and reopen unresolved issues.
   - **Administrator**: Central metrics, cross-department analytics, user provisioning, safe department management, SLA escalation monitoring, and audit trails.
   - **Department Officer**: Department-scoped queue, task acceptance/rejection with mandatory reasons, priority adjustments, worker dispatch, work inspection, and resolution approval.
   - **Field Worker**: Work order queue, site navigation, pre-work condition photos, repair execution, post-work proof uploads, and completion submission.
2. **Deterministic Complaint Workflow Lifecycle**:
   `Submitted` -> `Under Review` -> `Accepted` -> `Assigned` -> `In Progress` -> `Work Completed` -> `Verification Pending` -> `Resolved` (with branch states: `Rejected`, `Reopened`, `Escalated`).
3. **Interactive Maps (Leaflet.js + OpenStreetMap)**:
   - Draggable pin and GPS "Locate Me" for citizens.
   - Status-colored interactive marker overview for officials and navigation routing for field crews.
4. **Multilingual Interface**:
   - Native support for **English**, **Tamil (தமிழ்)**, and **Hindi (हिन्दी)** with persistent session language switching.
5. **Civic Intelligence**:
   - Duplicate complaint warning (Haversine formula within 500m / 30 days).
   - Automated category-to-department suggestion.
   - SLA tracking engine with automatic overdue escalation (24h Urgent, 48h High, 96h Medium, 168h Low).
   - CSV export with multi-criteria filters.
   - Tamper-evident system audit logging.

---

## Technology Stack

| Layer | Technology |
|---|---|
| **Backend Framework** | Python 3 Flask |
| **Database** | MySQL 8.0+ / MariaDB (via PyMySQL + Flask-SQLAlchemy) |
| **Authentication** | Secure session-based auth with Werkzeug password hashing |
| **Frontend** | HTML5, CSS3 (Modern Flexbox & CSS Grid, Light/Dark theme) |
| **Client Scripting** | Vanilla JavaScript (ES6+), Leaflet.js, Chart.js, Lucide Icons |
| **Maps** | Leaflet.js with OpenStreetMap tiles |
| **Charts** | Chart.js 4.4 |
| **Security** | Role-based Access Control (RBAC), URL-tamper protection, File validation |

---

## Project Architecture

```
smart-civic-complaint-system/
│
├── app/
│   ├── __init__.py                # Flask application factory, error handlers, context processors
│   ├── models/                    # SQLAlchemy database models (12 normalized tables)
│   │   ├── user.py                # Users & RBAC
│   │   ├── department.py          # Municipal departments
│   │   ├── category.py            # Complaint categories
│   │   ├── complaint.py           # Core complaints & SLA metadata
│   │   ├── workflow.py            # Workers, assignments, lifecycle history
│   │   ├── attachment.py          # Evidence photos & documents
│   │   ├── notification.py        # In-app notifications
│   │   ├── feedback.py            # Citizen ratings & reviews
│   │   └── audit.py               # Audit logs & system settings
│   │
│   ├── routes/                    # Modular Blueprints
│   │   ├── public.py              # Landing, About, How-it-Works, Departments, Track, Contact
│   │   ├── auth.py                # Login, Register, Logout, Forgot Password
│   │   ├── citizen.py             # Citizen dashboard, complaint CRUD, feedback, reopening
│   │   ├── admin.py               # Admin console, complaints, users, depts, workers, logs, CSV
│   │   ├── officer.py             # Department queue, worker assignment, verification, approval
│   │   ├── worker.py              # Work orders, site proofs, completion submission
│   │   └── api.py                 # REST APIs: map pins, duplicate check, notifications, SLA sweep
│   │
│   ├── services/                  # Business Logic Services
│   │   ├── complaint_service.py   # State machine, transitions, assignments, duplicate search
│   │   ├── notification_service.py# In-app notification dispatcher
│   │   ├── sla_service.py         # SLA resolution calculation & auto-escalation
│   │   └── audit_service.py       # Activity audit logging
│   │
│   ├── utils/                     # Helpers & Security
│   │   ├── decorators.py          # @login_required, @role_required
│   │   ├── helpers.py             # ID generation, Haversine, file upload security
│   │   └── translations.py        # English, Tamil, Hindi translation dictionaries
│   │
│   ├── templates/                 # Jinja2 HTML Templates
│   │   ├── base.html              # Master layout with theme switcher & notification bell
│   │   ├── shared/                # Navbar, role sidebars, alerts
│   │   ├── public/                # Landing, tracking, login, register, FAQ
│   │   ├── citizen/               # Citizen dashboard, complaint form with map, detail
│   │   ├── admin/                 # Admin dashboard with Chart.js, complaints, users, depts
│   │   ├── officer/               # Officer queue, review, verify, resolve
│   │   └── worker/                # Worker tasks, upload proofs, site map
│   │
│   └── static/                    # Assets
│       ├── css/main.css           # Master stylesheet with Light/Dark theme CSS variables
│       └── js/                    # Main UI, Leaflet map engine, notifications poller
│
├── uploads/                       # Secure file uploads folder (gitignored in production)
│   ├── complaints/                # Citizen initial photos
│   └── proofs/                    # Field technician before/after proofs
│
├── tests/                         # Automated unit and integration test suite
│   └── test_app.py                # 9 comprehensive tests covering all workflows
│
├── database.sql                   # Full MySQL schema DDL script
├── config.py                      # Application environments (dev, prod, test)
├── run.py                         # Application CLI & server entry point
├── requirements.txt               # Python package dependencies
├── .env                           # Environment secrets and database connection
└── README.md                      # Complete system documentation
```

---

## Database Design (MySQL)

The system features 12 normalized relational tables with foreign keys and strict referential integrity:

1. `users`: Core account details, credentials hash, role enum (`citizen`, `admin`, `officer`, `worker`), and ward.
2. `departments`: Civic units (Water, Roads, Sanitation, Electricity, etc.) with safe deletion constraints.
3. `complaint_categories`: Specific complaint types mapped to departments with default SLA hours.
4. `complaints`: Primary grievance record with unique reference ID (`CMP-YYYYMM-XXXXX`), status, priority, and coordinates.
5. `workers`: Field worker profiles linked to users and departments with workload tracking.
6. `complaint_assignments`: Work orders assigned by officers to technicians.
7. `complaint_status_history`: Tamper-proof audit trail of every status transition, timestamp, and remark.
8. `complaint_attachments`: Photos (initial citizen uploads, technician before/after repair proofs).
9. `notifications`: In-app notification messages with unread badges.
10. `feedback`: 1–5 star ratings, quality scores, and citizen comments.
11. `audit_logs`: Detailed operational logging with IP address, user, entity, and action.
12. `system_settings`: Key-value application parameters (SLA thresholds, duplicate detection radius).

---

## Installation & Setup Guide

### 1. Prerequisites
- Python 3.10+
- MySQL Server 8.0+ or MariaDB 10.4+ (e.g., via XAMPP, WAMP, or standalone MySQL service)

### 2. Configure Environment (`.env`)
Create or edit the `.env` file in the project root:
```ini
FLASK_APP=run.py
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=smart-civic-complaint-system-super-secure-key-2026

# MySQL Database Connection String
# Format: mysql+pymysql://<user>:<password>@<host>:<port>/<database>?charset=utf8mb4
DB_USER=root
DB_PASSWORD=
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=smart_civic_complaints
DATABASE_URL=mysql+pymysql://root:@127.0.0.1:3306/smart_civic_complaints?charset=utf8mb4

UPLOAD_FOLDER=uploads
MAX_CONTENT_LENGTH=10485760
PERMANENT_SESSION_LIFETIME=86400
```

### 3. Install Dependencies
```bash
python -m pip install -r requirements.txt
```

### 4. Initialize Database & Seed Demonstration Data
Initialize the MySQL database tables and seed sample accounts across all four user roles:
```bash
# Seed all 9 departments, 12 categories, 4 roles, and demo complaints
python run.py seed-db
```

*(Optional) Create a custom production administrator account interactively:*
```bash
python run.py create-admin
```

### 5. Start the Application Server
```bash
python run.py
```
The application will launch at: **`http://127.0.0.1:5000`**

---

## Demonstration Test Accounts

All accounts are pre-seeded when running `python run.py seed-db`:

| Role | Email | Password | Scope & Description |
|---|---|---|---|
| **Administrator** | `admin@civic.gov` | `Admin@123` | Full administrative control, analytics, user & dept management |
| **Department Officer** | `water.officer@civic.gov` | `Officer@123` | Water Supply & Sewage Department head |
| **Department Officer** | `roads.officer@civic.gov` | `Officer@123` | Roads & Transportation Department head |
| **Field Worker** | `tech.kumar@civic.gov` | `Worker@123` | Water Department technician (pipeline repairs) |
| **Field Worker** | `tech.selvam@civic.gov` | `Worker@123` | Roads Department asphalt crew lead |
| **Citizen** | `anita.citizen@example.com` | `Citizen@123` | Registered citizen (Ward 4) |
| **Citizen** | `karthik.citizen@example.com` | `Citizen@123` | Registered citizen (Ward 8) |

---

## Running Automated Tests

Run the complete integration test suite:
```bash
python -m unittest tests/test_app.py
```
**Test Coverage Includes:**
- Public page rendering (Homepage, About, How-it-Works, Departments, Track, Contact)
- Citizen registration with password validation and mobile/email uniqueness checks
- Role-based dashboard protection (URL manipulation prevents unauthorized cross-role access)
- Full end-to-end complaint lifecycle (Submit -> Accept -> Assign -> In Progress -> Work Completed -> Verify & Resolve -> Feedback -> Reopen)
- Leaflet map coordinate parsing and Haversine duplicate detection API
- Multilingual translation switching (English, Tamil, Hindi)
- Public reference tracking without login
- Notification center and mark-as-read API
- Administrator CSV export

---

## Security Features

- **Password Hashing**: Industry-standard PBKDF2 with SHA-256 via Werkzeug.
- **Session Security**: HTTP-only session cookies with `SameSite=Lax` protection.
- **Role-Based Access Control**: Strict server-side route guards prevent URL tampering.
- **Privacy Shield**: Citizen mobile numbers and email addresses are never exposed on public maps.
- **File Upload Protection**: Validated file types (JPG, PNG, WEBP, PDF), secure randomized UUID filenames, and size limits (10MB).
- **SQL Injection Prevention**: Parameterized queries through SQLAlchemy ORM.
- **XSS Mitigation**: Jinja2 auto-escaping on all user inputs and remarks.

---

## Multilingual Support

The portal interface, dashboard labels, form fields, and status badges are translated into:
- **English (`en`)**
- **Tamil (`ta`) - தமிழ்**
- **Hindi (`hi`) - हिन्दी**

Citizens and officials can toggle languages instantaneously via the top navbar dropdown; preferences persist across sessions.

---

## License & Compliance
Designed and developed for municipal and civic transparency in accordance with open-governance best practices.
