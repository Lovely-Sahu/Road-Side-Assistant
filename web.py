"""
RSA — AI-Powered Roadside Assistance: Flask web application.

Entry points
    python web.py      development server (http://127.0.0.1:5000)
    wsgi.py            production WSGI entry (waitress on Windows, gunicorn on Linux)
    python app.py      the original console (CLI) application — unchanged

All existing URLs and endpoint names are preserved. Business logic lives in
the existing packages (ai/, assistance/, provider/, driver/, vehicle/,
authentication/, admin/); this module only handles HTTP, sessions,
permissions and rendering.
"""

import json
import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

from flask import (
    Flask,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from markupsafe import Markup, escape

from config import load_settings
from database.models import create_tables
from database.migrations import migrate
from database.database import execute_query, fetch_one, fetch_all, transaction, utc_now
from authentication.auth import register_user, login_user, get_user_by_id
from driver.vehicle import add_vehicle, get_driver_vehicles
from vehicle.vehicle import update_vehicle as update_owned_vehicle, delete_vehicle as delete_owned_vehicle
from ai.incident_analyzer import IncidentAnalyzer, SUPPORTED_PROBLEMS, PROBLEM_LABELS
from ai.diagnosis import DiagnosisEngine
from ai.vehicle_health import VehicleHealthEngine
from assistance.matching import AssistanceMatcher
from assistance import lifecycle, notifications
from assistance.lifecycle import LifecycleError, status_label, ACTION_LABELS, ACTIVE_MATCH_STATUSES
from provider.provider import (
    PROVIDER_CATEGORIES,
    find_provider as _find_provider,
    get_provider_by_id as _get_provider_by_id,
    get_provider_by_user_id as _get_provider_by_user_id,
    haversine as _haversine,
    normalize_service as _normalize_service,
    rank_providers,
)
from admin.audit import log_action, recent_actions
from utils.validators import (
    ValidationError,
    clean_text,
    normalize_registration_number,
    parse_coordinates,
    parse_int,
    validate_email,
    validate_phone,
)


# ============================================================
# BASE CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

settings = load_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("rsa.web")

UPLOAD_DIR = settings.upload_dir  # private (outside /static), served only after permission checks
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = settings.secret_key
app.config.update(
    MAX_CONTENT_LENGTH=(settings.max_upload_mb + 1) * 1024 * 1024,
    SESSION_COOKIE_NAME="rsa_session",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=settings.session_cookie_secure,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=settings.session_hours),
    JSON_SORT_KEYS=False,
)

if settings.trust_proxy:
    from werkzeug.middleware.proxy_fix import ProxyFix

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


# ============================================================
# DATABASE INITIALIZATION + MIGRATIONS
# ============================================================

create_tables()
MIGRATION_REPORT = migrate()  # backs up rsa.db before applying any pending migration
if MIGRATION_REPORT["applied"]:
    logger.info("Database migrated v%s -> v%s (backup: %s)", MIGRATION_REPORT["from_version"],
                MIGRATION_REPORT["to_version"], MIGRATION_REPORT["backup"])
for _note in MIGRATION_REPORT["notes"]:
    logger.warning(_note)


# ============================================================
# AI ENGINES
# ============================================================

analyzer = IncidentAnalyzer()


def _warm_up_ml():
    """Load (or, after a scikit-learn upgrade, re-train) the ML models without delaying start-up."""
    try:
        from ml.incident_models import get_incident_models
        models = get_incident_models()
        if models.ensure_loaded():
            logger.info("ML incident models ready (TF-IDF + Logistic Regression / Random Forest, %s examples).",
                        models.meta.get("trained_on"))
        else:
            logger.warning("ML incident models not available: %s. The rule engine is used alone.", models.reason)
    except Exception:  # noqa: BLE001
        logger.exception("ML warm-up failed; the rule engine is used alone.")


if analyzer.use_ml:
    import threading as _threading
    _threading.Thread(target=_warm_up_ml, name="ml-warm-up", daemon=True).start()
matcher = AssistanceMatcher()
diagnosis_engine = DiagnosisEngine()
health_engine = VehicleHealthEngine()

ENGINES = dict(analyzer=analyzer, matcher=matcher, diagnosis_engine=diagnosis_engine, health_engine=health_engine)

PROVIDER_SERVICE_TYPES = [
    ("Mechanic", "Mechanic (engine, brakes, general repairs)"),
    ("Tyre Service", "Tyre service"),
    ("Battery Assistance", "Battery / jump-start"),
    ("Auto Electrician", "Auto electrician"),
    ("Towing / Recovery", "Towing / recovery"),
    ("Fuel Delivery", "Fuel delivery"),
    ("General Roadside Assistance", "General roadside assistance"),
]


# ============================================================
# BACKWARD-COMPATIBLE HELPERS (previously defined in web.py)
# ============================================================

def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in km (None for missing/invalid coordinates)."""
    return _haversine(lat1, lon1, lat2, lon2)


def normalize_service(value):
    return _normalize_service(value)


def get_provider_by_id(provider_id):
    return _get_provider_by_id(provider_id)


def get_provider_by_user_id(user_id):
    return _get_provider_by_user_id(user_id)


def find_provider(service_name, lat, lon):
    """Best eligible provider as (provider, distance) or None — never raises IndexError."""
    return _find_provider(service_name, lat, lon)


# ============================================================
# SEED PROVIDERS (development only; never in production)
# ============================================================

def ensure_seed_providers():
    """
    Create realistic demo providers only when the database
    has no providers. Existing provider data is never touched.
    """

    if not settings.seed_demo_data:
        return

    row = fetch_one("SELECT COUNT(*) AS c FROM providers")
    if row and row["c"]:
        return

    demo_email = "provider@rsa.local"
    existing_user = fetch_one("SELECT id FROM users WHERE email=?", (demo_email,))

    if not existing_user:
        demo_password = os.environ.get("RSA_DEMO_PROVIDER_PASSWORD") or secrets.token_urlsafe(12)
        demo_user = register_user("Raj Auto Care", demo_email, demo_password, "9000000001", "provider")
        demo_user_id = demo_user.get("user_id") if demo_user.get("success") else None
        if demo_user_id and not os.environ.get("RSA_DEMO_PROVIDER_PASSWORD"):
            logger.warning("Seeded demo provider %s with a random password; set RSA_DEMO_PROVIDER_PASSWORD "
                           "before first start to choose it.", demo_email)
    else:
        demo_user_id = existing_user["id"]

    demo = [
        ("Raj Auto Care", "Mechanic", "9000000001", 20.2961, 85.8245, 4.8),
        ("City Tyre Rescue", "Tyre Service", "9000000002", 20.3050, 85.8350, 4.7),
        ("Quick Battery Assist", "Battery Assistance", "9000000003", 20.2820, 85.8100, 4.6),
        ("24x7 Recovery", "Emergency Recovery", "9000000004", 20.3200, 85.8200, 4.9),
    ]
    for idx, (name, service, phone, lat, lon, rating) in enumerate(demo):
        execute_query(
            """
            INSERT INTO providers (user_id, business_name, service_type, phone, latitude, longitude,
                                   availability, rating)
            VALUES (?, ?, ?, ?, ?, ?, 'available', ?)
            """,
            (demo_user_id if idx == 0 else None, name, service, phone, lat, lon, rating),
        )


ensure_seed_providers()


# ============================================================
# REQUEST CONTEXT, SESSION USER
# ============================================================

def _public_user(row):
    user = dict(row)
    user.pop("password_hash", None)  # never carry the hash into templates/JSON
    return user


def current_user():
    """
    Return the signed-in, ACTIVE user (password hash removed).

    A deactivated account loses access on its next request, even with an
    existing session cookie.
    """

    if "rsa_user" in g:
        return g.rsa_user

    user = None
    uid = session.get("user_id")
    if uid:
        row = get_user_by_id(uid)
        if row and row["is_active"]:
            user = _public_user(row)
        else:
            session.clear()
    g.rsa_user = user
    return user


def client_ip():
    return (request.remote_addr or "")[:64]


def wants_json():
    if request.path.startswith("/api/"):
        return True
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return best == "application/json" and request.accept_mimetypes[best] > request.accept_mimetypes["text/html"]


def error_response(message, status=400, **extra):
    if wants_json():
        return jsonify({"success": False, "message": message, **extra}), status
    return render_template("error.html", status=status, message=message), status


@app.before_request
def _start_request():
    g.request_id = uuid.uuid4().hex[:12]
    g.request_started = datetime.now(timezone.utc)


access_logger = logging.getLogger("rsa.access")


@app.after_request
def _access_log(response):
    """One structured line per request (no query strings, bodies or secrets)."""
    started = g.get("request_started")
    duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000) if started else -1
    user = g.get("rsa_user")
    access_logger.info(
        "request_id=%s method=%s path=%s status=%s duration_ms=%s user_id=%s ip=%s",
        g.get("request_id", "-"), request.method, request.path, response.status_code, duration_ms,
        user["id"] if user else "-", client_ip() or "-",
    )
    return response


# ============================================================
# CSRF PROTECTION
# ============================================================

def csrf_token():
    token = session.get("_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf"] = token
    return token


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def _csrf_protect():
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return None
    sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token") or ""
    expected = session.get("_csrf") or ""
    if not expected or not sent or not secrets.compare_digest(str(sent), str(expected)):
        return error_response("Your security token is missing or expired. Reload the page and try again.", 400,
                              code="csrf")
    return None


# ============================================================
# SECURITY HEADERS
# ============================================================

@app.after_request
def _security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "geolocation=(self), camera=(), microphone=()")
    connect = "'self'" + (f" {settings.routing_url}" if settings.routing_url else "")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://unpkg.com; "
        "img-src 'self' data: blob: https:; "
        f"connect-src {connect}; "
        "font-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
    )
    if settings.is_production:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.path.startswith("/api/") or request.path.startswith("/attachments/"):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Request-ID"] = g.get("request_id", "")
    return response


# ============================================================
# ACCESS CONTROL
# ============================================================

def login_required(fn):

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            if wants_json():
                return jsonify({"success": False, "message": "Please sign in."}), 401
            return redirect(url_for("login", next=request.path))
        return fn(*args, **kwargs)

    return wrapper


def role_required(*roles):
    """Server-side role enforcement for both pages and JSON APIs."""

    def decorator(fn):

        @wraps(fn)
        def wrapper(*args, **kwargs):
            user = current_user()
            if not user:
                if wants_json():
                    return jsonify({"success": False, "message": "Please sign in."}), 401
                return redirect(url_for("login", next=request.path))
            if user["role"] not in roles:
                return error_response("Access denied.", 403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def home_for(user):
    if not user:
        return url_for("home")
    return {
        "provider": url_for("provider_dashboard"),
        "admin": url_for("admin_dashboard"),
    }.get(user["role"], url_for("dashboard"))


# ============================================================
# TEMPLATE HELPERS
# ============================================================

def _parse_utc(value):
    if not value:
        return None
    text = str(value).replace("T", " ").replace("Z", "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text[:26], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


@app.template_filter("utc")
def utc_filter(value):
    """Render a stored UTC timestamp; app.js converts it to the viewer's local time."""
    moment = _parse_utc(value)
    if not moment:
        return "—"
    iso = moment.strftime("%Y-%m-%dT%H:%M:%SZ")
    return Markup(f'<time class="ts" datetime="{iso}">{escape(moment.strftime("%d %b %Y %H:%M"))} UTC</time>')


@app.template_filter("service_name")
def service_name_filter(value):
    """Display name for a matcher service id (e.g. mechanic_or_roadside_assistance)."""
    service = matcher.services.get(str(value or ""))
    return service["name"] if service else label_filter(value)


@app.template_filter("label")
def label_filter(value):
    return (str(value or "").replace("_", " ").strip().title()) or "—"


@app.context_processor
def inject_globals():
    user = current_user()
    return {
        "current_user": user,
        "app_name": "RSA",
        "year": datetime.now(timezone.utc).year,
        "unread_notifications": notifications.unread_count(user["id"]) if user else 0,
        "status_label": status_label,
        "problem_labels": PROBLEM_LABELS,
        "map_config": {
            "tile_url": settings.map_tile_url,
            "attribution": settings.map_attribution,
            "routing_url": settings.routing_url,
            # Self-hosted Leaflet (static/vendor/leaflet/) is preferred when present.
            "leaflet_local": (BASE_DIR / "static" / "vendor" / "leaflet" / "leaflet.js").exists(),
        },
    }


# ============================================================
# HOME / HEALTH
# ============================================================

@app.get("/")
def home():
    if current_user():
        return redirect(home_for(current_user()))
    return render_template("landing.html")


@app.get("/healthz")
def healthz():
    """Liveness + database check for monitoring. Exposes no internal details."""
    try:
        fetch_one("SELECT 1")
        return jsonify({"status": "ok"}), 200
    except Exception:  # noqa: BLE001
        logger.exception("Health check failed")
        return jsonify({"status": "error"}), 503


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":
        data = request.form

        # Public registration must never permit self-assigned administrator access.
        requested_role = (data.get("role", "driver") or "driver").strip().lower()
        if requested_role not in {"driver", "provider"}:
            flash("Choose either a driver or provider account.", "error")
            return render_template("register.html", service_types=PROVIDER_SERVICE_TYPES), 400

        try:
            name = clean_text(data.get("name"), "Full name", 100, required=True, min_length=2)
            email = validate_email(data.get("email"))
            phone = validate_phone(data.get("phone"), required=requested_role == "provider")
            business_name = service_type = None
            if requested_role == "provider":
                business_name = clean_text(data.get("business_name"), "Business name", 120, required=True,
                                           min_length=2)
                service_type = data.get("service_type", "")
                if service_type not in {value for value, _ in PROVIDER_SERVICE_TYPES}:
                    raise ValidationError("Choose a service type from the list.")
        except ValidationError as error:
            flash(str(error), "error")
            return render_template("register.html", service_types=PROVIDER_SERVICE_TYPES), 400

        if phone and fetch_one("SELECT 1 FROM users WHERE phone = ?", (phone,)):
            flash("An account with this phone number already exists.", "error")
            return render_template("register.html", service_types=PROVIDER_SERVICE_TYPES), 400

        result = register_user(name=name, email=email, password=data.get("password", ""), phone=phone,
                               role=requested_role)

        if not result["success"]:
            message = result["message"]
            if message.startswith("Registration failed"):
                logger.error("Registration error for %s: %s", email, message)
                message = "Registration failed. Please try again."
            flash(message, "error")
            return render_template("register.html", service_types=PROVIDER_SERVICE_TYPES), 400

        # ----------------------------------------------------
        # PROVIDER PROFILE (pending admin verification unless auto-approve is configured)
        # ----------------------------------------------------
        if requested_role == "provider":
            verification = "approved" if settings.provider_auto_approve else "pending"
            try:
                execute_query(
                    """
                    INSERT INTO providers (user_id, business_name, service_type, phone, availability,
                                           verification_status)
                    VALUES (?, ?, ?, ?, 'available', ?)
                    """,
                    (result["user_id"], business_name, service_type, phone, verification),
                )
            except Exception:  # noqa: BLE001
                # Compensate so a half-created provider account cannot exist.
                logger.exception("Provider profile creation failed; removing user %s", result["user_id"])
                execute_query("DELETE FROM users WHERE id = ?", (result["user_id"],))
                flash("Registration failed. Please try again.", "error")
                return render_template("register.html", service_types=PROVIDER_SERVICE_TYPES), 500

            if verification == "pending":
                notifications.notify_admins(
                    "PROVIDER_VERIFICATION", "Provider awaiting verification",
                    f"{business_name} ({service_type}) registered and needs verification.",
                    dedupe_key=f"verify:{result['user_id']}",
                )

        log_action(result["user_id"], "user.register", "user", result["user_id"], {"role": requested_role},
                   client_ip())
        flash("Account created. Sign in to continue.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", service_types=PROVIDER_SERVICE_TYPES)


# ============================================================
# LOGIN (rate limited)
# ============================================================

def _login_blocked(email):
    window = f"-{settings.login_window_minutes} minutes"
    by_email = fetch_one(
        "SELECT COUNT(*) AS c FROM login_attempts WHERE success = 0 AND email = ? AND attempted_at > datetime('now', ?)",
        (email, window),
    )["c"]
    by_ip = fetch_one(
        "SELECT COUNT(*) AS c FROM login_attempts WHERE success = 0 AND ip_address = ? "
        "AND attempted_at > datetime('now', ?)",
        (client_ip(), window),
    )["c"]
    return by_email >= settings.login_max_failures or by_ip >= settings.login_max_failures * 4


def _record_login_attempt(email, success):
    try:
        execute_query("INSERT INTO login_attempts (email, ip_address, success, attempted_at) VALUES (?, ?, ?, ?)",
                      (email, client_ip(), 1 if success else 0, utc_now()))
        if success:
            execute_query("DELETE FROM login_attempts WHERE attempted_at < datetime('now', '-7 days')")
    except Exception:  # noqa: BLE001
        logger.exception("Could not record login attempt")


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":
        email = (request.form.get("email", "") or "").strip().lower()[:254]

        if _login_blocked(email):
            flash(f"Too many failed sign-in attempts. Try again in {settings.login_window_minutes} minutes.",
                  "error")
            return render_template("login.html"), 429

        result = login_user(email, request.form.get("password", ""))

        if not result["success"]:
            _record_login_attempt(email, False)
            flash(result["message"], "error")
            return render_template("login.html"), 401

        _record_login_attempt(email, True)

        # New session on login (prevents session fixation).
        session.clear()
        session.permanent = True
        session["user_id"] = result["user"]["id"]
        csrf_token()

        role = result["user"]["role"]
        default_target = (
            url_for("provider_dashboard") if role == "provider"
            else url_for("admin_dashboard") if role == "admin"
            else url_for("dashboard")
        )
        requested_target = request.args.get("next", "")
        parsed_target = urlsplit(requested_target)
        # Accept only same-site absolute paths; reject scheme-relative and external URLs.
        safe_target = (
            requested_target
            if requested_target.startswith("/")
            and not requested_target.startswith("//")
            and "\\" not in requested_target
            and not parsed_target.scheme
            and not parsed_target.netloc
            else default_target
        )
        return redirect(safe_target)

    return render_template("login.html")


# ============================================================
# LOGOUT (POST + CSRF; GET kept for old links but only shows a confirm button)
# ============================================================

@app.route("/logout", methods=["GET", "POST"])
def logout():
    if request.method == "POST":
        session.clear()
        flash("You have been signed out.", "success")
        return redirect(url_for("home"))
    if not current_user():
        return redirect(url_for("home"))
    return render_template("logout.html")


# ============================================================
# NOTIFICATIONS
# ============================================================

@app.get("/notifications")
@login_required
def notifications_page():
    user = current_user()
    items = notifications.list_notifications(user["id"], limit=100)
    return render_template("notifications.html", items=items)


@app.get("/api/notifications")
@login_required
def api_notifications():
    user = current_user()
    return jsonify({
        "success": True,
        "unread": notifications.unread_count(user["id"]),
        "items": notifications.list_notifications(user["id"], limit=20),
    })


@app.post("/api/notifications/read")
@login_required
def api_notifications_read():
    user = current_user()
    ids = request.form.getlist("id")
    notifications.mark_read(user["id"], ids or None)
    if wants_json():
        return jsonify({"success": True, "unread": notifications.unread_count(user["id"])})
    return redirect(url_for("notifications_page"))


# ============================================================
# DRIVER DASHBOARD
# ============================================================

def _open_request_for(user_id):
    return fetch_one(
        f"""
        SELECT ar.*, (
            SELECT p.business_name FROM service_matches sm JOIN providers p ON p.id = sm.provider_id
            WHERE sm.request_id = ar.id AND sm.status IN ({",".join("?" * len(ACTIVE_MATCH_STATUSES))})
            ORDER BY sm.id DESC LIMIT 1
        ) AS provider_name
        FROM assistance_requests ar
        WHERE ar.user_id = ? AND ar.status NOT IN ('COMPLETED', 'CANCELLED')
        ORDER BY ar.created_at DESC, ar.id DESC
        LIMIT 1
        """,
        (*ACTIVE_MATCH_STATUSES, user_id),
    )


def _requests_with_provider(where_sql, params, limit):
    """Requests plus the provider currently/finally responsible (no duplicate rows)."""
    return [dict(r) for r in fetch_all(
        f"""
        SELECT ar.*,
            (SELECT p.business_name FROM service_matches sm JOIN providers p ON p.id = sm.provider_id
              WHERE sm.request_id = ar.id AND sm.status NOT IN ('REJECTED','UNABLE_TO_COMPLETE','REASSIGNED')
              ORDER BY sm.id DESC LIMIT 1) AS business_name,
            (SELECT dr.diagnosis FROM diagnosis_records dr WHERE dr.request_id = ar.id
              ORDER BY dr.id DESC LIMIT 1) AS diagnosis_title,
            (SELECT sf.rating FROM service_feedback sf WHERE sf.request_id = ar.id) AS feedback_rating
        FROM assistance_requests ar
        WHERE {where_sql}
        ORDER BY ar.created_at DESC, ar.id DESC
        LIMIT ?
        """,
        (*params, limit),
    )]


def _dispatchable_provider_summary():
    """Providers that could take a job right now, by service category (real data)."""
    summary = {}
    for row in fetch_all(
        f"""
        SELECT p.service_type FROM providers p LEFT JOIN users u ON u.id = p.user_id
        WHERE lower(p.availability) IN ('available', 'busy')
          AND COALESCE(p.verification_status, 'approved') = 'approved'
          AND p.user_id IS NOT NULL AND COALESCE(u.is_active, 0) = 1
          AND NOT EXISTS (SELECT 1 FROM service_matches sm WHERE sm.provider_id = p.id
                          AND sm.status IN ({",".join("?" * len(ACTIVE_MATCH_STATUSES))}))
        """,
        ACTIVE_MATCH_STATUSES,
    ):
        category = _normalize_service(row["service_type"])
        summary[category] = summary.get(category, 0) + 1
    return summary


@app.get("/dashboard")
@login_required
def dashboard():

    user = current_user()

    if user["role"] != "driver":
        return redirect(home_for(user))

    vehicles_list = get_driver_vehicles(user["id"])
    active = _open_request_for(user["id"])
    recent = _requests_with_provider("ar.user_id = ?", (user["id"],), 6)

    health = None
    if vehicles_list:
        health = fetch_one(
            """
            SELECT vh.*, v.registration_number FROM vehicle_health vh
            JOIN vehicles v ON v.id = vh.vehicle_id
            WHERE v.user_id = ?
            ORDER BY vh.created_at DESC, vh.id DESC LIMIT 1
            """,
            (user["id"],),
        )

    provider_summary = _dispatchable_provider_summary()

    return render_template(
        "dashboard.html",
        vehicles=vehicles_list,
        active=active,
        recent=recent,
        health=health,
        provider_count=sum(provider_summary.values()),
        provider_summary=provider_summary,
    )


@app.get("/history")
@role_required("driver")
def history():
    user = current_user()
    items = _requests_with_provider("ar.user_id = ?", (user["id"],), 200)
    return render_template("history.html", items=items)


# ============================================================
# VEHICLES
# ============================================================

@app.get("/vehicles")
@login_required
def vehicles():

    user = current_user()

    if user["role"] != "driver":
        return redirect(home_for(user))

    rows = get_driver_vehicles(user["id"])
    in_use = {r["vehicle_id"]: r["c"] for r in fetch_all(
        "SELECT vehicle_id, COUNT(*) AS c FROM assistance_requests WHERE user_id = ? AND vehicle_id IS NOT NULL "
        "GROUP BY vehicle_id", (user["id"],))}
    for vehicle in rows:
        vehicle["request_count"] = in_use.get(vehicle["id"], 0)

    return render_template("vehicles.html", vehicles=rows, current_year=datetime.now(timezone.utc).year)


def _vehicle_form():
    registration = normalize_registration_number(request.form.get("registration_number"))
    make = clean_text(request.form.get("make"), "Make", 60) or None
    model = clean_text(request.form.get("model"), "Model", 60) or None
    fuel_type = clean_text(request.form.get("fuel_type"), "Fuel type", 30) or None
    year = parse_int(request.form.get("year"), "Year", 1950, datetime.now(timezone.utc).year + 1, required=False)
    return registration, make, model, year, fuel_type


@app.post("/api/vehicles")
@role_required("driver")
def api_add_vehicle():

    user = current_user()

    try:
        registration, make, model, year, fuel_type = _vehicle_form()
    except ValidationError as error:
        return jsonify({"success": False, "message": str(error)}), 400

    result = add_vehicle(user["id"], registration, make, model, year, fuel_type)
    if not result.get("success") and str(result.get("message", "")).startswith("Vehicle registration failed"):
        logger.error("Vehicle add failed: %s", result["message"])
        result["message"] = "Could not add the vehicle. Please try again."

    return jsonify(result), (200 if result.get("success") else 400)


@app.post("/api/vehicles/<int:vehicle_id>")
@role_required("driver")
def api_update_vehicle(vehicle_id):
    user = current_user()
    try:
        registration, make, model, year, fuel_type = _vehicle_form()
    except ValidationError as error:
        return jsonify({"success": False, "message": str(error)}), 400

    result = update_owned_vehicle(vehicle_id, user["id"], registration, make, model, year, fuel_type)
    status = 200 if result.get("success") else (404 if "not found" in result.get("message", "").lower() else 400)
    return jsonify(result), status


@app.post("/api/vehicles/<int:vehicle_id>/delete")
@role_required("driver")
def api_delete_vehicle(vehicle_id):
    user = current_user()
    owned = fetch_one("SELECT id FROM vehicles WHERE id = ? AND user_id = ?", (vehicle_id, user["id"]))
    if not owned:
        return jsonify({"success": False, "message": "Vehicle not found."}), 404

    used = fetch_one("SELECT COUNT(*) AS c, SUM(CASE WHEN status NOT IN ('COMPLETED','CANCELLED') THEN 1 ELSE 0 END) "
                     "AS open_count FROM assistance_requests WHERE vehicle_id = ?", (vehicle_id,))
    if used["open_count"]:
        return jsonify({"success": False, "message": "This vehicle has an active assistance request."}), 409
    if used["c"]:
        return jsonify({"success": False,
                        "message": "This vehicle has service history, so it is kept to preserve those records."}), 409

    result = delete_owned_vehicle(vehicle_id, user["id"])
    return jsonify(result), (200 if result.get("success") else 400)


# ============================================================
# REPORT PAGE + AI ANALYSIS
# ============================================================

@app.get("/report")
@role_required("driver")
def report():

    user = current_user()
    active = _open_request_for(user["id"])

    return render_template(
        "report.html",
        vehicles=get_driver_vehicles(user["id"]),
        active=active,
        supported_problems=[(p, PROBLEM_LABELS[p]) for p in SUPPORTED_PROBLEMS],
        max_photos=settings.max_photos_per_request,
        max_upload_mb=settings.max_upload_mb,
    )


@app.post("/api/analyze")
@role_required("driver")
def api_analyze():

    description = (request.form.get("description", "") or "").strip()

    if len(description) < 5:
        return jsonify({"success": False, "message": "Describe the problem in at least 5 characters."}), 400
    if len(description) > 2000:
        return jsonify({"success": False, "message": "Please keep the description under 2000 characters."}), 400

    override = request.form.get("incident_type") or None
    result = analyzer.analyze(description, problem_override=override)
    match = matcher.match_assistance(result["problem"], result["severity"], result["safe_to_drive"])
    diagnosis = diagnosis_engine.diagnose(result["problem"], description, result)
    # Health must use the same analysis; before, it re-read the text alone and could
    # report "GOOD / safe" for a CRITICAL smoke incident.
    health = health_engine.analyze(description, result["problem"], result["severity"], result["safe_to_drive"])

    preview = None
    try:
        lat, lon = parse_coordinates(request.form.get("latitude"), request.form.get("longitude"))
        ranking = rank_providers(match["service"], lat, lon, priority=match["priority"])
        preview = {
            "eligible": len(ranking["candidates"]),
            "location_used": lat is not None,
            "requested_service": ranking["requested_service"],
        }
    except ValidationError:
        preview = None

    return jsonify({
        "success": True,
        "analysis": result,
        "matching": match,
        "diagnosis": diagnosis,
        "health": health,
        "provider_preview": preview,
    })


# ============================================================
# CREATE ASSISTANCE REQUEST
# ============================================================

@app.post("/api/assistance/create")
@role_required("driver")
def api_create_assistance():

    user = current_user()

    try:
        outcome = lifecycle.create_request(
            user["id"],
            request.form.get("description", ""),
            vehicle_id=request.form.get("vehicle_id") or None,
            latitude=request.form.get("latitude"),
            longitude=request.form.get("longitude"),
            problem_override=request.form.get("incident_type") or None,
            **ENGINES,
        )
    except ValidationError as error:
        return jsonify({"success": False, "message": str(error)}), 400
    except LifecycleError as error:
        payload = {"success": False, "message": error.message, "code": error.code}
        if error.code == "active_request_exists":
            existing = _open_request_for(user["id"])
            if existing:
                payload["redirect"] = url_for("tracking", request_id=existing["id"])
        return jsonify(payload), error.status_code

    assignment = outcome["assignment"]
    provider = assignment.get("provider") if assignment.get("assigned") else None

    return jsonify({
        "success": True,
        "request_id": outcome["request_id"],
        "analysis": outcome["analysis"],
        "matching": outcome["matching"],
        "provider": provider,
        "distance_km": assignment.get("distance_km"),
        "assignment": {k: v for k, v in assignment.items() if k in ("assigned", "reason", "message", "score")},
        "message": (
            "Assistance request created and provider assigned."
            if provider else
            "Request saved. No suitable provider is available yet; it will be assigned automatically."
        ),
        "redirect": url_for("tracking", request_id=outcome["request_id"]),
    })


# ============================================================
# PHOTO ATTACHMENTS (stored privately; never analysed automatically)
# ============================================================

_IMAGE_SIGNATURES = (
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
)


def _sniff_image(head):
    for signature, mime, ext in _IMAGE_SIGNATURES:
        if head.startswith(signature):
            return mime, ext
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp", "webp"
    return None, None


@app.post("/api/requests/<int:request_id>/attachments")
@role_required("driver")
def api_upload_attachment(request_id):
    user = current_user()
    req = fetch_one("SELECT id, status FROM assistance_requests WHERE id = ? AND user_id = ?", (request_id, user["id"]))
    if not req:
        return jsonify({"success": False, "message": "Request not found."}), 404
    if req["status"] in ("COMPLETED", "CANCELLED"):
        return jsonify({"success": False, "message": "Photos can only be added to an open request."}), 409

    count = fetch_one("SELECT COUNT(*) AS c FROM request_attachments WHERE request_id = ?", (request_id,))["c"]
    if count >= settings.max_photos_per_request:
        return jsonify({"success": False,
                        "message": f"A request can have at most {settings.max_photos_per_request} photos."}), 409

    upload = request.files.get("photo")
    if not upload or not upload.filename:
        return jsonify({"success": False, "message": "Choose a photo to upload."}), 400

    data = upload.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        return jsonify({"success": False, "message": f"Each photo must be {settings.max_upload_mb} MB or smaller."}), 413
    if len(data) < 64:
        return jsonify({"success": False, "message": "That file is empty or not an image."}), 400

    mime, ext = _sniff_image(data[:16])
    if not mime:
        return jsonify({"success": False, "message": "Only JPEG, PNG or WebP photos are accepted."}), 400

    stored_name = f"{uuid.uuid4().hex}.{ext}"
    (UPLOAD_DIR / stored_name).write_bytes(data)
    try:
        execute_query(
            "INSERT INTO request_attachments (request_id, user_id, original_name, stored_name, content_type, "
            "size_bytes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (request_id, user["id"], clean_text(upload.filename, "File name", 255)[:255], stored_name, mime,
             len(data), utc_now()),
        )
    except Exception:  # noqa: BLE001
        (UPLOAD_DIR / stored_name).unlink(missing_ok=True)
        raise
    return jsonify({"success": True, "message": "Photo attached."})


def _attachments_for(request_id):
    return [
        {"id": r["id"], "url": url_for("attachment_file", attachment_id=r["id"]), "created_at": r["created_at"]}
        for r in fetch_all("SELECT id, created_at FROM request_attachments WHERE request_id = ? ORDER BY id",
                           (request_id,))
    ]


@app.get("/attachments/<int:attachment_id>")
@login_required
def attachment_file(attachment_id):
    user = current_user()
    row = fetch_one("SELECT * FROM request_attachments WHERE id = ?", (attachment_id,))
    if not row:
        return error_response("Not found.", 404)
    req = fetch_one("SELECT id, user_id FROM assistance_requests WHERE id = ?", (row["request_id"],))
    if not lifecycle.can_view_request(req, user):
        return error_response("Not found.", 404)
    path = (UPLOAD_DIR / row["stored_name"]).resolve()
    if path.parent != UPLOAD_DIR.resolve() or not path.exists():
        return error_response("Not found.", 404)
    return send_file(path, mimetype=row["content_type"], as_attachment=False, max_age=0)


# ============================================================
# TRACKING
# ============================================================

@app.get("/tracking/<int:request_id>")
@login_required
def tracking(request_id):

    user = current_user()

    try:
        view = lifecycle.get_tracking_view(request_id, user)
    except LifecycleError as error:
        return error_response(error.message, error.status_code)

    return render_template(
        "tracking.html",
        item=view["request"],
        view=view,
        attachments=_attachments_for(request_id),
        action_labels=ACTION_LABELS,
    )


@app.get("/api/tracking/<int:request_id>")
@login_required
def api_tracking(request_id):

    user = current_user()

    try:
        view = lifecycle.get_tracking_view(request_id, user)
    except LifecycleError as error:
        return jsonify({"success": False, "message": error.message}), error.status_code

    return jsonify({
        "success": True,
        # Backward-compatible keys used by the previous tracking page:
        "request": view["request"],
        "tracking": view["timeline"],
        "provider": view["provider"],
        # Additional data:
        "provider_location": view["provider_location"],
        "driver_location": view["driver_location"],
        "live_distance_km": view["live_distance_km"],
        "provider_base_location": view["provider_base_location"],
        "base_distance_km": view["base_distance_km"],
        "diagnosis": view["diagnosis"],
        "feedback": view["feedback"],
        "actions": view["actions"],
        "is_open": view["is_open"],
        "attachments": _attachments_for(request_id),
        "server_time": utc_now(),
    })


# ============================================================
# CANCEL / FEEDBACK (driver)
# ============================================================

@app.post("/api/requests/<int:request_id>/cancel")
@role_required("driver")
def api_cancel_request(request_id):

    user = current_user()

    try:
        result = lifecycle.cancel_request(request_id, user["id"], "driver", request.form.get("reason"))
    except ValidationError as error:
        return jsonify({"success": False, "message": str(error)}), 400
    except LifecycleError as error:
        return jsonify({"success": False, "message": error.message}), error.status_code

    return jsonify({
        "success": True,
        "message": "Request is already cancelled." if result.get("unchanged") else "Assistance request cancelled.",
    })


@app.post("/api/requests/<int:request_id>/feedback")
@role_required("driver")
def api_request_feedback(request_id):
    user = current_user()
    try:
        lifecycle.submit_feedback(request_id, user["id"], request.form.get("rating"), request.form.get("comment"))
    except ValidationError as error:
        return jsonify({"success": False, "message": str(error)}), 400
    except LifecycleError as error:
        return jsonify({"success": False, "message": error.message}), error.status_code
    return jsonify({"success": True, "message": "Thank you for your feedback."})


# ============================================================
# PROVIDER: JOB STATUS
# ============================================================

@app.post("/api/provider/job/<int:job_id>/status")
@role_required("provider")
def api_provider_job_status(job_id):

    user = current_user()

    provider = get_provider_by_user_id(user["id"])
    if not provider:
        return jsonify({"success": False, "message": "Provider profile not found."}), 404

    try:
        result = lifecycle.transition_match(
            job_id,
            request.form.get("status", ""),
            provider_user_id=user["id"],
            note=request.form.get("note"),
        )
    except ValidationError as error:
        return jsonify({"success": False, "message": str(error)}), 400
    except LifecycleError as error:
        return jsonify({"success": False, "message": error.message}), error.status_code

    payload = {"success": True, "status": result["status"], "status_label": status_label(result["status"])}
    if result.get("unchanged"):
        payload["message"] = "Status is unchanged."
    else:
        payload["message"] = f"Status updated: {payload['status_label']}."

    # The provider's browser sends its current position together with
    # Accept / On the way / Arrived, so the driver sees the live location the
    # moment the status changes. A location problem never undoes the status change.
    payload["location_shared"] = False
    if result["status"] in lifecycle.LOCATION_TRACKED_STATUSES and request.form.get("latitude"):
        try:
            shared = lifecycle.update_provider_location(
                user["id"], request.form.get("latitude"), request.form.get("longitude"),
                request.form.get("accuracy"),
            )
            payload["location_shared"] = bool(shared.get("tracking_active"))
        except (ValidationError, LifecycleError) as error:
            payload["location_error"] = getattr(error, "message", str(error))
    return jsonify(payload)


@app.post("/api/provider/location")
@role_required("provider")
def api_provider_location():
    user = current_user()
    try:
        result = lifecycle.update_provider_location(
            user["id"], request.form.get("latitude"), request.form.get("longitude"), request.form.get("accuracy"),
            record_tracking=request.form.get("mode") != "base",
        )
    except ValidationError as error:
        return jsonify({"success": False, "message": str(error)}), 400
    except LifecycleError as error:
        return jsonify({"success": False, "message": error.message}), error.status_code
    return jsonify({"success": True, **result})


@app.post("/api/provider/availability")
@role_required("provider")
def api_provider_availability():
    user = current_user()
    provider = get_provider_by_user_id(user["id"])
    if not provider:
        return jsonify({"success": False, "message": "Provider profile not found."}), 404
    availability = (request.form.get("availability") or "").strip().lower()
    if availability not in ("available", "offline"):
        return jsonify({"success": False, "message": "Availability must be available or offline."}), 400
    execute_query("UPDATE providers SET availability = ? WHERE id = ?", (availability, provider["id"]))
    log_action(user["id"], "provider.availability", "provider", provider["id"], {"availability": availability},
               client_ip())
    if availability == "available":
        try:
            lifecycle.retry_unassigned(limit=5)
        except Exception:  # noqa: BLE001
            logger.exception("Retry after availability change failed")
    return jsonify({"success": True, "availability": availability})


@app.post("/provider/profile")
@role_required("provider")
def provider_profile():
    """Create (if missing) or update the signed-in provider's business profile."""
    user = current_user()
    try:
        business_name = clean_text(request.form.get("business_name"), "Business name", 120, required=True,
                                   min_length=2)
        service_type = request.form.get("service_type", "")
        if service_type not in {value for value, _ in PROVIDER_SERVICE_TYPES}:
            raise ValidationError("Choose a service type from the list.")
        phone = validate_phone(request.form.get("phone"), required=True)
    except ValidationError as error:
        flash(str(error), "error")
        return redirect(url_for("provider_dashboard"))

    existing = get_provider_by_user_id(user["id"])
    if existing:
        category_changed = _normalize_service(existing["service_type"]) != _normalize_service(service_type)
        new_verification = "pending" if (category_changed and not settings.provider_auto_approve) else \
            existing["verification_status"]
        execute_query(
            "UPDATE providers SET business_name = ?, service_type = ?, phone = ?, verification_status = ? WHERE id = ?",
            (business_name, service_type, phone, new_verification, existing["id"]),
        )
        if category_changed and new_verification == "pending":
            notifications.notify_admins("PROVIDER_VERIFICATION", "Provider changed service type",
                                        f"{business_name} changed to {service_type} and needs re-verification.",
                                        dedupe_key=f"reverify:{existing['id']}:{service_type}")
            flash("Profile updated. Your new service type needs administrator verification.", "success")
        else:
            flash("Profile updated.", "success")
        log_action(user["id"], "provider.profile_update", "provider", existing["id"],
                   {"service_type": service_type, "verification": new_verification}, client_ip())
    else:
        verification = "approved" if settings.provider_auto_approve else "pending"
        provider_id = execute_query(
            "INSERT INTO providers (user_id, business_name, service_type, phone, availability, verification_status) "
            "VALUES (?, ?, ?, ?, 'available', ?)",
            (user["id"], business_name, service_type, phone, verification),
        )
        notifications.notify_admins("PROVIDER_VERIFICATION", "Provider awaiting verification",
                                    f"{business_name} ({service_type}) created a profile.",
                                    dedupe_key=f"verify:{user['id']}")
        log_action(user["id"], "provider.profile_create", "provider", provider_id, {"service_type": service_type},
                   client_ip())
        flash("Provider profile created.", "success")
    return redirect(url_for("provider_dashboard"))


# ============================================================
# PROVIDER DASHBOARD
# ============================================================

def _provider_jobs(provider_id):
    rows = fetch_all(
        """
        SELECT sm.*, ar.incident_type, ar.description, ar.priority, ar.latitude, ar.longitude,
               ar.status AS request_status, ar.safe_to_drive, ar.created_at AS request_created_at,
               u.name AS driver_name, u.phone AS driver_phone, v.registration_number, v.make, v.model
        FROM service_matches sm
        JOIN assistance_requests ar ON sm.request_id = ar.id
        JOIN users u ON ar.user_id = u.id
        LEFT JOIN vehicles v ON ar.vehicle_id = v.id
        WHERE sm.provider_id = ?
        ORDER BY sm.created_at DESC, sm.id DESC
        LIMIT 100
        """,
        (provider_id,),
    )
    active, closed = [], []
    for row in rows:
        job = dict(row)
        job["next_actions"] = lifecycle.provider_next_actions(job["status"])
        job["status_label"] = status_label(job["status"])
        if job["status"] in ACTIVE_MATCH_STATUSES:
            active.append(job)
        else:
            job["driver_phone"] = None  # contact details only while the job is active
            closed.append(job)
    return active, closed


def _provider_stats(provider_id):
    counts = {r["status"]: r["c"] for r in fetch_all(
        "SELECT status, COUNT(*) AS c FROM service_matches WHERE provider_id = ? GROUP BY status", (provider_id,))}
    completed = counts.get("COMPLETED", 0)
    failed = counts.get("UNABLE_TO_COMPLETE", 0)
    feedback = fetch_one("SELECT COUNT(*) AS n, ROUND(AVG(rating), 2) AS avg FROM service_feedback WHERE provider_id = ?",
                         (provider_id,))
    response = fetch_one(
        """
        SELECT ROUND(AVG((julianday(arr.updated_at) - julianday(sm.created_at)) * 1440), 1) AS minutes, COUNT(*) AS n
        FROM service_matches sm
        JOIN tracking arr ON arr.request_id = sm.request_id AND arr.provider_id = sm.provider_id
             AND arr.status = 'ARRIVED'
        WHERE sm.provider_id = ?
        """,
        (provider_id,),
    )
    return {
        "pending": counts.get("ASSIGNED", 0),
        "active": sum(counts.get(s, 0) for s in ("ACCEPTED", "ON_THE_WAY", "ARRIVED", "IN_PROGRESS")),
        "completed": completed,
        "rejected": counts.get("REJECTED", 0),
        "unable": failed,
        "completion_rate": round(100 * completed / (completed + failed), 1) if (completed + failed) else None,
        "feedback_count": feedback["n"],
        "feedback_avg": feedback["avg"],
        "avg_arrival_minutes": response["minutes"] if response["n"] else None,
        "arrival_samples": response["n"],
    }


@app.get("/provider")
@role_required("provider")
def provider_dashboard():

    user = current_user()
    provider = get_provider_by_user_id(user["id"])

    if not provider:
        return render_template("provider_setup.html", service_types=PROVIDER_SERVICE_TYPES)

    p = dict(provider)
    p["category"] = _normalize_service(p["service_type"])
    active_jobs, closed_jobs = _provider_jobs(p["id"])
    stats = _provider_stats(p["id"])
    stats["rating"] = p["rating"] or 0

    return render_template(
        "provider_dashboard.html",
        provider=p,
        jobs=active_jobs + closed_jobs,  # kept for compatibility with older templates
        active_jobs=active_jobs,
        closed_jobs=closed_jobs,
        stats=stats,
        action_labels=ACTION_LABELS,
        service_types=PROVIDER_SERVICE_TYPES,
    )


@app.get("/api/provider/jobs")
@role_required("provider")
def api_provider_jobs():
    """Lightweight polling endpoint: lets the dashboard detect new/changed jobs."""
    user = current_user()
    provider = get_provider_by_user_id(user["id"])
    if not provider:
        return jsonify({"success": False, "message": "Provider profile not found."}), 404
    row = fetch_one("SELECT COUNT(*) AS n, MAX(COALESCE(updated_at, created_at)) AS last FROM service_matches "
                    "WHERE provider_id = ?", (provider["id"],))
    active = fetch_one(
        f"SELECT sm.id, sm.status, sm.request_id FROM service_matches sm WHERE sm.provider_id = ? "
        f"AND sm.status IN ({','.join('?' * len(lifecycle.LOCATION_TRACKED_STATUSES))}) ORDER BY sm.id DESC LIMIT 1",
        (provider["id"], *lifecycle.LOCATION_TRACKED_STATUSES),
    )
    return jsonify({
        "success": True,
        "version": f"{row['n']}:{row['last']}",
        "tracking_job": dict(active) if active else None,
    })


# ============================================================
# ADMIN
# ============================================================

def _admin_overview():
    """Every statistic is defined precisely (shown on the page)."""
    def count(sql, params=()):
        return fetch_one(sql, params)["c"]

    active_list = ",".join("?" * len(ACTIVE_MATCH_STATUSES))
    return {
        "total_users": count("SELECT COUNT(*) c FROM users"),
        "active_drivers": count("SELECT COUNT(*) c FROM users WHERE role = 'driver' AND is_active = 1"),
        "registered_providers": count("SELECT COUNT(*) c FROM providers"),
        "approved_providers": count("SELECT COUNT(*) c FROM providers WHERE COALESCE(verification_status,'approved') = 'approved'"),
        "pending_verification": count("SELECT COUNT(*) c FROM providers WHERE verification_status = 'pending'"),
        "dispatchable_providers": sum(_dispatchable_provider_summary().values()),
        "requests_total": count("SELECT COUNT(*) c FROM assistance_requests"),
        "requests_unassigned": count("SELECT COUNT(*) c FROM assistance_requests WHERE status = 'REQUESTED'"),
        "requests_assigned": count("SELECT COUNT(*) c FROM assistance_requests WHERE status IN "
                                   "('ASSIGNED','ACCEPTED','ON_THE_WAY','ARRIVED')"),
        "requests_in_progress": count("SELECT COUNT(*) c FROM assistance_requests WHERE status = 'IN_PROGRESS'"),
        "requests_completed": count("SELECT COUNT(*) c FROM assistance_requests WHERE status = 'COMPLETED'"),
        "requests_cancelled": count("SELECT COUNT(*) c FROM assistance_requests WHERE status = 'CANCELLED'"),
        "unassigned_emergencies": count("SELECT COUNT(*) c FROM assistance_requests WHERE status = 'REQUESTED' "
                                        "AND priority = 'EMERGENCY'"),
        "active_jobs": count(f"SELECT COUNT(*) c FROM service_matches WHERE status IN ({active_list})",
                             ACTIVE_MATCH_STATUSES),
    }


STAT_DEFINITIONS = {
    "total_users": "All accounts (drivers, providers, admins), active or not.",
    "active_drivers": "Driver accounts that are active.",
    "registered_providers": "Provider business profiles.",
    "approved_providers": "Provider profiles with verification approved.",
    "pending_verification": "Provider profiles waiting for verification.",
    "dispatchable_providers": "Approved, available, linked to an active login and without an active job.",
    "requests_total": "All assistance requests ever created.",
    "requests_unassigned": "Open requests with no provider (status REQUESTED).",
    "requests_assigned": "Provider assigned, service not started (ASSIGNED, ACCEPTED, ON_THE_WAY, ARRIVED).",
    "requests_in_progress": "Service work started (IN_PROGRESS).",
    "requests_completed": "Requests with status COMPLETED.",
    "requests_cancelled": "Requests with status CANCELLED.",
    "unassigned_emergencies": "EMERGENCY priority requests still waiting for a provider.",
    "active_jobs": "Provider jobs in an active state.",
}


@app.get("/admin")
@role_required("admin")
def admin_dashboard():
    try:
        lifecycle.check_escalations()
    except Exception:  # noqa: BLE001
        logger.exception("Escalation check failed")

    stats = _admin_overview()
    emergencies = _requests_with_provider("ar.status = 'REQUESTED' AND ar.priority = 'EMERGENCY'", (), 20)
    recent = _requests_with_provider("1 = 1", (), 10)
    return render_template("admin_dashboard.html", stats=stats, definitions=STAT_DEFINITIONS,
                           emergencies=emergencies, recent=recent,
                           channels=notifications.channel_status())


@app.get("/api/admin/overview")
@role_required("admin")
def api_admin_overview():
    return jsonify({"success": True, "stats": _admin_overview()})


@app.post("/admin/maintenance")
@role_required("admin")
def admin_maintenance():
    user = current_user()
    retry = lifecycle.retry_unassigned()
    escalations = lifecycle.check_escalations()
    log_action(user["id"], "admin.maintenance", "system", None, {**retry, **escalations}, client_ip())
    flash(f"Matching retried for {retry['checked']} open request(s); {retry['assigned']} assigned.", "success")
    return redirect(url_for("admin_dashboard"))


# ---------------- users ----------------

@app.get("/admin/users")
@role_required("admin")
def admin_users():
    role = request.args.get("role") or None
    params, where = [], ""
    if role in ("driver", "provider", "admin"):
        where, params = "WHERE u.role = ?", [role]
    rows = [dict(r) for r in fetch_all(
        f"""
        SELECT u.id, u.name, u.email, u.phone, u.role, u.is_active, u.created_at,
               (SELECT COUNT(*) FROM assistance_requests ar WHERE ar.user_id = u.id) AS request_count,
               (SELECT p.business_name FROM providers p WHERE p.user_id = u.id) AS business_name
        FROM users u {where}
        ORDER BY u.id DESC LIMIT 500
        """,
        params,
    )]
    return render_template("admin_users.html", users=rows, role=role)


@app.post("/admin/users/<int:user_id>/status")
@role_required("admin")
def admin_user_status(user_id):
    admin = current_user()
    activate = request.form.get("active") == "1"
    target = fetch_one("SELECT id, role, is_active, name FROM users WHERE id = ?", (user_id,))
    if not target:
        return error_response("User not found.", 404)
    if not activate:
        if target["id"] == admin["id"]:
            flash("You cannot deactivate your own account.", "error")
            return redirect(url_for("admin_users"))
        if target["role"] == "admin":
            remaining = fetch_one("SELECT COUNT(*) AS c FROM users WHERE role = 'admin' AND is_active = 1 AND id != ?",
                                  (user_id,))["c"]
            if remaining < 1:
                flash("At least one active administrator must remain.", "error")
                return redirect(url_for("admin_users"))

    execute_query("UPDATE users SET is_active = ? WHERE id = ?", (1 if activate else 0, user_id))

    released = []
    if not activate and target["role"] == "provider":
        provider = get_provider_by_user_id(user_id)
        if provider:
            for job in fetch_all(
                f"SELECT request_id, status FROM service_matches WHERE provider_id = ? AND status IN "
                f"({','.join('?' * len(ACTIVE_MATCH_STATUSES))})",
                (provider["id"], *ACTIVE_MATCH_STATUSES),
            ):
                try:
                    lifecycle.admin_reassign(job["request_id"], admin["id"], None, "Provider account deactivated")
                    released.append(job["request_id"])
                except LifecycleError as error:
                    flash(f"Request #{job['request_id']}: {error.message}", "error")

    log_action(admin["id"], "user.activate" if activate else "user.deactivate", "user", user_id,
               {"role": target["role"], "released_requests": ",".join(map(str, released))}, client_ip())
    flash(f"{target['name']} {'activated' if activate else 'deactivated'}."
          + (f" Reassigned request(s): {', '.join(map(str, released))}." if released else ""), "success")
    return redirect(url_for("admin_users"))


# ---------------- providers ----------------

@app.get("/admin/providers")
@role_required("admin")
def admin_providers():
    rows = []
    for r in fetch_all(
        f"""
        SELECT p.*, u.email AS user_email, u.is_active AS user_is_active,
            (SELECT COUNT(*) FROM service_matches sm WHERE sm.provider_id = p.id) AS jobs_total,
            (SELECT COUNT(*) FROM service_matches sm WHERE sm.provider_id = p.id AND sm.status = 'COMPLETED') AS jobs_completed,
            (SELECT COUNT(*) FROM service_matches sm WHERE sm.provider_id = p.id AND sm.status IN ('REJECTED','UNABLE_TO_COMPLETE')) AS jobs_failed,
            (SELECT COUNT(*) FROM service_matches sm WHERE sm.provider_id = p.id AND sm.status IN ({','.join('?' * len(ACTIVE_MATCH_STATUSES))})) AS jobs_active,
            (SELECT COUNT(*) FROM service_feedback sf WHERE sf.provider_id = p.id) AS feedback_count
        FROM providers p LEFT JOIN users u ON u.id = p.user_id
        ORDER BY CASE p.verification_status WHEN 'pending' THEN 0 ELSE 1 END, p.id DESC
        """,
        ACTIVE_MATCH_STATUSES,
    ):
        item = dict(r)
        item["category"] = _normalize_service(item["service_type"])
        item["category_known"] = item["category"] in PROVIDER_CATEGORIES
        item["location_valid"] = _haversine(item["latitude"], item["longitude"], item["latitude"],
                                            item["longitude"]) is not None
        rows.append(item)
    linkable = fetch_all(
        "SELECT u.id, u.name, u.email FROM users u WHERE u.role = 'provider' AND u.is_active = 1 "
        "AND NOT EXISTS (SELECT 1 FROM providers p WHERE p.user_id = u.id) ORDER BY u.name"
    )
    return render_template("admin_providers.html", providers=rows, linkable=linkable)


@app.post("/admin/providers/<int:provider_id>/verification")
@role_required("admin")
def admin_provider_verification(provider_id):
    admin = current_user()
    decision = request.form.get("decision")
    if decision not in ("approved", "rejected", "pending"):
        return error_response("Invalid decision.", 400)
    provider = get_provider_by_id(provider_id)
    if not provider:
        return error_response("Provider not found.", 404)

    execute_query("UPDATE providers SET verification_status = ? WHERE id = ?", (decision, provider_id))

    if decision != "approved":
        for job in fetch_all(
            f"SELECT request_id FROM service_matches WHERE provider_id = ? AND status IN "
            f"('ASSIGNED','ACCEPTED','ON_THE_WAY','ARRIVED')",
            (provider_id,),
        ):
            try:
                lifecycle.admin_reassign(job["request_id"], admin["id"], None, f"Provider verification {decision}")
            except LifecycleError as error:
                flash(f"Request #{job['request_id']}: {error.message}", "error")
    else:
        lifecycle.retry_unassigned(limit=10)

    if provider["user_id"]:
        notifications.notify(provider["user_id"], "PROVIDER_VERIFICATION", f"Verification {decision}",
                             f"Your provider profile verification is now: {decision}.",
                             dedupe_key=f"verification:{provider_id}:{decision}:{utc_now()}")
    log_action(admin["id"], "provider.verification", "provider", provider_id, {"decision": decision}, client_ip())
    flash(f"{provider['business_name']}: verification {decision}.", "success")
    return redirect(url_for("admin_providers"))


@app.post("/admin/providers/<int:provider_id>/availability")
@role_required("admin")
def admin_provider_availability(provider_id):
    admin = current_user()
    availability = request.form.get("availability")
    if availability not in ("available", "offline"):
        return error_response("Invalid availability.", 400)
    provider = get_provider_by_id(provider_id)
    if not provider:
        return error_response("Provider not found.", 404)
    execute_query("UPDATE providers SET availability = ? WHERE id = ?", (availability, provider_id))
    log_action(admin["id"], "provider.availability", "provider", provider_id, {"availability": availability},
               client_ip())
    if availability == "available":
        lifecycle.retry_unassigned(limit=10)
    flash(f"{provider['business_name']} set to {availability}.", "success")
    return redirect(url_for("admin_providers"))


@app.post("/admin/providers/<int:provider_id>/link")
@role_required("admin")
def admin_provider_link(provider_id):
    """Link a provider profile that has no login (e.g. seeded) to a provider-role account."""
    admin = current_user()
    provider = get_provider_by_id(provider_id)
    if not provider:
        return error_response("Provider not found.", 404)
    if provider["user_id"]:
        flash("This provider is already linked to an account.", "error")
        return redirect(url_for("admin_providers"))
    try:
        user_id = parse_int(request.form.get("user_id"), "Account")
    except ValidationError as error:
        flash(str(error), "error")
        return redirect(url_for("admin_providers"))
    account = fetch_one("SELECT id, role FROM users WHERE id = ? AND role = 'provider' AND is_active = 1", (user_id,))
    if not account or fetch_one("SELECT 1 FROM providers WHERE user_id = ?", (user_id,)):
        flash("Choose an active provider account that has no profile yet.", "error")
        return redirect(url_for("admin_providers"))
    execute_query("UPDATE providers SET user_id = ? WHERE id = ? AND user_id IS NULL", (user_id, provider_id))
    log_action(admin["id"], "provider.link_account", "provider", provider_id, {"user_id": user_id}, client_ip())
    lifecycle.retry_unassigned(limit=10)
    flash(f"{provider['business_name']} linked to the selected account.", "success")
    return redirect(url_for("admin_providers"))


# ---------------- requests ----------------

@app.get("/admin/requests")
@role_required("admin")
def admin_requests():
    status = request.args.get("status") or None
    if status and status not in lifecycle.REQUEST_STATUSES:
        status = None
    if status:
        items = _requests_with_provider("ar.status = ?", (status,), 300)
    else:
        items = _requests_with_provider("1 = 1", (), 300)
    return render_template("admin_requests.html", items=items, status=status, statuses=lifecycle.REQUEST_STATUSES)


@app.get("/admin/requests/<int:request_id>")
@role_required("admin")
def admin_request_detail(request_id):
    user = current_user()
    try:
        view = lifecycle.get_tracking_view(request_id, user)
    except LifecycleError as error:
        return error_response(error.message, error.status_code)

    matches = []
    for row in fetch_all(
        "SELECT sm.*, p.business_name, p.service_type FROM service_matches sm JOIN providers p ON p.id = sm.provider_id "
        "WHERE sm.request_id = ? ORDER BY sm.id",
        (request_id,),
    ):
        item = dict(row)
        try:
            item["match_details"] = json.loads(item.get("match_details") or "null")
        except (TypeError, ValueError):
            item["match_details"] = None
        matches.append(item)

    req = view["request"]
    candidates = []
    excluded = []
    if req["status"] in lifecycle.REASSIGNABLE:
        current = next((m for m in matches if m["status"] in ACTIVE_MATCH_STATUSES), None)
        failed = {m["provider_id"] for m in matches if m["status"] in ("REJECTED", "UNABLE_TO_COMPLETE", "REASSIGNED")}
        ranking = rank_providers(req["recommended_service"], req["latitude"], req["longitude"],
                                 priority=req["priority"],
                                 exclude_provider_ids=failed | ({current["provider_id"]} if current else set()))
        candidates, excluded = ranking["candidates"], ranking["excluded"]

    full_history = [dict(r) for r in fetch_all("SELECT * FROM tracking WHERE request_id = ? ORDER BY id",
                                                (request_id,))]

    # Legacy records classified "unknown" by the old analyzer: show what the current
    # engine says, WITHOUT overwriting the stored record.
    reanalysis = None
    if req["incident_type"] == "unknown" and req.get("description"):
        current = analyzer.analyze(req["description"])
        if current["problem"] != "unknown":
            reanalysis = current

    return render_template("admin_request_detail.html", view=view, item=req, matches=matches,
                           candidates=candidates, excluded=excluded, history=full_history,
                           attachments=_attachments_for(request_id), reanalysis=reanalysis)


@app.post("/admin/requests/<int:request_id>/reassign")
@role_required("admin")
def admin_request_reassign(request_id):
    admin = current_user()
    provider_id = request.form.get("provider_id") or None
    try:
        result = lifecycle.admin_reassign(request_id, admin["id"], provider_id, request.form.get("reason"))
    except ValidationError as error:
        flash(str(error), "error")
        return redirect(url_for("admin_request_detail", request_id=request_id))
    except LifecycleError as error:
        flash(error.message, "error")
        return redirect(url_for("admin_request_detail", request_id=request_id))

    assignment = result["assignment"]
    log_action(admin["id"], "request.reassign", "assistance_request", request_id,
               {"previous_match_id": result["previous_match_id"], "requested_provider_id": provider_id,
                "assigned": assignment.get("assigned"), "new_provider_id": assignment.get("provider_id"),
                "reason": request.form.get("reason")}, client_ip())
    flash("Request reassigned." if assignment.get("assigned") else
          "Previous provider released, but no eligible provider is available; the request is waiting.",
          "success" if assignment.get("assigned") else "error")
    return redirect(url_for("admin_request_detail", request_id=request_id))


@app.post("/admin/requests/<int:request_id>/retry")
@role_required("admin")
def admin_request_retry(request_id):
    admin = current_user()
    try:
        result = lifecycle.assign_best_provider(request_id)
    except LifecycleError as error:
        flash(error.message, "error")
        return redirect(url_for("admin_request_detail", request_id=request_id))
    log_action(admin["id"], "request.retry_matching", "assistance_request", request_id,
               {"assigned": result.get("assigned")}, client_ip())
    flash("Provider assigned." if result.get("assigned") else "Still no eligible provider.",
          "success" if result.get("assigned") else "error")
    return redirect(url_for("admin_request_detail", request_id=request_id))


@app.post("/admin/requests/<int:request_id>/cancel")
@role_required("admin")
def admin_request_cancel(request_id):
    admin = current_user()
    try:
        lifecycle.cancel_request(request_id, admin["id"], "admin", request.form.get("reason"))
    except (ValidationError, LifecycleError) as error:
        flash(getattr(error, "message", str(error)), "error")
        return redirect(url_for("admin_request_detail", request_id=request_id))
    log_action(admin["id"], "request.cancel", "assistance_request", request_id,
               {"reason": request.form.get("reason")}, client_ip())
    flash("Request cancelled.", "success")
    return redirect(url_for("admin_request_detail", request_id=request_id))


# ---------------- audit + reports ----------------

@app.get("/admin/audit")
@role_required("admin")
def admin_audit():
    return render_template("admin_audit.html", items=recent_actions(300))


def _reports():
    response = fetch_one(
        """
        SELECT COUNT(*) AS n,
               ROUND(AVG((julianday(first_assigned) - julianday(created_at)) * 1440), 1) AS assign_minutes,
               ROUND(AVG((julianday(first_arrived) - julianday(created_at)) * 1440), 1) AS arrive_minutes
        FROM (
            SELECT ar.created_at,
                   (SELECT MIN(t.updated_at) FROM tracking t WHERE t.request_id = ar.id AND t.status = 'ASSIGNED') AS first_assigned,
                   (SELECT MIN(t.updated_at) FROM tracking t WHERE t.request_id = ar.id AND t.status = 'ARRIVED') AS first_arrived
            FROM assistance_requests ar
        )
        WHERE first_assigned IS NOT NULL
        """
    )
    arrived_n = fetch_one("SELECT COUNT(DISTINCT request_id) AS n FROM tracking WHERE status = 'ARRIVED'")["n"]
    closed = fetch_one(
        "SELECT SUM(status = 'COMPLETED') AS completed, SUM(status = 'CANCELLED') AS cancelled, "
        "SUM(status NOT IN ('COMPLETED','CANCELLED')) AS open_count, COUNT(*) AS total FROM assistance_requests"
    )
    completed = closed["completed"] or 0
    cancelled = closed["cancelled"] or 0
    providers = [dict(r) for r in fetch_all(
        """
        SELECT p.id, p.business_name, p.service_type, p.rating,
               COUNT(sm.id) AS assigned,
               SUM(sm.status = 'COMPLETED') AS completed,
               SUM(sm.status = 'REJECTED') AS rejected,
               SUM(sm.status = 'UNABLE_TO_COMPLETE') AS unable,
               (SELECT COUNT(*) FROM service_feedback sf WHERE sf.provider_id = p.id) AS feedback_count,
               (SELECT ROUND(AVG(sf.rating), 2) FROM service_feedback sf WHERE sf.provider_id = p.id) AS feedback_avg
        FROM providers p LEFT JOIN service_matches sm ON sm.provider_id = p.id
        GROUP BY p.id ORDER BY assigned DESC, p.business_name
        """
    )]
    incidents = [dict(r) for r in fetch_all(
        "SELECT incident_type, priority, COUNT(*) AS n FROM assistance_requests GROUP BY incident_type, priority "
        "ORDER BY n DESC"
    )]
    failures = {
        "currently_unassigned": fetch_one("SELECT COUNT(*) AS c FROM assistance_requests WHERE status = 'REQUESTED'")["c"],
        "requests_never_matched": fetch_one(
            "SELECT COUNT(*) AS c FROM assistance_requests ar WHERE NOT EXISTS "
            "(SELECT 1 FROM service_matches sm WHERE sm.request_id = ar.id)")["c"],
        "no_provider_events": fetch_one(
            "SELECT COUNT(DISTINCT request_id) AS c FROM tracking WHERE notes LIKE 'No eligible provider%' "
            "OR notes LIKE 'No available provider%'")["c"],
        "rejections": fetch_one("SELECT COUNT(*) AS c FROM service_matches WHERE status = 'REJECTED'")["c"],
        "unable_to_complete": fetch_one("SELECT COUNT(*) AS c FROM service_matches WHERE status = 'UNABLE_TO_COMPLETE'")["c"],
        "admin_reassignments": fetch_one("SELECT COUNT(*) AS c FROM service_matches WHERE status = 'REASSIGNED'")["c"],
    }
    return {
        "response": {**dict(response), "arrived_samples": arrived_n},
        "completion": {
            "completed": completed, "cancelled": cancelled, "open": closed["open_count"] or 0,
            "total": closed["total"],
            "rate": round(100 * completed / (completed + cancelled), 1) if (completed + cancelled) else None,
        },
        "providers": providers,
        "incidents": incidents,
        "failures": failures,
    }


@app.get("/admin/reports")
@role_required("admin")
def admin_reports():
    return render_template("admin_reports.html", report=_reports())


# ============================================================
# ERROR HANDLERS (no stack traces to clients)
# ============================================================

@app.errorhandler(400)
def bad_request(_):
    return error_response("The request could not be processed.", 400)


@app.errorhandler(403)
def forbidden(_):
    return error_response("Access denied.", 403)


@app.errorhandler(404)
def not_found(_):
    return error_response("Page not found.", 404)


@app.errorhandler(405)
def method_not_allowed(_):
    return error_response("Method not allowed.", 405)


@app.errorhandler(413)
def too_large(_):
    return error_response(f"Upload must be {settings.max_upload_mb} MB or smaller.", 413)


@app.errorhandler(500)
def server_error(error):
    logger.error("Unhandled error (request %s): %s", g.get("request_id"), error)
    return error_response(f"Something went wrong. Reference: {g.get('request_id', '-')}", 500)


@app.errorhandler(Exception)
def unhandled_exception(error):
    from werkzeug.exceptions import HTTPException

    if isinstance(error, HTTPException):
        return error
    logger.exception("Unhandled exception (request %s)", g.get("request_id"))
    return error_response(f"Something went wrong. Reference: {g.get('request_id', '-')}", 500)


# ============================================================
# APPLICATION START (development server only)
# ============================================================

if __name__ == "__main__":

    if settings.is_production:
        raise SystemExit("RSA_ENV=production: run with a WSGI server (see wsgi.py / DEPLOYMENT.md), "
                         "not the Flask development server.")

    app.run(
        host=os.environ.get("RSA_HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", 5000)),
        # Debug mode is opt-in; never expose the interactive debugger by default.
        debug=settings.debug,
    )
