"""
Helpers UI : CSS global + mode nuit cohérent.
Utilise des variables CSS pour une gestion centralisée du thème.
"""
import streamlit as st


def _theme_vars(dark: bool) -> str:
    if dark:
        return """
  --bg-main: #0F172A;
  --bg-secondary: #1E293B;
  --bg-sidebar: #0F172A;
  --text-main: #F1F5F9;
  --text-secondary: #CBD5E1;
  --border: #334155;
  --card-bg: linear-gradient(145deg, #1E293B, #0F172A);
  --preview-text: #F1F5F9;
  --preview-primary: #A5B4FC;
  --preview-secondary: #C4B5FD;
  --preview-border: #334155;
  --preview-code-bg: #1E293B;
  --preview-quote-bg: #1E293B;"""
    return """
  --bg-main: #FFFFFF;
  --bg-secondary: #F8FAFC;
  --bg-sidebar: linear-gradient(180deg, #F8FAFC 0%, #EEF2FF 100%);
  --text-main: #1E293B;
  --text-secondary: #64748B;
  --border: #E2E8F0;
  --card-bg: linear-gradient(145deg, #FFFFFF, #F0F4FF);
  --preview-text: #1E293B;
  --preview-primary: #4F46E5;
  --preview-secondary: #7C3AED;
  --preview-border: #E2E8F0;
  --preview-code-bg: #F1F5F9;
  --preview-quote-bg: #F8FAFC;"""


def inject_css(dark_mode: bool = False):
    theme = _theme_vars(dark_mode)

    st.markdown(f"""
<style>
:root {{\n{theme}\n}}

/* Hide Streamlit chrome */
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
header {{ visibility: hidden; }}
[data-testid="stSidebarNav"] a[href*="admin"] {{ display: none !important; }}

/* Base */
.stApp {{
    background-color: var(--bg-main) !important;
    color: var(--text-main) !important;
}}
.stApp p, .stApp label, .stApp span, .stApp div, .stApp li {{
    color: var(--text-main);
}}
.stMarkdown {{ color: var(--text-main) !important; }}
.stMarkdown p, .stMarkdown li, .stMarkdown span {{ color: var(--text-main) !important; }}
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
.stMarkdown h4, .stMarkdown h5, .stMarkdown h6 {{
    color: var(--text-main) !important;
}}

/* Sidebar */
[data-testid="stSidebar"] {{
    background: var(--bg-sidebar) !important;
    border-right: 1px solid var(--border);
}}
[data-testid="stSidebar"] * {{ color: var(--text-main) !important; }}

/* Inputs */
.stTextInput input, .stTextArea textarea, .stSelectbox select {{
    background-color: var(--bg-secondary) !important;
    color: var(--text-main) !important;
    border: 1px solid var(--border) !important;
}}
.stTextInput input::placeholder, .stTextArea textarea::placeholder {{
    color: var(--text-secondary) !important;
}}
[data-baseweb="select"] {{
    background-color: var(--bg-secondary) !important;
}}
[data-baseweb="select"] * {{ color: var(--text-main) !important; }}

/* Cards */
.card {{
    background: var(--card-bg) !important;
    border: 1.5px solid var(--border) !important;
    border-radius: 20px;
    padding: 2rem;
    color: var(--text-main) !important;
    box-shadow: 0 4px 20px rgba(79, 70, 229, 0.08);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}}
.card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(79, 70, 229, 0.12);
}}

/* Buttons */
.stButton > button[kind="primary"] {{
    background: linear-gradient(135deg, #4F46E5, #7C3AED) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.6rem 1.5rem !important;
    font-weight: 700 !important;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}}
.stButton > button[kind="primary"]:hover {{
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(79, 70, 229, 0.4);
}}
.stButton > button {{
    background: var(--bg-secondary) !important;
    color: var(--text-main) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    transition: background 0.15s ease;
}}
.stButton > button:hover {{
    background: var(--border) !important;
}}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {{
    background: var(--bg-secondary) !important;
    border-radius: 12px;
    padding: 4px;
}}
.stTabs [data-baseweb="tab"] {{
    color: var(--text-main) !important;
    border-radius: 8px;
}}

/* Chat */
.stChatMessage {{
    background: var(--bg-secondary) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    color: var(--text-main) !important;
}}
.stChatMessage * {{ color: var(--text-main) !important; }}

/* Metrics */
[data-testid="stMetric"] {{
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1rem;
}}
[data-testid="stMetric"] * {{ color: var(--text-main) !important; }}

/* Misc */
.stCaption {{ color: var(--text-secondary) !important; }}
.stAlert {{ border-radius: 12px; }}
.streamlit-expanderHeader {{
    background: var(--bg-secondary) !important;
    color: var(--text-main) !important;
    border-radius: 8px;
}}

.gradient-title {{
    font-size: 3rem;
    font-weight: 900;
    background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 60%, #EC4899 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-align: center;
    line-height: 1.1;
}}

/* Scrollbar */
::-webkit-scrollbar {{ width: 8px; height: 8px; }}
::-webkit-scrollbar-track {{ background: var(--bg-secondary); }}
::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 4px; }}
::-webkit-scrollbar-thumb:hover {{ background: #4F46E5; }}

/* Steps on home page */
.step-container {{
    text-align: center;
    padding: 1.5rem;
    transition: transform 0.2s ease;
}}
.step-container:hover {{
    transform: translateY(-3px);
}}
.step-emoji {{ font-size: 2.5rem; margin-bottom: 0.5rem; }}
.step-title {{ font-size: 1.1rem; font-weight: 700; color: var(--text-main); }}
.step-desc {{ font-size: 0.9rem; color: var(--text-secondary); }}

/* Privacy box */
.privacy-box {{
    background: #F0FDF4;
    border: 1.5px solid #86EFAC;
    border-radius: 16px;
    padding: 1.5rem;
    color: #166534;
}}

/* Responsive */
@media (max-width: 768px) {{
    .gradient-title {{ font-size: 2rem !important; }}
    .card {{ padding: 1.2rem !important; }}
    .step-container {{ padding: 1rem !important; }}
    .step-emoji {{ font-size: 2rem !important; }}
    .stButton > button {{ font-size: 0.85rem !important; padding: 0.5rem 1rem !important; }}
}}
</style>""", unsafe_allow_html=True)


def show_quota_sidebar(quotas: dict, keys: list | None = None):
    """Affiche les quotas dans la sidebar avec une charte graphique unifiée.

    keys: liste de tuples (key, emoji, label, color). Si None, utilise les défauts.
    """
    if keys is None:
        keys = [
            ("pdf", "📄", "PDF"),
            ("chat", "💬", "Messages"),
            ("search", "🔍", "Recherches"),
            ("ai", "✨", "IA"),
        ]
    st.markdown("### 📊 Tes quotas du jour")
    for key, emoji, label in keys:
        q = quotas.get(key, {})
        used = q.get("used", 0)
        limit = q.get("limit", 10)
        remaining = max(0, limit - used)
        pct = min(used / limit, 1) if limit > 0 else 0
        exhausted = remaining <= 0
        st.caption(f"{emoji} {label} : {remaining}/{limit}{' ❌ Épuisé' if exhausted else ''}")
        st.progress(pct)


def show_feature_disabled(feature_name: str):
    st.info(f"⚙️ **{feature_name}** est temporairement indisponible. Reviens bientôt !")


def quota_warning(remaining: int, limit: int, label: str) -> bool:
    if remaining <= 0:
        st.error(f"❌ Limite de **{label}** atteinte ({limit}/{limit}). Reviens demain !")
        return False
    if remaining <= 3:
        st.warning(f"⚠️ Plus que **{remaining}** {label} aujourd'hui")
    return True


def apply_dark_mode() -> bool:
    if "dark_mode" not in st.session_state:
        st.session_state["dark_mode"] = False

    current = st.session_state["dark_mode"]
    new_value = st.toggle("🌙 Mode nuit", value=current, key="dark_mode_global")

    if new_value != current:
        st.session_state["dark_mode"] = new_value
        st.rerun()

    return new_value
