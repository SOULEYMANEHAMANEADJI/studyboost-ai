"""StudyBoost AI — Page d'accueil."""
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
from services.session_manager import get_session_id, init_session, get_quota
from services.ui_helpers import inject_css, show_quota_sidebar


def main():
    inject_css()

    try:
        db = get_db()
    except RuntimeError as e:
        st.error(str(e))
        st.stop()

    settings = get_settings(db)
    session_id = get_session_id()

    # Mode maintenance
    if settings.get("maintenance_mode", "false").lower() == "true":
        st.warning("🔧 StudyBoost AI est en maintenance. Reviens dans quelques instants !")
        st.stop()

    # Message admin global
    if (settings.get("global_message") or "").strip():
        st.info(settings["global_message"])

    init_session(db, settings)
    quotas = get_quota(db, session_id, settings)

    # Sidebar
    with st.sidebar:
        st.markdown("## 📚 StudyBoost AI")
        st.markdown("---")
        show_quota_sidebar(quotas)
        st.markdown("---")
        if st.button("💡 Laisser un avis", use_container_width=True):
            st.switch_page("pages/3_Feedback.py")
        st.markdown("---")
        st.markdown(
            "<div style='text-align:center;color:#64748B;font-size:0.8rem;'>"
            "Phase beta gratuite</div>",
            unsafe_allow_html=True,
        )

    # Hero
    st.markdown(
        "<div style='text-align:center;padding:2rem 0 0.5rem;'>"
        "<span class='badge'>BETA GRATUITE</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<h1 class='gradient-title'>🎓 StudyBoost AI</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p class='subtitle'>Ton assistant de révision intelligent — 100% gratuit · Sans compte</p>",
        unsafe_allow_html=True,
    )

    # Steps
    cols = st.columns(3)
    steps = [
        ("📋", "Colle ton cours", "Copie ton texte depuis n'importe quelle source."),
        ("🤖", "L'IA transforme", "Résumé, quiz, fiche, simplification… à toi de choisir !"),
        ("📥", "Exporte et révise", "Télécharge en PDF ou Markdown et étudie à ton rythme."),
    ]
    for col, (emoji, title, desc) in zip(cols, steps):
        with col:
            st.markdown(
                f"<div class='step-container'>"
                f"<div class='step-emoji'>{emoji}</div>"
                f"<div class='step-title'>{title}</div>"
                f"<div class='step-desc'>{desc}</div></div>",
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # Feature cards
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(
            "<div class='card'><h3>📝 Éditeur de révision</h3>"
            "<div class='feature-item'>✅ Résumer, simplifier, créer des fiches</div>"
            "<div class='feature-item'>✅ Quiz interactif et points clés</div>"
            "<div class='feature-item'>✅ Export PDF avec logo + pagination</div>"
            "<div class='feature-item'>✅ Export Markdown pour tes notes</div>"
            "<div class='feature-item'>📊 10 exports PDF par jour</div></div>",
            unsafe_allow_html=True,
        )
        if st.button("🚀 Ouvrir l'éditeur", key="btn_editeur", use_container_width=True, type="primary"):
            st.switch_page("pages/1_Editeur.py")
    with col_b:
        st.markdown(
            "<div class='card'><h3>💬 Chat IA</h3>"
            "<div class='feature-item'>✅ Pose des questions sur ton cours</div>"
            "<div class='feature-item'>✅ Recherche web intégrée</div>"
            "<div class='feature-item'>✅ Fonctionne même sans texte</div>"
            "<div class='feature-item'>✅ Assistant étudiant général</div>"
            "<div class='feature-item'>📊 15 messages par jour</div></div>",
            unsafe_allow_html=True,
        )
        if st.button("💬 Ouvrir le chat", key="btn_chat", use_container_width=True, type="primary"):
            st.switch_page("pages/2_Chat.py")

    # Privacy section
    st.markdown("---")
    st.markdown("<h2 style='text-align:center;'>🔒 Tes données sont protégées</h2>", unsafe_allow_html=True)
    st.markdown(
        "<div class='privacy-box'>"
        "<div class='privacy-item'>✅ Aucun compte requis — utilise directement</div>"
        "<div class='privacy-item'>🗑️ Données supprimées après 7 jours automatiquement</div>"
        "<div class='privacy-item'>📊 10 PDF / 15 messages / 15 recherches par jour</div>"
        "<div class='privacy-item'>🚫 Zéro publicité, zéro revente de données</div>"
        "<div class='privacy-item'>🔒 100% anonyme — aucun email demandé</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    # Beta feedback
    st.markdown(
        "<div style='text-align:center;padding:1.5rem;background:linear-gradient(135deg,#EEF2FF,#E0E7FF);"
        "border-radius:16px;margin:1.5rem 0;'>"
        "<p style='font-size:1.1rem;color:#4338CA;font-weight:700;'>💡 Cette app est en beta gratuite</p>"
        "<p style='color:#475569;'>Ton avis nous aide à l'améliorer !</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    if st.button("Donner mon avis", use_container_width=True, type="primary"):
        st.switch_page("pages/3_Feedback.py")

    # Cleanup 1/50
    if random.randint(1, 50) == 1:
        cleanup_old_data(db)


if __name__ == "__main__":
    main()
