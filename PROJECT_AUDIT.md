# RSA AI Project — Audit & Development Report (October 2026)

This report covers the audit and the reliability, integration and security work done on the
existing project. The previous audit is kept unchanged at the end of this file.

## 1. Entry points and environment (verified)

- `web.py` is the Flask web app. `app.py` is the separate console app, kept and verified working. Both are in the project root next to `rsa.db`.
- Database: the root `rsa.db` is the live one, used by `database/database.py`. `database/rsa.db` is a legacy file with a different schema. No code uses it, and it contains a test user whose `password_hash` is the plaintext `test_password`. It is preserved, but it should be deleted before deployment.
- Dependencies: Flask only (`requirements-web.txt`). The test suite uses only the standard library. The production server, Waitress, is in `requirements-prod.txt`.

## 2. Baseline (before any change; run on a copy of the project)

| Check | Result |
|---|---|
| `python -m unittest discover -s tests` | 6/6 passed |
| Built-in self-tests (`python -m ai.incident_analyzer` etc., 8 modules) | all passed (9/9, 9/9, 8/8, 9/9, 9/9, 9/9, 9/9, 9/9) |
| Web flow probe (Flask test client, copy of `rsa.db`) | **several broken behaviours, listed below** |

The existing tests passed, but they did not exercise the web workflow. A real request flow showed:

| # | Finding | Severity |
|---|---|---|
| B1 | Reports of an **accident, running out of fuel, or an electrical fault crashed with HTTP 500** (`IndexError` in `web.find_provider` when no provider type matched). The request and diagnosis were already committed, so half-created requests were left with no match and no tracking. | Critical |
| B2 | "smoke **is** coming from the engine" was classified `unknown` because only exact contiguous phrases matched. This is the "Unknown incident" on request #2. | High |
| B3 | Brake failure ("Emergency Roadside Assistance") was normalized to "general" by substring matching, so **any specialist (tyre, battery) could be dispatched to a brake failure**. | High |
| B4 | A missing driver location was silently replaced with hard-coded coordinates (20.2961, 85.8245). | High |
| B5 | `VehicleHealthEngine` was called with the description only. A CRITICAL smoke incident was reported as "health GOOD, safe to drive". | High |
| B6 | The tracking page's **Cancel button posted to a provider-only endpoint** and always failed. The map was a CSS animation; "LIVE NETWORK" pins and the "provider moving" marker were fake. | High |
| B7 | **Deactivated users kept working sessions** (`current_user()` did not check `is_active`). | High |
| B8 | **Any provider could read any request's tracking data**, including the driver's phone number. | High |
| B9 | **Stored XSS**: the tracking page put `business_name` and notes into `innerHTML` without escaping. | High |
| B10 | No CSRF protection, no login rate limiting, and a hard-coded fallback secret key. | High |
| B11 | Request, diagnosis, match and tracking were written by separate connections (not atomic). Nothing prevented two active assignments for one request. | High |
| B12 | **Job state machine:** `web.py` allowed ASSIGNED→ON_THE_WAY, but `ACCEPTED` could not be reached, the dashboard showed all four buttons whatever the state, and updates were not atomic. The CLI (`provider/jobs.py`, `provider/dashboard.py`, `provider/requests.py`) had **no transition validation**, and `provider/requests.py` updated the request without the match, leaving them out of sync. | High |
| B13 | **Provider dashboard showed no jobs for `provider.demo`.** This was not a query bug: every request went to Raj Auto Care (rating 4.8 against 0), and provider workload was never considered. | Medium |
| B14 | `normalize_text` turned "significant" into "significan't" (plain `replace("cant", …)`). | Low |
| B15 | Login said "inactive" before checking the password (account enumeration). Registration leaked SQLite errors. | Medium |
| B16 | Admin CLI modules opened `rsa.db` with their own `sqlite3.connect`, bypassing foreign keys. | Low |
| B17 | Overstated AI claims: `ai/vision.py` "analyses" the image **file name**. The ML "90.6% accuracy" was measured on its own 32 training sentences. | Medium (honesty) |

**About the reported "Cannot change job status from ASSIGNED to ON_THE_WAY":** the current `web.py`
already permitted that transition, and it was reproduced succeeding. The message came from an
earlier revision. The underlying problems were the inconsistent and unvalidated state machine (B12)
and a UI that offered invalid actions. Those are now fixed in one place.

### Duplicate / conflicting implementations found

- Provider matching in both `web.py` and `provider/provider.py` (different results). Now one implementation, `provider/provider.py`.
- Job status updates in `web.py`, `provider/jobs.py`, `provider/dashboard.py` and `provider/requests.py`. Now all of them call `assistance/lifecycle.py`.
- Password hashing in `authentication/password.py` (used) and `authentication/security.py` (different format, unused by login). Left as is and documented. Changing either would invalidate existing hashes.
- Vehicle CRUD in `driver/vehicle.py` and `vehicle/vehicle.py`. Both kept. The web app uses the ownership-aware `vehicle/vehicle.py` for edit and delete.
- In-memory engines `assistance/requests.py` and `assistance/tracking.py` (not database-backed). Kept; they are used by their own self-tests only.

No import errors or circular imports: all modules import cleanly, which the existing test confirms.

## 3. What was changed (by phase)

**Database** (`database/database.py`, new `database/migrations.py`, new `database/backup.py`)
- Configurable path (`RSA_DATABASE_PATH`), foreign keys and a busy timeout on every connection, a `transaction()` helper (`BEGIN IMMEDIATE`, rollback on error), and a rollback in `execute_query`.
- Versioned, additive migrations with an automatic verified backup:
  - **v1:** 11 indexes; a **unique partial index allowing one active match per request**; one provider profile per user; new columns `service_matches.updated_at/status_reason/match_details`, `tracking.location_source`, `assistance_requests.ai_incident_type`, `providers.verification_status` (existing providers set to `approved`) and `providers.location_updated_at`.
  - **v2:** new tables `notifications`, `audit_log`, `login_attempts`, `service_feedback`, `request_attachments`.
- Verified on a copy of the real `rsa.db`: every original row and column is identical after migration, `integrity_check` is ok, and there are no foreign-key violations.

**AI engine** (`ai/incident_analyzer.py`, `ai/diagnosis.py`, `ai/vehicle_health.py`)
- Word-proximity symptom layer below the existing phrase patterns (fixes B2), negation handling ("no smoke"), hazard detection (fire, smoke, fuel leak, injury, brake loss, steam, burning smell), ambiguity detection with follow-up questions, driver correction that can never hide a hazard, and a supported-type list.
- Rule order fixed to accident > brake failure > overheating, so a crash with smoke is treated as an accident.
- Confidence is labelled a heuristic match strength. Inferred-only matches are capped at 0.60.
- Diagnosis is always `is_confirmed: false`, with a disclaimer, hazard-first safety steps, a towing recommendation and "call 112" advice when relevant. The health result declares `sensor_data_used: false`.
- All original output keys are unchanged, and all original self-tests still pass.

**Matching** (`provider/provider.py`)
- An explicit service→provider-category suitability table replaces substring guessing.
- Hard rules: available, verified, linked active login, below job capacity, compatible, not previously rejected, inside the radius.
- Score: suitability, distance and rating, with distance weighted more for EMERGENCY. Unrated providers get a neutral score, disclosed as such.
- Missing coordinates are never treated as real. Ordering is deterministic, and the full breakdown is stored for explainability.

**Lifecycle service** (new `assistance/lifecycle.py`, new `assistance/notifications.py`, new `admin/audit.py`)
- The request is persisted atomically before assignment. If assignment fails, the request stays REQUESTED and is retried.
- Request status, match status and tracking always change together.
- State machine: `ASSIGNED → ACCEPTED | ON_THE_WAY | REJECTED`, `ACCEPTED → ON_THE_WAY`, `ON_THE_WAY → ARRIVED`, `ARRIVED → IN_PROGRESS`, `IN_PROGRESS → COMPLETED`, and `UNABLE_TO_COMPLETE` (reason required) from any accepted state. Repeated updates are idempotent, and invalid ones return a clear 409.
- Rejection or failure triggers automatic reassignment, excluding that provider.
- Drivers can cancel until service starts. Admins can reassign (reason required, target validated before anything changes), cancel, or retry matching.
- Provider live location is recorded only while travelling, throttled, and visible only to the parties involved.
- Emergencies are escalated to admins (configurable), and waiting requests are retried with emergencies first.
- In-app notifications are written after commit, deduplicated, and never break the workflow. E-mail is optional via SMTP; SMS is an interface only.

**Authentication & authorization** (`web.py`, `authentication/auth.py`, `authentication/login.py`, `authentication/security.py`, `config.py`)
- Active-account check on every request, CSRF on all state-changing requests, session regeneration at login, a POST-only logout, and secure cookie flags.
- Login rate limiting, and the password is checked before the account state is revealed.
- Strict `next` redirect validation, server-side role checks, and ownership checks for requests, jobs, vehicles and attachments.
- Security headers, error pages without stack traces, and secrets only from environment variables.

**Web modules** (`web.py`, templates, `static/`)
- Every original URL and endpoint name is preserved.
- **Driver:** dashboard built from real data only; vehicle add, edit and safe delete (vehicles with history are kept); report with analysis, follow-up questions, safety steps, confirm/correct, photos and location; live tracking (Leaflet map of real positions, timeline, "why this provider", cancel, feedback); history; notifications.
- **Provider:** profile setup and edit (changing the service type triggers re-verification), availability toggle, buttons for valid next actions only, reasons for reject/unable, live-location sharing tied to active jobs, closed-job history, stats from real records.
- **Admin:** overview with a written definition for every statistic, users (protected against locking out the last admin), provider verification, availability and account linking, request list and detail (matching breakdown, full tracking, controlled reassignment, cancel, retry), audit log, reports (time to assignment and arrival, completion rate, provider performance, incident categories, assignment failures).
- The dark visual identity is preserved. CSS was appended only; nothing was removed.

**Deployment** (new `wsgi.py`, `requirements-prod.txt`, `.env.example`, `.gitignore`, `DEPLOYMENT.md`, `PRIVACY.md`)
- `/healthz`, a structured access log with request IDs, and backup/restore commands.

## 4. Verification actually performed

| Check | Result |
|---|---|
| Automated tests: `python -m unittest discover -s tests -t . -v` | **87 passed** (6 original + 81 new: AI, matching, assignment, database, migration on a copy of the real DB, backup/restore, auth, authorization, CSRF, uploads, end-to-end workflows) |
| Fault injection: the reported bugs were reintroduced in a scratch copy (no ASSIGNED→ON_THE_WAY, no proximity layer, CSRF off, inactive sessions kept, provider sees all requests, old substring matching) | each one made tests fail |
| Original built-in AI/assistance self-tests | all still pass |
| Real browser (Chromium/Playwright) on a scratch copy of the app and DB: driver registers → adds vehicle → reports "smoke is coming from the engine" → assigned; provider sees the job → On the way → live location → Arrived → Start → Complete; driver sees each status, rates the service; admin pages, legacy request #2/#1 views; mobile 390 px | **34/34 checks, no console errors**, in both runs (CDN blocked, and local Leaflet stub) |
| Console app `python app.py` and CLI job updates through the state machine | work; ASSIGNED→ARRIVED rejected, ASSIGNED→ON_THE_WAY accepted and synced |
| Original `rsa.db` | **unchanged**; md5 `1a8b2cd8c730fc7ee689ef259d08a856` before and after all work |

**Not verifiable in the build environment:**
- Real Leaflet/OpenStreetMap tiles. The CDN and the tile server were blocked by the sandbox network policy, so the fallback and a Leaflet stub were tested instead.
- Waitress or Gunicorn (could not be installed there). `wsgi.py` imports correctly.
- SMTP delivery and OSRM routing.

## 5. Remaining limitations / next steps

1. The analyzer is rule-based. A real ML classifier needs a genuine labelled dataset with a held-out evaluation. The current `ml/` "accuracy" must not be cited.
2. No computer-vision model exists. Photos are stored and shown only. Any future model must be evaluated on real labelled images.
3. Predictive maintenance needs real data (service history, mileage, OBD). There is none yet, so no risk scores are produced from it.
4. SMS needs a gateway account. E-mail needs SMTP settings.
5. Data-retention deletions (location breadcrumbs, photos) are documented but not automated.
6. SQLite is fine for a single-server pilot. Move to PostgreSQL for multiple workers or servers (see `DEPLOYMENT.md`).
7. The existing open request #1 (driver Kaya Chiranjive Reddy, ASSIGNED to Raj Auto Care since 18 Sept 2026) is preserved. While it stays open, Raj Auto Care receives no new jobs. An admin should complete, cancel or reassign it.
8. Delete the legacy `database/rsa.db` (it holds a plaintext test password) and change the demo passwords before any real use.

---

# Previous audit (kept unchanged)

# RSA AI Project — Development Audit

## Existing architecture preserved

- `ai/`: incident analysis, diagnosis, severity, safety, decision support, vehicle health and vision.
- `assistance/`: service matching, request handling, resolution and tracking.
- `database/`, `authentication/`, `vehicle/`: existing SQLite schema and account/vehicle modules.
- `driver/`, `provider/`, `admin/`: existing role-specific workflows.
- `web.py`, `templates/`, `static/`: existing Flask web interface.
- `app.py`: existing console entry point.

## Changes made in this continuation

1. Repaired `provider/provider.py`, whose package exports referenced nine missing functions and whose matching code referenced undefined database/distance helpers.
2. Added provider lookup, listing, availability, create/update/delete and rating APIs against the existing `providers` table.
3. Added robust service normalization and Haversine distance handling; provider matching now rejects incompatible specialists instead of potentially assigning them to the wrong incident.
4. Hardened public registration so a client cannot self-register as an administrator.
5. Hardened the post-login redirect to prevent external/open redirects and route admins to the admin dashboard by default.
6. Validated that an assistance request's selected vehicle belongs to the signed-in driver and rejected invalid coordinates.
7. Added provider job status transition checks to prevent jobs from jumping between invalid states or reopening terminal jobs.
8. Disabled Flask debug mode by default. Set `RSA_DEBUG=1` only for local development.
9. Replaced the Windows UTF-16 dependency snapshot with a readable UTF-8 requirements file (`Flask` and `Streamlit`); `requirements-web.txt` remains the minimal Flask web dependency.
10. Added regression and module-import tests in `tests/`.

## Validation performed

- Python syntax compilation: passed for all project Python files outside the bundled virtual environment.
- Regression tests: 6 passed.
- Existing AI/assistance self-tests run: Incident Analyzer 9/9, Diagnosis 9/9, Severity 8/8, Decision Engine 9/9, Safety Risk 9/9, Assistance Matching 9/9.
- Existing core modules import successfully.

## Remaining verification note

The current analysis environment did not have Flask installed and could not reach the package index, so the Flask server/browser workflow could not be launched here. Install dependencies from `requirements-web.txt` (or `requirements.txt`) on your machine and test the register → login → report → match → tracking → provider status flow.

## Deployment reminders

- Set a strong `RSA_SECRET_KEY` environment variable before deployment; do not use the development fallback.
- Leave `RSA_DEBUG` unset or set it to `0` in production.
- The project currently includes both the root `rsa.db` used by `database/database.py` and a legacy `database/rsa.db` with a different schema. They were preserved rather than merged automatically to avoid data loss.
