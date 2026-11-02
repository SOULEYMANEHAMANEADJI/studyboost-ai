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
    maybe_cleanup_old_data()
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


def clear_chat_history(user_id: str) -> bool:
    try:
        _execute("DELETE FROM chat_history WHERE session_id = %s", (user_id,))
        return True
    except Exception as e:
        logger.warning("Chat deletion failed type=%s", type(e).__name__)
        st.error("La conversation n'a pas pu être effacée. Ton historique est conservé.")
        return False


# ---------------------------------------------------------------------------
# Draft persistence (éditeur)
# ---------------------------------------------------------------------------

@st.cache_resource
def ensure_draft_schema():
    # Additive and idempotent; never rewrites existing drafts.
    _execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS draft_title TEXT NOT NULL DEFAULT ''")


def save_draft(user_id: str, text: str, model: str | None = None, title: str | None = None) -> bool:
    try:
        ensure_draft_schema()
        changed = _execute(
            "UPDATE sessions SET draft_text=%s, preferred_model=COALESCE(%s,preferred_model), "
            "draft_title=COALESCE(%s,draft_title), last_active=NOW() WHERE id=%s",
            (text[:15000], model, title[:100] if title is not None else None, user_id),
        )
        if changed != 1:
            raise RuntimeError("Session missing during draft save")
    except Exception as error:
        logger.warning("Draft save failed type=%s", type(error).__name__)
        st.error("Le brouillon n'a pas été sauvegardé. Réessaie avant de fermer la page.")
        return False
    load_draft.clear()
    return True


@st.cache_data(ttl=5)
def load_draft(user_id: str) -> tuple:
    try:
        ensure_draft_schema()
        row = _fetchone(
            "SELECT draft_text, preferred_model, draft_title FROM sessions WHERE id = %s",
            (user_id,),
        )
        if row:
            return (row.get("draft_text") or "", row.get("preferred_model") or "", row.get("draft_title") or "")
    except Exception as e:
        logger.warning("load_draft failed type=%s", type(e).__name__)
        st.error("Impossible de charger ton brouillon. Réessaie plus tard.")
        st.stop()
    return ("", "", "")


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

def cleanup_old_data(force: bool = False) -> bool | None:
    """All deletions + success marker commit together; None means skipped."""
    conn = None
    try:
        conn = get_db()
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SELECT pg_try_advisory_xact_lock(%s) AS acquired", (735120432,))
                if not cur.fetchone()["acquired"]:
                    return None
                cur.execute("SELECT key,value FROM admin_settings WHERE key IN ('auto_cleanup_enabled','retention_days','last_cleanup')")
                settings = {r["key"]:r["value"] for r in cur.fetchall()}
                if not force and settings.get("auto_cleanup_enabled","true") != "true":
                    return None
                now = datetime.now(timezone.utc)
                if not force and settings.get("last_cleanup"):
                    try:
                        last = datetime.fromisoformat(settings["last_cleanup"].replace("Z","+00:00"))
                        if last.tzinfo is None: last = last.replace(tzinfo=timezone.utc)
                        if now - last < timedelta(hours=6): return None
                    except ValueError:
                        pass
                days = int(settings.get("retention_days","7"))
                if not 1 <= days <= 365: raise ValueError("Invalid retention")
                cutoff = now - timedelta(days=days)
                for table in ("chat_history","activity_logs","feedbacks"):
                    cur.execute(f"DELETE FROM {table} WHERE created_at < %s", (cutoff,))
                cur.execute("DELETE FROM sessions WHERE last_active < %s", (cutoff,))
                cur.execute("DELETE FROM admin_settings WHERE key LIKE 'ai_usage:%%' AND key < %s", ("ai_usage:"+cutoff.strftime("%Y-%m-%d"),))
                cur.execute("INSERT INTO admin_settings (key,value) VALUES ('last_cleanup',%s) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value", (now.isoformat(),))
        logger.info("Retention cleanup completed")
        return True
    except Exception as error:
        logger.error("Retention cleanup failed type=%s",type(error).__name__)
        return False
    finally:
        if conn is not None: release_db(conn)


@st.cache_data(ttl=300, show_spinner=False)
def maybe_cleanup_old_data():
    # Every page loads settings; no dependency on visiting the home page.
    return cleanup_old_data()


def admin_get_stats(days: int = 7) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=max(1,min(int(days),365)))
    stats = {"total_sessions":0,"actions_period":0,"feedbacks":0,"average_rating":0.0,
             "email_count":0,"emails_collected":[],"actions_by_day":{},"active_users_by_day":{},
             "actions_by_type":{},"recent_actions":[],"feedbacks_list":[],
             "rating_distribution":{i:0 for i in range(1,6)},"feature_requests":{},"oldest_data":None,"load_failed":False}
    try:
        row = _fetchone("SELECT COUNT(*) AS cnt FROM sessions")
        stats["total_sessions"] = row["cnt"]
        rows = _fetchall("SELECT to_char(created_at AT TIME ZONE 'UTC','YYYY-MM-DD') AS day, COUNT(*) AS cnt, COUNT(DISTINCT session_id) AS active FROM activity_logs WHERE created_at >= %s GROUP BY day ORDER BY day", (since,))
        for row in rows:
            stats["actions_by_day"][row["day"]] = row["cnt"]
            stats["active_users_by_day"][row["day"]] = row["active"]
        stats["actions_period"] = sum(stats["actions_by_day"].values())
        rows = _fetchall("SELECT action_type, COUNT(*) AS cnt FROM activity_logs WHERE created_at >= %s GROUP BY action_type", (since,))
        stats["actions_by_type"] = {r["action_type"]:r["cnt"] for r in rows}
        stats["recent_actions"] = _fetchall("SELECT session_id,action_type,action_detail,created_at FROM activity_logs WHERE created_at >= %s ORDER BY created_at DESC,id DESC LIMIT 30", (since,))
        row = _fetchone("SELECT COUNT(*) AS cnt, AVG(rating) FILTER (WHERE rating BETWEEN 1 AND 5) AS avg_rating, COUNT(*) FILTER (WHERE email IS NOT NULL AND email <> '') AS emails FROM feedbacks WHERE created_at >= %s", (since,))
        stats.update(feedbacks=row["cnt"],average_rating=round(float(row["avg_rating"] or 0),2),email_count=row["emails"])
        rows = _fetchall("SELECT rating,COUNT(*) AS cnt FROM feedbacks WHERE created_at >= %s AND rating BETWEEN 1 AND 5 GROUP BY rating", (since,))
        stats["rating_distribution"].update({r["rating"]:r["cnt"] for r in rows})
        stats["feedbacks_list"] = _fetchall("SELECT * FROM feedbacks WHERE created_at >= %s ORDER BY created_at DESC,id DESC LIMIT 100", (since,))
        stats["emails_collected"] = _fetchall("SELECT email,created_at,rating FROM feedbacks WHERE created_at >= %s AND email IS NOT NULL AND email <> '' ORDER BY created_at DESC,id DESC LIMIT 100", (since,))
        rows = _fetchall("SELECT trim(feature) AS feature,COUNT(*) AS cnt FROM feedbacks CROSS JOIN LATERAL unnest(string_to_array(feature_request,',')) AS requested(feature) WHERE created_at >= %s AND trim(feature) <> '' GROUP BY trim(feature)", (since,))
        stats["feature_requests"] = {r["feature"]:r["cnt"] for r in rows}
    except Exception as error:
        logger.error("Admin statistics failed type=%s",type(error).__name__)
        stats["load_failed"] = True
    return stats
