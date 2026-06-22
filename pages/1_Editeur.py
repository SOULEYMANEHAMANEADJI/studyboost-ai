"""Éditeur de révision — Mode direct + Transformation IA."""
from __future__ import annotations

from datetime import datetime

import streamlit as st
from services.ai import AVAILABLE_MODELS, format_text, DEFAULT_MODEL
from services.database import get_db, get_settings, log_activity, use_quota
from services.session_manager import get_session_id, init_session, get_quota, get_model_quota, consume_model_quota
from services.pdf_generator import markdown_to_pdf, generate_default_title
from services.ui_helpers import inject_css, show_quota_sidebar, show_feature_disabled, quota_warning

st.set_page_config(page_title="Éditeur - StudyBoost AI", page_icon="📝", layout="wide")

TRANSFORMATIONS = {
    "📄 Résumer": "resume",
    "🧒 Simplifier": "simplify",
    "📋 Fiche de révision": "fiche",
    "🎓 Style académique": "academic",
    "📌 Points clés": "bullet_points",
    "❓ Quiz": "quiz",
}


def main():
    dark_mode = st.sidebar.toggle("🌙 Mode nuit", value=False, key="editor_dark")
    inject_css(dark_mode)

    db = get_db()
    settings = get_settings(db)
    session_id = get_session_id()
    init_session(db, settings)
    quotas = get_quota(db, session_id, settings)

    pdf_enabled = settings.get("feature_pdf_enabled", "true").lower() == "true"
    md_enabled = settings.get("feature_md_enabled", "true").lower() == "true"

    # Sidebar
    with st.sidebar:
        st.markdown("## 📝 Éditeur")
        st.markdown("---")
        doc_title = st.text_input("Nom du fichier", value=generate_default_title())
        st.markdown("---")

        st.markdown("### 🤖 Modèle IA")
        model_choice = st.selectbox(
            "Choisir le modèle",
            options=list(AVAILABLE_MODELS.keys()),
            index=0,
            key="editor_model",
            help="Llama 8B pour la vitesse, Llama 70B pour la qualité.",
        )
        selected_model = AVAILABLE_MODELS[model_choice]
        st.session_state["editor_model"] = selected_model

        model_enabled = settings.get(f"model_enabled_{selected_model}", "true").lower() == "true"
        if not model_enabled:
            st.warning("🔇 Modèle désactivé par l'administrateur.")
        else:
            mq = get_model_quota(db, session_id, selected_model, settings)
            st.caption(f"📊 {mq['remaining']}/{mq['limit']} utilisations aujourd'hui")
        st.markdown("---")

        show_quota_sidebar(quotas)
        st.markdown("---")
        if not pdf_enabled:
            show_feature_disabled("Export PDF")

    # Titre
    st.markdown("<h1 class='gradient-title'>📝 Éditeur de révision</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p class='subtitle'>Colle ton texte, transforme-le avec l'IA ou édite-le directement.</p>",
        unsafe_allow_html=True,
    )

    # Étape 1 : Zone de saisie
    source_text = st.text_area(
        "📋 Colle ton texte ici",
        height=200,
        placeholder="Colle du texte brut, du Markdown, des notes de cours…",
        key="source_text",
    )

    if source_text:
        st.caption(f"{len(source_text.split())} mots · {len(source_text)} caractères")

    # Étape 2 : Choix du mode
    mode = st.radio(
        "Mode",
        ["✨ Transformer avec l'IA", "✏️ Éditer directement"],
        horizontal=True,
    )

    if mode == "✨ Transformer avec l'IA":
        st.markdown("### Choisis une transformation")
        cols = st.columns(3)
        selected_style = None
        for i, (label, style) in enumerate(TRANSFORMATIONS.items()):
            with cols[i % 3]:
                if st.button(label, use_container_width=True, key=f"btn_{style}"):
                    selected_style = style

        model_enabled = settings.get(f"model_enabled_{selected_model}", "true").lower() == "true"

        if selected_style and source_text:
            if not model_enabled:
                st.error(f"🔇 Le modèle **{model_choice}** est désactivé par l'administrateur.")
            else:
                with st.spinner("🤖 L'IA transforme ton texte…"):
                    try:
                        result = format_text(source_text, selected_style, model=selected_model)
                        st.session_state["result_text"] = result
                        consume_model_quota(db, session_id, selected_model)
                        log_activity(db, session_id, "editor_transform", f"style={selected_style}")
                    except Exception as e:
                        st.error(f"Erreur IA : {e}")
        elif selected_style and not source_text:
            st.warning("Colle d'abord ton texte dans la zone ci-dessus.")
    else:
        # Mode direct : le texte collé va directement dans l'édition
        if source_text:
            st.session_state["result_text"] = source_text

    # Étape 3 : Zone d'édition + preview
    if "result_text" in st.session_state and st.session_state["result_text"]:
        tab_edit, tab_preview = st.tabs(["✏️ Éditer", "👁️ Prévisualiser"])

        with tab_edit:
            edited = st.text_area(
                "Édite ton texte",
                value=st.session_state["result_text"],
                height=400,
                key="final_edited_text",
            )

        with tab_preview:
            display = st.session_state.get("final_edited_text", st.session_state["result_text"])
            st.markdown(display)

        final_text = st.session_state.get("final_edited_text", st.session_state["result_text"])

        # Étape 4 : Export
        st.markdown("---")
        st.markdown("### 📤 Exporter")

        col1, col2, col3 = st.columns(3)

        with col1:
            if md_enabled:
                st.download_button(
                    "📥 Télécharger .md",
                    data=final_text.encode("utf-8"),
                    file_name=f"{doc_title}.md",
                    mime="text/markdown",
                    use_container_width=True,
                    type="primary",
                )
            else:
                st.button("📥 Markdown désactivé", disabled=True, use_container_width=True)

        with col2:
            if pdf_enabled:
                if quotas["pdf"]["remaining"] > 0:
                    if st.button("📄 Générer PDF", use_container_width=True, type="primary"):
                        with st.spinner("Génération du PDF…"):
                            try:
                                pdf_bytes = markdown_to_pdf(
                                    final_text, title=doc_title, logo_path="assets/logo.png"
                                )
                                use_quota(db, session_id, "pdf")
                                log_activity(db, session_id, "pdf_export", doc_title)
                                st.session_state["pdf_bytes"] = pdf_bytes
                                st.session_state["pdf_title"] = doc_title
                                st.success(f"✅ PDF prêt : {doc_title}.pdf")
                            except Exception as e:
                                st.error(f"Erreur PDF : {e}")
                    if st.session_state.get("pdf_bytes"):
                        st.download_button(
                            "⬇️ Télécharger le PDF",
                            data=st.session_state["pdf_bytes"],
                            file_name=f"{st.session_state.get('pdf_title', 'document')}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )
                else:
                    st.button(
                        f"📄 PDF (limite atteinte)",
                        disabled=True,
                        use_container_width=True,
                    )
                    st.caption("Limite quotidienne atteinte. Reviens demain !")
            else:
                st.button("📄 PDF désactivé", disabled=True, use_container_width=True)

        with col3:
            st.text_area("📋 Copier le texte", value=final_text, height=100, key="copy_box")
            st.caption("Sélectionne tout et copie (Ctrl+A, Ctrl+C)")


if __name__ == "__main__":
    main()
