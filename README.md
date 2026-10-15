# Samadhan Sathi

**A civic grievance reporting and tracking website for Gwalior, Madhya Pradesh.**

Samadhan Sathi gives citizens a single place to report local problems—such as potholes, garbage, drainage, water supply, and streetlights—and follow their status. Administrators can review submissions, assign departments, update progress, and see patterns across complaints.

## The problem

Civic problems can be difficult to report and follow up on. Residents may not know whether an issue has been recorded, who is handling it, or whether its status has changed.

## What the website does

### For citizens
- Create an account and sign in.
- Submit a complaint with a title, description, category, and locality.
- Receive a complaint reference number and view the status and update history.
- Search their own complaints and request that a resolved issue be reopened.
- Optionally share their current GPS coordinates with a complaint. The browser asks for location permission, and coordinates are attached only when the citizen explicitly opts in.

### For administrators
- Sign in to a restricted admin account.
- View and search complaints across users, with filters for status and category.
- Review a complaint, assign a department, update its status, and add an update note.
- View dashboard summaries and visual breakdowns by category, status, locality, and month.
- See GPS-tagged complaints on an interactive map and open directions to a reported location.
- Export the currently filtered complaint list as a CSV file and inspect the audit trail.

## How it works

1. A citizen registers and submits a report.
2. The system saves it in the local database and generates a reference ID.
3. An administrator reviews it and records status or department updates.
4. The citizen can sign back in to check the recorded progress.

**Project scope:** This is a prototype civic-tech project. It is not connected to Gwalior Municipal Corporation or another government department, and submitting a complaint here does not file an official government grievance.

## Technology

- **Frontend:** HTML, CSS, JavaScript
- **Backend:** Python standard library HTTP server
- **Database:** SQLite
- **Map:** Leaflet with OpenStreetMap tiles
- **Browser location:** Geolocation API (requires user permission; available on localhost or HTTPS in supported browsers)

No third-party Python packages are required for the current local version. The PostgreSQL schema file is a reference for a possible future migration; the current server uses SQLite.

## Run it locally

Requirements: Python 3.10 or newer.

### Windows

Open Command Prompt in the project folder and run:

```bat
python --version
python server.py
```

If `python` is not recognized, install Python and select **Add Python to PATH** in the installer, then reopen Command Prompt.

### macOS / Linux

```bash
python3 --version
python3 server.py
```

Then open **http://127.0.0.1:3000** in your browser. Keep the terminal open while the server is running. The SQLite database file is created locally on first startup and is excluded from Git.

## Troubleshooting sign-in

- **New citizen on this copy:** choose **Sign in → Create a citizen account** and register with a valid email and a password of at least 12 characters.
- **Account made in the visual preview or another project folder:** those accounts are separate from this version's SQLite database. Register again in this local version; accounts are not automatically shared between previews, databases, or project folders.
- **Existing account suddenly not found:** start `server.py` from the same folder every time and keep the same `samadhan_sathi.sqlite3` file. Do not delete the database file; it stores account and complaint records.
- **Admin sign-in:** admin accounts are separate from citizen accounts and must be provisioned in the SQLite database used by this running server (see the admin setup section below).

## Create the first administrator

Stop the server, then run:

```bash
python server.py --create-admin
```

Follow the prompts and choose a unique password of at least 14 characters. If the email already belongs to a citizen account, the command requires an explicit confirmation before promoting it. To reset an existing administrator account, use the same command and follow the `RESET ADMIN` prompt. Restart the server with `python server.py`.

Administrator accounts cannot be created from the public registration form.

## Project structure

```text
samadhan-sathi/
├── server.py
├── README.md
├── .gitignore
├── schema-postgresql-reference.sql
├── start-windows.bat
├── start-mac-linux.sh
└── public/
    ├── index.html
    ├── styles.css
    └── app.js
```

## Current limitations

- The project currently stores data in a local SQLite file, not a hosted database. For a multi-user production deployment, use persistent managed storage and review the application's security and deployment configuration first.
- Map tiles need an internet connection. Complaints without opted-in GPS coordinates still appear in the admin complaint table but cannot be shown as exact map pins.
- This prototype does not submit reports to a government system, verify identities by email, or provide official service-level guarantees.
- Do not commit passwords, API keys, the SQLite database, or real citizens' personal information to this public repository.
