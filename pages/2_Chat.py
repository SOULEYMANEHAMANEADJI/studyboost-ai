"""Chat IA — avec/sans contexte, recherche web, multi-modèles."""
import time
from dotenv import load_dotenv; load_dotenv()
import streamlit as st

from version import VERSION
from services.ai import AVAILABLE_MODELS, StudyBoostAIError, chat_response, chat_with_search
from services.database import (
    get_settings, log_activity, save_chat_message,
    get_chat_history, clear_chat_history, get_user_quotas,
)
from services.identity import get_user_id, init_user_identity, is_admin
from services.search import search_web, format_results
from services.ui_helpers import inject_css, show_user_identity_sidebar, show_quota_sidebar, show_ai_error
from services.quotas import reserve_quota, QuotaError
from services.logger import get_logger

logger = get_logger("chat")

st.set_page_config(page_title="Chat - StudyBoost AI", page_icon="💬", layout="wide")

SEARCH_KEYWORDS = [
    "cherche", "recherche", "internet", "web", "trouve",
    "actualité", "récent", "news", "aujourd'hui", "dernières",
]


def main():
    dark_mode = st.session_state.get("dark_mode", False)
    new_dark = st.sidebar.toggle("🌙 Mode nuit", value=dark_mode, key="chat_dark")
    if new_dark != dark_mode:
        st.session_state["dark_mode"] = new_dark
        st.rerun()
    inject_css(dark_mode, page="chat")

    init_user_identity()
    settings = get_settings()
    user_id = get_user_id()

    if settings.get("maintenance_mode", "false") == "true":
        st.error("🔧 **Maintenance en cours** — Le chat est temporairement indisponible.")
        st.markdown("[🏠 Retour à l'accueil](/)")
        st.stop()

    chat_enabled = settings.get("feature_chat_enabled", "true").lower() == "true"
    search_enabled = settings.get("feature_search_enabled", "true").lower() == "true"

    if not chat_enabled:
        st.warning("💬 Le chat est temporairement indisponible.")
        st.stop()

    quotas = get_user_quotas(user_id, admin_bypass=is_admin())

    with st.sidebar:
        show_quota_sidebar(quotas)
        show_user_identity_sidebar()
    title_col, model_col = st.columns([1, 1.5])
    with title_col: st.title("Chat")
    with model_col:
        enabled_models = {name:mid for name,mid in AVAILABLE_MODELS.items() if settings.get(f"model_enabled_{mid}","true") == "true"}
        model_choice = st.selectbox("Modèle",options=list(enabled_models),key="chat_model",disabled=not enabled_models,placeholder="Aucun modèle disponible")
        selected_model = enabled_models.get(model_choice)
    course_col,clear_col = st.columns([3,2])
    with course_col:
        with st.expander("Ajouter mon cours",expanded=bool(st.session_state.get("chat_context"))):
            context_text=st.text_area("Cours de référence",height=140,max_chars=15000,key="chat_context",placeholder="Colle le cours sur lequel baser les réponses…")
            st.caption("Sans cours, l'IA répond comme assistant général.")
            web_search=st.toggle("Recherche web",value=False,key="chat_web_search",disabled=not search_enabled or quotas["search"]["used"]>=quotas["search"]["limit"])
    with clear_col:
        if st.button("Effacer la conversation",key="request_clear"):
            st.session_state["confirm_clear_chat"]=True
        if st.session_state.get("confirm_clear_chat"):
            st.warning("Tous les messages de cet espace seront supprimés. Cette action est définitive.")
            if st.button("Confirmer l'effacement",key="confirm_clear",type="primary"):
                if clear_chat_history(user_id):
                    for key in ("_failed_question","_retry_prompt","confirm_clear_chat"):
                        st.session_state.pop(key,None)
                    st.session_state["messages"]=[]
                    st.rerun()
            if st.button("Annuler",key="cancel_clear"):
                st.session_state.pop("confirm_clear_chat",None)
                st.rerun()

    if "messages" not in st.session_state or st.session_state.get("last_user_id") != user_id:
        history = get_chat_history(user_id)
        st.session_state["messages"] = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in (history or [])
        ]
        st.session_state["last_user_id"] = user_id
        if not st.session_state["messages"] and "user_data" in st.session_state:
            welcome = (
                "Bonjour ! Pose une question ou ajoute ton cours pour commencer à réviser."
            )
            st.session_state["messages"].append({"role": "assistant", "content": welcome})
            save_chat_message(user_id, "assistant", welcome)

    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    chat_disabled = not selected_model or bool(quotas and max(0, quotas["chat"]["limit"] - quotas["chat"]["used"]) <= 0)
    if not selected_model: st.info("Aucun modèle IA n'est activé. Ton historique reste consultable.")
    elif chat_disabled: st.info("Ton quota de messages est épuisé pour aujourd'hui.")

    entered_prompt = st.chat_input("Pose ta question…", disabled=chat_disabled)
    retry_prompt = st.session_state.pop("_retry_prompt", None)
    prompt = entered_prompt or retry_prompt
    if prompt and not chat_disabled:
        if len(prompt) > 5000:
            st.error("❌ Message trop long (5000 caractères max).")
            st.stop()

        if entered_prompt:
            st.session_state["messages"].append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            save_chat_message(user_id, "user", prompt)

        wants_search = web_search or any(kw in prompt.lower() for kw in SEARCH_KEYWORDS)
        used_search_quota = False

        with st.chat_message("assistant"):
            with st.spinner("🤔 Réflexion en cours…"):
                start = time.time()
                try:
                    reserve_quota(user_id, "chat", model=selected_model, admin_bypass=is_admin())
                    if wants_search and search_enabled and quotas and max(0, quotas["search"]["limit"] - quotas["search"]["used"]) > 0:
                        try:
                            reserve_quota(user_id, "search", admin_bypass=is_admin())
                            results = search_web(prompt)
                        except QuotaError as error:
                            st.info(str(error))
                            results = []
                        if results:
                            with st.expander("🔍 Sources web consultées"):
                                st.markdown(format_results(results))
                            used_search_quota = True
                            response = chat_with_search(prompt, results, context_text, model=selected_model)
                        else:
                            response = chat_response(context_text, prompt, st.session_state["messages"], model=selected_model)
                    else:
                        if wants_search and quotas and max(0, quotas["search"]["limit"] - quotas["search"]["used"]) <= 0:
                            st.info("ℹ️ Quota recherche épuisé. Je réponds sans recherche web.")
                        response = chat_response(context_text, prompt, st.session_state["messages"], model=selected_model)

                    if not response.strip():
                        response = "🤔 L'IA n'a pas pu générer de réponse. Reformule ta question."

                    st.session_state.pop("_failed_question", None)
                    st.markdown(response)
                    elapsed = time.time() - start
                    st.session_state["messages"].append({"role": "assistant", "content": response})
                    save_chat_message(user_id, "assistant", response)
                    log_activity(user_id, "chat_search" if used_search_quota else "chat", prompt[:100])
                except QuotaError as e:
                    st.error(str(e))
                except StudyBoostAIError as e:
                    show_ai_error(e, selected_model, "chat")
                    if getattr(e, "code", "") not in ("auth", "config", "rate_limit", "credits"):
                        st.session_state["_failed_question"] = prompt
                except Exception as e:
                    logger.warning("Erreur inattendue chat: %s", e)
                    st.error("❌ Une erreur inattendue s'est produite.")

    if st.session_state.get("_failed_question"):
        if st.button("Réessayer la dernière question", key="retry_chat_question", disabled=chat_disabled):
            st.session_state["_retry_prompt"] = st.session_state.pop("_failed_question")
            st.rerun()

    st.markdown(
        f'<div style="text-align:center;color:#94A3B8;font-size:0.75rem;margin-top:2rem;">'
        f'v{VERSION} · StudyBoost AI</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
