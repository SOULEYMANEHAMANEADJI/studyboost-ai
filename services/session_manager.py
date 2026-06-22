"""Anonymous session and quota management for StudyBoost AI."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import streamlit as st
from supabase import Client

from services.database import get_or_create_session, use_quota, get_model_usage, use_model_usage


def get_session_id() -> str:
    """Return a stable anonymous UUID stored in session state."""
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())
    return st.session_state["session_id"]


def init_session(db: Client, settings: dict[str, str]) -> dict[str, Any]:
    """Initialize or refresh the anonymous session."""
    session_id = get_session_id()
    session = get_or_create_session(db, session_id)
    st.session_state["session"] = session
    return session


def get_quota(
    db: Client, session_id: str, settings: dict[str, str]
) -> dict[str, dict[str, int]]:
    """Return used/limit/remaining for each quota type."""
    session = get_or_create_session(db, session_id)
    quotas = {}
    for key, column in (
        ("pdf", "pdf_used"),
        ("chat", "chat_used"),
        ("search", "search_used"),
    ):
        limit_key = f"quota_{key}_per_day"
        limit = int(settings.get(limit_key, DEFAULT_QUOTAS[key]))
        used = int(session.get(column, 0) or 0)
        quotas[key] = {
            "used": used,
            "limit": limit,
            "remaining": max(0, limit - used),
        }
    return quotas


DEFAULT_QUOTAS = {
    "pdf": 10,
    "chat": 15,
    "search": 15,
}


def consume_quota(
    db: Client, session_id: str, quota_type: str
) -> tuple[bool, str]:
    """Check, consume a quota, and return (success, message)."""
    from services.database import get_settings

    settings = get_settings(db)
    quotas = get_quota(db, session_id, settings)
    if quota_type not in quotas:
        return False, "Type de quota inconnu."

    if quotas[quota_type]["remaining"] <= 0:
        return False, f"Quota {quota_type} atteint pour aujourd'hui. Reviens demain !"

    if use_quota(db, session_id, quota_type):
        return True, ""
    return False, "Impossible de mettre à jour le quota. Réessaie plus tard."


def get_model_quota(
    db: Client, session_id: str, model_id: str, settings: dict[str, str]
) -> dict[str, int]:
    """Return used/limit/remaining for a specific AI model."""
    limit = int(settings.get(f"model_quota_{model_id}", "20"))
    used = get_model_usage(db, session_id, model_id)
    return {"used": used, "limit": limit, "remaining": max(0, limit - used)}


def consume_model_quota(db: Client, session_id: str, model_id: str) -> bool:
    """Increment per-model usage counter. Returns success."""
    return use_model_usage(db, session_id, model_id)


def update_session_activity(db: Client, session_id: str) -> None:
    """Bump the last_active_at timestamp for the session."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        db.table("anonymous_sessions").update(
            {"last_active_at": now}
        ).eq("id", session_id).execute()
    except Exception:
        pass
