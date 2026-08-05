"""Supabase database layer with caching for StudyBoost AI."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
import streamlit as st
from supabase import Client, create_client

from services.logger import get_logger

logger = get_logger("database")

load_dotenv()


def _get_creds() -> dict:
    try:
        return {"url": st.secrets["SUPABASE_URL"], "key": st.secrets["SUPABASE_ANON_KEY"]}
    except Exception as e:
        logger.warning("_get_creds: fallback secrets→os.environ", exc_info=e)
        return {
            "url": os.environ.get("SUPABASE_URL", ""),
            "key": os.environ.get("SUPABASE_ANON_KEY", ""),
        }


@st.cache_resource
def get_db() -> Client:
    creds = _get_creds()
    if not creds["url"] or not creds["key"]:
        raise RuntimeError("Supabase credentials are missing.")
    try:
        from supabase import ClientOptions
        opts = ClientOptions(postgrest_client_timeout=30)
        return create_client(creds["url"], creds["key"], options=opts)
    except (ImportError, TypeError):
        return create_client(creds["url"], creds["key"])


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
    db = get_db()
    try:
        result = db.table("admin_settings").select("key, value").execute()
        rows = result.data or []
        settings = {row["key"]: row["value"] for row in rows}
    except Exception as e:
        logger.error("get_settings: échec chargement settings depuis Supabase", exc_info=e)
        settings = {}

    for key, val in DEFAULT_SETTINGS.items():
        if key not in settings:
            settings[key] = val
            try:
                db.table("admin_settings").insert({"key": key, "value": val}).execute()
            except Exception as e:
                logger.warning("get_settings: échec insertion setting %s", key, exc_info=e)
    return settings


def update_setting(key: str, value: str | int | bool) -> bool:
    db = get_db()
    s = str(value).lower() if isinstance(value, bool) else str(value)
    try:
        existing = db.table("admin_settings").select("key").eq("key", key).execute()
        if existing.data:
            db.table("admin_settings").update({"value": s}).eq("key", key).execute()
        else:
            db.table("admin_settings").insert({"key": key, "value": s}).execute()
        get_settings.clear()
        return True
    except Exception as e:
        logger.error("update_setting(%s): échec", key, exc_info=e)
        st.error("Erreur lors de la mise à jour des paramètres.")
        return False


# ---------------------------------------------------------------------------
# Quotas (cache 30s)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def _table() -> str:
    """Return sessions table name if it exists, else anonymous_sessions."""
    db = get_db()
    try:
        db.table("sessions").select("id").limit(1).execute()
        return "sessions"
    except Exception as e:
        logger.warning("_table(): sessions introuvable, fallback anonymous_sessions", exc_info=e)
        return "anonymous_sessions"


def get_user_quotas(user_id: str, admin_bypass: bool = False) -> dict | None:
    db = get_db()
    settings = get_settings()
    tbl = _table()

    if admin_bypass:
        return {
            "pdf": {"used": 0, "limit": 9999},
            "chat": {"used": 0, "limit": 9999},
            "search": {"used": 0, "limit": 9999},
            "ai": {"used": 0, "limit": 9999},
        }

    _maybe_reset_quotas(user_id, tbl)

    try:
        result = (
            db.table(tbl)
            .select("pdf_count, chat_count, search_count, ai_count")
            .eq("id", user_id)
            .execute()
        )
    except Exception as e:
        logger.error("get_user_quotas: échec récupération quotas pour %s", user_id, exc_info=e)
        return None

    if not result.data:
        return None

    usage = result.data[0]
    return {
        "pdf": {
            "used": usage.get("pdf_count", 0) or 0,
            "limit": int(settings.get("quota_pdf_per_day", 10)),
        },
        "chat": {
            "used": usage.get("chat_count", 0) or 0,
            "limit": int(settings.get("quota_chat_per_day", 20)),
        },
        "search": {
            "used": usage.get("search_count", 0) or 0,
            "limit": int(settings.get("quota_search_per_day", 10)),
        },
        "ai": {
            "used": usage.get("ai_count", 0) or 0,
            "limit": int(settings.get("quota_ai_per_day", 15)),
        },
    }


def _quota_date_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _maybe_reset_quotas(user_id: str, tbl: str):
    """Reset quota counters if quota_date != today."""
    db = get_db()
    today = _quota_date_today()
    try:
        row = db.table(tbl).select("quota_date, last_active").eq("id", user_id).execute()
        if row.data:
            stored = row.data[0].get("quota_date") or ""
            if stored != today:
                db.table(tbl).update({
                    "pdf_count": 0, "chat_count": 0,
                    "search_count": 0, "ai_count": 0,
                    "quota_date": today,
                    "last_active": datetime.now(timezone.utc).isoformat(),
                }).eq("id", user_id).execute()
                return True
    except Exception as e:
        logger.warning("_maybe_reset_quotas: échec pour %s", user_id, exc_info=e)
    return False


def increment_quota(user_id: str, quota_type: str):
    db = get_db()
    tbl = _table()
    col = f"{quota_type}_count"

    try:
        result = db.table(tbl).select(col).eq("id", user_id).execute()
        current = (result.data or [{}])[0].get(col, 0) or 0

        db.table(tbl).update({
            col: current + 1,
            "quota_date": _quota_date_today(),
            "last_active": datetime.now(timezone.utc).isoformat(),
        }).eq("id", user_id).execute()
    except Exception as e:
        logger.error("increment_quota: échec pour %s/%s", user_id, quota_type, exc_info=e)


# ---------------------------------------------------------------------------
# Activity logging
# ---------------------------------------------------------------------------

def log_activity(user_id: str, action_type: str, detail: str = ""):
    db = get_db()
    try:
        db.table("activity_logs").insert({
            "session_id": user_id,
            "action_type": action_type,
            "action_detail": detail[:500],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        logger.warning("log_activity: échec pour %s / %s", user_id, action_type, exc_info=e)


# ---------------------------------------------------------------------------
# Chat history
# ---------------------------------------------------------------------------

def save_chat_message(user_id: str, role: str, content: str):
    db = get_db()
    try:
        db.table("chat_history").insert({
            "session_id": user_id,
            "role": role,
            "content": content[:5000],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
        logger.info("Saved chat message for %s, role=%s, %d chars", user_id, role, len(content))
    except Exception as e:
        logger.error("save_chat_message: échec pour session %s", user_id, exc_info=e)


def get_chat_history(user_id: str) -> list:
    db = get_db()
    try:
        result = (
            db.table("chat_history")
            .select("role, content")
            .eq("session_id", user_id)
            .order("created_at")
            .execute()
        )
        msgs = result.data or []
        logger.info("Fetched %d chat messages for %s", len(msgs), user_id)
        return msgs
    except Exception as e:
        logger.error("get_chat_history: échec pour session %s", user_id, exc_info=e)
        return []


def clear_chat_history(user_id: str):
    db = get_db()
    try:
        db.table("chat_history").delete().eq("session_id", user_id).execute()
    except Exception as e:
        logger.warning("clear_chat_history: échec pour session %s", user_id, exc_info=e)


# ---------------------------------------------------------------------------
# Draft persistence (éditeur)
# ---------------------------------------------------------------------------

def save_draft(user_id: str, text: str, model: str | None = None):
    db = get_db()
    tbl = _table()
    update = {"draft_text": text[:15000], "last_active": datetime.now(timezone.utc).isoformat()}
    if model:
        update["preferred_model"] = model
    try:
        db.table(tbl).update(update).eq("id", user_id).execute()
        logger.info("Saved draft for %s, %d chars, model=%s", user_id, len(text), model or "none")
    except Exception as e:
        logger.warning("save_draft: échec pour %s", user_id, exc_info=e)
    load_draft.clear()


@st.cache_data(ttl=5)
def load_draft(user_id: str) -> tuple:
    db = get_db()
    tbl = _table()
    try:
        row = db.table(tbl).select("draft_text, preferred_model").eq("id", user_id).execute()
        if row.data:
            r = row.data[0]
            txt = r.get("draft_text") or ""
            mod = r.get("preferred_model") or ""
            logger.info("Loaded draft for %s, %d chars", user_id, len(txt))
            return (txt, mod)
    except Exception as e:
        logger.warning("load_draft: échec pour %s", user_id, exc_info=e)
    return ("", "")


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

def save_feedback(user_id: str, rating: int, comment: str, feature_request: str, other_idea: str, email: str) -> bool:
    db = get_db()
    try:
        db.table("feedbacks").insert({
            "session_id": user_id,
            "rating": rating,
            "comment": comment[:2000],
            "feature_request": feature_request[:500],
            "other_idea": other_idea[:500],
            "email": email[:255] if email else None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
        log_activity(user_id, "feedback", f"rating={rating}")
        return True
    except Exception as e:
        logger.error("save_feedback: échec enregistrement pour session %s", user_id, exc_info=e)
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
    db = get_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    logger.info("cleanup_old_data: suppression données antérieures à %d jours (%s)", days, cutoff)

    try:
        db.table("chat_history").delete().lt("created_at", cutoff).execute()
    except Exception as e:
        logger.warning("cleanup_old_data: échec nettoyage chat_history", exc_info=e)

    try:
        db.table("activity_logs").delete().lt("created_at", cutoff).execute()
    except Exception as e:
        logger.warning("cleanup_old_data: échec nettoyage activity_logs", exc_info=e)

    try:
        db.table("feedbacks").delete().lt("created_at", cutoff).execute()
    except Exception as e:
        logger.warning("cleanup_old_data: échec nettoyage feedbacks", exc_info=e)

    try:
        db.table("sessions").delete().lt("last_active", cutoff).execute()
    except Exception as e:
        logger.warning("cleanup_old_data: échec nettoyage sessions", exc_info=e)

    if force:
        try:
            db.table("admin_settings").upsert({"key": "last_cleanup", "value": datetime.now(timezone.utc).isoformat()}).execute()
        except Exception as e:
            logger.warning("cleanup_old_data: échec enregistrement last_cleanup", exc_info=e)


# ---------------------------------------------------------------------------
# Admin stats
# ---------------------------------------------------------------------------

def admin_get_stats(days: int = 7) -> dict:
    db = get_db()
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
        r = (
            db.table("sessions")
            .select("id", count="exact")
            .execute()
        )
        stats["total_sessions"] = r.count or 0
    except Exception as e:
        logger.error("admin_get_stats: échec sessions count", exc_info=e)

    try:
        r = (
            db.table("activity_logs")
            .select("action_type,action_detail,created_at,session_id")
            .gte("created_at", since)
            .order("created_at", desc=True)
            .execute()
        )
        actions = r.data or []
        stats["actions_period"] = len(actions)
        stats["recent_actions"] = actions[:30]
    except Exception as e:
        logger.error("admin_get_stats: échec activity_logs", exc_info=e)
        actions = []

    for a in actions:
        day = (a.get("created_at") or "")[:10]
        if day:
            stats["actions_by_day"][day] = stats["actions_by_day"].get(day, 0) + 1
            stats["active_users_by_day"].setdefault(day, set()).add(a.get("session_id", ""))
            t = a.get("action_type", "unknown")
            stats["actions_by_type"][t] = stats["actions_by_type"].get(t, 0) + 1

    for d, u in stats["active_users_by_day"].items():
        stats["active_users_by_day"][d] = len(u)

    try:
        r = db.table("feedbacks").select("*").execute()
        fbs = r.data or []
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



