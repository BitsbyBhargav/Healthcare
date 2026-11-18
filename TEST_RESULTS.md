# MediBed verification

Executed locally on **18 November 2026**, Windows, Python **3.12.10**, using the virtual environment at `%LOCALAPPDATA%\MediBed\venv`.

## Automated backend tests

Command:

```powershell
& "$env:LOCALAPPDATA\MediBed\venv\Scripts\python.exe" -m pytest
```

Latest full backend run: **30 passed in 44.50 seconds**, exit code 0. This run includes the final seed adjustment assigning an administrator to every hospital.

The tests use Flask test clients, real CSRF/session behavior and isolated temporary file-backed SQLite databases. They do not modify the running demo database.

Coverage of acceptance workflows:

| Workflow | Executed check |
|---|---|
| Startup, tables, seed and health | Factory startup, health SELECT, six hospitals |
| Public homepage and all public pages | HTML routes and JSON APIs return 200 |
| Hospital filters | City + ICU + oxygen + ventilator; invalid parameter rejection |
| Physical bed counting | Category totals and status partitions agree; capabilities do not inflate capacity |
| Admin/patient authentication | Demo accounts, registration, normalized email, hashing, login/logout |
| CSRF and roles | Missing token rejected; patient/admin privileged routes separated |
| Inventory CRUD | Add/update/delete, duplicate code, invalid booleans/capabilities/status validation |
| Public availability update | Available → occupied decrements public and admin counts |
| Hospital ownership | Cross-hospital listing, updates, deletion and request decisions denied |
| Request submission/approval | Admin sees request; eligible bed becomes reserved; patient sees approved and notification |
| Double reservation | Two simultaneous clients compete for one matching ICU/ventilator bed; exactly one 200 and one 409 |
| Decision replay | Already approved request cannot be approved again |
| Rejection | Patient request rejected with inventory unchanged |
| Cancellation | Owning patient cancels active request/reservation; reserved bed restored; occupied bed remains occupied |
| Waiting list | No-match request requires waitlist opt-in; new availability notifies without auto-approving |
| Notification privacy | Only notification owner can mark it read |
| Forecast | Numeric capacity-bounded result, actual RandomForest fit, measured holdout MAE, required disclaimer |
| Fallbacks | Missing history/current-state fallback and insufficient-history moving average |
| Demo ambulances | Six is_demo providers and simulated labels |
| Idempotence | Repeat seed leaves record counts and deliberately edited status unchanged |
| Errors | Consistent 400/401/403/404/409 API behavior and rendered error pages |

`pip check` also completed successfully: **No broken requirements found.**

## Browser verification

Used the in-app browser against `http://127.0.0.1:5000` and the actual local demo database:

1. Inspected homepage and filtered Pune + ICU; two matching hospitals appeared.
2. Signed in as patient. Submitted request **#6** for an ICU bed with oxygen and ventilator at Demo City Hospital, emergency demo priority. UI showed Pending and a submission notification.
3. Signed out and signed in as the main hospital admin. Approved #6 through the confirmation dialog. The history table showed Approved and **ICU-001**.
4. Confirmed admin/public ICU availability fell from **6 to 5**, and the reservation count increased.
5. Edited **GEN-001** from available to occupied through the modal. Admin/public general availability fell from **13 to 12**. Restored GEN-001 to available afterward.
6. Signed back in as patient. Observed Approved, ICU-001 and the approval notification. Marked the notification read.
7. Cancelled the demo reservation through the confirmation dialog. The public hospital profile returned to **6 available ICU beds**. Request #6 remains in cancelled history; its reservation was released.
8. Opened the forecast page with bundled Chart.js; model, bounded numeric output, synthetic-data disclaimer and measured chronological validation MAE displayed. Opened fictional ambulance explorer and filtered Surat; two providers with simulated ETAs appeared.
9. Inspected responsive homepage and admin overview at **390 × 844**. Fixed a mobile admin overflow and verified page scroll width no longer exceeded the viewport. Mobile navigation opened correctly; tables/sidebar tabs scroll within their containers.
10. Rechecked bundled CSS, JS and Bootstrap hospital icon: each returned 200. The current app CSP permits same-origin scripts/styles, with no runtime CDN dependency. Inspected browser console warnings/errors on the forecast page: none were returned.

Screenshots were captured during browser verification; the approval screenshot lives at `C:\Users\offic\AppData\Local\MediBed\screenshots\patient-approval.jpg` on this computer. It shows the intermediate approved state before the cancellation test. The UI remains a fictional demo; no external medical action took place.

## Limits of verification

This is local prototype verification, not a production security audit, load test, clinical validation or real-hospital integration test. The concurrency test checks a real two-client SQLite allocation race, but does not establish production-scale throughput. Only the documented local browser and responsive sizes were inspected.
