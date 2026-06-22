"""Chat IA — avec/sans contexte, recherche web, multi-modèles."""
from __future__ import annotations

import streamlit as st
from services.ai import AVAILABLE_MODELS, chat_response, chat_with_search, DEFAULT_MODEL
from services.database import (
    get_db,
    get_settings,
    log_activity,
    save_chat_message,
    get_chat_history,
    clear_chat_history,
    use_quota,
)
from services.search import search_web, format_results
from services.session_manager import get_session_id, init_session, get_quota
from services.ui_helpers import inject_css, show_quota_sidebar, show_feature_disabled

st.set_page_config(page_title="Chat - StudyBoost AI", page_icon="💬", layout="wide")

SEARCH_KEYWORDS = [
    "cherche", "recherche", "internet", "web", "trouve",
    "actualité", "récent", "news", "aujourd'hui", "dernières",
]


def main():
    dark_mode = st.sidebar.toggle("🌙 Mode nuit", value=False, key="chat_dark")
    inject_css(dark_mode)

    db = get_db()
    settings = get_settings(db)
    session_id = get_session_id()
    init_session(db, settings)

    chat_enabled = settings.get("feature_chat_enabled", "true").lower() == "true"
    search_enabled = settings.get("feature_search_enabled", "true").lower() == "true"

    if not chat_enabled:
        st.warning("💬 Le chat est temporairement indisponible.")
        st.stop()

    quotas = get_quota(db, session_id, settings)

    # Sidebar
    with st.sidebar:
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
        if search_enabled:
            web_search = st.toggle(
                "🌐 Activer la recherche web",
                value=False,
                help=f"Recherche en ligne. {quotas['search']['remaining']} restantes.",
            )
        else:
            st.caption("🌐 Recherche web désactivée")

        st.markdown("---")
        st.markdown("### 🤖 Modèle IA")
        model_choice = st.selectbox(
            "Choisir le modèle",
            options=list(AVAILABLE_MODELS.keys()),
            index=0,
            key="chat_model",
        )
        selected_model = AVAILABLE_MODELS[model_choice]
        st.markdown("---")

        show_quota_sidebar(quotas)
        st.markdown("---")

        if st.button("🗑️ Nouvelle conversation", use_container_width=True):
            clear_chat_history(db, session_id)
            st.session_state["messages"] = []
            st.rerun()

    # Main chat
    st.markdown("<h1 class='gradient-title'>💬 Chat IA</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p class='subtitle'>Pose tes questions, l'IA te répond — avec ou sans cours.</p>",
        unsafe_allow_html=True,
    )

    # Initialiser messages
    if "messages" not in st.session_state:
        history = get_chat_history(db, session_id)
        st.session_state["messages"] = history if history else []
        if not st.session_state["messages"]:
            welcome = (
                "Bonjour ! 👋 Je suis **StudyBoost AI**. "
                "Colle ton cours dans la barre latérale ou pose-moi directement une question !"
            )
            st.session_state["messages"].append({"role": "assistant", "content": welcome})
            save_chat_message(db, session_id, "assistant", welcome)

    # Afficher messages
    for msg in st.session_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input
    if prompt := st.chat_input("Pose ta question…"):
        if quotas["chat"]["remaining"] <= 0:
            st.error("❌ Limite de messages atteinte (15/15). Reviens demain !")
            st.stop()

        # Message user
        st.session_state["messages"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        save_chat_message(db, session_id, "user", prompt)

        # Détection recherche web
        wants_search = web_search or any(kw in prompt.lower() for kw in SEARCH_KEYWORDS)
        used_search_quota = False

        with st.chat_message("assistant"):
            with st.spinner("🤔 Réflexion en cours…"):
                try:
                    if wants_search and search_enabled and quotas["search"]["remaining"] > 0:
                        results = search_web(prompt)
                        if results:
                            with st.expander("🔍 Sources web consultées"):
                                st.markdown(format_results(results))
                            use_quota(db, session_id, "search")
                            used_search_quota = True
                            response = chat_with_search(prompt, results, context_text, model=selected_model)
                        else:
                            response = chat_response(context_text, prompt, st.session_state["messages"], model=selected_model)
                    else:
                        if wants_search and quotas["search"]["remaining"] <= 0:
                            st.info("ℹ️ Quota recherche épuisé. Je réponds sans recherche web.")
                        response = chat_response(context_text, prompt, st.session_state["messages"], model=selected_model)

                    st.markdown(response)
                    use_quota(db, session_id, "chat")
                    st.session_state["messages"].append({"role": "assistant", "content": response})
                    save_chat_message(db, session_id, "assistant", response)
                    log_activity(
                        db, session_id,
                        "chat_search" if used_search_quota else "chat",
                        prompt[:100],
                    )
                except Exception as e:
                    st.error(f"❌ Erreur : {e}")


if __name__ == "__main__":
    main()
