"""Supabase database interactions for StudyBoost AI."""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
import streamlit as st
from supabase import Client, create_client

load_dotenv()


DEFAULT_SETTINGS = {
    "feature_chat_enabled": "true",
    "feature_search_enabled": "true",
    "feature_pdf_enabled": "true",
    "feature_md_enabled": "true",
    "auto_cleanup_enabled": "true",
    "maintenance_mode": "false",
    "quota_pdf_per_day": "10",
    "quota_chat_per_day": "15",
    "quota_search_per_day": "15",
    "global_message": "",
}

# Per-model flags and quotas — populated lazily in get_settings()
_MODEL_SETTINGS_KEYS: list[str] | None = None


def _get_model_setting_keys() -> list[str]:
    global _MODEL_SETTINGS_KEYS
    if _MODEL_SETTINGS_KEYS is None:
        from services.ai import AVAILABLE_MODELS

        keys = []
        for mid in AVAILABLE_MODELS.values():
            keys.append(f"model_enabled_{mid}")
            keys.append(f"model_quota_{mid}")
        _MODEL_SETTINGS_KEYS = keys
    return _MODEL_SETTINGS_KEYS


def _get_secrets() -> dict[str, str]:
    """Retrieve Supabase credentials from environment or Streamlit secrets."""
    try:
        return {
            "url": st.secrets["SUPABASE_URL"],
            "key": st.secrets["SUPABASE_ANON_KEY"],
        }
    except Exception:
        return {
            "url": os.environ.get("SUPABASE_URL", ""),
            "key": os.environ.get("SUPABASE_ANON_KEY", ""),
        }


@st.cache_resource(show_spinner=False)
def get_db() -> Client:
    """Return a cached Supabase client."""
    creds = _get_secrets()
    if not creds["url"] or not creds["key"]:
        raise RuntimeError("Supabase credentials are missing.")
    return create_client(creds["url"], creds["key"])


@st.cache_data(ttl=60, show_spinner=False)
def get_settings(_db: Client | None = None) -> dict[str, str]:
    """Load admin settings from Supabase with a 60s cache."""
    db = _db or get_db()
    try:
        response = db.table("admin_settings").select("key, value").execute()
        rows = response.data or []
        settings = {row["key"]: row["value"] for row in rows}
    except Exception:
        settings = {}

    all_defaults = dict(DEFAULT_SETTINGS)
    for mk in _get_model_setting_keys():
        all_defaults.setdefault(mk, "true" if mk.startswith("model_enabled_") else "20")

    for key, value in all_defaults.items():
        if key not in settings:
            settings[key] = value
            try:
                db.table("admin_settings").insert(
                    {"key": key, "value": value}
                ).execute()
            except Exception:
                pass
    return settings


def update_setting(db: Client, key: str, value: str | int | bool) -> bool:
    """Update a single admin setting and invalidate the cache."""
    value_str = str(value).lower() if isinstance(value, bool) else str(value)
    try:
        response = (
            db.table("admin_settings")
            .select("key")
            .eq("key", key)
            .execute()
        )
        if response.data:
            db.table("admin_settings").update({"value": value_str}).eq(
                "key", key
            ).execute()
        else:
            db.table("admin_settings").insert(
                {"key": key, "value": value_str}
            ).execute()
        get_settings.clear()
        return True
    except Exception as e:
        st.error(f"Erreur lors de la mise à jour du paramètre : {e}")
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def log_activity(
    db: Client, session_id: str, action_type: str, action_detail: str = ""
) -> bool:
    """Insert an entry into activity_logs."""
    try:
        db.table("activity_logs").insert({
            "session_id": session_id,
            "action_type": action_type,
            "action_detail": action_detail[:500],
            "created_at": _now().isoformat(),
        }).execute()
        return True
    except Exception:
        return False


def save_feedback(
    db: Client,
    session_id: str,
    rating: int,
    comment: str,
    feature_request: str,
    other_idea: str,
    email: str,
) -> bool:
    """Save a user feedback into Supabase."""
    try:
        db.table("feedbacks").insert({
            "session_id": session_id,
            "rating": rating,
            "comment": comment[:2000],
            "feature_request": feature_request,
            "other_idea": other_idea[:500],
            "email": email[:255] if email else None,
            "created_at": _now().isoformat(),
        }).execute()
        log_activity(db, session_id, "feedback", f"rating={rating}")
        return True
    except Exception as e:
        st.error(f"Erreur lors de l'envoi du feedback : {e}")
        return False


def save_chat_message(db: Client, session_id: str, role: str, content: str) -> bool:
    """Persist a chat message; content is truncated to 5000 chars."""
    try:
        db.table("chat_history").insert({
            "session_id": session_id,
            "role": role,
            "content": content[:5000],
            "created_at": _now().isoformat(),
        }).execute()
        return True
    except Exception:
        return False


def get_chat_history(db: Client, session_id: str) -> list[dict[str, Any]]:
    """Return ordered chat history for a session."""
    try:
        response = (
            db.table("chat_history")
            .select("role, content, created_at")
            .eq("session_id", session_id)
            .order("created_at", desc=False)
            .execute()
        )
        return response.data or []
    except Exception:
        return []


def clear_chat_history(db: Client, session_id: str) -> bool:
    """Remove all chat messages for a session."""
    try:
        db.table("chat_history").delete().eq("session_id", session_id).execute()
        return True
    except Exception:
        return False


def get_or_create_session(db: Client, session_id: str) -> dict[str, Any]:
    """Fetch an anonymous session or create a new one with today's quota reset."""
    now = _now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        response = (
            db.table("anonymous_sessions")
            .select("*")
            .eq("id", session_id)
            .execute()
        )
        rows = response.data or []
        if rows:
            session = rows[0]
            last_active = _parse_iso(session.get("last_active_at")) or now
            quota_reset = _parse_iso(session.get("quota_reset_at")) or today

            # Reset daily quotas if we crossed midnight since last reset.
            if today > quota_reset:
                session["pdf_used"] = 0
                session["chat_used"] = 0
                session["search_used"] = 0
                session["quota_reset_at"] = today.isoformat()

            db.table("anonymous_sessions").update({
                "last_active_at": now.isoformat(),
                "quota_reset_at": session["quota_reset_at"],
                "pdf_used": session["pdf_used"],
                "chat_used": session["chat_used"],
                "search_used": session["search_used"],
            }).eq("id", session_id).execute()
            return session
    except Exception:
        pass

    try:
        db.table("anonymous_sessions").insert({
            "id": session_id,
            "created_at": now.isoformat(),
            "last_active_at": now.isoformat(),
            "quota_reset_at": today.isoformat(),
            "pdf_used": 0,
            "chat_used": 0,
            "search_used": 0,
        }).execute()
    except Exception:
        pass

    return {
        "id": session_id,
        "pdf_used": 0,
        "chat_used": 0,
        "search_used": 0,
        "quota_reset_at": today.isoformat(),
    }


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def use_quota(db: Client, session_id: str, quota_type: str) -> bool:
    """Increment a quota counter if possible; return success."""
    if quota_type not in ("pdf", "chat", "search"):
        return False
    column = f"{quota_type}_used"
    try:
        response = (
            db.table("anonymous_sessions")
            .select(column)
            .eq("id", session_id)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return False
        current = int(rows[0].get(column, 0) or 0)
        db.table("anonymous_sessions").update({column: current + 1}).eq(
            "id", session_id
        ).execute()
        return True
    except Exception:
        return False


def use_model_usage(db: Client, session_id: str, model_id: str) -> bool:
    """Increment per-model usage counter (JSONB column). Graceful if column missing."""
    try:
        resp = (
            db.table("anonymous_sessions")
            .select("model_usage")
            .eq("id", session_id)
            .execute()
        )
        rows = resp.data or []
        current: dict = {}
        if rows and rows[0].get("model_usage"):
            current = rows[0]["model_usage"]
        current[model_id] = current.get(model_id, 0) + 1
        db.table("anonymous_sessions").update({"model_usage": current}).eq(
            "id", session_id
        ).execute()
        return True
    except Exception:
        return False


def get_model_usage(db: Client, session_id: str, model_id: str) -> int:
    """Return usage count for a specific model. 0 if column missing."""
    try:
        resp = (
            db.table("anonymous_sessions")
            .select("model_usage")
            .eq("id", session_id)
            .execute()
        )
        rows = resp.data or []
        if rows and rows[0].get("model_usage"):
            return int(rows[0]["model_usage"].get(model_id, 0))
    except Exception:
        pass
    return 0


def cleanup_old_data(db: Client) -> dict[str, int]:
    """Delete chat_history > 7 days and inactive sessions > 7 days if enabled."""
    settings = get_settings(db)
    if settings.get("auto_cleanup_enabled", "true").lower() != "true":
        return {"chat_deleted": 0, "sessions_deleted": 0}

    cutoff = _now() - timedelta(days=7)
    stats = {"chat_deleted": 0, "sessions_deleted": 0}
    try:
        chat_resp = (
            db.table("chat_history")
            .delete()
            .lt("created_at", cutoff.isoformat())
            .execute()
        )
        stats["chat_deleted"] = len(chat_resp.data or [])
    except Exception:
        pass

    try:
        sess_resp = (
            db.table("anonymous_sessions")
            .delete()
            .lt("last_active_at", cutoff.isoformat())
            .execute()
        )
        stats["sessions_deleted"] = len(sess_resp.data or [])
    except Exception:
        pass

    return stats


def admin_get_stats(db: Client, days: int = 7) -> dict[str, Any]:
    """Aggregate statistics for the admin dashboard."""
    since = (_now() - timedelta(days=days)).isoformat()
    stats = {
        "days": days,
        "total_sessions": 0,
        "total_actions": 0,
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
        sess_resp = db.table("anonymous_sessions").select("id", count="exact").execute()
        stats["total_sessions"] = sess_resp.count or 0
    except Exception:
        pass

    try:
        action_all = db.table("activity_logs").select("id", count="exact").execute()
        stats["total_actions"] = action_all.count or 0
    except Exception:
        pass

    try:
        action_resp = (
            db.table("activity_logs")
            .select("action_type,action_detail,created_at,session_id")
            .gte("created_at", since)
            .order("created_at", desc=True)
            .execute()
        )
        actions = action_resp.data or []
        stats["actions_period"] = len(actions)
        stats["recent_actions"] = actions[:30]
    except Exception:
        actions = []

    for action in actions:
        day = action["created_at"][:10] if action.get("created_at") else ""
        if day:
            stats["actions_by_day"][day] = stats["actions_by_day"].get(day, 0) + 1
            stats["active_users_by_day"].setdefault(day, set()).add(
                action.get("session_id", "")
            )
            action_type = action.get("action_type", "unknown")
            stats["actions_by_type"][action_type] = (
                stats["actions_by_type"].get(action_type, 0) + 1
            )

    for day, users in stats["active_users_by_day"].items():
        stats["active_users_by_day"][day] = len(users)

    try:
        feedback_resp = db.table("feedbacks").select("*").execute()
        feedbacks = feedback_resp.data or []
        stats["feedbacks"] = len(feedbacks)
        stats["feedbacks_list"] = feedbacks
        ratings = [f["rating"] for f in feedbacks if f.get("rating")]
        if ratings:
            stats["average_rating"] = round(sum(ratings) / len(ratings), 2)
        for r in ratings:
            if 1 <= r <= 5:
                stats["rating_distribution"][r] += 1
        stats["emails_collected"] = [
            {"email": f.get("email"), "created_at": f.get("created_at"), "rating": f.get("rating")}
            for f in feedbacks
            if f.get("email")
        ]
        for f in feedbacks:
            req = f.get("feature_request") or ""
            for feature in req.split(","):
                feature = feature.strip()
                if feature:
                    stats["feature_requests"][feature] = (
                        stats["feature_requests"].get(feature, 0) + 1
                    )
    except Exception:
        pass

    try:
        oldest_chat = (
            db.table("chat_history")
            .select("created_at")
            .order("created_at", desc=False)
            .limit(1)
            .execute()
        )
        oldest_session = (
            db.table("anonymous_sessions")
            .select("created_at")
            .order("created_at", desc=False)
            .limit(1)
            .execute()
        )
        dates = [row.get("created_at") for row in (oldest_chat.data or []) + (oldest_session.data or []) if row.get("created_at")]
        if dates:
            stats["oldest_data"] = min(dates)[:10]
    except Exception:
        pass

    return stats
