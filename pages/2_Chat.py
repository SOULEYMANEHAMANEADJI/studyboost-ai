"""StudyBoost AI - Chat page."""
from __future__ import annotations

import streamlit as st
from services.database import (
    get_db,
    get_settings,
    log_activity,
    save_chat_message,
    get_chat_history,
    clear_chat_history,
)
from services.session_manager import get_session_id, init_session, get_quota, consume_quota
from services.ai import chat_response, chat_with_search
from services.search import search_web, format_results
from services.ui import inject_css, render_quota_sidebar


st.set_page_config(page_title="Chat - StudyBoost AI", page_icon="💬", layout="wide")

WEB_SEARCH_KEYWORDS = [
    "cherche", "recherche", "internet", "web", "trouve",
    "actualité", "récent", "news", "aujourd'hui",
]


def _should_search_web(question: str) -> bool:
    q = question.lower()
    return any(kw in q for kw in WEB_SEARCH_KEYWORDS)


def main():
    inject_css()
    db = get_db()
    settings = get_settings(db)
    session_id = get_session_id()
    init_session(db, settings)

    chat_enabled = settings.get("feature_chat_enabled", "true").lower() == "true"
    search_enabled = settings.get("feature_search_enabled", "true").lower() == "true"

    if not chat_enabled:
        st.warning("💬 Le chat est actuellement désactivé par l'administrateur.")
        st.stop()

    # Sidebar
    with st.sidebar:
        st.markdown("## 💬 Chat avec ton cours")
        st.sidebar.markdown("---")
        course_context = st.sidebar.text_area(
            "📖 Colle ton cours ici",
            height=280,
            placeholder="Colle ton cours, article ou notes...",
            key="course_context",
        )
        if course_context:
            wc = len(course_context.split())
            st.sidebar.caption(f"📄 {wc} mots chargés")
        else:
            st.sidebar.caption("📄 Aucun cours chargé")

        st.sidebar.markdown("---")
        quotas = get_quota(db, session_id, settings)
        chat_remaining = quotas["chat"]["remaining"]
        chat_limit = quotas["chat"]["limit"]
        chat_used = quotas["chat"]["used"]
        chat_pct = int((chat_used / chat_limit) * 100) if chat_limit else 0
        st.sidebar.markdown("#### 💬 Chat")
        st.sidebar.progress(min(chat_pct, 100), text=f"{chat_remaining} restant(s)")

        search_remaining = quotas["search"]["remaining"]
        search_limit = quotas["search"]["limit"]
        search_used = quotas["search"]["used"]
        search_pct = int((search_used / search_limit) * 100) if search_limit else 0
        st.sidebar.markdown("#### 🌐 Recherche web")
        st.sidebar.progress(min(search_pct, 100), text=f"{search_remaining} restant(s)")

        st.sidebar.markdown("---")

        web_search_toggle = st.sidebar.checkbox(
            "🌐 Recherche web",
            value=False,
            disabled=not search_enabled,
            help="Active la recherche web pour les questions qui le nécessitent"
            if search_enabled
            else "Recherche web désactivée",
        )

        if st.sidebar.button("🗑️ Nouvelle conversation", use_container_width=True):
            clear_chat_history(db, session_id)
            st.session_state["chat_messages"] = []
            st.rerun()

        st.sidebar.markdown("---")
        render_quota_sidebar(db, session_id, settings)

    # Main chat area
    st.markdown("<h1 class='gradient-title'>💬 Chat avec ton cours</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align:center;color:#64748B;'>Pose des questions sur ton cours, "
        "et l'IA te répond en contexte.",
        unsafe_allow_html=True,
    )

    if chat_remaining <= 0:
        st.warning(
            "🚫 Tu as atteint ta limite de messages pour aujourd'hui. "
            "Reviens demain pour continuer à apprendre !"
        )
        st.stop()

    # Load chat history
    if "chat_messages" not in st.session_state:
        stored = get_chat_history(db, session_id)
        st.session_state["chat_messages"] = stored or []

    # Display messages
    for msg in st.session_state["chat_messages"]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        with st.chat_message(role):
            st.markdown(content)

    # Chat input
    if prompt := st.chat_input("Pose ta question sur le cours..."):
        if not course_context and not web_search_toggle:
            st.warning("Colle d'abord ton cours dans la barre latérale.")
            st.stop()

        # Add user message
        st.session_state["chat_messages"].append({
            "role": "user", "content": prompt
        })
        with st.chat_message("user"):
            st.markdown(prompt)
        save_chat_message(db, session_id, "user", prompt)

        should_search = web_search_toggle or _should_search_web(prompt)

        if should_search and search_enabled:
            if quotas["search"]["remaining"] <= 0:
                st.warning("Quota de recherche web épuisé pour aujourd'hui.")
                st.stop()
            success, msg = consume_quota(db, session_id, "search")
            if not success:
                st.warning(msg)
                st.stop()

        # Consume chat quota before AI call
        success, msg = consume_quota(db, session_id, "chat")
        if not success:
            st.warning(msg)
            st.stop()

        with st.chat_message("assistant"):
            with st.spinner("🤖 Réflexion en cours..."):
                try:
                    if should_search and search_enabled:
                        results = search_web(prompt)
                        formatted = format_results(results)
                        response = chat_with_search(prompt, formatted, course_context or "")
                        log_activity(
                            db, session_id, "chat_search",
                            f"query={prompt[:100]}, results={len(results)}"
                        )
                        if results:
                            with st.expander("🌐 Sources web", expanded=False):
                                for r in results:
                                    st.markdown(f"- [{r['title']}]({r['href']})")
                    else:
                        response = chat_response(
                            course_context or "", prompt,
                            st.session_state["chat_messages"][-10:-1]
                        )
                        log_activity(
                            db, session_id, "chat_message",
                            f"query={prompt[:100]}"
                        )

                    st.markdown(response)
                    st.session_state["chat_messages"].append({
                        "role": "assistant", "content": response
                    })
                    save_chat_message(db, session_id, "assistant", response)
                except Exception as e:
                    st.error(f"Erreur : {e}")


if __name__ == "__main__":
    main()
