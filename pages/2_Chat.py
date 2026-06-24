"""Chat IA — avec/sans contexte, recherche web, multi-modèles."""
import time
from dotenv import load_dotenv; load_dotenv()
import streamlit as st
from services.ai import AVAILABLE_MODELS, StudyBoostAIError, chat_response, chat_with_search
from services.database import (
    get_db, get_settings, log_activity, save_chat_message,
    get_chat_history, clear_chat_history, get_user_quotas, increment_quota,
)
from services.identity import get_user_id, init_user_identity, is_admin
from services.search import search_web, format_results
from services.ui_helpers import inject_css, show_user_identity_sidebar, show_quota_sidebar, show_ai_error

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
    inject_css(dark_mode)

    db = get_db()
    init_user_identity(db)
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
        show_user_identity_sidebar()
        st.markdown("## 💬 Chat IA")
        st.markdown("---")

        context_text = st.text_area(
            "📋 Texte de référence (optionnel)",
            height=200,
            placeholder="Colle ton cours ici…\nSi vide, l'IA répond de manière générale.",
            key="chat_context",
        )
        if context_text.strip():
            st.success(f"✅ {len(context_text.split())} mots chargés")
        else:
            st.info("💡 Sans texte, l'IA répond comme assistant général")
        st.markdown("---")

        web_search = False
        if search_enabled and quotas:
            search_left = max(0, quotas["search"]["limit"] - quotas["search"]["used"])
            search_exhausted = search_left <= 0
            web_search = st.toggle(
                "🌐 Activer la recherche web",
                value=False, disabled=search_exhausted,
                help=("Quota épuisé pour aujourd'hui." if search_exhausted
                      else f"Recherche en ligne. {search_left} restantes."),
            )
        else:
            st.caption("🌐 Recherche web désactivée")
        st.markdown("---")

        st.markdown("### 🤖 Modèle IA")
        model_choice = st.selectbox(
            "Choisir le modèle",
            options=list(AVAILABLE_MODELS.keys()),
            index=0, key="chat_model",
        )
        selected_model = AVAILABLE_MODELS[model_choice]
        st.markdown("---")

        if quotas:
            show_quota_sidebar(quotas)
        st.markdown("---")

        if st.button("🗑️ Nouvelle conversation", use_container_width=True):
            clear_chat_history(user_id)
            st.session_state["messages"] = []
            st.rerun()

    st.markdown("<h1 class='gradient-title'>💬 Chat IA</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p class='subtitle'>Pose tes questions, l'IA te répond — avec ou sans cours.</p>",
        unsafe_allow_html=True,
    )

    if "messages" not in st.session_state or st.session_state.get("last_user_id") != user_id:
        if st.session_state.get("last_user_id") and st.session_state["last_user_id"] != user_id:
            get_chat_history.clear()
        history = get_chat_history(user_id)
        st.session_state["messages"] = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in (history or [])
        ]
        st.session_state["last_user_id"] = user_id
        if not st.session_state["messages"]:
            welcome = (
                "Bonjour ! 👋 Je suis **StudyBoost AI**. "
                "Colle ton cours dans la barre latérale ou pose-moi directement une question !"
            )
            st.session_state["messages"].append({"role": "assistant", "content": welcome})
            save_chat_message(user_id, "assistant", welcome)

    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    chat_disabled = quotas and max(0, quotas["chat"]["limit"] - quotas["chat"]["used"]) <= 0
    if chat_disabled:
        st.error(f"❌ Limite de messages atteinte ({quotas['chat']['limit']}/{quotas['chat']['limit']}). Reviens demain !")

    if prompt := st.chat_input("Pose ta question…", disabled=chat_disabled):
        if len(prompt) > 5000:
            st.error("❌ Message trop long (5000 caractères max).")
            st.stop()

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
                    if wants_search and search_enabled and quotas and max(0, quotas["search"]["limit"] - quotas["search"]["used"]) > 0:
                        results = search_web(prompt)
                        if results:
                            with st.expander("🔍 Sources web consultées"):
                                st.markdown(format_results(results))
                            increment_quota(user_id, "search")
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

                    st.markdown(response)
                    elapsed = time.time() - start
                    increment_quota(user_id, "chat")
                    st.session_state["messages"].append({"role": "assistant", "content": response})
                    save_chat_message(user_id, "assistant", response)
                    log_activity(user_id, "chat_search" if used_search_quota else "chat", prompt[:100])
                except StudyBoostAIError as e:
                    show_ai_error(e, selected_model, "chat")
                except Exception:
                    show_ai_error(Exception("unknown"), selected_model, "chat")


if __name__ == "__main__":
    main()
