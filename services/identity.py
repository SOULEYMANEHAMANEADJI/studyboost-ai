"""Browser-owned anonymous identity. URL parameters never grant access."""
from __future__ import annotations

import hashlib
import random
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg2.extras
import streamlit as st
from streamlit.components.v1 import declare_component
from services.logger import get_logger

logger = get_logger("identity")
_browser_identity = declare_component(
    "studyboost_browser_identity", path=str(Path(__file__).parent / "identity_component")
)


def is_admin() -> bool:
    return bool(st.session_state.get("admin_auth") and time.time() < st.session_state.get("admin_auth_until",0))


ANIMALS = [
    ("🐼", "Panda"), ("🦊", "Renard"), ("🦉", "Hibou"),
    ("🦁", "Lion"), ("🐯", "Tigre"), ("🦄", "Licorne"),
    ("🐢", "Tortue"), ("🦋", "Papillon"), ("🐬", "Dauphin"),
    ("🦅", "Aigle"), ("🦝", "Raton"), ("🐺", "Loup"),
    ("🦔", "Hérisson"), ("🐨", "Koala"), ("🐧", "Pingouin"),
    ("🦓", "Zèbre"), ("🦘", "Kangourou"), ("🐰", "Lapin"),
]

ADJECTIVES = [
    "Curieux", "Malin", "Sage", "Brillant", "Audacieux",
    "Créatif", "Astucieux", "Intrépide", "Joyeux", "Vif",
    "Génial", "Inventif", "Studieux", "Perspicace", "Talentueux",
]


def generate_alias() -> dict:
    emoji, animal = random.choice(ANIMALS)
    adjective = random.choice(ADJECTIVES)
    number = random.randint(1000, 9999)
    return {
        "emoji": emoji,
        "animal": animal,
        "adjective": adjective,
        "number": number,
        "display": f"{emoji} {animal}-{adjective}-{number}",
    }


def _clear_user_state():
    # Includes editor widgets, exports, chat context and admin authentication.
    for key in list(st.session_state.keys()):
        if key not in ("browser_identity", "identity_rotation"):
            del st.session_state[key]


def init_user_identity():
    from services.database import get_db, release_db, get_settings

    # Legacy shared links must never restore someone else's session.
    if "sid" in st.query_params:
        del st.query_params["sid"]
    rotation = st.session_state.get("identity_rotation", "")
    value = _browser_identity(rotation=rotation, key="browser_identity", default=None)
    if not isinstance(value, dict) or value.get("rotation") != rotation:
        st.info("Initialisation de ton espace privé…")
        st.stop()
    if value.get("error"):
        st.error("Le stockage du navigateur est bloqué. Autorise le stockage pour conserver un espace privé, puis recharge la page.")
        st.stop()
    token = value.get("token", "")
    if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{64}", token):
        st.error("Identité du navigateur invalide. Recharge la page.")
        st.stop()
    # Only a one-way digest is persisted; knowing a database ID is not sufficient.
    user_id = hashlib.sha256(token.encode("ascii")).hexdigest()
    current = st.session_state.get("user_data")
    if current and current.get("id") != user_id:
        _clear_user_state()
        st.rerun()
    elif current:
        return current

    db = None
    try:
        days = int(get_settings().get("retention_days", "7"))
        db = get_db()
        with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM sessions WHERE id = %s", (user_id,))
            row = cur.fetchone()
            returning = bool(row)
            if row:
                active = row.get("last_active") or row["created_at"]
                if isinstance(active, str):
                    active = datetime.fromisoformat(active.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) - active >= timedelta(days=days):
                    # Rotate instead of exposing expired records before cleanup.
                    db.rollback()
                    logout()
            else:
                alias = generate_alias()
                cur.execute(
                    "INSERT INTO sessions (id, alias_emoji, alias_animal, alias_adjective, "
                    "alias_number, alias_display, quota_date, created_at, last_active) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,NOW(),NOW()) ON CONFLICT (id) DO NOTHING",
                    (user_id, alias["emoji"], alias["animal"], alias["adjective"],
                     alias["number"], alias["display"], datetime.now(timezone.utc).strftime("%Y-%m-%d")),
                )
                cur.execute("SELECT * FROM sessions WHERE id = %s", (user_id,))
                row = cur.fetchone()
                if not row:
                    raise RuntimeError("Session insertion could not be verified")
            cur.execute("UPDATE sessions SET last_active = NOW() WHERE id = %s", (user_id,))
        db.commit()
    except Exception as error:
        if db is not None:
            db.rollback()
        logger.error("Identity persistence failed type=%s", type(error).__name__)
        st.error("Connexion à la base indisponible : ton espace ne peut pas être chargé ou sauvegardé. Réessaie plus tard.")
        st.stop()
    finally:
        if db is not None:
            release_db(db)

    user = {
        "id": user_id,
        "alias": {
            "emoji": row.get("alias_emoji", "🎓"),
            "animal": row.get("alias_animal", "Étudiant"),
            "adjective": row.get("alias_adjective", "Anonyme"),
            "number": row.get("alias_number", 0),
            "display": row.get("alias_display", "🎓 Anonyme"),
        },
        "is_returning": returning,
    }
    st.session_state["user_data"] = user
    return user


def get_user_id() -> str:
    if "user_data" in st.session_state:
        return st.session_state["user_data"]["id"]
    raise RuntimeError("Initialise l'identité avant d'accéder aux données.")


def get_user_alias() -> dict:
    return st.session_state.get("user_data", {}).get("alias", {"display": "🎓 Anonyme", "emoji": "🎓"})


def logout():
    _clear_user_state()
    st.session_state["identity_rotation"] = str(uuid.uuid4())
    if "sid" in st.query_params:
        del st.query_params["sid"]
    st.rerun()
