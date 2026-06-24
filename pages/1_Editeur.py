"""
Éditeur Markdown avec preview en temps réel.
Layout : éditeur à gauche + preview à droite.
"""
import time
from dotenv import load_dotenv; load_dotenv()
import streamlit as st
from services.ai import AVAILABLE_MODELS, StudyBoostAIError, format_text
from services.database import get_db, get_settings, get_user_quotas, increment_quota, log_activity, save_draft, load_draft
from services.identity import get_user_id, init_user_identity, is_admin
from services.pdf_generator import markdown_to_pdf, generate_default_title
from services.ui_helpers import inject_css, show_user_identity_sidebar, show_quota_sidebar, show_ai_error


def _render_markdown_html(text: str) -> str:
    import markdown as md_lib

    html = md_lib.markdown(text, extensions=["fenced_code", "tables", "nl2br"])

    return """
    <style>
    .preview-content { color: var(--preview-text); font-family: 'Inter', sans-serif; line-height: 1.6; }
    .preview-content h1 { color: var(--preview-text); font-size: 1.8rem; font-weight: 800; margin-top: 0.5rem; border-bottom: 2px solid var(--preview-primary); padding-bottom: 0.3rem; }
    .preview-content h2 { color: var(--preview-primary); font-size: 1.4rem; font-weight: 700; margin-top: 1rem; }
    .preview-content h3 { color: var(--preview-text); font-size: 1.15rem; font-weight: 700; margin-top: 0.8rem; }
    .preview-content p { margin: 0.5rem 0; }
    .preview-content ul, .preview-content ol { margin: 0.5rem 0; padding-left: 1.5rem; }
    .preview-content li { margin: 0.2rem 0; }
    .preview-content code { background: var(--preview-code-bg); color: var(--preview-secondary); padding: 2px 6px; border-radius: 4px; font-size: 0.9rem; }
    .preview-content pre { background: var(--preview-code-bg); padding: 12px; border-radius: 8px; overflow-x: auto; }
    .preview-content blockquote { border-left: 4px solid var(--preview-primary); background: var(--preview-quote-bg); padding: 8px 16px; margin: 0.5rem 0; border-radius: 4px; }
    .preview-content strong { color: var(--preview-primary); }
    .preview-content hr { border: none; border-top: 1px solid var(--preview-border); margin: 1rem 0; }
    .preview-content table { border-collapse: collapse; width: 100%; margin: 0.5rem 0; }
    .preview-content th, .preview-content td { border: 1px solid var(--preview-border); padding: 8px; text-align: left; }
    .preview-content th { background: var(--preview-code-bg); }
    </style>
    <div class="preview-content">""" + html + "</div>"


st.set_page_config(
    page_title="Éditeur — StudyBoost AI",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="collapsed",
)

MAX_CHARS = 15000

db = get_db()
init_user_identity(db)
settings = get_settings()
user_id = get_user_id()

if settings.get("maintenance_mode", "false") == "true":
    st.error("🔧 **Maintenance en cours** — L'éditeur est temporairement indisponible.")
    st.markdown("[🏠 Retour à l'accueil](/)")
    st.stop()

dark_mode = st.session_state.get("dark_mode", False)
inject_css(dark_mode=dark_mode)

with st.sidebar:
    show_user_identity_sidebar()
    st.markdown("### ⚙️ Options")
    dark_mode_new = st.toggle("🌙 Mode nuit", value=dark_mode, key="editor_dark")
    if dark_mode_new != dark_mode:
        st.session_state["dark_mode"] = dark_mode_new
        st.rerun()
    st.markdown("---")

    st.markdown("### 🤖 Modèle IA")
    saved_model = st.session_state.get("preferred_model", "")
    model_keys = list(AVAILABLE_MODELS.keys())
    model_index = 0
    if saved_model:
        for i, k in enumerate(model_keys):
            if AVAILABLE_MODELS[k] == saved_model:
                model_index = i
                break
    model_name = st.selectbox(
        "Modèle", options=model_keys, index=model_index, label_visibility="collapsed",
    )
    selected_model = AVAILABLE_MODELS[model_name]
    if st.session_state.get("preferred_model") != selected_model:
        st.session_state["preferred_model"] = selected_model
        save_draft(user_id, st.session_state.get("editor_text", ""), model=selected_model)
    st.markdown("---")

    quotas = get_user_quotas(user_id, admin_bypass=is_admin())
    if quotas:
        show_quota_sidebar(quotas)

col_title, col_name, col_download = st.columns([1, 2, 1.5])
with col_title:
    st.markdown(
        '<div style="display:flex;align-items:center;gap:10px;padding-top:10px;">'
        '<span style="font-size:1.8rem;">🎓</span>'
        '<span style="font-size:1.3rem;font-weight:800;background:linear-gradient(135deg,#4F46E5,#7C3AED);'
        "-webkit-background-clip:text;-webkit-text-fill-color:transparent;"
        '">StudyBoost</span></div>',
        unsafe_allow_html=True,
    )

with col_name:
    if "doc_title" not in st.session_state:
        st.session_state["doc_title"] = generate_default_title()
    doc_title = st.text_input(
        "Nom", value=st.session_state["doc_title"],
        label_visibility="collapsed", placeholder="Nom du document...",
        key="doc_title_input", max_chars=100,
    )
    clean = "".join(c for c in doc_title if c.isprintable()).strip()[:100]
    st.session_state["doc_title"] = clean or "document"

with col_download:
    download_format = st.selectbox(
        "Format",
        ["📥 .MD", "📄 .PDF"],
        label_visibility="collapsed", key="download_format",
    )

st.markdown('<div style="border-bottom:1px solid #E2E8F0;margin:10px 0 20px 0;"></div>', unsafe_allow_html=True)

if "editor_text" not in st.session_state:
    draft_text, draft_model = load_draft(user_id)
    if draft_text:
        st.session_state["editor_text"] = draft_text
        if draft_model:
            st.session_state["preferred_model"] = draft_model
    else:
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

with col_editor:
    st.markdown(
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
        '<span style="font-weight:700;color:#4F46E5;">✏️ ÉDITEUR</span>'
        '<span style="color:#94A3B8;font-size:0.85rem;">— Markdown</span></div>',
        unsafe_allow_html=True,
    )
    editor_text = st.text_area(
        "Éditeur", value=st.session_state["editor_text"],
        height=550, max_chars=MAX_CHARS,
        label_visibility="collapsed", key="editor_textarea",
        placeholder="Tape ou colle ton Markdown ici...",
    )
    st.session_state["editor_text"] = editor_text
    if st.session_state.get("_last_draft") != editor_text:
        save_draft(user_id, editor_text)
        st.session_state["_last_draft"] = editor_text
    chars = len(editor_text)
    words = len(editor_text.split())
    pct = (chars / MAX_CHARS) * 100
    color = "#EF4444" if pct > 90 else ("#F59E0B" if pct > 70 else "#64748B")
    st.markdown(
        f'<div style="display:flex;justify-content:space-between;font-size:0.85rem;color:{color};margin-top:5px;">'
        f"<span>📊 {chars:,} / {MAX_CHARS:,} caractères</span>"
        f"<span>📝 {words:,} mots</span></div>",
        unsafe_allow_html=True,
    )

with col_preview:
    st.markdown(
        '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
        '<span style="font-weight:700;color:#7C3AED;">👁️ PREVIEW</span>'
        '<span style="color:#94A3B8;font-size:0.85rem;">— Rendu en temps réel</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="height:550px;overflow-y:auto;padding:20px;'
        f"border:1px solid var(--preview-border);border-radius:8px;background:var(--bg-main);color:var(--text-main);"
        f'">{_render_markdown_html(editor_text)}</div>',
        unsafe_allow_html=True,
    )

st.markdown('<div style="margin:20px 0;"></div>', unsafe_allow_html=True)

col_dl1, col_dl2, col_dl3 = st.columns([1, 2, 1])
with col_dl2:
    if download_format == "📥 .MD":
        if settings.get("feature_md_enabled", "true") == "true":
            st.download_button(
                "⬇️ Télécharger",
                data=editor_text.encode("utf-8"),
                file_name=f"{doc_title}.md",
                mime="text/markdown",
                use_container_width=True, type="primary",
            )
        else:
            st.warning("⚠️ Export Markdown temporairement désactivé")
    else:
        if settings.get("feature_pdf_enabled", "true") != "true":
            st.warning("⚠️ Export PDF temporairement désactivé")
        elif quotas and quotas["pdf"]["used"] >= quotas["pdf"]["limit"]:
            st.error(f"❌ Limite atteinte ({quotas['pdf']['limit']} PDF/jour). Reviens demain !")
        else:
            logo_choice = st.radio(
                "Logo", ["Avec logo", "Sans logo"],
                index=0, horizontal=True, label_visibility="collapsed",
                key="pdf_logo_choice",
            )
            with_logo = logo_choice == "Avec logo"

            _sig = f"{editor_text[-100:]}_{doc_title}_{with_logo}"
            if st.session_state.get("_pdf_sig") != _sig:
                st.session_state["_pdf_bytes"] = markdown_to_pdf(
                    text=editor_text, title=doc_title,
                    logo_path="assets/logo.png" if with_logo else None,
                    neutral=not with_logo,
                )
                st.session_state["_pdf_sig"] = _sig
                st.session_state["_pdf_charged"] = False

            def _charge_pdf():
                if not st.session_state.get("_pdf_charged"):
                    increment_quota(user_id, "pdf")
                    log_activity(user_id, "pdf_export", doc_title)
                    st.session_state["_pdf_charged"] = True

            st.download_button(
                "⬇️ Télécharger",
                data=st.session_state["_pdf_bytes"],
                file_name=f"{doc_title}.pdf",
                mime="application/pdf",
                use_container_width=True, type="primary",
                on_click=_charge_pdf,
            )

st.markdown(
    '<div style="margin:30px 0 10px 0;border-top:1px solid #E2E8F0;padding-top:20px;"></div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div style="text-align:center;margin-bottom:15px;">'
    '<span style="font-weight:700;color:#4F46E5;font-size:1.1rem;">✨ Transformer avec l\'IA</span>'
    '<br><span style="color:#64748B;font-size:0.85rem;">Optionnel — choisis une action ci-dessous</span></div>',
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

is_text_valid = len(editor_text.strip()) >= 50
ia_tooltip = None if is_text_valid else "📝 Écris au moins 50 caractères pour utiliser l'IA"

cols = st.columns(6)
for col, (label, action) in zip(cols, ia_actions):
    with col:
        if st.button(label, use_container_width=True, key=f"ia_{action}", disabled=not is_text_valid, help=ia_tooltip):
            if quotas and quotas["ai"]["used"] >= quotas["ai"]["limit"]:
                st.error(f"❌ Limite IA atteinte ({quotas['ai']['limit']} transformations/jour). Reviens demain !")
            else:
                with st.spinner(f"✨ {label} en cours..."):
                    start = time.time()
                    try:
                        result = format_text(editor_text, action, model=selected_model)
                        elapsed = time.time() - start
                        st.session_state["editor_text"] = result
                        increment_quota(user_id, "ai")
                        log_activity(user_id, f"ai_{action}", selected_model)
                        st.success(f"✅ {label} terminé en {elapsed:.1f}s")
                        st.rerun()
                    except StudyBoostAIError as e:
                        show_ai_error(e, model_name.split(" (")[0], action)
                    except Exception:
                        show_ai_error(Exception("unknown"), model_name.split(" (")[0], action)
