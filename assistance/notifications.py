"""
RSA Notifications
-----------------

Reliable in-app notifications, with optional e-mail delivery.

Design rules:
- Notifications are written AFTER the lifecycle change has committed, so a
  notification always describes something that really happened.
- A failure to notify is logged and swallowed: it can never roll back or
  corrupt a request, assignment or status change.
- ``dedupe_key`` (unique per user) prevents duplicate messages when the same
  event is processed twice (retries, double clicks, repeated escalation checks).
- E-mail is optional and only used when SMTP settings are configured
  (RSA_SMTP_HOST, RSA_SMTP_PORT, RSA_SMTP_USER, RSA_SMTP_PASSWORD,
  RSA_SMTP_FROM, RSA_SMTP_STARTTLS). SMS needs an external provider account;
  ``SmsChannel`` is an interface that reports itself as not configured.
"""

import logging
import os
import smtplib
from email.message import EmailMessage

from database.database import execute_query, fetch_all, fetch_one, get_connection


logger = logging.getLogger("rsa.notifications")

EVENT_TYPES = {
    "REQUEST_CREATED",
    "PROVIDER_ASSIGNED",
    "JOB_ASSIGNED",
    "PROVIDER_ACCEPTED",
    "PROVIDER_REJECTED",
    "PROVIDER_ON_THE_WAY",
    "PROVIDER_ARRIVED",
    "SERVICE_STARTED",
    "SERVICE_COMPLETED",
    "PROVIDER_UNABLE",
    "REQUEST_CANCELLED",
    "JOB_CANCELLED",
    "EMERGENCY_ESCALATED",
    "NO_PROVIDER_AVAILABLE",
    "REQUEST_REASSIGNED",
    "ACCOUNT_STATUS",
    "PROVIDER_VERIFICATION",
}

# Events important enough to also e-mail (when SMTP is configured).
EMAIL_EVENTS = {"PROVIDER_ASSIGNED", "JOB_ASSIGNED", "EMERGENCY_ESCALATED", "NO_PROVIDER_AVAILABLE",
                "SERVICE_COMPLETED", "REQUEST_CANCELLED", "JOB_CANCELLED"}


# ==========================================================
# CHANNELS
# ==========================================================

class EmailChannel:

    def __init__(self):
        self.host = os.environ.get("RSA_SMTP_HOST", "").strip()
        self.port = int(os.environ.get("RSA_SMTP_PORT", "587") or 587)
        self.user = os.environ.get("RSA_SMTP_USER", "").strip()
        self.password = os.environ.get("RSA_SMTP_PASSWORD", "")
        self.sender = os.environ.get("RSA_SMTP_FROM", self.user).strip()
        self.starttls = os.environ.get("RSA_SMTP_STARTTLS", "1").strip() not in {"0", "false", "no"}

    @property
    def configured(self):
        return bool(self.host and self.sender)

    def send(self, to_address, subject, body):
        if not self.configured or not to_address:
            return False
        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = to_address
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(self.host, self.port, timeout=10) as smtp:
            if self.starttls:
                smtp.starttls()
            if self.user:
                smtp.login(self.user, self.password)
            smtp.send_message(message)
        return True


class SmsChannel:
    """Interface only. Connect a real SMS gateway (e.g. an Indian DLT-registered
    provider) by implementing ``send``; until then it reports not configured."""

    configured = False

    def send(self, phone, body):  # pragma: no cover - intentionally not implemented
        return False


_email = None


def _email_channel():
    global _email
    if _email is None:
        _email = EmailChannel()
    return _email


# ==========================================================
# CREATE
# ==========================================================

def notify(user_id, event_type, title, message, request_id=None, dedupe_key=None):
    """Create one in-app notification. Never raises. Returns the new id or None."""

    if not user_id:
        return None

    try:
        connection = get_connection()
        try:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO notifications
                    (user_id, request_id, event_type, title, message, dedupe_key)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, request_id, event_type, title[:200], message[:1000], dedupe_key),
            )
            connection.commit()
            created = cursor.lastrowid if cursor.rowcount else None
        finally:
            connection.close()
    except Exception:  # noqa: BLE001 - notification failure must not break callers
        logger.exception("In-app notification failed (event=%s user=%s)", event_type, user_id)
        return None

    if created and event_type in EMAIL_EVENTS and _email_channel().configured:
        try:
            user = fetch_one("SELECT email FROM users WHERE id = ? AND is_active = 1", (user_id,))
            if user:
                _email_channel().send(user["email"], f"RSA: {title}", message)
        except Exception:  # noqa: BLE001
            logger.exception("E-mail delivery failed (event=%s user=%s)", event_type, user_id)

    return created


def notify_admins(event_type, title, message, request_id=None, dedupe_key=None):
    """Notify every active administrator."""

    try:
        admins = fetch_all("SELECT id FROM users WHERE role = 'admin' AND is_active = 1")
    except Exception:  # noqa: BLE001
        logger.exception("Could not load administrators for notification")
        return 0

    sent = 0
    for admin in admins:
        if notify(admin["id"], event_type, title, message, request_id,
                  f"{dedupe_key}" if dedupe_key else None):
            sent += 1
    return sent


# ==========================================================
# READ
# ==========================================================

def list_notifications(user_id, limit=50, unread_only=False):
    limit = max(1, min(int(limit or 50), 200))
    where = "WHERE user_id = ?" + (" AND is_read = 0" if unread_only else "")
    return [dict(row) for row in fetch_all(
        f"SELECT id, request_id, event_type, title, message, is_read, created_at "
        f"FROM notifications {where} ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    )]


def unread_count(user_id):
    try:
        row = fetch_one("SELECT COUNT(*) AS c FROM notifications WHERE user_id = ? AND is_read = 0", (user_id,))
        return row["c"] if row else 0
    except Exception:  # noqa: BLE001 - e.g. table missing before migration
        return 0


def mark_read(user_id, notification_ids=None):
    """Mark the user's notifications read (all when ids is None). Only the owner's rows change."""

    if notification_ids is None:
        execute_query("UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0", (user_id,))
        return True

    ids = [int(i) for i in notification_ids if str(i).isdigit()]
    if not ids:
        return False
    placeholders = ",".join("?" * len(ids))
    execute_query(
        f"UPDATE notifications SET is_read = 1 WHERE user_id = ? AND id IN ({placeholders})",
        (user_id, *ids),
    )
    return True


def channel_status():
    return {
        "in_app": True,
        "email": _email_channel().configured,
        "sms": SmsChannel.configured,
    }
