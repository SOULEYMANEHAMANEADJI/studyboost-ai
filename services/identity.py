"""
Gestion de l'identité anonyme persistante via cookie + URL query param.
Chaque utilisateur reçoit un alias mignon et garde son espace 7 jours.
"""
import random
import uuid
from datetime import datetime, timedelta, timezone

import streamlit as st
from streamlit_cookies_controller import CookieController

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


_controller = None

def get_cookie_controller():
    global _controller
    if _controller is None:
        _controller = CookieController()
    return _controller


def _read_cookie_with_retry(controller, key="studyboost_session_id", retries=2, delay=0.15):
    """Read cookie with retry to account for JS component mount time."""
    for _ in range(retries):
        val = controller.get(key)
        if val:
            return val
        import time
        time.sleep(delay)
    return controller.get(key)


def init_user_identity(db=None):
    controller = get_cookie_controller()

    # 1) Cookie d'abord (per-browser, sécurisé)
    existing_token = _read_cookie_with_retry(controller)

    # 2) Fallback URL param (F5/first load quand JS cookie pas encore monté)
    if not existing_token:
        sid_from_url = st.query_params.get("sid")
        if sid_from_url:
            existing_token = sid_from_url

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
                    # Transférer l'identité dans le cookie et nettoyer l'URL
                    try:
                        controller.set("studyboost_session_id", session["id"], max_age=7 * 24 * 60 * 60)
                    except Exception:
                        pass
                    try:
                        del st.query_params["sid"]
                    except Exception:
                        pass
                    return st.session_state["user_data"]
        except Exception as e:
            logger.warning("init_user_identity: échec validation session cookie %s", existing_token[:8], exc_info=e)

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
            except Exception as e:
                logger.error("init_user_identity: échec création session Supabase pour %s", new_id[:8], exc_info=e)

        # Cookie uniquement (pas de sid dans l'URL pour éviter le partage)
        try:
            controller.set("studyboost_session_id", new_id, max_age=7 * 24 * 60 * 60)
        except Exception as e:
            logger.warning("init_user_identity: échec set cookie pour %s", new_id[:8], exc_info=e)

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
    except Exception as e:
        logger.warning("logout: échec suppression cookie", exc_info=e)
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()
