"""
Production WSGI entry point for the RSA web application.

Windows (your current setup) — Waitress:
    pip install -r requirements-prod.txt
    set RSA_ENV=production
    set RSA_SECRET_KEY=<64 hex chars>
    python wsgi.py                       (serves on 127.0.0.1:8000 by default)

Linux — Gunicorn (one worker process recommended with SQLite, see DEPLOYMENT.md):
    gunicorn --workers 1 --threads 8 --bind 127.0.0.1:8000 wsgi:app

Put HTTPS in front (Caddy / nginx / IIS reverse proxy) and set RSA_TRUST_PROXY=1.
"""

import os

from web import app, settings  # noqa: F401  (importing web runs migrations once, with backup)

application = app  # some hosts look for "application"


def main():
    host = os.environ.get("RSA_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    threads = int(os.environ.get("RSA_THREADS", "8"))
    try:
        from waitress import serve
    except ImportError:
        raise SystemExit("Waitress is not installed. Run: pip install -r requirements-prod.txt")
    if not settings.is_production:
        print("Warning: RSA_ENV is not 'production' (development settings are active).")
    print(f"RSA serving on http://{host}:{port} with {threads} threads (put HTTPS in front of this).")
    serve(app, host=host, port=port, threads=threads)


if __name__ == "__main__":
    main()
