# Verification record

Source commit: a9cea9218ca35e40019a52c54298443b9d12ab08 (BitsbyBhargav/Healthcare).

On 19 November 2026, the targeted hosted-admin bootstrap regression file passed all 6 tests. Coverage includes missing admin provisioning in directory-only mode, preservation of existing patients, stable reseeding, explicitly configured password synchronization, malformed/weak configuration rejection, hospital ownership isolation, approval and rejection.

The live Render deployment was then verified with all six user-supplied hospital credentials: successful login, admin page access, hospital-scoped request visibility and rejection of cross-hospital access. A separate clearly named synthetic workflow identity exercised approval, rejection, patient-visible updates and cancellation; only its newly created test requests were decided, and the approved test reservation was cancelled to release its bed. Existing patients' requests were not changed.

Re-run the targeted regression tests on another computer after dependency installation:

```powershell
& $medibedPython -B -m pytest tests/test_hosted_admin_bootstrap.py -p no:cacheprovider -q
```

Historical test files are included as source. They were not re-run as a complete suite during this handover; this record does not claim that the entire historical suite passed or that tests have run on the recipient's computer.

The archive was checked for ZIP integrity, Python syntax, source provenance, forbidden runtime filenames and all six live hospital password strings. Live credentials, databases, virtual environments and environment secrets are not included.
