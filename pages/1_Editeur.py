"""
Éditeur Markdown avec preview en temps réel.
Layout : éditeur à gauche + preview à droite.
"""
import streamlit as st
from services.ai import AVAILABLE_MODELS, format_text, DEFAULT_MODEL
from services.database import get_db, get_settings, log_activity, use_quota
from services.session_manager import init_session, get_quota
from services.pdf_generator import markdown_to_pdf, generate_default_title
from services.ui_helpers import inject_css


def _render_markdown_html(text: str, dark_mode: bool = False) -> str:
    import markdown as md_lib

    html = md_lib.markdown(text, extensions=["fenced_code", "tables", "nl2br"])

    text_color = "#F1F5F9" if dark_mode else "#1E293B"
    primary = "#A5B4FC" if dark_mode else "#4F46E5"
    secondary = "#C4B5FD" if dark_mode else "#7C3AED"
    border = "#334155" if dark_mode else "#E2E8F0"
    code_bg = "#1E293B" if dark_mode else "#F1F5F9"
    quote_bg = "#1E293B" if dark_mode else "#F8FAFC"

    return f"""
    <style>
    .preview-content {{ color: {text_color}; font-family: 'Inter', sans-serif; line-height: 1.6; }}
    .preview-content h1 {{ color: {text_color}; font-size: 1.8rem; font-weight: 800; margin-top: 0.5rem; border-bottom: 2px solid {primary}; padding-bottom: 0.3rem; }}
    .preview-content h2 {{ color: {primary}; font-size: 1.4rem; font-weight: 700; margin-top: 1rem; }}
    .preview-content h3 {{ color: {text_color}; font-size: 1.15rem; font-weight: 700; margin-top: 0.8rem; }}
    .preview-content p {{ margin: 0.5rem 0; }}
    .preview-content ul, .preview-content ol {{ margin: 0.5rem 0; padding-left: 1.5rem; }}
    .preview-content li {{ margin: 0.2rem 0; }}
    .preview-content code {{ background: {code_bg}; color: {secondary}; padding: 2px 6px; border-radius: 4px; font-size: 0.9rem; }}
    .preview-content pre {{ background: {code_bg}; padding: 12px; border-radius: 8px; overflow-x: auto; }}
    .preview-content blockquote {{ border-left: 4px solid {primary}; background: {quote_bg}; padding: 8px 16px; margin: 0.5rem 0; border-radius: 4px; }}
    .preview-content strong {{ color: {primary}; }}
    .preview-content hr {{ border: none; border-top: 1px solid {border}; margin: 1rem 0; }}
    .preview-content table {{ border-collapse: collapse; width: 100%; margin: 0.5rem 0; }}
    .preview-content th, .preview-content td {{ border: 1px solid {border}; padding: 8px; text-align: left; }}
    .preview-content th {{ background: {code_bg}; }}
    </style>
    <div class="preview-content">{html}</div>
    """


st.set_page_config(
    page_title="Éditeur — StudyBoost AI",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="collapsed",
)

MAX_CHARS = 15000

db = get_db()
settings = get_settings(db)
session_id = st.session_state.setdefault("session_id", __import__("uuid").uuid4().hex)
init_session(db, settings)

dark_mode = st.session_state.get("dark_mode", False)
inject_css(dark_mode=dark_mode)

# ============================================
# SIDEBAR — Options minimales
# ============================================
with st.sidebar:
    st.markdown("### ⚙️ Options")

    dark_mode_new = st.toggle("🌙 Mode nuit", value=dark_mode, key="dark_mode_toggle")
    if dark_mode_new != dark_mode:
        st.session_state["dark_mode"] = dark_mode_new
        st.rerun()

    st.markdown("---")

    st.markdown("### 🤖 Modèle IA")
    model_name = st.selectbox(
        "Modèle",
        options=list(AVAILABLE_MODELS.keys()),
        index=0,
        label_visibility="collapsed",
    )
    selected_model = AVAILABLE_MODELS[model_name]

    st.markdown("---")

    quotas = get_quota(db, session_id, settings)
    st.markdown("### 📊 Quotas du jour")
    pdf_limit = quotas["pdf"]["limit"]
    pdf_used = quotas["pdf"]["used"]
    st.caption(f"📄 PDF : {quotas['pdf']['remaining']}/{pdf_limit}")
    st.progress(pdf_used / pdf_limit if pdf_limit > 0 else 0)
    st.caption("📥 Markdown : illimité")

# ============================================
# HEADER — Nom doc + bouton download
# ============================================
col_title, col_name, col_download = st.columns([1, 2, 1.5])

with col_title:
    st.markdown(
        '<div style="display:flex;align-items:center;gap:10px;padding-top:10px;">'
        '<span style="font-size:1.8rem;">🎓</span>'
        '<span style="font-size:1.3rem;font-weight:800;background:linear-gradient(135deg,#4F46E5,#7C3AED);'
        "-webkit-background-clip:text;-webkit-text-fill-color:transparent;"
        '">StudyBoost</span>'
        "</div>",
        unsafe_allow_html=True,
    )

with col_name:
    if "doc_title" not in st.session_state:
        st.session_state["doc_title"] = generate_default_title()
    doc_title = st.text_input(
        "Nom du document",
        value=st.session_state["doc_title"],
        label_visibility="collapsed",
        placeholder="Nom du document...",
        key="doc_title_input",
    )
    st.session_state["doc_title"] = doc_title

with col_download:
    download_format = st.selectbox(
        "Format",
        ["📥 Télécharger en .MD", "📄 Télécharger en .PDF"],
        label_visibility="collapsed",
        key="download_format",
    )

st.markdown(
    '<div style="border-bottom:1px solid #E2E8F0;margin:10px 0 20px 0;"></div>',
    unsafe_allow_html=True,
)

# ============================================
# LAYOUT PRINCIPAL — Éditeur | Preview
# ============================================
if "editor_text" not in st.session_state:
    st.session_state["editor_text"] = """# Bienvenue sur StudyBoost AI 🎓

Commence à **écrire ton Markdown** ici ou colle ton cours.

## Fonctionnalités

- ✏️ Éditeur Markdown avec preview en temps réel
- 📄 Export PDF professionnel avec logo
- 📥 Export Markdown
- 🤖 Transformation par IA (résumé, fiche, quiz...)

## Comment ça marche ?

1. Colle ton texte ou édite ici
2. Le **preview** s'affiche à droite en temps réel
3. Clique sur **Télécharger** quand tu es prêt

---

> 💡 Astuce : utilise les boutons IA en bas pour transformer ton texte automatiquement.
"""

col_editor, col_preview = st.columns([1, 1], gap="medium")

# ---------- COLONNE ÉDITEUR ----------
with col_editor:
    st.markdown(
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
        '<span style="font-weight:700;color:#4F46E5;">✏️ ÉDITEUR</span>'
        '<span style="color:#94A3B8;font-size:0.85rem;">— Markdown</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    editor_text = st.text_area(
        "Éditeur",
        value=st.session_state["editor_text"],
        height=550,
        max_chars=MAX_CHARS,
        label_visibility="collapsed",
        key="editor_textarea",
        placeholder="Tape ou colle ton Markdown ici...",
    )

    st.session_state["editor_text"] = editor_text

    chars = len(editor_text)
    words = len(editor_text.split())
    pct = (chars / MAX_CHARS) * 100

    if pct > 90:
        color = "#EF4444"
    elif pct > 70:
        color = "#F59E0B"
    else:
        color = "#64748B"

    st.markdown(
        f'<div style="display:flex;justify-content:space-between;font-size:0.85rem;color:{color};margin-top:5px;">'
        f"<span>📊 {chars:,} / {MAX_CHARS:,} caractères</span>"
        f"<span>📝 {words:,} mots</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

# ---------- COLONNE PREVIEW ----------
with col_preview:
    st.markdown(
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
        '<span style="font-weight:700;color:#7C3AED;">👁️ PREVIEW</span>'
        '<span style="color:#94A3B8;font-size:0.85rem;">— Rendu en temps réel</span>'
        "</div>",
        unsafe_allow_html=True,
    )

    preview_bg = "#0F172A" if dark_mode else "#FFFFFF"
    preview_color = "#F1F5F9" if dark_mode else "#1E293B"
    border_color = "#334155" if dark_mode else "#E2E8F0"

    st.markdown(
        f'<div style="height:550px;overflow-y:auto;padding:20px;'
        f"border:1px solid {border_color};border-radius:8px;"
        f"background:{preview_bg};color:{preview_color};" 
        f'">{_render_markdown_html(editor_text, dark_mode)}'
        f"</div>",
        unsafe_allow_html=True,
    )

# ============================================
# ACTION DOWNLOAD
# ============================================
st.markdown('<div style="margin:20px 0;"></div>', unsafe_allow_html=True)

col_dl1, col_dl2, col_dl3 = st.columns([1, 2, 1])
with col_dl2:
    if download_format == "📥 Télécharger en .MD":
        if settings.get("feature_md_enabled", "true") == "true":
            st.download_button(
                "📥 Télécharger en Markdown",
                data=editor_text.encode("utf-8"),
                file_name=f"{doc_title}.md",
                mime="text/markdown",
                use_container_width=True,
                type="primary",
            )
        else:
            st.warning("⚠️ Export Markdown temporairement désactivé")
    else:
        pdf_enabled = settings.get("feature_pdf_enabled", "true") == "true"
        if pdf_enabled:
            if quotas["pdf"]["remaining"] > 0:
                gen_btn = st.button(
                    "📄 Générer et télécharger le PDF",
                    use_container_width=True,
                    type="primary",
                )
                if gen_btn:
                    with st.spinner("📄 Génération du PDF..."):
                        try:
                            pdf_bytes = markdown_to_pdf(
                                text=editor_text,
                                title=doc_title,
                                logo_path="assets/logo.png",
                            )
                            use_quota(db, session_id, "pdf")
                            log_activity(db, session_id, "pdf_export", doc_title)
                            st.session_state["pdf_bytes"] = pdf_bytes
                            st.session_state["pdf_title"] = doc_title
                        except Exception as e:
                            st.error(f"❌ Erreur lors de la génération : {e}")

                if st.session_state.get("pdf_bytes"):
                    st.download_button(
                        "⬇️ Télécharger le PDF",
                        data=st.session_state["pdf_bytes"],
                        file_name=f"{st.session_state.get('pdf_title', 'document')}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
            else:
                st.error(f"❌ Limite atteinte ({pdf_limit} PDF/jour). Reviens demain !")
        else:
            st.warning("⚠️ Export PDF temporairement désactivé")

# ============================================
# SECTION IA — Boutons en bas
# ============================================
st.markdown(
    '<div style="margin:30px 0 10px 0;border-top:1px solid #E2E8F0;padding-top:20px;"></div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div style="text-align:center;margin-bottom:15px;">'
    '<span style="font-weight:700;color:#4F46E5;font-size:1.1rem;">✨ Transformer avec l\'IA</span>'
    '<br><span style="color:#64748B;font-size:0.85rem;">Optionnel — choisis une action ci-dessous</span>'
    "</div>",
    unsafe_allow_html=True,
)

ia_actions = [
    ("📄 Résumer", "resume"),
    ("🧒 Simplifier", "simplify"),
    ("📋 Fiche", "fiche"),
    ("🎓 Académique", "academic"),
    ("📌 Points clés", "bullet_points"),
    ("❓ Quiz", "quiz"),
]

cols = st.columns(6)
for col, (label, action) in zip(cols, ia_actions):
    with col:
        if st.button(label, use_container_width=True, key=f"ia_{action}"):
            if not editor_text.strip():
                st.warning("⚠️ Ajoute du texte avant d'utiliser l'IA")
            else:
                with st.spinner(f"✨ {label} en cours..."):
                    try:
                        result = format_text(editor_text, action, model=selected_model)
                        st.session_state["editor_text"] = result
                        log_activity(db, session_id, "editor", action)
                        st.success(f"✅ {label} terminé !")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erreur IA : {e}")
