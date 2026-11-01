"""Neon PostgreSQL database layer for StudyBoost AI."""
from __future__ import annotations

import os
import threading
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
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
        url = st.secrets.get("DATABASE_URL")
    except (FileNotFoundError, KeyError):
        url = None
    url = url or os.environ.get("DATABASE_URL", "")
    if not isinstance(url, str) or not url.startswith(("postgresql://", "postgres://")):
        raise RuntimeError("Configure DATABASE_URL avec la chaîne PostgreSQL Neon dans les secrets Streamlit.")
    return url


class ManagedPool:
    """Bound wait time and validate idle connections before handing them out."""
    def __init__(self, url, maximum=10, wait_seconds=3):
        self.raw = psycopg2.pool.ThreadedConnectionPool(
            1, maximum, url, connect_timeout=10,
            options="-c statement_timeout=10000 -c lock_timeout=3000",
        )
        self.slots = threading.BoundedSemaphore(maximum)
        self.lock = threading.Lock()
        self.borrowed = set()
        self.wait_seconds = wait_seconds

    def getconn(self):
        if not self.slots.acquire(timeout=self.wait_seconds):
            raise RuntimeError("Database busy: retry later")
        try:
            for attempt in range(2):
                conn = self.raw.getconn()
                try:
                    with conn:
                        with conn.cursor() as cur:
                            cur.execute("SELECT 1")
                    with self.lock:
                        self.borrowed.add(id(conn))
                    return conn
                except (psycopg2.OperationalError, psycopg2.InterfaceError):
                    self.raw.putconn(conn, close=True)
                    if attempt:
                        raise
                except Exception:
                    self.raw.putconn(conn, close=True)
                    raise
        except BaseException:
            self.slots.release()
            raise

    def putconn(self, conn):
        with self.lock:
            if id(conn) not in self.borrowed:
                raise RuntimeError("Connection already released")
            self.borrowed.remove(id(conn))
        try:
            self.raw.putconn(conn, close=bool(conn.closed))
        finally:
            self.slots.release()


@st.cache_resource
def _get_pool():
    url = _get_db_url()
    parsed = urlsplit(url)
    query = dict(parse_qsl(parsed.query))
    query.setdefault("sslmode", "require")
    url = urlunsplit(parsed._replace(query=urlencode(query)))
    return ManagedPool(url)


def get_db():
    return _get_pool().getconn()


def release_db(conn):
    try:
        _get_pool().putconn(conn)
    except Exception as error:
        logger.error("Connection release failed type=%s", type(error).__name__)


def _fetchone(query: str, params: tuple | None = None) -> dict | None:
    conn = get_db()
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                row = cur.fetchone()
                return dict(row) if row else None
    finally:
        release_db(conn)


def _fetchall(query: str, params: tuple | None = None) -> list[dict]:
    conn = get_db()
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, params)
                return [dict(r) for r in cur.fetchall()]
    finally:
        release_db(conn)


def _execute(query: str, params: tuple | None = None) -> int:
    conn = get_db()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.rowcount
    finally:
        release_db(conn)


def check_database_health() -> bool:
    """Read-only schema/connection probe: never fetch user content."""
    conn = None
    try:
        conn = get_db()
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
                for query in (
                    "SELECT id, alias_emoji, alias_animal, alias_adjective, alias_number, alias_display, pdf_count, chat_count, search_count, ai_count, last_active, created_at, quota_date, draft_text, preferred_model FROM sessions LIMIT 0",
                    "SELECT session_id, role, content, created_at FROM chat_history LIMIT 0",
                    "SELECT key, value FROM admin_settings LIMIT 0",
                    "SELECT session_id, action_type, action_detail, created_at FROM activity_logs LIMIT 0",
                    "SELECT session_id, rating, comment, feature_request, other_idea, email, created_at FROM feedbacks LIMIT 0",
                ):
                    cur.execute(query)
        return True
    except Exception as error:
        logger.error("Database health check failed type=%s", type(error).__name__)
        return False
    finally:
        if conn is not None:
            release_db(conn)


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
    "quota_ai_global_per_day": "50",
    "quota_ai_global_per_minute": "20",
    "quota_ai_user_per_minute": "3",
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


def get_user_quotas(user_id: str, admin_bypass: bool = False) -> dict:
    settings = get_settings()
    try:
        row = _fetchone(
            "SELECT pdf_count, chat_count, search_count, ai_count, quota_date FROM sessions WHERE id=%s", (user_id,)
        )
        if not row:
            raise RuntimeError("Session missing")
        today = _quota_date_today()
        return {
            kind: {
                "used": int(row.get(kind + "_count") or 0) if row.get("quota_date") == today else 0,
                "limit": 9999 if admin_bypass else int(settings.get("quota_" + kind + "_per_day", default)),
            }
            for kind, default in (("pdf", 10), ("chat", 20), ("search", 10), ("ai", 15))
        }
    except Exception as error:
        logger.error("Quota display failed type=%s", type(error).__name__)
        return {**{kind: {"used": 0, "limit": 0} for kind in ("pdf", "chat", "search", "ai")}, "_fallback": True}


# ---------------------------------------------------------------------------
# Activity logging
# ---------------------------------------------------------------------------

def log_activity(user_id: str, action_type: str, detail: str = ""):
    try:
        _execute(
            "INSERT INTO activity_logs (session_id, action_type, action_detail, created_at) "
            "VALUES (%s, %s, %s, NOW())",
            (user_id, action_type, ""),
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
            (user_id, role, content[:15000]),
        )
    except Exception as e:
        logger.error("save_chat_message failed type=%s", type(e).__name__)
        st.error("Le message n'a pas été sauvegardé en base. La persistance est indisponible.")


def get_chat_history(user_id: str) -> list:
    try:
        return _fetchall(
            "SELECT role, content FROM (SELECT id, role, content, created_at FROM chat_history WHERE session_id = %s ORDER BY created_at DESC, id DESC LIMIT 100) recent ORDER BY created_at, id",
            (user_id,),
        )
    except Exception as e:
        logger.error("get_chat_history failed type=%s", type(e).__name__)
        st.error("Impossible de charger ton historique. Réessaie plus tard.")
        st.stop()


def clear_chat_history(user_id: str):
    try:
        _execute("DELETE FROM chat_history WHERE session_id = %s", (user_id,))
    except Exception as e:
        logger.warning("clear_chat_history: échec pour %s", user_id, exc_info=e)


# ---------------------------------------------------------------------------
# Draft persistence (éditeur)
# ---------------------------------------------------------------------------

def save_draft(user_id: str, text: str, model: str | None = None) -> bool:
    try:
        if model:
            changed = _execute(
                "UPDATE sessions SET draft_text=%s, preferred_model=%s, last_active=NOW() WHERE id=%s",
                (text[:15000], model, user_id),
            )
        else:
            changed = _execute(
                "UPDATE sessions SET draft_text=%s, last_active=NOW() WHERE id=%s",
                (text[:15000], user_id),
            )
        if changed != 1:
            raise RuntimeError("Session missing during draft save")
    except Exception as e:
        logger.warning("save_draft failed type=%s", type(e).__name__)
        st.error("Le brouillon n'a pas été sauvegardé en base. Réessaie avant de fermer cette page.")
        return False
    load_draft.clear()
    return True


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
        logger.warning("load_draft failed type=%s", type(e).__name__)
        st.error("Impossible de charger ton brouillon. Réessaie plus tard.")
        st.stop()
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

    try:
        _execute("DELETE FROM admin_settings WHERE key LIKE 'ai_usage:%%' AND key < %s", ("ai_usage:" + cutoff[:10],))
    except Exception as error:
        logger.warning("Quota history cleanup failed type=%s", type(error).__name__)

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
