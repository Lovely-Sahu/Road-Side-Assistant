"""
RSA Administrator - Audit Log
-----------------------------

Records administrative and security-relevant actions with actor, action,
affected resource, timestamp and metadata. Secrets are never stored: any
metadata key that looks like a credential is dropped before writing.
"""

import json
import logging

from database.database import execute_query, fetch_all


logger = logging.getLogger("rsa.audit")

_SECRET_MARKERS = ("password", "passwd", "secret", "token", "hash", "csrf", "key")


def _clean(metadata):
    if not isinstance(metadata, dict):
        return {}
    cleaned = {}
    for key, value in metadata.items():
        if any(marker in str(key).lower() for marker in _SECRET_MARKERS):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            cleaned[str(key)] = value if not isinstance(value, str) else value[:500]
        else:
            cleaned[str(key)] = str(value)[:500]
    return cleaned


def log_action(actor_user_id, action, resource_type=None, resource_id=None, metadata=None, ip_address=None):
    """Write one audit entry. Never raises (an audit failure is logged instead)."""

    try:
        execute_query(
            """
            INSERT INTO audit_log (actor_user_id, action, resource_type, resource_id, metadata, ip_address)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (actor_user_id, action, resource_type, resource_id,
             json.dumps(_clean(metadata or {})), (ip_address or "")[:64] or None),
        )
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Audit log write failed: %s %s %s", action, resource_type, resource_id)
        return False


def recent_actions(limit=100, action=None):
    limit = max(1, min(int(limit or 100), 500))
    params = []
    where = ""
    if action:
        where = "WHERE a.action = ?"
        params.append(action)
    rows = fetch_all(
        f"""
        SELECT a.id, a.action, a.resource_type, a.resource_id, a.metadata, a.ip_address, a.created_at,
               u.name AS actor_name, u.email AS actor_email
        FROM audit_log a
        LEFT JOIN users u ON u.id = a.actor_user_id
        {where}
        ORDER BY a.id DESC
        LIMIT ?
        """,
        (*params, limit),
    )
    output = []
    for row in rows:
        item = dict(row)
        try:
            item["metadata"] = json.loads(item["metadata"] or "{}")
        except (TypeError, ValueError):
            item["metadata"] = {}
        output.append(item)
    return output
