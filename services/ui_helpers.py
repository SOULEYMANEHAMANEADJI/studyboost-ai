"""UI helpers — CSS global, quotas, feature flags."""
import streamlit as st


def inject_css(dark_mode: bool = False):
    css = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
[data-testid="stSidebarNav"] a[href*="admin"] {display: none !important;}

* { font-family: 'Inter', -apple-system, sans-serif; }

.gradient-title {
    font-size: 3rem; font-weight: 900;
    background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 60%, #EC4899 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; text-align: center; line-height: 1.1; margin-bottom: 0.5rem;
}
.subtitle {
    text-align: center; color: #64748B; font-size: 1.2rem; margin-bottom: 1.5rem;
}
.card {
    background: linear-gradient(145deg, #FFFFFF 0%, #F0F4FF 100%);
    border: 1.5px solid #E2E8F0; border-radius: 20px; padding: 2rem;
    margin: 0.8rem 0; box-shadow: 0 4px 20px rgba(79,70,229,0.08);
    transition: all 0.3s cubic-bezier(0.4,0,0.2,1); height: 100%;
}
.card:hover {
    transform: translateY(-6px); box-shadow: 0 20px 40px rgba(79,70,229,0.18);
    border-color: #818CF8;
}
.feature-item { display: flex; align-items: center; gap: 0.6rem; padding: 0.4rem 0; color: #475569; font-size: 0.92rem; }

.step-container {
    background: linear-gradient(135deg, #F8FAFC, #EEF2FF); border-radius: 16px;
    padding: 1.8rem 1.5rem; text-align: center; border: 1px solid #E0E7FF;
    transition: all 0.3s ease; height: 100%;
}
.step-container:hover {
    background: linear-gradient(135deg, #EEF2FF, #E0E7FF); transform: translateY(-3px);
}
.step-emoji { font-size: 2.5rem; margin-bottom: 0.8rem; }
.step-title { font-weight: 700; color: #1E293B; font-size: 1rem; }
.step-desc { color: #64748B; font-size: 0.85rem; margin-top: 0.4rem; }

.badge {
    display: inline-block; background: linear-gradient(135deg, #4F46E5, #7C3AED);
    color: white; padding: 0.35rem 1.2rem; border-radius: 50px;
    font-size: 0.72rem; font-weight: 800; letter-spacing: 0.12em;
    text-transform: uppercase; box-shadow: 0 4px 15px rgba(79,70,229,0.3);
}

.privacy-box {
    background: linear-gradient(135deg, #F0FDF4, #DCFCE7);
    border: 1.5px solid #86EFAC; border-radius: 16px; padding: 1.5rem 2rem; margin: 1.5rem 0;
}
.privacy-item { color: #166534; font-size: 0.9rem; padding: 0.3rem 0; display: flex; align-items: center; gap: 0.5rem; }

.quota-container { background: #F8FAFC; border-radius: 12px; padding: 1rem; margin: 0.5rem 0; border: 1px solid #E2E8F0; }
.quota-label { font-size: 0.8rem; color: #64748B; font-weight: 600; margin-bottom: 0.3rem; }
.quota-numbers { font-size: 0.75rem; color: #94A3B8; text-align: right; }

.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #4F46E5, #7C3AED) !important;
    border: none !important; border-radius: 12px !important;
    padding: 0.6rem 1.5rem !important; font-weight: 700 !important;
    box-shadow: 0 4px 15px rgba(79,70,229,0.3) !important;
    transition: all 0.3s ease !important;
}
.stButton > button[kind="primary"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(79,70,229,0.4) !important;
}

.stTabs [data-baseweb="tab-list"] { gap: 8px; background: #F8FAFC; padding: 0.5rem; border-radius: 12px; }
.stTabs [data-baseweb="tab"] { border-radius: 8px; font-weight: 600; }

.stChatMessage { border-radius: 16px !important; margin: 0.5rem 0 !important; }

[data-testid="stSidebar"] { background: linear-gradient(180deg, #F8FAFC 0%, #EEF2FF 100%); border-right: 1px solid #E2E8F0; }

[data-testid="stMetric"] { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 1rem; }

@media (prefers-color-scheme: dark) {
    .card { background: linear-gradient(145deg, #1E293B, #0F172A); border-color: #334155; }
    .step-container { background: linear-gradient(135deg, #1E293B, #0F172A); }
}
</style>"""

    if dark_mode:
        css += """
<style>
.stApp { background-color: #0F172A; }
.card { background: linear-gradient(145deg, #1E293B, #0F172A) !important; }
.step-container { background: #1E293B !important; }
.stTextArea textarea { background: #1E293B !important; color: #F1F5F9 !important; }
.stTextInput input { background: #1E293B !important; color: #F1F5F9 !important; }
.stSelectbox div[data-baseweb="select"] { background: #1E293B !important; }
[data-testid="stSidebar"] { background: linear-gradient(180deg, #1E293B, #0F172A) !important; }
.gradient-title { filter: brightness(1.2); }
.stMarkdown, p, h1, h2, h3, h4, h5, h6, label { color: #F1F5F9 !important; }
.quota-container { background: #1E293B !important; border-color: #334155 !important; }
[data-testid="stMetric"] { background: #1E293B !important; border-color: #334155 !important; }
.stTabs [data-baseweb="tab-list"] { background: #1E293B !important; }
.stTabs [data-baseweb="tab"] { color: #F1F5F9 !important; }
.stChatMessage { background: #1E293B !important; }
</style>"""

    st.markdown(css, unsafe_allow_html=True)


def show_quota_sidebar(quotas: dict):
    st.markdown("### 📊 Quotas du jour")
    for key, label, color in (
        ("pdf", "Exports PDF", "#4F46E5"),
        ("chat", "Messages", "#7C3AED"),
        ("search", "Recherches web", "#EC4899"),
    ):
        info = quotas.get(key, {})
        used = info.get("used", 0)
        limit = info.get("limit", 10)
        remaining = info.get("remaining", 0)
        pct = int((used / limit) * 100) if limit else 0
        st.markdown(f"""
        <div class="quota-container">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span class="quota-label">{label}</span>
                <span class="quota-numbers">{used}/{limit}</span>
            </div>
            <div style="height:6px;background:#E2E8F0;border-radius:3px;margin-top:4px;">
                <div style="height:6px;width:{min(pct,100)}%;background:{color};border-radius:3px;"></div>
            </div>
            <div style="text-align:right;font-size:0.7rem;color:#94A3B8;margin-top:2px;">{remaining} restant(s)</div>
        </div>
        """, unsafe_allow_html=True)


def show_feature_disabled(feature_name: str):
    st.info(f"⚙️ **{feature_name}** est temporairement indisponible. Reviens bientôt !")


def quota_warning(remaining: int, limit: int, label: str) -> bool:
    if remaining <= 0:
        st.error(f"❌ Limite de **{label}** atteinte ({limit}/{limit}). Reviens demain !")
        return False
    if remaining <= 3:
        st.warning(f"⚠️ Plus que **{remaining}** {label} aujourd'hui")
    return True
