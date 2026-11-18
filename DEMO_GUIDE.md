# MediBed — live demonstration guide

Use fictional accounts only. Begin with: **“This is a university prototype using demo data. It cannot provide actual medical admissions or emergency transport. For real emergencies in India, call 112.”**

## Before presenting

Open VS Code PowerShell in this project and run:

```powershell
& "$env:LOCALAPPDATA\MediBed\venv\Scripts\python.exe" app.py
```

Browse to [http://127.0.0.1:5000](http://127.0.0.1:5000). Keep the terminal running. UI libraries are bundled locally, so no CDN is needed during the presentation. Use an ordinary window for the patient and a private/incognito window for the admin if you want both roles simultaneously; ordinary tabs share a session. Do not submit real patient details.

Demo credentials (development only):

- Patient: `patient@medibed.demo` / `Demo@123`
- Main admin: `admin@medibed.demo` / `Demo@123` (Demo City Hospital, Pune)
- Second admin: `admin2@medibed.demo` / `Demo@123` (Demo Care Center, Pune)

The app preserves previous demonstrations. Cancel your previous matching patient request before creating another one. `python seed.py` is idempotent and does not reset your edits. An unused `MEDIBED_INSTANCE_DIR` starts a separate demo database without deleting existing work.

## A polished eight-minute presentation

### 1. Start with the public portal (one minute)

Show the demo banner first, then the homepage summary cards. Explain six fictional hospitals across Pune, Mumbai and Surat. Choose **Pune**, **ICU**, **Oxygen required** and **Ventilator required**, then click **Find hospitals**. These filters query SQLite. Open **MediBed Demo City Hospital** and note its ICU/ventilator availability.

Explain: General/ICU/emergency are exclusive physical categories. One ventilator-equipped ICU bed counts as **one physical bed**, with overlapping equipment attributes. Availability is not a confirmed reservation.

### 2. Submit the patient's request (one minute)

Sign in with the patient account. Reopen Demo City Hospital (hospital 1). Choose ICU, oxygen and ventilator. Select normal or emergency priority. Explain that priority is only a demonstration sorting aid, not clinical triage. Leave **Join waiting list if unavailable** checked. Submit.

Show the request ID, **Pending** status and submission notification in **My requests**. No inventory reservation occurs at submission. If no matching bed exists, the status is **Waitlisted** instead.

### 3. Approve as hospital administrator (one minute)

In the private window, sign in with the main admin account. Point out the hospital assigned in the sidebar. Open **Admission requests** and identify the patient's new request by name/ID. Click **Approve → Confirm**. Show the assigned bed code and approved status.

Explain that the service checks hospital ownership and all requirements, conditionally reserves one available bed, records the decision and sends the patient a notification in one transaction. Another request cannot take that same bed. If no eligible bed remains, approval returns a clear conflict and preserves the request.

### 4. Show shared state and notifications (one minute)

Open **Overview**: available count decreases, reserved count increases. Open the public hospital profile to show the same updated count. Return to the patient window and allow a 5-second poll (or focus it after switching). Show **Approved**, the assigned code and **Demo request approved** notification. Click **Mark as read** and show the bell count decrease.

Call this **near-real-time polling**, not live verified availability or continuous push synchronization.

### 5. Show cancellation (30 seconds)

In **My requests**, cancel the approved demo reservation and confirm. Show its cancelled status and the restored available count. Explain that only that still-reserved bed is released; an occupied bed is never automatically released. Reservation history stays attached to the request.

### 6. Demonstrate inventory management (one minute)

As admin, open **Bed inventory**. Filter to available general beds. Choose an unallocated bed such as GEN-001 → **Edit → Occupied → Save bed**. Show the overview and public availability decrease. Change the same bed back to available after explaining that this is an explicit administrator edit.

Add `DEMO-NEW-01`, choose ICU, enable oxygen/ventilator, and save. Show its single physical bed contribution, then optionally delete it while it has no allocation history. Reserved rows display **Reservation protected**, and have no ordinary Edit/Delete actions. Deleting occupied beds or beds with historical assignments is prohibited server-side.

### 7. Demonstrate a waiting-list notification (optional, one minute)

For a reproducible case at the main hospital:

1. As admin, filter **emergency** beds and set each currently available emergency bed to **maintenance**. Note the codes/statuses so you can restore your deliberate demonstration edits.
2. As patient, request an emergency-category bed at Demo City Hospital with **Join waiting list if unavailable** selected. Its status becomes **Waitlisted**.
3. As admin, change one of those maintenance beds back to **Available**.
4. The patient receives **A matching demo bed is available** on the next poll. The request remains **Waitlisted**. No automatic approval occurs.
5. Approve it manually, or cancel the request as patient. Restore remaining demonstration maintenance changes if desired.

The seeded patient also has a waitlisted ICU/ventilator example at fictional hospital 3, where all ventilator-equipped beds initially have occupied status.

### 8. Finish with forecasts and transport (one minute)

Open **Forecasts**. Choose Demo City Hospital and ICU. Show current database availability, next-day experimental prediction, physical capacity and 45 synthetic history points. Explain actual RandomForest training, previous-day/three-day/trend features, chronological validation and the measured MAE. The prediction is capped at category capacity. No clinical accuracy or real-world forecast quality is claimed.

Open **Demo ambulances**. Filter by city. Read the **simulated ETA** label and demonstrate that there is no dispatch or vehicle tracking. Point back to the 112 guidance.

## What is functional database state vs simulation?

| Real local application behavior | Fictional/synthetic inputs |
|---|---|
| Account creation, password hashing, signed sessions and CSRF | Seeded identities and development credentials |
| SQL filtering and actual physical bed counts | Institution names, addresses, contact references and initial bed statuses |
| Inventory CRUD, transactional approval, cancellation, ownership checks | Every reservation represents a demo action, never an actual admission |
| Persisted notification delivery and read flags | No external email/SMS service |
| Actual sklearn fitting and measured holdout MAE | All historical training/validation availability |
| Ambulance database filtering | Fictional providers, statuses and simulated ETAs; no GPS |

## Suggested faculty viva questions

**Why Flask and SQLite?** A clear Python monolith is easy to run and explain locally. SQLite gives persistent relational data without a database server. Production-scale requirements would need further architecture and operational work.

**How do you prevent double booking?** Conditional `available → reserved` updates and conditional request decisions run in one transaction; a failed update rolls back. A partial unique index also prevents two active approvals referencing one bed. A concurrent two-client pytest verifies exactly one succeeds for a single eligible bed.

**Why store each bed rather than total counters?** A physical record has one category and a status. Aggregation is derived, avoiding independent counters drifting apart and preventing capability double counting.

**How is hospital ownership enforced?** The signed session identifies an admin, whose hospital assignment is stored server-side. Every inventory/request mutation verifies that assignment. Submitted hospital IDs cannot grant access to another hospital.

**What happens if a reserved bed is edited?** Ordinary edits/deletion return conflict. It must be released through the owning patient's cancellation. There is no production admit/discharge workflow in this prototype.

**What is CSRF and how is it handled?** It is an unwanted state-changing request using a victim's session. Every write requires a per-session token in a custom header. Tokens rotate on authentication and logout; cookies use SameSite=Lax and HttpOnly.

**Is Flask session authentication server-side storage?** The identity is stored in a signed cookie, while account role/hospital data is looked up in SQLite per request. The signature protects against modification; the cookie is not a place for passwords or clinical records.

**What makes the dashboard near-real-time?** JavaScript polls JSON endpoints every five seconds while visible. Switching back triggers refresh. It is periodic polling, not push synchronization and not a hospital-verified data feed.

**Does emergency priority perform triage?** No. It only sorts fictional requests; no automated clinical prioritization or medical advice is provided.

**How do you prevent ML leakage?** For a target day, all availability features use strictly previous observations. Validation is chronological. After measuring holdout MAE the model is refitted on observed data to predict the next day.

**What if ML fails?** A three-day moving average is used, or current availability for missing/stale history. The method is labeled and core booking/inventory routes remain independent.

**Is the MAE a medical accuracy claim?** No. It is an actually calculated regression error on held-out synthetic data, measured in beds. It says nothing about clinical validity or performance at real hospitals.

**What are the privacy boundaries?** The app asks for a name, email and password only. It collects no diagnoses, Aadhaar numbers, medical reports or clinical records. Do not put real patient information into this classroom demo.

**What would be next for production?** Verified institutional participation, data governance/consent, auditability, migrations, stronger identity controls, rate limiting, TLS, production hosting, an authorized admit/discharge workflow and validated real-data forecasting.

## Troubleshooting on stage

- **No matching bed:** use a different category/capability, join the waiting list, or add a fictional matching bed as the owning admin. Do not claim a real reservation.
- **Already active matching request:** use My requests to review/cancel it; repeated seeding intentionally preserves it.
- **CSRF expired:** refresh the tab; signing in/out rotates the token. Avoid using the same session for both roles in ordinary tabs.
- **Counts appear stale:** focus the tab and allow the next five-second poll; check the connection indicator and running terminal.
- **Port already in use:** use the existing app or set `$env:PORT = "5001"` before starting a second one.
- **OneDrive signed out / protected folder writes fail:** the runtime and virtual environment are outside OneDrive; use the commands in README. Do not disable Defender.
