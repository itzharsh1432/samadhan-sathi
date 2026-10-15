# Samadhan Sathi — Civic Grievance Website

Samadhan Sathi is a locally runnable civic complaint website prototype for Gwalior. It includes a Python backend, citizen registration/login, admin login, complaint tracking, status history, audit trail, notifications, and a SQLite database.

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

## Run locally

1. Install Python 3.10 or newer.
2. Open a terminal in the repository folder.
3. Run `python server.py` (on macOS/Linux, `python3 server.py`).
4. Open http://127.0.0.1:3000.

The SQLite database is created automatically and remains on the local machine. It is deliberately excluded from Git.

## Admin setup

Stop the server and run `python server.py --create-admin`. Enter an admin email and a strong password (at least 14 characters), then confirm the password. If the email already belongs to a citizen account, the command requires you to type `PROMOTE` before it changes that existing account to admin and resets its password. If an existing admin cannot sign in, type `RESET ADMIN` when prompted to reset its password. Restart with `python server.py`. Admin accounts cannot be created or promoted through public registration.

If admin sign-in fails, make sure the server is running from this exact project folder and create/reset the admin account using the command above. The demo credentials in the standalone preview do not work in the real local website.

## Deployment warning

This is a local prototype, not yet an official public service. Do not expose it directly to the public internet or enter sensitive citizen data before a security review and deployment hardening. For a real deployment, configure HTTPS, a persistent managed database or durable storage, secure session settings, backups, monitoring, email verification/password recovery, rate limiting, and privacy/data-retention processes. Review `schema-postgresql-reference.sql` before planning a PostgreSQL migration; the current `server.py` uses SQLite and does not connect to PostgreSQL. GPS is optional; browser geolocation generally works on localhost or HTTPS. Exact coordinates are only saved after the citizen opts in, and the admin map uses Leaflet/OpenStreetMap tiles when internet access is available.

AI-assisted wording/category suggestions use a rule-based fallback and are not official decisions.
