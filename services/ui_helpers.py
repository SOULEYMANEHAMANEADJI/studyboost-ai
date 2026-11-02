"""Restrained application styling and native Streamlit controls."""
from html import escape
import streamlit as st


def inject_css(dark_mode: bool = False, page: str = ""):
    paper,side,ink,muted,line,accent,accent_ink,bubble = (
        ("#171b22","#12161d","#e7ebf1","#a6afbd","#323843","#a6c3e8","#132338","#242d39") if dark_mode else
        ("#ffffff","#f5f6f7","#252b34","#68717e","#e5e7eb","#324e70","#ffffff","#f0f2f5")
    )
    width = "820px" if page == "chat" else "1180px"
    st.markdown(f"""<style>
:root {{ --bg-main:{paper};--bg-secondary:{side};--text-main:{ink};--text-secondary:{muted};--border:{line};--sb-accent:{accent};--sb-accent-ink:{accent_ink};--preview-text:{ink};--preview-primary:{accent};--preview-secondary:{accent};--preview-border:{line};--preview-code-bg:{side};--preview-quote-bg:{side}; }}
.stApp {{background:{paper};color:{ink};}}
[data-testid="stMainBlockContainer"] {{max-width:{width};padding-top:2.2rem;padding-bottom:3rem;}}
[data-testid="stSidebar"] {{background:{side};border-right:1px solid {line};}}
[data-testid="stSidebarNav"] {{display:none;}}
[data-testid="stSidebarUserContent"] {{padding-top:1.4rem;}}
h1,.gradient-title {{font-size:1.7rem!important;line-height:1.3!important;letter-spacing:-.04em;font-weight:600!important;text-align:left!important;color:{ink}!important;background:none!important;-webkit-text-fill-color:currentColor!important;}}
.stMarkdown,.stMarkdown p,.stMarkdown li,.stHeading,[data-testid="stWidgetLabel"] p,[data-testid="stPageLink-NavLink"] p {{color:{ink};}}
.stTextInput input::placeholder,.stTextArea textarea::placeholder {{color:{muted};}}
h2 {{font-size:1.25rem!important;}} h3 {{font-size:1.05rem!important;}}
.stMarkdown p,.stMarkdown li {{line-height:1.7;}}
[data-testid="stCaptionContainer"],.subtitle {{color:{muted};}}
.stButton button,.stDownloadButton button {{border-radius:7px;box-shadow:none;}}
button[kind="primary"] {{background:{accent}!important;color:{accent_ink}!important;border-color:{accent}!important;}}
button[kind="primary"] p {{color:inherit;}}
.stTextInput input,.stTextArea textarea,[data-baseweb="select"] > div {{background:{paper};color:{ink};border-color:{line};}}
.stChatMessage {{background:transparent;border:0;padding:1rem 0;}}
.stChatMessage:has([data-testid="stChatMessageAvatarUser"]) {{background:{bubble};border-radius:12px;padding:1rem;margin-left:12%;width:88%;}}
[data-testid="stChatInput"] {{border:1px solid {line};border-radius:10px;background:{paper};}}
.sb-identity {{padding:1rem 0;border-top:1px solid {line};margin-top:1rem;}}
.sb-identity strong {{display:block;font-size:.85rem;font-weight:500;}}
.sb-identity small {{color:{muted};font-size:.75rem;}}
.sb-brand {{font-size:1.25rem;font-weight:600;letter-spacing:-.04em;margin-bottom:1rem;}}
.preview-content {{color:{ink};line-height:1.7;overflow-wrap:anywhere;}}
.preview-content h1 {{font-size:1.5rem!important;}} .preview-content h2 {{margin-top:1.5rem;}}
.preview-content blockquote {{border-left:2px solid {accent};padding-left:1rem;color:{muted};}}
.preview-content pre {{background:{side};padding:1rem;border-radius:6px;white-space:pre-wrap;}}
.preview-content table {{border-collapse:collapse;width:100%;}} .preview-content th,.preview-content td {{border:1px solid {line};padding:.5rem;}}
.card,.privacy-box {{border:1px solid {line};border-radius:10px;padding:1.3rem;background:{paper};}}
.step-container {{padding:1rem 0;}} .step-title {{font-weight:500;}} .step-desc {{color:{muted};}}
.badge {{font-size:.75rem;color:{muted};}} .stAlert {{border-radius:8px;}}
@media(max-width:700px) {{[data-testid="stMainBlockContainer"]{{padding:1.5rem 1rem;}} .stChatMessage:has([data-testid="stChatMessageAvatarUser"]){{margin-left:4%;width:96%;}} .stTextArea textarea{{font-size:16px;}}}}
</style>""",unsafe_allow_html=True)
    with st.sidebar:
        st.markdown('<div class="sb-brand">StudyBoost <span style="font-weight:400">AI</span></div>',unsafe_allow_html=True)
        st.page_link("pages/0_Accueil.py",label="Accueil",icon="🏠")
        st.page_link("pages/2_Chat.py",label="Chat",icon="💬")
        st.page_link("pages/1_Editeur.py",label="Éditeur",icon="📝")
        st.page_link("pages/3_Feedback.py",label="Avis",icon="✉️")


def show_user_identity_sidebar(retention_days: int | None = None):
    from services.identity import get_user_alias
    from services.database import get_settings
    if retention_days is None: retention_days=int(get_settings().get("retention_days","7"))
    name=escape(get_user_alias().get("display","Espace privé"))
    st.markdown(f'<div class="sb-identity"><strong>{name}</strong><small>Espace privé · ce navigateur<br>Historique : {retention_days} jours</small></div>',unsafe_allow_html=True)


def show_quota_sidebar(quotas=None):
    if quotas is None:
        from services.identity import get_user_id
        from services.database import get_user_quotas
        quotas=get_user_quotas(get_user_id())
    if quotas.get("_fallback"):
        st.warning("Vérification des quotas indisponible : actions temporairement suspendues.")
        return
    with st.expander("Demandes restantes"):
        for key,label in (("chat","Messages"),("ai","Transformations"),("pdf","Imports / préparations PDF"),("search","Recherches web")):
            q=quotas.get(key,{"used":0,"limit":0}); remaining=max(0,q["limit"]-q["used"])
            st.caption(f"{label} : {remaining} / {q['limit']}")
        st.caption("Le budget OpenRouter est partagé par toute l'application. Les tentatives IA sont comptées.")


def show_ai_error(error, model_name, action):
    from services.ai import StudyBoostAIError
    st.error(str(error) if isinstance(error,StudyBoostAIError) else "Une erreur inattendue s'est produite. Réessaie plus tard.")
