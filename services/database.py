"""Neon PostgreSQL database layer for StudyBoost AI."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import psycopg2
import psycopg2.extras
import psycopg2.pool
from dotenv import load_dotenv
import streamlit as st

from services.logger import get_logger

logger = get_logger("database")

load_dotenv()


def _get_db_url() -> str:
    try:
        url = st.secrets.get("DATABASE_URL") or st.secrets.get("SUPABASE_URL")
    except Exception as e:
        logger.warning("_get_db_url: fallback secrets→os.environ", exc_info=e)
        url = None
    if not url:
        url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL is missing in secrets and environment.")
    return url


@st.cache_resource
def _get_pool():
    url = _get_db_url()
    return psycopg2.pool.ThreadedConnectionPool(1, 10, url, connect_timeout=15)


def get_db():
    pool = _get_pool()
    return pool.getconn()


def release_db(conn):
    try:
        _get_pool().putconn(conn)
    except Exception:
        pass


def _fetchone(query: str, params: tuple | None = None) -> dict | None:
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        pool.putconn(conn)


def _fetchall(query: str, params: tuple | None = None) -> list[dict]:
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
    finally:
        pool.putconn(conn)


def _execute(query: str, params: tuple | None = None) -> None:
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
        conn.commit()
    finally:
        pool.putconn(conn)


# ---------------------------------------------------------------------------
# Settings (cache 60s)
# ---------------------------------------------------------------------------

DEFAULT_SETTINGS = {
    "feature_chat_enabled": "true",
    "feature_search_enabled": "true",
    "feature_pdf_enabled": "true",
    "feature_md_enabled": "true",
    "auto_cleanup_enabled": "true",
    "maintenance_mode": "false",
    "quota_pdf_per_day": "10",
    "quota_chat_per_day": "20",
    "quota_search_per_day": "10",
    "quota_ai_per_day": "15",
    "global_message": "",
    "retention_days": "7",
}


@st.cache_data(ttl=60)
def get_settings() -> dict:
    try:
        rows = _fetchall("SELECT key, value FROM admin_settings")
        settings = {r["key"]: r["value"] for r in rows}
    except Exception as e:
        logger.error("get_settings: échec chargement depuis Neon", exc_info=e)
        settings = {}

    for key, val in DEFAULT_SETTINGS.items():
        if key not in settings:
            settings[key] = val
            try:
                _execute(
                    "INSERT INTO admin_settings (key, value) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (key, val),
                )
            except Exception as e:
                logger.warning("get_settings: échec insertion default %s", key, exc_info=e)
    return settings


def update_setting(key: str, value: str | int | bool) -> bool:
    s = str(value).lower() if isinstance(value, bool) else str(value)
    try:
        _execute(
            "INSERT INTO admin_settings (key, value) VALUES (%s, %s) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            (key, s),
        )
        get_settings.clear()
        return True
    except Exception as e:
        logger.error("update_setting(%s): échec", key, exc_info=e)
        st.error("Erreur lors de la mise à jour des paramètres.")
        return False


# ---------------------------------------------------------------------------
# Quotas
# ---------------------------------------------------------------------------

def _quota_date_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _maybe_reset_quotas(user_id: str) -> bool:
    today = _quota_date_today()
    try:
        row = _fetchone(
            "SELECT quota_date FROM sessions WHERE id = %s", (user_id,)
        )
        if row and row.get("quota_date") != today:
            _execute(
                "UPDATE sessions SET pdf_count=0, chat_count=0, search_count=0, "
                "ai_count=0, quota_date=%s, last_active=NOW() WHERE id=%s",
                (today, user_id),
            )
            return True
    except Exception as e:
        logger.warning("_maybe_reset_quotas: échec pour %s", user_id, exc_info=e)
    return False


def get_user_quotas(user_id: str, admin_bypass: bool = False) -> dict:
    if admin_bypass:
        return {
            "pdf": {"used": 0, "limit": 9999},
            "chat": {"used": 0, "limit": 9999},
            "search": {"used": 0, "limit": 9999},
            "ai": {"used": 0, "limit": 9999},
        }

    _fallback = {
        "pdf": {"used": 0, "limit": 2},
        "chat": {"used": 0, "limit": 3},
        "search": {"used": 0, "limit": 1},
        "ai": {"used": 0, "limit": 2},
        "_fallback": True,
    }

    settings = get_settings()
    _maybe_reset_quotas(user_id)

    try:
        row = _fetchone(
            "SELECT pdf_count, chat_count, search_count, ai_count FROM sessions WHERE id = %s",
            (user_id,),
        )
    except Exception as e:
        logger.error("get_user_quotas: échec pour %s — fallback actif", user_id, exc_info=e)
        return _fallback

    if not row:
        return _fallback

    return {
        "pdf": {
            "used": row.get("pdf_count", 0) or 0,
            "limit": int(settings.get("quota_pdf_per_day", 10)),
        },
        "chat": {
            "used": row.get("chat_count", 0) or 0,
            "limit": int(settings.get("quota_chat_per_day", 20)),
        },
        "search": {
            "used": row.get("search_count", 0) or 0,
            "limit": int(settings.get("quota_search_per_day", 10)),
        },
        "ai": {
            "used": row.get("ai_count", 0) or 0,
            "limit": int(settings.get("quota_ai_per_day", 15)),
        },
    }


def increment_quota(user_id: str, quota_type: str):
    col = f"{quota_type}_count"
    today = _quota_date_today()

    try:
        _execute(
            f"UPDATE sessions SET {col} = COALESCE({col}, 0) + 1, "
            "quota_date = %s, last_active = NOW() WHERE id = %s",
            (today, user_id),
        )
    except Exception as e:
        logger.error("increment_quota: échec pour %s/%s", user_id, quota_type, exc_info=e)


# ---------------------------------------------------------------------------
# Activity logging
# ---------------------------------------------------------------------------

def log_activity(user_id: str, action_type: str, detail: str = ""):
    try:
        _execute(
            "INSERT INTO activity_logs (session_id, action_type, action_detail, created_at) "
            "VALUES (%s, %s, %s, NOW())",
            (user_id, action_type, detail[:500]),
        )
    except Exception as e:
        logger.warning("log_activity: échec pour %s / %s", user_id, action_type, exc_info=e)


# ---------------------------------------------------------------------------
# Chat history
# ---------------------------------------------------------------------------

def save_chat_message(user_id: str, role: str, content: str):
    try:
        _execute(
            "INSERT INTO chat_history (session_id, role, content, created_at) "
            "VALUES (%s, %s, %s, NOW())",
            (user_id, role, content[:5000]),
        )
    except Exception as e:
        logger.error("save_chat_message: échec pour %s", user_id, exc_info=e)


def get_chat_history(user_id: str) -> list:
    try:
        return _fetchall(
            "SELECT role, content FROM chat_history WHERE session_id = %s ORDER BY created_at",
            (user_id,),
        )
    except Exception as e:
        logger.error("get_chat_history: échec pour %s", user_id, exc_info=e)
        return []


def clear_chat_history(user_id: str):
    try:
        _execute("DELETE FROM chat_history WHERE session_id = %s", (user_id,))
    except Exception as e:
        logger.warning("clear_chat_history: échec pour %s", user_id, exc_info=e)


# ---------------------------------------------------------------------------
# Draft persistence (éditeur)
# ---------------------------------------------------------------------------

def save_draft(user_id: str, text: str, model: str | None = None):
    try:
        if model:
            _execute(
                "UPDATE sessions SET draft_text=%s, preferred_model=%s, last_active=NOW() WHERE id=%s",
                (text[:15000], model, user_id),
            )
        else:
            _execute(
                "UPDATE sessions SET draft_text=%s, last_active=NOW() WHERE id=%s",
                (text[:15000], user_id),
            )
    except Exception as e:
        logger.warning("save_draft: échec pour %s", user_id, exc_info=e)
    load_draft.clear()


@st.cache_data(ttl=5)
def load_draft(user_id: str) -> tuple:
    try:
        row = _fetchone(
            "SELECT draft_text, preferred_model FROM sessions WHERE id = %s",
            (user_id,),
        )
        if row:
            return (row.get("draft_text") or "", row.get("preferred_model") or "")
    except Exception as e:
        logger.warning("load_draft: échec pour %s", user_id, exc_info=e)
    return ("", "")


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

def save_feedback(user_id: str, rating: int, comment: str, feature_request: str, other_idea: str, email: str) -> bool:
    try:
        _execute(
            "INSERT INTO feedbacks (session_id, rating, comment, feature_request, "
            "other_idea, email, created_at) VALUES (%s, %s, %s, %s, %s, %s, NOW())",
            (user_id, rating, comment[:2000], feature_request[:500], other_idea[:500], email[:255] if email else None),
        )
        log_activity(user_id, "feedback", f"rating={rating}")
        return True
    except Exception as e:
        logger.error("save_feedback: échec pour %s", user_id, exc_info=e)
        st.error("Une erreur est survenue lors de l'envoi de ton avis. Réessaie plus tard.")
        return False


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def cleanup_old_data(force: bool = False):
    settings = get_settings()
    if settings.get("auto_cleanup_enabled", "true") != "true":
        return

    days = int(settings.get("retention_days", "7"))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    logger.info("cleanup_old_data: suppression données antérieures à %d jours (%s)", days, cutoff)

    for table in ("chat_history", "activity_logs", "feedbacks"):
        try:
            _execute(f"DELETE FROM {table} WHERE created_at < %s", (cutoff,))
        except Exception as e:
            logger.warning("cleanup_old_data: échec nettoyage %s", table, exc_info=e)

    try:
        _execute("DELETE FROM sessions WHERE last_active < %s", (cutoff,))
    except Exception as e:
        logger.warning("cleanup_old_data: échec nettoyage sessions", exc_info=e)

    if force:
        try:
            _execute(
                "INSERT INTO admin_settings (key, value) VALUES ('last_cleanup', %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                (datetime.now(timezone.utc).isoformat(),),
            )
        except Exception as e:
            logger.warning("cleanup_old_data: échec enregistrement last_cleanup", exc_info=e)


# ---------------------------------------------------------------------------
# Admin stats
# ---------------------------------------------------------------------------

def admin_get_stats(days: int = 7) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    stats = {
        "total_sessions": 0,
        "actions_period": 0,
        "feedbacks": 0,
        "average_rating": 0.0,
        "emails_collected": [],
        "actions_by_day": {},
        "active_users_by_day": {},
        "actions_by_type": {},
        "recent_actions": [],
        "feedbacks_list": [],
        "rating_distribution": {i: 0 for i in range(1, 6)},
        "feature_requests": {},
        "oldest_data": None,
    }

    try:
        row = _fetchone("SELECT count(*) AS cnt FROM sessions")
        stats["total_sessions"] = row["cnt"] if row else 0
    except Exception as e:
        logger.error("admin_get_stats: échec sessions count", exc_info=e)

    actions = []
    try:
        actions = _fetchall(
            "SELECT action_type, action_detail, created_at, session_id "
            "FROM activity_logs WHERE created_at >= %s ORDER BY created_at DESC",
            (since,),
        )
        stats["actions_period"] = len(actions)
        stats["recent_actions"] = actions[:30]
    except Exception as e:
        logger.error("admin_get_stats: échec activity_logs", exc_info=e)

    for a in actions:
        created = a.get("created_at")
        day = created.strftime("%Y-%m-%d") if created else ""
        if day:
            stats["actions_by_day"][day] = stats["actions_by_day"].get(day, 0) + 1
            stats["active_users_by_day"].setdefault(day, set()).add(a.get("session_id", ""))
            t = a.get("action_type", "unknown")
            stats["actions_by_type"][t] = stats["actions_by_type"].get(t, 0) + 1

    for d, u in stats["active_users_by_day"].items():
        stats["active_users_by_day"][d] = len(u)

    try:
        fbs = _fetchall("SELECT * FROM feedbacks ORDER BY created_at DESC LIMIT 500")
        stats["feedbacks"] = len(fbs)
        stats["feedbacks_list"] = fbs
        ratings = [f["rating"] for f in fbs if f.get("rating")]
        if ratings:
            stats["average_rating"] = round(sum(ratings) / len(ratings), 2)
        for rv in ratings:
            if 1 <= rv <= 5:
                stats["rating_distribution"][rv] += 1
        stats["emails_collected"] = [
            {"email": f.get("email"), "created_at": f.get("created_at"), "rating": f.get("rating")}
            for f in fbs if f.get("email")
        ]
        for f in fbs:
            req = (f.get("feature_request") or "").strip()
            for feat in req.split(","):
                feat = feat.strip()
                if feat:
                    stats["feature_requests"][feat] = stats["feature_requests"].get(feat, 0) + 1
    except Exception as e:
        logger.error("admin_get_stats: échec feedbacks", exc_info=e)

    return stats
