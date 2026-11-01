"""Atomic quota reservations. Failed provider attempts still consume a reservation."""
from __future__ import annotations

import json
from datetime import datetime, timezone

# Serializes the short reservation transaction, never the external AI request.
RESERVATION_LOCK = 735120431
COLUMNS = {"pdf": "pdf_count", "chat": "chat_count", "search": "search_count", "ai": "ai_count"}
DEFAULTS = {"pdf": 10, "chat": 20, "search": 10, "ai": 15}


class QuotaError(RuntimeError):
    pass


def _limit(settings, key, default):
    try:
        value = int(settings.get(key, default))
        if value < 0:
            raise ValueError()
        return value
    except (ValueError, TypeError):
        raise QuotaError("Configuration des quotas invalide. Contacte l'administrateur.") from None


def reserve_quota(user_id: str, kind: str, model: str | None = None, admin_bypass: bool = False):
    """Check and consume user + shared budgets in a single committed transaction.

    Uses the existing admin_settings table; no DDL or schema migration is needed.
    Shared AI ceilings apply even to admins and survive identity rotations/restarts.
    """
    from services.database import get_db, release_db
    import psycopg2.extras

    if kind not in COLUMNS or (kind in ("chat", "ai") and not model):
        raise ValueError("Unsupported quota reservation")
    conn = None
    try:
        conn = get_db()
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT pg_advisory_xact_lock(%s)", (RESERVATION_LOCK,))
                cur.execute("SELECT key, value FROM admin_settings")
                settings = {row["key"]: row["value"] for row in cur.fetchall()}
                if settings.get("maintenance_mode", "false") == "true":
                    raise QuotaError("L'application est en maintenance. Réessaie plus tard.")
                flag = {"chat":"feature_chat_enabled", "search":"feature_search_enabled", "pdf":"feature_pdf_enabled"}.get(kind)
                if flag and settings.get(flag, "true") != "true":
                    raise QuotaError("Cette fonctionnalité est temporairement désactivée.")
                if model and settings.get(f"model_enabled_{model}", "true") != "true":
                    raise QuotaError("Ce modèle a été désactivé. Choisis un autre modèle.")
                cur.execute("SELECT pdf_count, chat_count, search_count, ai_count, quota_date FROM sessions WHERE id=%s FOR UPDATE", (user_id,))
                row = cur.fetchone()
                if not row:
                    raise QuotaError("Ton espace a expiré. Recharge la page avant de continuer.")
                now = datetime.now(timezone.utc)
                today = now.strftime("%Y-%m-%d")
                counts = {name: (int(row.get(column) or 0) if row.get("quota_date") == today else 0) for name, column in COLUMNS.items()}
                if not admin_bypass and counts[kind] >= _limit(settings, f"quota_{kind}_per_day", DEFAULTS[kind]):
                    raise QuotaError("Quota journalier atteint pour cette action. Reviens demain.")
                if kind in ("chat", "ai"):
                    key = "ai_usage:" + today
                    cur.execute("SELECT value FROM admin_settings WHERE key=%s", (key,))
                    saved = cur.fetchone()
                    usage = json.loads(saved["value"]) if saved else {}
                    minute = now.strftime("%H:%M")
                    total = int(usage.get("total", 0))
                    if total >= _limit(settings, "quota_ai_global_per_day", 50):
                        raise QuotaError("Le budget IA partagé de l'application est épuisé pour aujourd'hui. Tes documents restent accessibles.")
                    minute_count = int(usage.get("minute_count", 0)) if usage.get("minute") == minute else 0
                    if minute_count >= _limit(settings, "quota_ai_global_per_minute", 20):
                        raise QuotaError("L'IA reçoit trop de demandes. Réessaie dans une minute.")
                    users = usage.get("users", {})
                    own = users.get(user_id, {})
                    own_count = int(own.get("count", 0)) if own.get("minute") == minute else 0
                    if own_count >= _limit(settings, "quota_ai_user_per_minute", 3):
                        raise QuotaError("Tu as envoyé plusieurs demandes rapidement. Réessaie dans une minute.")
                    models = usage.get("models", {})
                    owner_model = user_id + ":" + model
                    model_count = int(models.get(owner_model, 0))
                    if not admin_bypass and model_count >= _limit(settings, f"model_quota_{model}", 20):
                        raise QuotaError("Ton quota journalier pour ce modèle est atteint. Choisis un autre modèle.")
                    users[user_id] = {"minute": minute, "count": own_count + 1}
                    models[owner_model] = model_count + 1
                    usage = {"total": total + 1, "minute": minute, "minute_count": minute_count + 1, "users": users, "models": models}
                    cur.execute("INSERT INTO admin_settings (key,value) VALUES (%s,%s) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value", (key, json.dumps(usage)))
                counts[kind] += 1
                cur.execute("UPDATE sessions SET pdf_count=%s, chat_count=%s, search_count=%s, ai_count=%s, quota_date=%s, last_active=NOW() WHERE id=%s", (counts["pdf"], counts["chat"], counts["search"], counts["ai"], today, user_id))
    except QuotaError:
        raise
    except Exception as error:
        from services.logger import get_logger
        get_logger("quotas").error("Quota reservation failed type=%s", type(error).__name__)
        raise QuotaError("Impossible de vérifier les quotas en base. Réessaie plus tard ; aucune demande IA n'a été envoyée.") from None
    finally:
        if conn is not None:
            release_db(conn)
