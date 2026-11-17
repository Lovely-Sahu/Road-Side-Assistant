# RSA — Deployment and operations (controlled pilot)

## 1. Configuration

All settings come from environment variables. See `.env.example` for the full list.

The minimum for production:

```powershell
$env:RSA_ENV="production"
$env:RSA_SECRET_KEY="<output of: python -c "import secrets; print(secrets.token_hex(32))">"
$env:RSA_TRUST_PROXY="1"          # when behind an HTTPS reverse proxy
$env:RSA_DATABASE_PATH="D:\rsa-data\rsa.db"   # keep data outside the code folder
```

With `RSA_ENV=production`:

- The app refuses to start without a strong `RSA_SECRET_KEY`.
- Session cookies are `Secure`, `HttpOnly` and `SameSite=Lax`.
- HSTS is sent.
- Debug mode and demo seeding are disabled.
- `python web.py` refuses to run, so you must use a WSGI server.

In development, a random secret key is generated once in `instance/.dev_secret_key`. No secret is
hard-coded anywhere.

## 2. WSGI server + HTTPS

**Windows:**

```powershell
pip install -r requirements-prod.txt
python wsgi.py                      # Waitress on 127.0.0.1:8000
```

**Linux:** `gunicorn --workers 1 --threads 8 --bind 127.0.0.1:8000 wsgi:app`

Put an HTTPS reverse proxy in front: Caddy (automatic certificates), nginx or IIS ARR. Example
`Caddyfile`:

```
rsa.example.org {
    reverse_proxy 127.0.0.1:8000
}
```

HTTPS is required in practice, because browsers only allow geolocation on secure origins.

Add proxy-level rate limiting for extra protection (for example nginx `limit_req` on `/api/` and
`/login`). The app itself rate-limits failed logins (5 per account or 20 per IP in 15 minutes).

## 3. Health and monitoring

- `GET /healthz` returns `{"status":"ok"}` (200), or 503 when the database is unreachable. Point an uptime monitor at it.
- Each request is logged on one line: `request_id`, method, path, status, duration, user id and IP. Error pages show only a reference ID; the full traceback is in the server log under that ID.
- Schedule `python -m assistance.lifecycle` every 1–5 minutes (Windows Task Scheduler or cron). It retries matching for waiting requests (emergencies first) and sends escalation notifications. The admin dashboard also runs it whenever it is opened.

## 4. Database: backups, migrations, restore

- **Migrations** are versioned (`PRAGMA user_version` plus the `schema_migrations` table), additive only, and applied automatically at start-up. A verified backup is written to `backups/` first.
- **Manual backup:** `python -m database.backup create`. This makes a consistent online copy with an integrity check. Schedule it daily and copy `backups/` off the machine.
- **Restore:** stop the server, then run `python -m database.backup restore backups\<file>.db`. The current DB is backed up first, the backup is integrity-checked, and the schema is migrated afterwards.
- Migration and restore are covered by the automated tests (`tests/test_database.py`).

### Is SQLite suitable?

**For a single-site pilot (one server, tens of concurrent users), yes.** All writes use short
`BEGIN IMMEDIATE` transactions, a 10-second busy timeout and indexes. Run **one** WSGI worker
process with threads.

**Move to PostgreSQL when** any of these apply:

- you need several app servers or worker processes;
- you have sustained concurrent writes (many providers sharing location every 10 seconds);
- you need point-in-time recovery.

The SQL is standard apart from SQLite date functions (`datetime('now', ...)`, `julianday`). A
migration plan:

1. Introduce a DB adapter in `database/database.py`.
2. Port the date expressions.
3. Copy the data table by table, verifying row counts.
4. Run the test suite against PostgreSQL.

## 5. Security checklist

- [x] Passwords: PBKDF2-SHA256 with salt. The existing hash format is unchanged, so existing passwords keep working.
- [x] Roles enforced on the server for every page and API. Ownership is checked before every request, job, vehicle and attachment operation.
- [x] CSRF token on every state-changing request.
- [x] Session regenerated at login. Deactivated accounts lose access on their next request.
- [x] Login rate limiting. The "inactive account" message is shown only after a correct password.
- [x] Security headers: CSP, X-Frame-Options, nosniff, Referrer-Policy, Permissions-Policy, HSTS in production.
- [x] Uploads: magic-byte image check, size limit, random file names, stored outside `/static`, served only to authorized users.
- [x] No stack traces sent to clients.
- [ ] Before going live, delete or move the legacy `database/rsa.db`. It is unused by the code but contains a test user with a **plaintext** password.
- [ ] Change all demo account passwords, or deactivate the demo accounts.
- [ ] Set up off-machine backups and HTTPS.

## 6. What is prototype vs. externally verified

| Feature | Status |
|---|---|
| Incident analysis | Rule-based (phrases + word proximity + negation). Its "confidence" is a heuristic match strength and is labelled as such. Not a trained or validated model. |
| `ml/` classifier | Trained and "evaluated" on the same 32 example sentences. The 90.6% figure is **not** a real accuracy and must not be presented as one. Not used by the web app. |
| `ai/vision.py` | Infers from the image *file name*, not the pixels. **Not used.** Photos are stored for the provider to view only. |
| Vehicle health score | Derived from incident text only. There are no sensors, OBD or maintenance data, and it is labelled that way in the UI. |
| Maps / routing | Leaflet + OSM tiles (internet required; heavy production use needs a commercial tile provider). Road ETA only with your own `RSA_ROUTING_URL`. |
| E-mail | Works when SMTP is configured. Not tested here (no SMTP server). |
| SMS | Interface only (`assistance/notifications.py: SmsChannel`). Needs a DLT-registered SMS gateway account in India. |
| Emergency services | RSA tells users to call **112**. It does not contact emergency services and promises no response time. |
