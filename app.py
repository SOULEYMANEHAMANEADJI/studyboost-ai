"""StudyBoost AI - Home page."""
from __future__ import annotations

import random
import streamlit as st

st.set_page_config(
    page_title="StudyBoost AI",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

from services.database import get_db, get_settings, cleanup_old_data, log_activity
from services.session_manager import get_session_id, init_session
from services.ui import inject_css, render_quota_sidebar


def main():
    inject_css()

    try:
        db = get_db()
    except RuntimeError as e:
        st.error(str(e))
        st.stop()

    settings = get_settings(db)
    session_id = get_session_id()

    # Maintenance mode check
    if settings.get("maintenance_mode", "false").lower() == "true":
        st.warning(
            "🔧 StudyBoost AI est actuellement en maintenance. "
            "Reviens dans quelques instants ! 🚀"
        )
        st.stop()

    # Global admin message
    global_msg = settings.get("global_message", "").strip()
    if global_msg:
        st.info(global_msg)

    # Initialize session
    init_session(db, settings)

    # Sidebar
    with st.sidebar:
        st.markdown("## 📚 StudyBoost AI")
        st.markdown("---")
        render_quota_sidebar(db, session_id, settings)
        st.sidebar.markdown("---")
        if st.sidebar.button("💡 Laisser un avis", use_container_width=True):
            st.switch_page("pages/3_Feedback.py")
        st.sidebar.markdown("---")
        st.sidebar.markdown(
            "<div style='text-align:center;color:#64748B;font-size:0.8rem;'>"
            "Phase beta gratuite</div>",
            unsafe_allow_html=True,
        )

    # Main content

    # Hero section
    st.markdown(
        "<div style='text-align:center; padding: 1rem 0 0.5rem 0;'>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<span class='badge'>BETA</span>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<h1 class='gradient-title'>StudyBoost AI</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center; font-size:1.2rem; color:#64748B; "
        "max-width:600px; margin:0 auto 2rem auto;'>"
        "Transforme tes cours en fiches de révision, résumés et quiz "
        "avec l'intelligence artificielle. Gratuit, anonyme, sans inscription.</p>",
        unsafe_allow_html=True,
    )

    # How it works
    st.markdown("## Comment ça marche")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            "<div class='step-card'>"
            "<div style='font-size:2.5rem;'>📋</div>"
            "<h3>1. Colle ton cours</h3>"
            "<p style='color:#64748B; font-size:0.9rem;'>Copie ton texte depuis n'importe "
            "quelle source.</p></div>",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            "<div class='step-card'>"
            "<div style='font-size:2.5rem;'>🤖</div>"
            "<h3>2. L'IA transforme</h3>"
            "<p style='color:#64748B; font-size:0.9rem;'>Choisis une transformation : "
            "résumé, quiz, fiche, etc.</p></div>",
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            "<div class='step-card'>"
            "<div style='font-size:2.5rem;'>📥</div>"
            "<h3>3. Exporte et révise</h3>"
            "<p style='color:#64748B; font-size:0.9rem;'>Télécharge en PDF ou Markdown "
            "et étudie à ton rythme.</p></div>",
            unsafe_allow_html=True,
        )

    # Main feature cards
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(
            "<div class='card'>"
            "<h3>📝 Éditeur de révision</h3>"
            "<p style='color:#64748B;'>Résume, simplifie, crée des fiches de révision "
            "et des quiz à partir de tes cours.</p>"
            "<div style='display:flex; gap:0.5rem; flex-wrap:wrap; margin:0.8rem 0;'>"
            "<span class='tag'>Résumé</span><span class='tag'>Fiche</span>"
            "<span class='tag'>Quiz</span><span class='tag'>Points clés</span>"
            "</div></div>",
            unsafe_allow_html=True,
        )
        if st.button("🚀 Lancer l'éditeur", key="btn_editor", use_container_width=True):
            st.switch_page("pages/1_Editeur.py")
    with col_b:
        st.markdown(
            "<div class='card'>"
            "<h3>💬 Chat avec ton cours</h3>"
            "<p style='color:#64748B;'>Pose des questions sur ton cours, fais des "
            "recherches web et obtiens des réponses contextualisées.</p>"
            "<div style='display:flex; gap:0.5rem; flex-wrap:wrap; margin:0.8rem 0;'>"
            "<span class='tag'>Questions</span><span class='tag'>Recherche web</span>"
            "<span class='tag'>Synthèse</span>"
            "</div></div>",
            unsafe_allow_html=True,
        )
        if st.button("💬 Ouvrir le chat", key="btn_chat", use_container_width=True):
            st.switch_page("pages/2_Chat.py")

    # Rules / Privacy section
    st.markdown("---")
    st.markdown("## Règles d'utilisation")
    st.markdown(
        "<div class='privacy-box'>"
        "✅ <strong>Aucun compte requis</strong> — Utilise StudyBoost "
        "instantanément, sans inscription<br>"
        "🔒 <strong>Session 100% anonyme</strong> — Aucune donnée personnelle "
        "collectée<br>"
        "🗑️ <strong>Données supprimées après 7 jours</strong> — Tes cours et "
        "messages sont automatiquement effacés<br>"
        "📊 <strong>Limites quotidiennes :</strong> 10 exports PDF, 15 messages "
        "chat, 15 recherches par jour<br>"
        "🚫 <strong>Aucune publicité ni revente</strong> — Ton contenu "
        "t'appartient, on ne le partage pas<br>"
        "💡 <strong>Ton avis compte</strong> — Laisse un feedback pour nous "
        "aider à améliorer l'outil !"
        "</div>",
        unsafe_allow_html=True,
    )

    # Random cleanup (1/50 chance)
    if random.randint(1, 50) == 1:
        cleanup_old_data(db)


if __name__ == "__main__":
    main()
