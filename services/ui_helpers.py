"""
Helpers UI : CSS global + mode nuit cohérent.
"""
import streamlit as st


def inject_css(dark_mode: bool = False):
    if dark_mode:
        bg_main = "#0F172A"
        bg_secondary = "#1E293B"
        bg_sidebar = "#0F172A"
        text_main = "#F1F5F9"
        text_secondary = "#CBD5E1"
        border = "#334155"
        card_bg = "linear-gradient(145deg, #1E293B, #0F172A)"
    else:
        bg_main = "#FFFFFF"
        bg_secondary = "#F8FAFC"
        bg_sidebar = "linear-gradient(180deg, #F8FAFC 0%, #EEF2FF 100%)"
        text_main = "#1E293B"
        text_secondary = "#64748B"
        border = "#E2E8F0"
        card_bg = "linear-gradient(145deg, #FFFFFF, #F0F4FF)"

    st.markdown(f"""
<style>
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
header {{ visibility: hidden; }}
[data-testid="stSidebarNav"] a[href*="admin"] {{ display: none !important; }}

.stApp {{
    background-color: {bg_main} !important;
    color: {text_main} !important;
}}
.stApp p, .stApp label, .stApp span, .stApp div, .stApp li {{
    color: {text_main};
}}
.stMarkdown {{ color: {text_main} !important; }}
.stMarkdown p, .stMarkdown li, .stMarkdown span {{ color: {text_main} !important; }}
.stMarkdown h1, .stMarkdown h2, .stMarkdown h3,
.stMarkdown h4, .stMarkdown h5, .stMarkdown h6 {{
    color: {text_main} !important;
}}

[data-testid="stSidebar"] {{
    background: {bg_sidebar} !important;
    border-right: 1px solid {border};
}}
[data-testid="stSidebar"] * {{ color: {text_main} !important; }}

.stTextInput input, .stTextArea textarea, .stSelectbox select {{
    background-color: {bg_secondary} !important;
    color: {text_main} !important;
    border: 1px solid {border} !important;
}}
.stTextInput input::placeholder, .stTextArea textarea::placeholder {{
    color: {text_secondary} !important;
}}
[data-baseweb="select"] {{
    background-color: {bg_secondary} !important;
}}
[data-baseweb="select"] * {{ color: {text_main} !important; }}

.card {{
    background: {card_bg} !important;
    border: 1.5px solid {border} !important;
    border-radius: 20px;
    padding: 2rem;
    color: {text_main} !important;
    box-shadow: 0 4px 20px rgba(79, 70, 229, 0.08);
}}

.stButton > button[kind="primary"] {{
    background: linear-gradient(135deg, #4F46E5, #7C3AED) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.6rem 1.5rem !important;
    font-weight: 700 !important;
}}
.stButton > button[kind="primary"]:hover {{
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(79, 70, 229, 0.4);
}}
.stButton > button {{
    background: {bg_secondary} !important;
    color: {text_main} !important;
    border: 1px solid {border} !important;
    border-radius: 10px !important;
}}

.stTabs [data-baseweb="tab-list"] {{
    background: {bg_secondary} !important;
    border-radius: 12px;
    padding: 4px;
}}
.stTabs [data-baseweb="tab"] {{
    color: {text_main} !important;
    border-radius: 8px;
}}

.stChatMessage {{
    background: {bg_secondary} !important;
    border: 1px solid {border} !important;
    border-radius: 12px !important;
    color: {text_main} !important;
}}
.stChatMessage * {{ color: {text_main} !important; }}

[data-testid="stMetric"] {{
    background: {bg_secondary};
    border: 1px solid {border};
    border-radius: 12px;
    padding: 1rem;
}}
[data-testid="stMetric"] * {{ color: {text_main} !important; }}

.stCaption {{ color: {text_secondary} !important; }}
.stAlert {{ border-radius: 12px; }}

.streamlit-expanderHeader {{
    background: {bg_secondary} !important;
    color: {text_main} !important;
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

::-webkit-scrollbar {{ width: 8px; height: 8px; }}
::-webkit-scrollbar-track {{ background: {bg_secondary}; }}
::-webkit-scrollbar-thumb {{ background: {border}; border-radius: 4px; }}
::-webkit-scrollbar-thumb:hover {{ background: #4F46E5; }}
</style>""", unsafe_allow_html=True)


def apply_dark_mode() -> bool:
    if "dark_mode" not in st.session_state:
        st.session_state["dark_mode"] = False

    current = st.session_state["dark_mode"]
    new_value = st.toggle("🌙 Mode nuit", value=current, key="dark_mode_global")

    if new_value != current:
        st.session_state["dark_mode"] = new_value
        st.rerun()

    return new_value
