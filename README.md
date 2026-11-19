# MediBed Pune: codebase handover

The Python / Flask codebase deployed on Render, including the hospital-login repair. Start with ARCHITECTURE.md and docs/architecture.png for the design.

## Share and run

Yes, this ZIP can be sent to another computer. Extract it, install Python 3.11 or 3.12, install dependencies and start the application. This copies the source code, not the hosted database, registered patients, passwords or public URL. Phones can open the hosted site; running the code requires a suitable computer/server.

On Windows, open PowerShell in the extracted MediBed-Pune folder:

```powershell
python -m venv --copies "$env:LOCALAPPDATA\MediBedShowcase\venv"
$medibedPython = "$env:LOCALAPPDATA\MediBedShowcase\venv\Scripts\python.exe"
& $medibedPython -m pip install -r requirements.txt
$env:PYTHONDONTWRITEBYTECODE = '1'
& $medibedPython -B app.py
```

On macOS/Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B app.py
```

Open http://127.0.0.1:5000. Keep the terminal running. There is no Node/npm build step. Dependencies require internet for the initial installation. Run from a normal local folder; changing Windows security settings is unnecessary.

## Accounts and private runtime

A fresh local installation initializes the Pune directory, labeled synthetic evaluation inventory/history and six hospital-workspace accounts. It does not seed patient accounts. Patients register on /register. Hospital usernames are jehangir, ruby-hall, kem-pune, deenanath-mangeshkar, poona-hospital and sassoon-general. Fresh passwords are random and differ from the hosted site.

To find the private credential file on Windows:

```powershell
& $medibedPython -B -c "from app import create_app; app=create_app(); print(app.config['INSTANCE_DIRECTORY'])"
```

Open admin-credentials.txt inside that directory. Runtime storage is outside source under LOCALAPPDATA on Windows, and instance/pune-v2 under the extracted folder on macOS/Linux. Do not redistribute databases, private credential files or a real .env.

## Code walkthrough

- app.py: Flask application factory, security hooks, routes and database initialization.
- config.py: development/production configuration, SQLite or PostgreSQL connection settings.
- models.py: nine application tables, foreign keys and reservation constraints.
- routes/: public pages/API, authentication, patient actions, hospital admin actions, forecasts.
- services/: booking transactions, inventory/history, notifications, throttling/auditing and forecasts.
- seed.py and data/: sourced Pune directory, labeled synthetic evaluation inventory, optional private admin bootstrap.
- templates/ and static/: Jinja UI, vendored Bootstrap/Chart.js, browser polling and tap-to-call links.
- tests/: regression and historical test sources; see VERIFICATION.md for exactly what was executed.
- tools/: explicit backup, migration and password-rotation utilities.
- render.yaml and wsgi.py: Render infrastructure declaration and Gunicorn entry point.

## Hosted hospital account provisioning

Directory-only deployments use AUTO_SEED=false and PUBLIC_DIRECTORY_SEED=true. If the hosted database has no hospital admins, supply HOSPITAL_ADMIN_BOOTSTRAP_JSON privately in the host's environment: a JSON object mapping exactly the six hospital usernames above to strong distinct passwords. Never commit this mapping. With an explicit mapping, startup creates missing admins or synchronizes their passwords; repeated unchanged settings do not rehash passwords. Without the mapping, directory-only startup does not create/alter admin accounts. Existing patient accounts and requests are preserved.

Production also requires APP_ENV=production, a random SECRET_KEY of at least 32 characters, the trusted hostname, HTTPS, and DATABASE_URL pointing to durable storage. Render stores application state in managed PostgreSQL. The checked-in render.yaml is infrastructure configuration, not a copy of the active service's private environment. A new hosting deployment needs its own private environment/account setup; do not reuse live secrets from another deployment.

## Operating boundaries

The Render-hosted app does not require the laptop to remain online. A localhost server or old temporary tunnel does require its host computer to stay awake and connected. Turning off only the display is fine; sleep, hibernation, shutdown and internet loss stop a laptop-hosted link. Closing the lid may trigger sleep. No Windows power/security settings have been changed.

The six real Pune hospital listings are directory references, not affiliated accounts. Inventory/history are explicitly labeled synthetic or unverified workspace data; hospital feeds are not connected. Requests and decisions remain internal to this application. Phone links open a dialer/calling app; no automatic call, vehicle dispatch, GPS tracking or live ETA is implemented. Forecasts are experimental and not for clinical decisions. See THIRD_PARTY_NOTICES.md and data/ license/source files for third-party assets and the evaluation dataset.
