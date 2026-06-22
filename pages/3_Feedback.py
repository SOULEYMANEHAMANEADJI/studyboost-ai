"""Feedback — formulaire d'avis utilisateur."""
from __future__ import annotations

import streamlit as st
from services.database import get_db, get_settings, save_feedback
from services.session_manager import get_session_id, init_session
from services.ui_helpers import inject_css

st.set_page_config(page_title="Avis - StudyBoost AI", page_icon="💡", layout="centered")

FEATURES = [
    "📄 Import de fichiers PDF",
    "🃏 Flashcards et cartes mémoire",
    "📅 Planning de révision",
    "⏱️ Mode examen chronométré",
    "🔊 Résumé audio",
    "🌍 Multi-langues",
    "📚 Historique des documents",
    "👥 Partage de fiches",
    "📱 Application mobile",
    "🔗 Intégration Notion et Google Drive",
]


def main():
    dark_mode = st.sidebar.toggle("🌙 Mode nuit", value=False, key="fb_dark")
    inject_css(dark_mode)

    db = get_db()
    settings = get_settings(db)
    session_id = get_session_id()
    init_session(db, settings)

    st.markdown("<h1 class='gradient-title'>💡 Donne ton avis</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p class='subtitle'>Tes retours nous aident à améliorer StudyBoost AI. Chaque suggestion compte !</p>",
        unsafe_allow_html=True,
    )

    already_sent = st.session_state.get("feedback_sent", False)

    with st.form("feedback_form", clear_on_submit=False):
        rating = st.slider(
            "Note globale",
            min_value=1, max_value=5, value=3, format="%d ⭐",
            disabled=already_sent,
        )
        rating_labels = {1: "😞 Pas top", 2: "🙁 Bof", 3: "😊 Bien", 4: "🤩 Super", 5: "🔥 Excellent"}
        st.caption(rating_labels.get(rating, ""))

        st.markdown("---")

        comment = st.text_area(
            "💬 Ton commentaire",
            placeholder="Dis-nous ce que tu penses…",
            max_chars=2000, height=150,
            disabled=already_sent,
        )

        st.markdown("---")

        feature_request = st.multiselect(
            "🚀 Quelles fonctionnalités aimerais-tu voir ?",
            options=FEATURES,
            disabled=already_sent,
        )

        other_idea = st.text_input(
            "💭 Autre idée ?",
            placeholder="Une fonctionnalité qui n'est pas dans la liste ?",
            disabled=already_sent,
        )

        email = st.text_input(
            "📧 Email (optionnel)",
            placeholder="Pour être prévenu du lancement premium…",
            disabled=already_sent,
        )
        st.caption("Optionnel — seulement si tu veux être prévenu du lancement premium.")

        submitted = st.form_submit_button(
            "💌 Envoyer mon avis",
            disabled=already_sent,
            use_container_width=True,
            type="primary",
        )

        if submitted and not already_sent:
            if not comment.strip() and not other_idea.strip() and rating == 3:
                st.warning("Ajoute au moins un commentaire ou une idée.")
            else:
                ok = save_feedback(
                    db, session_id, rating, comment,
                    ",".join(feature_request) if feature_request else "",
                    other_idea, email,
                )
                if ok:
                    st.session_state["feedback_sent"] = True
                    st.success("🎉 Merci infiniment pour ton retour !")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("Une erreur est survenue. Réessaie plus tard.")

    st.markdown("---")
    st.markdown(
        "<div class='privacy-box'>"
        "🔒 <strong>Tes données sont anonymes.</strong> Aucun nom, prénom ou email "
        "n'est obligatoire."
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
