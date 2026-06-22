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
from services.ui_helpers import inject_css


def remaining(q: dict) -> int:
    return max(0, q["limit"] - q["used"])


def main():
    db = get_db()
    settings = get_settings()
    user = init_user_identity(db)

    if random.randint(1, 100) == 1:
        cleanup_old_data()

    dark_mode = st.session_state.get("dark_mode", False)
    inject_css(dark_mode=dark_mode)

    if settings.get("maintenance_mode") == "true":
        st.error("🔧 Application en maintenance. Revenez bientôt !")
        st.stop()

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
        st.caption("Ton espace est conservé 7 jours")
        st.markdown("---")

        dark_new = st.toggle("🌙 Mode nuit", value=dark_mode)
        if dark_new != dark_mode:
            st.session_state["dark_mode"] = dark_new
            st.rerun()

        st.markdown("---")
        quotas = get_user_quotas(user["id"], admin_bypass=is_admin())
        if quotas:
            st.markdown("### 📊 Tes quotas du jour")
            for key, emoji, label in [
                ("pdf", "📄", "PDF"),
                ("chat", "💬", "Messages"),
                ("search", "🔍", "Recherches"),
                ("ai", "✨", "IA"),
            ]:
                q = quotas[key]
                pct = q["used"] / q["limit"] if q["limit"] > 0 else 0
                remaining_qty = remaining(q)
                st.caption(f"{emoji} {label} : {remaining_qty}/{q['limit']}")
                if remaining_qty <= 0:
                    st.caption(f"❌ Épuisé — reviens demain")
                st.progress(pct)

        st.markdown("---")
        if st.button("🔄 Nouvelle identité", use_container_width=True):
            logout()

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
            "<li>📥 Export Markdown illimité</li></ul></div>",
            unsafe_allow_html=True,
        )
        if st.button("📝 Ouvrir l'éditeur", use_container_width=True, type="primary"):
            st.switch_page("pages/1_Editeur.py")

    with col_b:
        st.markdown(
            '<div class="card"><h3>💬 Chat IA</h3>'
            "<p>Pose des questions, l'IA répond avec ou sans contexte</p>"
            "<ul>"
            "<li>💬 Chat fluide et naturel</li>"
            "<li>📋 Colle ton cours pour des réponses ciblées</li>"
            "<li>🌐 Recherche web intégrée</li>"
            "<li>🤖 4 modèles IA au choix</li>"
            "<li>💾 Historique sauvegardé 7 jours</li></ul></div>",
            unsafe_allow_html=True,
        )
        if st.button("💬 Ouvrir le chat", use_container_width=True, type="primary"):
            st.switch_page("pages/2_Chat.py")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<div class="privacy-box">'
        '<div style="font-weight:700;color:#166534;margin-bottom:0.5rem;">🔒 Tes données sont protégées</div>'
        '<div class="privacy-item">✅ Aucun compte requis — accès direct</div>'
        '<div class="privacy-item">🆔 Identité anonyme (alias mignon)</div>'
        '<div class="privacy-item">🗑️ Toutes tes données sont supprimées après 7 jours</div>'
        '<div class="privacy-item">🚫 Zéro publicité · Zéro revente de données</div>'
        '<div class="privacy-item">💡 Tes feedbacks nous aident à améliorer l\'app</div></div>',
        unsafe_allow_html=True,
    )

    col_f1, col_f2, col_f3 = st.columns([1, 2, 1])
    with col_f2:
        if st.button("💡 Laisser mon avis", use_container_width=True):
            st.switch_page("pages/3_Feedback.py")


if __name__ == "__main__":
    main()
