# MediBed — Smart Hospital Bed Availability & Emergency Coordination

A complete locally runnable university PBL prototype for browsing public Pune hospital directory entries, managing illustrative bed inventory, and coordinating demo admission requests. The Flask monolith uses real SQLite state for accounts, inventory, requests, reservations and notifications.

**Demo Data — Not for Emergency Use.** Hospital directory details are public references, not evidence of participation or endorsement. All bed availability, equipment attributes, ambulance states and forecasts are synthetic or workspace-entered, not hospital-reported or verified. This is not a deployed medical service; no real admission, vehicle tracking or clinically validated prediction is claimed. For a real emergency in India, call [112](tel:112).

## Problem and proposed solution

Fragmented bed information makes coordination hard to demonstrate clearly. MediBed presents one searchable inventory, patient request tracking and a hospital workspace. A hospital administrator can approve a request only when an eligible physical bed can be reserved in a database transaction. Waiting-list users receive availability notifications but are never automatically approved.

## Quick start in VS Code PowerShell (Windows)

Python 3.11+ is required; this workspace was tested with Python 3.12.10. Open the **Healthcare** folder in VS Code, then its PowerShell terminal:

```powershell
cd "C:\Users\offic\OneDrive\Desktop\Healthcare"
$medibedEnv = Join-Path $env:LOCALAPPDATA "MediBed\venv"
python -m venv --copies $medibedEnv
& "$medibedEnv\Scripts\python.exe" -m pip install -r requirements.txt
$env:Path = "$medibedEnv\Scripts;$env:Path"
python app.py
```

Open [MediBed locally](http://127.0.0.1:5000). The first startup creates tables and seeds fictional records automatically. The environment in `%LOCALAPPDATA%\MediBed\venv` is already installed on this machine. Subsequent starts can simply use:

```powershell
& "$env:LOCALAPPDATA\MediBed\venv\Scripts\python.exe" app.py
```

Alternatively, run ` .\start.ps1 ` from a terminal that already permits local PowerShell scripts. It creates the environment if missing, checks imports, installs missing dependencies and starts the app. If script execution is disabled, use the explicit Python commands above; changing Windows security settings is unnecessary.

Stop the development server with **Ctrl+C**. It binds to `127.0.0.1` only, with debug mode disabled. To choose another port: `$env:PORT = "5001"` before starting. No Docker, Node/npm, paid API, API credential, external database or cloud deployment is required.

### Runtime files and OneDrive

On Windows, SQLite and the local secret key live in `%LOCALAPPDATA%\MediBed\<workspace-id>\`, outside OneDrive and protected Documents. The workspace ID is derived from the project path, so separate checkouts have separate databases. On other systems they default to `instance/`. The virtual environment is separate from source as well. This avoids the write failures encountered in this computer's OneDrive folder. No Defender exclusions or security settings are changed.

To print the actual database location:

```powershell
& "$env:LOCALAPPDATA\MediBed\venv\Scripts\python.exe" -c "from app import create_app; a=create_app(); print(a.config['SQLALCHEMY_DATABASE_URI'])"
```

`MEDIBED_INSTANCE_DIR` can override runtime storage; `DATABASE_URL` can override the database URL. Use a **new empty runtime directory** if you want an independent fresh demo. Existing demo changes are intentionally preserved. Moving the project changes its default workspace ID.

### Environment configuration

`.env.example` documents available settings. Optionally copy it to `.env` and set a strong random `SECRET_KEY` (never commit it):

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Without an environment key, MediBed generates and persists a random development secret in the runtime directory. Session cookies are HttpOnly and SameSite=Lax, with a two-hour lifetime. Secure cookies are opt-in through `SESSION_COOKIE_SECURE=true` for HTTPS; keep false for localhost HTTP. The temporary Render setup below is not production hardening.

### Temporary free hosting on Render

The included `render.yaml` configures a free web service with a free PostgreSQL database. This is only suitable for a short demonstration, not production or real patient information: free web instances sleep after 15 minutes without traffic and can take about a minute to wake; free databases expire after 30 days. The hosted app gets a new `onrender.com` address; a `trycloudflare.com` quick-tunnel address cannot be retained while your device is offline.

1. Keep the GitHub repository **private**. Never commit `.env`, a database file, admin passwords, or a database connection URL.
2. Before migrating, back up the local database and rotate the six hospital-admin passwords using hidden terminal prompts:

   ```powershell
   $python = Join-Path $env:LOCALAPPDATA "MediBed\venv\Scripts\python.exe"
   & $python tools/backup_database.py
   & $python tools/rotate_hospital_admin_passwords.py
   ```

   Passwords are hashed in the local database and are not printed. This does not change patient registrations.
3. In Render, create a **Blueprint** from the private GitHub repository. The blueprint sets `AUTO_SEED=false` and `PUBLIC_DIRECTORY_SEED=true`: the public hospital directory and labeled synthetic demo inventory are initialized, but no replacement hospital-admin accounts are created. Existing accounts and registrations must be migrated separately.
4. Copy the Render database's **external** connection URL into a PowerShell secure prompt and migrate the current local database. Determine the local SQLite path before setting `DATABASE_URL`:

   ```powershell
   $sourceDb = & $python -c "from config import configuration; from sqlalchemy.engine import make_url; print(make_url(configuration()['SQLALCHEMY_DATABASE_URI']).database)"
   $secureUrl = Read-Host "Render external PostgreSQL URL" -AsSecureString
   $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureUrl)
   try {
       $env:DATABASE_URL = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
       & $python tools/migrate_sqlite_to_postgres.py --source $sourceDb
       if ($LASTEXITCODE -ne 0) { throw "Database migration failed." }
   } finally {
       Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
       [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
   }
   ```

   The migration makes a timestamped local backup first and refuses to copy into a non-empty database. It copies account hashes and application records; the admin passwords rotated in step 2 are the ones that remain valid. Keep the backup private.

The free service may be slow on its first request after sleeping. Export the hosted database before Render's 30-day free-database expiry if you need to keep registrations beyond the demo.

## Account credentials

Public registration creates patient accounts; hospital-admin accounts are created by the seed process and assigned to one hospital. Newly generated admin passwords are written only to the private runtime credentials file. Do not put account passwords in source control or public documentation. The temporary hosting procedure above rotates admin passwords before upload.

## Features and modules

- Public portal: city, hospital category, bed type, oxygen and ventilator filters implemented by SQLAlchemy queries; actual inventory cards, profiles, timestamps and 5-second refreshes.
- Patient portal: registration, sign-in, normal/emergency demo request priority, capability requirements, waiting-list option, request history, assigned demo beds, cancellation and notifications.
- Hospital workspace: assigned-hospital KPIs, status doughnut, category availability bars, add/edit bed dialogs, safe deletion, request decisions, reservation history, analytics and notifications.
- Transactional reservations: least-equipped eligible available bed selected, conditional status change, conditional request decision, notifications and commit as one transaction. Conflict returns HTTP 409 and rolls back.
- Cancellation: active pending/waitlisted requests or approved reservations can be cancelled by their patient. Only a bed still reserved for the cancelled request is released. Occupied beds are never automatically released.
- Waiting list: notification on newly matching availability; administrator approval is still required. A ventilator requirement implies oxygen.
- Notifications: persisted records, unread bell count, notification lists and mark-as-read action.
- Transport explorer: six fictional ambulance providers, city/status filters, clearly simulated ETAs; no dispatch controls or GPS claims.
- Availability lab: actual RandomForestRegressor, 45 days of synthetic history per hospital/category, next-day prediction, history chart, calculated chronological validation MAE and graceful fallbacks.
- Responsive design, local vendored Bootstrap 5 / Chart.js, Bootstrap hospital icon and custom SVG icons, native dialogs, accessible labels, empty/error states and toast feedback.

## Architecture and folder structure

```text
Healthcare/
├── app.py                 # Application factory, security hooks, error envelopes
├── config.py              # Environment configuration and runtime paths
├── models.py              # Seven relational model classes + constraints
├── seed.py                # Idempotent fictional data
├── requirements.txt
├── start.ps1
├── pytest.ini
├── .env.example
├── .gitignore
├── README.md
├── DEMO_GUIDE.md
├── TEST_RESULTS.md
├── THIRD_PARTY_NOTICES.md
├── routes/
│   ├── auth.py            # Authentication APIs
│   ├── public.py          # Pages, public APIs, notifications, ambulances
│   ├── patient.py         # Patient requests and cancellation
│   ├── admin.py           # Hospital-owned inventory and decisions
│   └── predictions.py
├── services/
│   ├── common.py          # Validation, response helper, role guard
│   ├── inventory.py       # Derived physical counts
│   ├── booking_service.py # Atomic allocation and cancellation
│   ├── notification_service.py
│   └── prediction_service.py
├── templates/
│   ├── base.html / icons.html
│   ├── index.html / hospital_detail.html / auth.html
│   ├── patient_dashboard.html / admin_dashboard.html
│   └── ambulances.html / predictions.html / error.html
├── static/
│   ├── css/style.css / responsive.css
│   ├── js/main.js / dashboard.js / admin.js
│   ├── img/mark.svg
│   └── vendor/bootstrap.min.css / chart.umd.min.js / hospital.svg
└── tests/
    ├── conftest.py
    ├── test_auth.py / test_inventory.py / test_requests.py
    └── test_predictions.py / test_pages.py
```

Browser → Jinja pages and Fetch APIs → Flask blueprints → services → SQLAlchemy → SQLite. There is no frontend build step. Flask's factory supports temporary test databases. Every write route checks CSRF before role/ownership and domain validation. Response output uses Jinja autoescaping or explicit JavaScript HTML escaping. A same-origin CSP, no-store API responses, frame denial and content-type protection are applied.

## Technology stack

Python 3.11+, Flask, Flask-SQLAlchemy, SQLite, Werkzeug hashing, signed Flask sessions, Jinja2, HTML5, CSS3, Bootstrap 5.3.8, vanilla JavaScript, Fetch, Chart.js 4.5.1, Bootstrap Icons 1.13.1, scikit-learn RandomForestRegressor, NumPy, pytest and the Flask test client. Runtime UI assets are served locally; after Python dependencies are installed, the app has no outbound network requirement.

## Relational schema

| Model | Purpose and integrity rules |
|---|---|
| User | Name, unique normalized email, hash, patient/admin role, optional assigned hospital, created timestamp. Role/hospital consistency constraint. |
| Hospital | Unique fictional name, city/area/address, government/private category, fictional non-callable contact reference, optional coordinates, last_updated. |
| Bed | Hospital FK, hospital-unique code, one physical category, oxygen/ventilator booleans, status, updated timestamp. Ventilator requires oxygen. |
| AdmissionRequest | Patient/hospital FKs, category, requirements, priority, status, assigned bed FK, submission/decision timestamps. Partial unique index forbids two active approvals sharing a bed. |
| Notification | User FK, title/message, unread flag, created timestamp. |
| Ambulance | Unique fictional provider, city/area, status, simulated nonnegative ETA, type, is_demo. |
| BedHistory | Hospital/category/date unique record, physical capacity and bounded synthetic availability. |

**General, ICU and emergency are mutually exclusive physical categories. Oxygen and ventilator are attributes.** Status totals partition the physical bed count. Capability counts overlap those categories and each other. There are no independently editable aggregate counters. Foreign-key enforcement is enabled on SQLite connections. Beds linked to any reservation history cannot be deleted; occupied and reserved beds cannot be deleted. Approved allocations are protected against ordinary edits.

## JSON API

Success envelope: `{"ok":true,"data":...,"message":...}`. Error envelope: `{"ok":false,"data":null,"error":{"code":409,"message":"..."}}`. Codes: 200/201 success, 400 validation/CSRF, 401 unauthenticated, 403 unauthorized, 404 missing record, 409 conflict, 500 unexpected failure. Unexpected internals are logged locally and not returned to the browser.

| Method | Endpoint | Access / useful parameters |
|---|---|---|
| POST | `/api/auth/register` | Public + CSRF; name/email/password; patient only |
| POST | `/api/auth/login` | Public + CSRF; email/password |
| POST | `/api/auth/logout` | Session + CSRF |
| GET | `/api/auth/me` | Public; user and CSRF token |
| GET | `/api/health` | Public; database connectivity |
| GET | `/api/hospitals` | city, hospital_type, bed_type, oxygen_required, ventilator_required, available_only, q |
| GET | `/api/hospitals/<id>` | Public; profile + counts |
| GET | `/api/dashboard/stats` | scope=public; scope=admin requires admin |
| GET | `/api/admin/beds` | Admin; bed_type/status, own hospital only |
| POST | `/api/admin/beds` | Admin; bed_code, bed_type, has_oxygen, has_ventilator, status |
| PATCH | `/api/admin/beds/<id>` | Admin; validated editable fields, own unallocated bed |
| DELETE | `/api/admin/beds/<id>` | Admin; only own available/maintenance bed without history |
| GET | `/api/admin/requests` | Admin; status, own hospital only |
| POST | `/api/admin/requests/<id>/decision` | Admin; decision=approve/reject |
| POST | `/api/requests` | Patient; hospital_id, requested_bed_type, oxygen_required, ventilator_required, priority, join_waitlist |
| GET | `/api/requests/mine` | Patient; status |
| POST | `/api/requests/<id>/cancel` | Owning patient |
| GET | `/api/ambulances` | Public; city/status |
| GET | `/api/predictions` | Public; hospital_id, bed_type |
| GET | `/api/notifications` | Authenticated; unread_only; latest 100, plus total unread count |
| POST | `/api/notifications/<id>/read` | Notification owner |

Booleans in JSON must be actual `true` / `false`. Query booleans accept `true`, `false`, `1`, `0`. All state-changing requests require the session's `X-CSRF-Token`, even login, registration and logout. Obtain it from `/api/auth/me`, retain the session cookie and update the token after authentication. Browsers get it through the HTML meta tag; `main.js` sends it automatically. No permissive CORS is configured.

Example request body:

```json
{"hospital_id":1,"requested_bed_type":"icu","oxygen_required":true,"ventilator_required":true,"priority":"emergency","join_waitlist":true}
```

Emergency priority changes display/sorting only. It is not clinical triage. Submitting a request never reserves a bed. A no-match request needs the explicit waiting-list option; otherwise the API returns 409.

## Reservation integrity

Approval checks hospital/category/capability/status, conditionally updates `available → reserved`, conditionally changes an undecided request to approved, assigns the bed, touches the hospital timestamp, creates notifications and commits. Any failed conditional write or database contention rolls back the transaction and returns 409. A partial unique database index independently disallows two approved requests with the same bed. The test suite runs two simultaneous clients against a file-backed SQLite database with one matching bed; exactly one approval succeeds.

Inventory edits and deletion also use conditional writes so a concurrently reserved bed cannot be overwritten or deleted. Cancelling approved requests conditionally claims the request and releases only its still-reserved bed; an occupied bed is left occupied. Historical assignments stay attached for auditability. SQLite foreign keys prevent dangling references.

## Near-real-time updates

Vanilla Fetch polling runs every **5 seconds**, with a loading state and connection feedback. Public availability, hospital profiles, admin KPIs/request tables, patient request status and notification counts/lists refresh without full-page reloads. Polls pause in hidden tabs and refresh on return. This is periodic near-real-time observation, **not continuous push-based synchronization**. It is not live verified hospital data. Ambulance ETAs remain static simulated values.

## Machine learning methodology

For hospitals without existing inventory or history, seeding creates 45 deterministic synthetic daily observations per bed category. Scaled availability/capacity profiles come from the synthetic Kaggle dataset linked in `data/KAGGLE_HOSPITAL_BEDS_NOTICE.txt`; daily variation, equipment flags and hospital-specific assignments are illustrative demo transformations, not hospital facts. For a target day, features are weekday, preceding-day availability, a mean of the preceding three observations and the recent availability change. No target/future availability is used to construct that example's features.

The first 80% of chronological training examples train a 60-tree RandomForestRegressor (`random_state=42`, bounded depth). The last 20% form a chronological one-step holdout; the displayed MAE is actually computed on those synthetic days. The model is then refitted on all observed historical examples to estimate next-day availability. Results are cached per series/date and clamped between zero and current physical category capacity. Current editable inventory is shown separately from synthetic history.

Insufficient history or training/import failure uses a recent three-day average. Missing or stale history uses current availability and labels this fallback. Model failure never blocks admission or inventory endpoints. No clinical predictive accuracy is claimed. Forecast responses identify the synthetic Kaggle source when applicable and include an explicit medical-use disclaimer.

## Seeding and testing

After selecting the environment in the quick start:

```powershell
python seed.py
python -m pytest
```

Or use the full local interpreter path. Repeated seeding preserves existing hospitals, beds, account credentials and request state. The source CSVs and license/attribution notice are stored in `data/`. The first seed creates a scaled sample inventory and 45 synthetic history rows per category only for hospitals without existing inventory/history. Each generated bed code and forecast source is labeled as Kaggle-derived synthetic demo data. Availability can change during your demonstration.

Tests create isolated temporary SQLite files, use genuine CSRF tokens and do not alter your demo database. They cover authentication, role/hospital ownership, CRUD, filters, counts, decisions, concurrent allocation, cancellation, waiting lists, notifications, forecasting/fallbacks, page rendering and idempotence. See `TEST_RESULTS.md` for executed results and browser verification.

## Step-by-step demonstration

1. Open the homepage and point out the demo banner and 112 link.
2. Search **Pune → ICU → Oxygen + Ventilator**. Open **MediBed Demo City Hospital** and note available counts.
3. Sign in as `patient@medibed.demo`. Open that hospital, choose ICU, required capabilities and demo priority, then submit a request. Its initial status is pending; inventory has not been reserved.
4. Sign out, then sign in as `admin@medibed.demo`. Review the matching request in **Admission requests** and select **Approve → Confirm**.
5. Show the assigned bed code, reserved count increase and available count decrease. Visit the public profile to show the same database state.
6. Sign in as the patient again. Show approved status, assigned bed and notification. Mark the notification read.
7. Cancel that reservation and show the bed becomes available again. No occupied beds are automatically changed.
8. As admin, **Bed inventory → Edit** an unallocated available bed → Occupied → Save. Observe the public count change; restore it if desired.
9. Show the existing patient waiting-list example and explain notifications require newly matching availability while approval remains manual.
10. Open **Forecasts** and **Demo ambulances**. Describe synthetic history, measured MAE and simulated ETAs.

For a fuller script and faculty viva answers, see [DEMO_GUIDE.md](DEMO_GUIDE.md).

## Prototype limitations and future scope

No real hospitals, contacts, admissions, medical records, clinical triage, vehicle tracking, dispatch, payment, email or SMS integration. Forecast history is synthetic and is not rewritten by inventory edits. There is no admit/discharge workflow that converts reservations to occupied beds; approved reservations are intentionally immutable in ordinary inventory editing and can be cancelled by their patient. Notifications do not guarantee a bed remains available. The demonstration polling interval is not a service-level commitment.

This is a development prototype. It has no password reset/email verification, lockout, multi-factor authentication, production audit system or verified institutional integrations. Demo credentials must never be used in production. The temporary Render setup is for a short demonstration only; multi-site production operation would require a different operational design and verified institutional integrations.

Future scope: verified hospital onboarding, consent and privacy review, authorized admit/discharge workflows, audited inventory feeds, PostgreSQL/migrations, production identity management, accessible map navigation, validated forecasting on appropriately governed real datasets and separately integrated authorized transport coordination.

Technical references: [Flask security](https://flask.palletsprojects.com/en/stable/web-security/), [SQLAlchemy ORM DML](https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html), [RandomForestRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestRegressor.html). Third-party UI attribution is in `THIRD_PARTY_NOTICES.md`.
