"""
Gestion de l'identité anonyme persistante via st.session_state + URL.
Chaque onglet/navigateur reçoit SA propre identité.
Pas de cookies (partagés entre onglets d'un même navigateur).
"""
import random
import uuid
from datetime import datetime, timedelta, timezone

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


def init_user_identity(db=None):
    # Déjà chargé dans cette session (même onglet)
    if "user_data" in st.session_state:
        return st.session_state["user_data"]

    # Tentative de restauration depuis l'URL (F5 dans le même onglet)
    sid_from_url = st.query_params.get("sid")
    if sid_from_url and db:
        try:
            result = db.table("sessions").select("*").eq("id", sid_from_url).execute()
            if result.data:
                session = result.data[0]
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
                            "display": session.get(
                                "alias_display", "🎓 Étudiant-Anonyme"
                            ),
                        },
                        "is_returning": True,
                    }
                    return st.session_state["user_data"]
        except Exception as e:
            logger.warning("init_user_identity: échec validation URL sid %s", sid_from_url[:8], exc_info=e)

    # Nouvelle identité
    new_id = str(uuid.uuid4())
    alias = generate_alias()

    if db:
        try:
            db.table("sessions").insert({
                "id": new_id,
                "alias_emoji": alias["emoji"],
                "alias_animal": alias["animal"],
                "alias_adjective": alias["adjective"],
                "alias_number": alias["number"],
                "alias_display": alias["display"],
                "pdf_count": 0,
                "chat_count": 0,
                "search_count": 0,
                "ai_count": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_active": datetime.now(timezone.utc).isoformat(),
            }).execute()
        except Exception as e:
            logger.error("init_user_identity: échec création session Supabase pour %s", new_id[:8], exc_info=e)

    st.session_state["user_data"] = {
        "id": new_id,
        "alias": alias,
        "is_returning": False,
    }

    # Persister dans l'URL pour le F5 (uniquement ce même onglet)
    st.query_params["sid"] = new_id

    return st.session_state["user_data"]


def get_user_id() -> str:
    if "user_data" in st.session_state:
        return st.session_state["user_data"]["id"]
    return str(uuid.uuid4())


def get_user_alias() -> dict:
    if "user_data" in st.session_state:
        return st.session_state["user_data"]["alias"]
    return {"display": "🎓 Anonyme", "emoji": "🎓"}


def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
