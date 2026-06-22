"""
Gestion de l'identité anonyme persistante via cookie.
Chaque utilisateur reçoit un alias mignon et garde son espace 7 jours.
"""
import random
import uuid
from datetime import datetime, timedelta, timezone

import streamlit as st
from streamlit_cookies_controller import CookieController


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


_controller = None

def get_cookie_controller():
    global _controller
    if _controller is None:
        _controller = CookieController()
    return _controller


def init_user_identity(db=None):
    controller = get_cookie_controller()

    existing_token = controller.get("studyboost_session_id")

    if existing_token and "user_data" not in st.session_state and db:
        try:
            result = db.table("sessions").select("*").eq("id", existing_token).execute()
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
        except Exception:
            pass

    if "user_data" not in st.session_state:
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
            except Exception:
                pass

        try:
            controller.set("studyboost_session_id", new_id, max_age=7 * 24 * 60 * 60)
        except Exception:
            pass

        st.session_state["user_data"] = {
            "id": new_id,
            "alias": alias,
            "is_returning": False,
        }

    return st.session_state["user_data"]


def get_user_id() -> str:
    if "user_data" in st.session_state:
        return st.session_state["user_data"]["id"]
    if "session_id" in st.session_state:
        return st.session_state["session_id"]
    return str(uuid.uuid4())


def get_user_alias() -> dict:
    if "user_data" in st.session_state:
        return st.session_state["user_data"]["alias"]
    return {"display": "🎓 Anonyme", "emoji": "🎓"}


def logout():
    controller = get_cookie_controller()
    try:
        controller.remove("studyboost_session_id")
    except Exception:
        pass
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
