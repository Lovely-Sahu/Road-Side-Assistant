# RSA — AI-Powered Roadside Assistance (web application)

Flask web app on top of the existing RSA Python modules (`ai/`, `assistance/`, `provider/`,
`driver/`, `vehicle/`, `authentication/`, `admin/`). The console app (`python app.py`) is unchanged
and still works.

## Entry points

| What | Command | Notes |
|---|---|---|
| Web app (development) | `python web.py` | http://127.0.0.1:5000 |
| Web app (production) | `python wsgi.py` (Waitress) | see `DEPLOYMENT.md` |
| Console (CLI) app | `python app.py` | original menu-driven app |
| Tests | `python -m unittest discover -s tests -t . -v` | uses temporary databases only |
| DB migrations | `python -m database.migrations` | runs automatically when the web app starts |
| DB backup / restore | `python -m database.backup create` / `restore <file>` | |
| Escalation + retry job | `python -m assistance.lifecycle` | optional, e.g. every minute via Task Scheduler |

`app.py` and `web.py` both live in the project root (the folder that contains `rsa.db`). Run all
commands from that folder.

## Easiest start (Windows): double-click `start_rsa.bat`

It always uses the `rsa.db` in its own folder and makes sure the demo logins work. If another copy is
already running, it picks a free port, then opens the sign-in page in Chrome Incognito. The same thing
without the .bat file is `python run_rsa.py`.

## Run on Windows (PowerShell)

```powershell
cd $HOME\Downloads\RSA_AI_Real\RSA_AI_Real      # the folder containing web.py and rsa.db
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements-web.txt
python web.py
```

Open http://127.0.0.1:5000.

**Keep your own `rsa.db`.** If you copy this project over your existing folder, keep the `rsa.db`
you already have. On first start the app backs it up to `backups\rsa-<timestamp>-pre-v2.db`, then
applies two additive migrations. Those migrations add columns, tables and indexes only. No
existing rows are changed or deleted.

To use a phone on the same Wi-Fi: `$env:RSA_HOST="0.0.0.0"; python web.py`. Phone browsers only
allow location sharing over HTTPS (or `localhost`), so test live location from the PC browser, or
put HTTPS in front as described in `DEPLOYMENT.md`.

## Accounts

Passwords are stored as PBKDF2 hashes and are never shown.

| Account | Role | Notes |
|---|---|---|
| `admin@rsa.local` | admin | |
| `driver.demo@rsa.local` | driver | |
| `provider.demo@rsa.local` | provider | "RSA Demo Provider Service" (Mechanic) |
| `provider@rsa.local` | provider | "Raj Auto Care". Holds the open job for request #1 (Sept), so it receives no new job until that one is finished or reassigned |

To set known passwords for the four demo accounts (it backs up `rsa.db` first and touches only these accounts):

```powershell
python reset_demo_passwords.py
```

This sets `admin@rsa.local` → `Admin@12345`, `driver.demo@rsa.local` → `Driver@12345`, and both provider accounts → `Provider@12345`. Change them before any real use.

New provider registrations need **admin approval** before they receive jobs. Set
`RSA_PROVIDER_AUTO_APPROVE=1` to skip approval during demos.

The three seeded providers "City Tyre Rescue", "Quick Battery Assist" and "24x7 Recovery" have **no
login account**. They are not dispatched automatically, because nobody could accept or update
their jobs. To make one dispatchable, an admin links it to a provider account under *Providers*.
Alternatively, set `RSA_ALLOW_UNLINKED_PROVIDERS=1`.

## Workflow

1. **Driver:** Report → AI analysis (with follow-up questions when unclear) → confirm or correct the incident type → request assistance.
2. **Matching:** the request is saved first. Then the best eligible provider is assigned, based on service suitability, distance, rating and workload.
3. **Provider:** Accept or reject → On the way → Arrived → Start service → Complete. *Unable to complete* (reason required) at any stage after accepting.
4. **Rejection or failure:** the job is automatically reassigned to the next eligible provider. With no eligible provider, the request waits and is retried.
5. **Driver tracking:** live status, timeline, the provider's last shared location and straight-line distance; cancel until service starts; rate the service when completed.
6. **Admin:** overview with defined statistics, users, provider verification, requests (inspect, reassign, cancel, retry), audit log and reports.

## Provider location on the driver's tracking page

- As soon as a provider is assigned, the driver sees the provider's **base location**, labelled *base · not live yet*. This is the location saved in the provider's profile. If the provider has none, the driver sees *Not shared yet — shared automatically when the provider accepts or is on the way*.
- When the provider taps **Accept**, **On the way** or **Arrived** (on the dashboard or on the job page), the browser's current position is sent **together with that status change**, so the driver's page switches to **LIVE** on its next refresh (every 5 seconds). There is no extra question: the browser's own location permission (asked once, "Allow") is the consent.
- While the job is Accepted / On the way / Arrived and the provider's dashboard or job page is open, the position keeps updating, at most every 10 seconds, and the driver sees the straight-line distance shrink.
- If location is blocked or unavailable, the status still changes; the provider sees a *blocked* message saying how to allow it, and the driver keeps seeing the base location (never a made-up live position).
- Providers can switch automatic sharing off with the checkbox on their dashboard (remembered in that browser). They can also set a base location with the GPS button or by typing latitude/longitude ("Save base location"). A typed base location is never shown to drivers as live.
- Live sharing stops automatically once service starts or the job ends.

## AI: rules + machine learning (hybrid)

The incident analysis combines a rule-based NLP engine with two machine-learning text classifiers:

- **TF-IDF + Logistic Regression** (main ML model: probability + the key words behind it)
- **TF-IDF + Random Forest** (second opinion: 400 decision trees voting)

The rules always decide hazards (smoke, fire, fuel leak, injury, brake loss), severity and "safe to drive".
The ML decides the incident *type* only when the rules find nothing or are unsure, and it never replaces a
rule decision of accident or brake failure. The report page and the request views show an "ML check" line.

- Needs `scikit-learn` (`python -m pip install scikit-learn`; `run_rsa.py` offers to install it). Without it, RSA uses the rules only.
- Dataset: `ml/datasets/incidents_train.csv` (810 rows) and a separately written test set `incidents_test.csv` (135 rows),
  9 classes (8 incident types + "other"). Written by the project team, not real customer reports.
- Retrain and evaluate: `python -m ml.train_incident_models` (writes `ml/evaluation/incident_models_report.json`
  and confusion-matrix images). Saved models are re-trained automatically after a scikit-learn upgrade.
- Switch ML off: `RSA_ML_ENABLED=0`.

## Maps

The tracking page uses Leaflet with OpenStreetMap tiles. Both need internet access. To run without
the CDN, download Leaflet 1.9.4 into `static/vendor/leaflet/` (`leaflet.js`, `leaflet.css`); it is
then used automatically. If the map cannot load, the page shows the location details as text.

A road ETA is shown only when `RSA_ROUTING_URL` points to an OSRM-compatible router. Otherwise the
page shows the straight-line distance and says the road ETA is unavailable.
