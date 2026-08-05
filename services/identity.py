"""
Gestion de l'identité anonyme persistante via st.session_state + URL.
Chaque onglet/navigateur reçoit SA propre identité.
Pas de cookies (partagés entre onglets d'un même navigateur).
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone

import psycopg2.extras
import streamlit as st

from services.logger import get_logger

logger = get_logger("identity")


def is_admin() -> bool:
    return st.session_state.get("admin_auth", False)

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


def init_user_identity():
    """Initialise ou restaure l'identité anonyme de l'utilisateur."""
    from services.database import get_db, release_db

    if "user_data" in st.session_state:
        return st.session_state["user_data"]

    sid_from_url = st.query_params.get("sid")
    if sid_from_url:
        db = get_db()
        try:
            cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT * FROM sessions WHERE id = %s", (sid_from_url,))
            session = cur.fetchone()
            if session:
                cur.execute(
                    "UPDATE sessions SET last_active = NOW() WHERE id = %s",
                    (sid_from_url,),
                )
                db.commit()
            cur.close()
            if session:
                created = datetime.fromisoformat(
                    str(session["created_at"]).replace("Z", "+00:00")
                )
                if (datetime.now(timezone.utc) - created) < timedelta(days=7):
                    st.session_state["user_data"] = {
                        "id": session["id"],
                        "alias": {
                            "emoji": session.get("alias_emoji", "🎓"),
                            "animal": session.get("alias_animal", "Étudiant"),
                            "adjective": session.get("alias_adjective", "Anonyme"),
                            "number": session.get("alias_number", 0),
                            "display": session.get("alias_display", "🎓 Étudiant-Anonyme"),
                        },
                        "is_returning": True,
                    }
                    release_db(db)
                    return st.session_state["user_data"]
        except Exception as e:
            logger.warning("init_user_identity: échec restauration session %s", sid_from_url[:8], exc_info=e)
        finally:
            release_db(db)

    new_id = str(uuid.uuid4())
    alias = generate_alias()

    inserted = False
    for attempt in range(2):
        db = get_db()
        try:
            cur = db.cursor()
            cur.execute(
                "INSERT INTO sessions (id, alias_emoji, alias_animal, alias_adjective, "
                "alias_number, alias_display, pdf_count, chat_count, search_count, "
                "ai_count, quota_date, created_at, last_active) "
                "VALUES (%s, %s, %s, %s, %s, %s, 0, 0, 0, 0, %s, %s, %s)",
                (
                    new_id,
                    alias["emoji"], alias["animal"], alias["adjective"],
                    alias["number"], alias["display"],
                    datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                    datetime.now(timezone.utc).isoformat(),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            db.commit()
            cur.close()

            cur = db.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT id FROM sessions WHERE id = %s", (new_id,))
            row = cur.fetchone()
            cur.close()
            if row:
                inserted = True
                break
        except Exception as e:
            logger.error("init_user_identity: échec création session (tentative %d) pour %s", attempt + 1, new_id[:8], exc_info=e)
        finally:
            release_db(db)

    if not inserted:
        logger.error("init_user_identity: ÉCHEC CRITIQUE — impossible de créer la session %s après 2 tentatives", new_id[:8])

    st.session_state["user_data"] = {
        "id": new_id,
        "alias": alias,
        "is_returning": False,
    }
    if inserted:
        st.query_params["sid"] = new_id

    return st.session_state["user_data"]


def get_user_id() -> str:
    if "user_data" in st.session_state:
        return st.session_state["user_data"]["id"]
    raise RuntimeError("get_user_id() appelé sans init_user_identity() — appelle init_user_identity() en premier.")


def get_user_alias() -> dict:
    if "user_data" in st.session_state:
        return st.session_state["user_data"]["alias"]
    return {"display": "🎓 Anonyme", "emoji": "🎓"}


def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
