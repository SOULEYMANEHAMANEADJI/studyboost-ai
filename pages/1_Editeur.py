"""StudyBoost AI - Editor page."""
from __future__ import annotations

from datetime import datetime

import streamlit as st
from services.database import get_db, get_settings, log_activity
from services.session_manager import get_session_id, init_session, get_quota, consume_quota
from services.ai import format_text
from services.pdf_generator import markdown_to_pdf, generate_default_title
from services.ui import inject_css, render_quota_sidebar

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
    inject_css()
    db = get_db()
    settings = get_settings(db)
    session_id = get_session_id()
    init_session(db, settings)

    pdf_enabled = settings.get("feature_pdf_enabled", "true").lower() == "true"
    md_enabled = settings.get("feature_md_enabled", "true").lower() == "true"

    with st.sidebar:
        st.markdown("## 📝 Éditeur de révision")
        st.sidebar.markdown("---")
        file_name = st.sidebar.text_input(
            "Nom du fichier",
            value=generate_default_title(),
            placeholder="Mon_cours",
        )
        st.sidebar.markdown("---")
        quotas = get_quota(db, session_id, settings)
        pdf_remaining = quotas["pdf"]["remaining"]
        pdf_limit = quotas["pdf"]["limit"]
        pdf_used = quotas["pdf"]["used"]
        pdf_pct = int((pdf_used / pdf_limit) * 100) if pdf_limit else 0
        st.sidebar.markdown("#### 📊 Quota PDF")
        st.sidebar.progress(min(pdf_pct, 100), text=f"{pdf_remaining} restant(s)")
        if not pdf_enabled:
            st.sidebar.warning("L'export PDF est désactivé par l'administrateur.")
        st.sidebar.markdown("---")
        render_quota_sidebar(db, session_id, settings)

    st.markdown("<h1 class='gradient-title'>📝 Éditeur de révision</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align:center;color:#64748B;'>Colle ton texte, choisis une "
        "transformation IA, édite et exporte.</p>",
        unsafe_allow_html=True,
    )

    # Main text input
    user_input = st.text_area(
        "✏️ Colle ton cours ici",
        height=220,
        placeholder="Colle ton cours, article ou notes ici... (max 15 000 caractères)",
        max_chars=15000,
        key="editor_input",
    )

    # Word/char counter
    if user_input:
        words = len(user_input.split())
        chars = len(user_input)
        st.caption(f"{words} mots · {chars} caractères")
    else:
        st.caption("0 mots · 0 caractères")

    # Transformation buttons
    st.markdown("### Choisis une transformation")
    cols = st.columns(3)
    selected_style = None
    for i, (label, style) in enumerate(TRANSFORMATIONS.items()):
        with cols[i % 3]:
            if st.button(label, use_container_width=True, key=f"btn_{style}"):
                selected_style = style

    # Process transformation
    result = st.session_state.get("editor_result", "")
    if selected_style and user_input:
        with st.spinner("🤖 L'IA transforme ton texte..."):
            try:
                result = format_text(user_input, selected_style)
                st.session_state["editor_result"] = result
                log_activity(
                    db, session_id, "editor_transform",
                    f"style={selected_style}, chars={len(user_input)}"
                )
            except Exception as e:
                st.error(f"Erreur lors de la génération : {e}")
                st.session_state["editor_result"] = ""
    elif selected_style and not user_input:
        st.warning("Colle d'abord ton texte dans la zone ci-dessus.")

    # Display result
    if st.session_state.get("editor_result"):
        tab_edit, tab_preview = st.tabs(["✏️ Éditer", "👁️ Prévisualiser"])
        with tab_edit:
            edited = st.text_area(
                "Texte éditable",
                value=st.session_state["editor_result"],
                height=350,
                key="edit_area",
            )
            if edited != st.session_state["editor_result"]:
                st.session_state["editor_result"] = edited

        with tab_preview:
            st.markdown(st.session_state["editor_result"])

        # Export section
        st.markdown("---")
        st.markdown("### 📤 Exporter")
        exp_col1, exp_col2, exp_col3 = st.columns(3)
        final_text = st.session_state["editor_result"]
        file_title = file_name or generate_default_title()

        with exp_col1:
            if md_enabled:
                st.download_button(
                    "📄 Télécharger .md",
                    data=final_text.encode("utf-8"),
                    file_name=f"{file_title}.md",
                    mime="text/markdown",
                    use_container_width=True,
                    on_click=lambda: log_activity(
                        db, session_id, "export_md",
                        f"file={file_title}.md"
                    ),
                )
            else:
                st.info("Export Markdown désactivé")

        with exp_col2:
            if pdf_enabled:
                if st.button("📕 Générer PDF", use_container_width=True):
                    if quotas["pdf"]["remaining"] <= 0:
                        st.error("Quota PDF atteint pour aujourd'hui ! Reviens demain.")
                    else:
                        with st.spinner("Génération du PDF..."):
                            try:
                                success, msg = consume_quota(db, session_id, "pdf")
                                if not success:
                                    st.error(msg)
                                else:
                                    logo_path = "assets/logo.png"
                                    pdf_bytes = markdown_to_pdf(
                                        final_text, title=file_title, logo_path=logo_path
                                    )
                                    st.session_state["pdf_bytes"] = pdf_bytes
                                    st.session_state["pdf_file_title"] = file_title
                                    log_activity(
                                        db, session_id, "export_pdf",
                                        f"file={file_title}.pdf"
                                    )
                                    st.success("PDF généré avec succès !")
                            except Exception as e:
                                st.error(f"Erreur PDF : {e}")

                if st.session_state.get("pdf_bytes"):
                    st.download_button(
                        "📕 Télécharger PDF",
                        data=st.session_state["pdf_bytes"],
                        file_name=f"{st.session_state.get('pdf_file_title', 'document')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
            else:
                st.info("Export PDF désactivé")

        with exp_col3:
            st.text_area(
                "📋 Copier le texte",
                value=final_text,
                height=200,
                key="copy_area",
            )
            st.caption("Sélectionne et copie (Ctrl+C / Cmd+C)")


if __name__ == "__main__":
    main()
