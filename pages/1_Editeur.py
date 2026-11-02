"""
Éditeur Markdown avec preview en temps réel.
Layout : éditeur à gauche + preview à droite.
"""
import hashlib
import time
from dotenv import load_dotenv; load_dotenv()
import streamlit as st

from version import VERSION
from services.ai import AVAILABLE_MODELS, StudyBoostAIError, format_text
from services.logger import get_logger

logger = get_logger("editor")
from services.database import get_settings, get_user_quotas, log_activity, save_draft, load_draft
from services.identity import get_user_id, init_user_identity, is_admin
from services.pdf_generator import markdown_to_pdf, generate_default_title
from services.docx_generator import markdown_to_docx
from services.pdf_reader import pdf_bytes_to_markdown, MAX_UPLOAD_SIZE_MB, MAX_PDF_PAGES, PDFImportError
from services.quotas import reserve_quota, QuotaError
from services.editor_state import stage_editor_text, apply_pending_editor_text, editor_value
from services.markup import safe_markdown
from services.ui_helpers import inject_css, show_user_identity_sidebar, show_quota_sidebar, show_ai_error


def _render_markdown_html(text: str) -> str:
    return '<div class="preview-content">'+safe_markdown(text)+'</div>'


st.set_page_config(
    page_title="Éditeur — StudyBoost AI",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)

MAX_CHARS = 15000

init_user_identity()
settings = get_settings()
user_id = get_user_id()

if settings.get("maintenance_mode", "false") == "true":
    st.error("🔧 **Maintenance en cours** — L'éditeur est temporairement indisponible.")
    st.markdown("[🏠 Retour à l'accueil](/)")
    st.stop()

dark_mode = st.session_state.get("dark_mode", False)
inject_css(dark_mode=dark_mode, page="editor")

if "editor_text" not in st.session_state:
    draft_text, draft_model, draft_title = load_draft(user_id)
    st.session_state["doc_title"] = draft_title or generate_default_title()
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

apply_pending_editor_text(st.session_state)
if "_pending_doc_title" in st.session_state:
    st.session_state["doc_title_input"] = st.session_state.pop("_pending_doc_title")

with st.sidebar:
    new_dark=st.toggle("Mode sombre",value=dark_mode,key="editor_dark")
    if new_dark != dark_mode:
        st.session_state["dark_mode"]=new_dark
        st.rerun()
    show_user_identity_sidebar()
    quotas=get_user_quotas(user_id,admin_bypass=is_admin())
    show_quota_sidebar(quotas)

header,model_column=st.columns([1,1.5])
with header: st.title("Éditeur")
with model_column:
    enabled_models={name:mid for name,mid in AVAILABLE_MODELS.items() if settings.get(f"model_enabled_{mid}","true")=="true"}
    model_keys=list(enabled_models)
    selected_index=next((i for i,k in enumerate(model_keys) if enabled_models[k]==st.session_state.get("preferred_model")),0)
    model_name=st.selectbox("Modèle",model_keys,index=selected_index if model_keys else None,key="editor_model",disabled=not model_keys)
    selected_model=enabled_models.get(model_name)
    if selected_model: st.session_state["preferred_model"]=selected_model

col_title, col_name, col_download = st.columns([1, 2, 1.5])
with col_title:
    st.caption("Mon document")

with col_name:
    if "doc_title" not in st.session_state:
        st.session_state["doc_title"] = generate_default_title()
    doc_title = st.text_input(
        "Nom", value=st.session_state["doc_title"],
        label_visibility="collapsed", placeholder="Nom du document...",
        key="doc_title_input", max_chars=100,
    )
    clean = "".join(c for c in doc_title if c.isprintable()).strip()[:100]
    doc_title=clean or "document"
    st.session_state["doc_title"]=doc_title

with col_download:
    download_format = st.selectbox(
        "Format",
        ["📥 .MD", "📄 .PDF", "📝 .DOCX"],
        label_visibility="collapsed", key="download_format",
    )



has_pdf_preview = st.session_state.get("_pdf_info") is not None
with st.expander("📄 Importer un PDF → Markdown", expanded=has_pdf_preview):
    st.caption(f"PDF texte : {MAX_UPLOAD_SIZE_MB} Mo, {MAX_PDF_PAGES} pages et {MAX_CHARS:,} caractères maximum")
    uploaded_pdf = st.file_uploader("Choisir un fichier PDF", type=["pdf"], key="pdf_uploader")

if uploaded_pdf is not None:
    upload_sig = hashlib.sha256(uploaded_pdf.getvalue()).hexdigest()
    if st.session_state.get("_pdf_upload_sig") != upload_sig:
        st.session_state.pop("_pdf_info", None)
        st.session_state["_pdf_upload_sig"] = upload_sig
        try:
            with st.spinner("Analyse du PDF…"):
                st.session_state["_pdf_info"] = pdf_bytes_to_markdown(uploaded_pdf)
            st.session_state.pop("_pdf_error", None)
        except PDFImportError as error:
            st.session_state["_pdf_error"] = str(error)
    if st.session_state.get("_pdf_error"):
        st.warning(st.session_state["_pdf_error"])
    pdf_info = st.session_state.get("_pdf_info")
    if pdf_info:
        st.success(f"{uploaded_pdf.name} — {pdf_info.pages} page(s) · {len(pdf_info.text):,} caractères")
        st.text(pdf_info.text[:3000])
        ci1, ci2 = st.columns(2)
        with ci1:
            if st.button("✅ Importer dans l'éditeur", type="primary", key="import_confirm"):
                try:
                    reserve_quota(user_id, "pdf", admin_bypass=is_admin())
                    stage_editor_text(st.session_state, pdf_info.text)
                    st.session_state["doc_title"] = pdf_info.title
                    st.session_state["_pending_doc_title"] = pdf_info.title
                    st.session_state.pop("_pdf_info", None)
                    log_activity(user_id, "pdf_import")
                    st.rerun()
                except QuotaError as error:
                    st.error(str(error))
        with ci2:
            if st.button("❌ Annuler", key="import_cancel"):
                st.session_state.pop("_pdf_info", None)
                st.rerun()
else:
    for key in ("_pdf_info", "_pdf_upload_sig", "_pdf_error"):
        st.session_state.pop(key, None)

view=st.radio("Disposition",["Côte à côte","Écrire","Aperçu"],horizontal=True,key="editor_view")
if view=="Côte à côte":
    col_editor,col_preview=st.columns([1,1],gap="medium")
else:
    col_editor,col_preview=st.container(),st.container()
editor_text=editor_value(st.session_state)
if view != "Aperçu":
    with col_editor:
        st.markdown(
            '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
            '<span style="font-weight:500;">Mon texte</span>'
            '<span style="color:#94A3B8;font-size:0.85rem;">— Markdown</span></div>',
            unsafe_allow_html=True,
        )
        if "editor_textarea" not in st.session_state:
            st.session_state["editor_textarea"] = st.session_state["editor_text"]
        editor_text = st.text_area(
            "Éditeur",
            height=550, max_chars=MAX_CHARS,
            label_visibility="collapsed", key="editor_textarea",
            placeholder="Tape ou colle ton Markdown ici...",
        )
        st.session_state["editor_text"] = editor_text
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

if view != "Écrire":
    with col_preview:
        st.markdown(
            '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
            '<span style="font-weight:500;">Aperçu</span>'
            '<span style="color:#94A3B8;font-size:0.85rem;">— Rendu en temps réel</span></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="min-height:420px;padding:20px;'
            f"border:1px solid var(--preview-border);border-radius:8px;background:var(--bg-main);color:var(--text-main);"
            f'">{_render_markdown_html(editor_text)}</div>',
            unsafe_allow_html=True,
        )

draft_signature=(editor_text,selected_model,doc_title)
if st.session_state.get("_last_draft") != draft_signature:
    if save_draft(user_id,editor_text,model=selected_model,title=doc_title):
        st.session_state["_last_draft"]=draft_signature
if st.session_state.get("_last_draft") == draft_signature:
    st.caption("Brouillon sauvegardé")

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

    elif download_format == "📝 .DOCX":
        _sig = f"docx_{hashlib.md5(editor_text.encode()).hexdigest()}_{doc_title}"
        if st.session_state.get("_docx_sig") != _sig:
            with st.spinner("📝 Génération du document Word..."):
                st.session_state["_docx_bytes"] = markdown_to_docx(
                    text=editor_text, title=doc_title,
                )
            st.session_state["_docx_sig"] = _sig

        st.download_button(
            "⬇️ Télécharger",
            data=st.session_state["_docx_bytes"],
            file_name=f"{doc_title}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True, type="primary",
            on_click=lambda: log_activity(user_id, "docx_export", doc_title),
        )

    else:
        if settings.get("feature_pdf_enabled", "true") != "true":
            st.warning("⚠️ Export PDF temporairement désactivé")
        else:
            logo_choice = st.radio(
                "Logo", ["Avec logo", "Sans logo"],
                index=0, horizontal=True, label_visibility="collapsed",
                key="pdf_logo_choice",
            )
            with_logo = logo_choice == "Avec logo"

            _sig = f"{hashlib.md5(editor_text.encode()).hexdigest()}_{doc_title}_{with_logo}"
            if st.session_state.get("_pdf_sig") != _sig:
                if st.button("Préparer le PDF", type="primary", key="prepare_pdf"):
                    try:
                        reserve_quota(user_id, "pdf", admin_bypass=is_admin())
                        with st.spinner("Génération du PDF…"):
                            pdf_bytes = markdown_to_pdf(
                                text=editor_text, title=doc_title,
                                logo_path="assets/logo.png" if with_logo else None,
                                neutral=not with_logo,
                            )
                        st.session_state["_pdf_bytes"] = pdf_bytes
                        st.session_state["_pdf_sig"] = _sig
                        log_activity(user_id, "pdf_export")
                    except QuotaError as error:
                        st.error(str(error))
                    except Exception as error:
                        logger.warning("PDF generation failed type=%s", type(error).__name__)
                        st.error("Impossible de préparer ce PDF. Ton texte reste dans l'éditeur.")
            if st.session_state.get("_pdf_sig") == _sig:
                st.download_button(
                    "⬇️ Télécharger", data=st.session_state["_pdf_bytes"],
                    file_name=f"{doc_title}.pdf", mime="application/pdf",
                    use_container_width=True, type="primary",
                )

st.subheader("Transformer mon texte")

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

action_col,button_col=st.columns([3,1])
with action_col:
    action_label=st.selectbox("Transformer",[label for label,action in ia_actions],key="transform_action")
with button_col:
    transform=st.button("Transformer",key="transform_submit",type="primary",disabled=not is_text_valid or not selected_model)
if transform:
    action=dict(ia_actions)[action_label]
    with st.spinner("Transformation en cours…"):
        try:
            reserve_quota(user_id,"ai",model=selected_model,admin_bypass=is_admin())
            result=format_text(editor_text,action,model=selected_model)
            if len(result)>MAX_CHARS:
                raise StudyBoostAIError("La réponse dépasse la taille de l'éditeur. Demande une version plus courte.","validation")
            stage_editor_text(st.session_state,result)
            log_activity(user_id,f"ai_{action}")
            st.rerun()
        except QuotaError as error: st.error(str(error))
        except StudyBoostAIError as error: show_ai_error(error,model_name,action)
        except Exception as error:
            logger.warning("Editor transformation failed type=%s",type(error).__name__)
            st.error("La transformation a échoué. Ton texte est conservé.")

st.markdown(
    f'<div style="text-align:center;color:#94A3B8;font-size:0.75rem;margin-top:1rem;padding-bottom:1rem;">'
    f'v{VERSION} · StudyBoost AI</div>',
    unsafe_allow_html=True,
)
