"""StudyBoost AI — Page d'accueil avec identité persistante."""
import os
import random

from dotenv import load_dotenv
import streamlit as st

load_dotenv()

st.set_page_config(
    page_title="StudyBoost AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

from services.database import get_db, get_settings, get_user_quotas, cleanup_old_data
from services.identity import init_user_identity, get_user_alias, logout, is_admin
from services.ui_helpers import inject_css, show_quota_sidebar


def main():
    db = get_db()
    settings = get_settings()
    user = init_user_identity(db)
    retention_days = settings.get("retention_days", "7")

    if random.randint(1, 100) == 1:
        cleanup_old_data()

    dark_mode = st.session_state.get("dark_mode", False)
    inject_css(dark_mode=dark_mode)

    if settings.get("maintenance_mode", "false") == "true":
        st.warning("🔧 **Maintenance en cours** — certaines fonctionnalités peuvent être indisponibles. Reviens bientôt !")

    msg = settings.get("global_message", "")
    if msg:
        st.info(f"📢 {msg}")

    with st.sidebar:
        alias = user["alias"]
        st.markdown(f"### {alias['display']}")
        if user.get("is_returning"):
            st.caption("👋 Bon retour parmi nous !")
        else:
            st.caption("🎉 Bienvenue !")
        st.caption(f"Ton espace est conservé {retention_days} jours")
        st.markdown("---")

        dark_new = st.toggle("🌙 Mode nuit", value=dark_mode)
        if dark_new != dark_mode:
            st.session_state["dark_mode"] = dark_new
            st.rerun()

        st.markdown("---")
        quotas = get_user_quotas(user["id"], admin_bypass=is_admin())
        if quotas:
            show_quota_sidebar(quotas)

        st.markdown("---")
        if st.session_state.get("confirm_new_id"):
            st.warning("⚠️ Cette action supprime ton historique de la session.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Oui, nouvelle identité", use_container_width=True, type="primary"):
                    st.session_state["confirm_new_id"] = False
                    logout()
            with c2:
                if st.button("❌ Annuler", use_container_width=True):
                    st.session_state["confirm_new_id"] = False
                    st.rerun()
        elif st.button("🔄 Nouvelle identité", use_container_width=True):
            st.session_state["confirm_new_id"] = True
            st.rerun()

    st.markdown(
        '<h1 class="gradient-title">🎓 StudyBoost AI</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="text-align:center;color:#64748B;font-size:1.2rem;">'
        "Ton assistant de révision intelligent — 100% gratuit"
        "</p>",
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="text-align:center;"><span class="badge">BETA</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown("<br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(
            '<div class="step-container"><div class="step-emoji">📋</div>'
            '<div class="step-title">1. Colle ton cours</div>'
            '<div class="step-desc">Texte, Markdown, notes...</div></div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            '<div class="step-container"><div class="step-emoji">🤖</div>'
            '<div class="step-title">2. L\'IA transforme</div>'
            '<div class="step-desc">Résumé, fiche, quiz...</div></div>',
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            '<div class="step-container"><div class="step-emoji">📥</div>'
            '<div class="step-title">3. Exporte et révise</div>'
            '<div class="step-desc">PDF ou Markdown</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br><br>", unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(
            '<div class="card"><h3>📝 Éditeur Markdown</h3>'
            "<p>Éditeur professionnel avec preview en temps réel</p>"
            "<ul>"
            "<li>✏️ Édition Markdown live</li>"
            "<li>👁️ Preview à droite</li>"
            "<li>🤖 Transformations IA (résumé, fiche, quiz)</li>"
            "<li>📄 Export PDF avec logo</li>"
            "<li>📥 Export Markdown illimité</li></ul>"
            '<div style="margin-top:1.5rem;">',
            unsafe_allow_html=True,
        )
        if st.button("📝 Ouvrir l'éditeur", use_container_width=True, type="primary"):
            st.switch_page("pages/1_Editeur.py")
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_b:
        st.markdown(
            '<div class="card"><h3>💬 Chat IA</h3>'
            "<p>Pose des questions, l'IA répond avec ou sans contexte</p>"
            "<ul>"
            "<li>💬 Chat fluide et naturel</li>"
            "<li>📋 Colle ton cours pour des réponses ciblées</li>"
            "<li>🌐 Recherche web intégrée</li>"
            "<li>🤖 4 modèles IA au choix</li>"
            "<li>💾 Historique sauvegardé 7 jours</li></ul>"
            '<div style="margin-top:1.5rem;">',
            unsafe_allow_html=True,
        )
        if st.button("💬 Ouvrir le chat", use_container_width=True, type="primary"):
            st.switch_page("pages/2_Chat.py")
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div style="margin:2rem 0;"></div>', unsafe_allow_html=True)

    col_fb1, col_fb2 = st.columns(2)
    with col_fb1:
        st.markdown(
            '<div class="card" style="height:100%;">'
            '<h3>💡 Laisser mon avis</h3>'
            "<p>Partage ton expérience et aide-nous à améliorer StudyBoost AI</p>"
            "<ul>"
            "<li>⭐ Note l'application</li>"
            "<li>💬 Propose des idées</li>"
            "<li>📧 Laisse ton email (optionnel)</li>"
            "</ul>"
            '<div style="margin-top:1.5rem;">',
            unsafe_allow_html=True,
        )
        if st.button("💡 Donner mon avis", use_container_width=True, type="primary"):
            st.switch_page("pages/3_Feedback.py")
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with col_fb2:
        st.markdown(
            '<div class="card" style="height:100%;">'
            '<h3>🔒 Tes données sont protégées</h3>'
            "<ul>"
            "<li>✅ Aucun compte requis — accès direct</li>"
            "<li>🆔 Identité anonyme (alias mignon)</li>"
            f"<li>🗑️ Données supprimées après {retention_days} jours</li>"
            "<li>🚫 Zéro publicité · Zéro revente</li>"
            "<li>💡 Les feedbacks améliorent l'app</li>"
            "</ul></div>",
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
