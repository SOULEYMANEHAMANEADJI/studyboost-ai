"""Shared UI helpers for StudyBoost AI pages."""
from __future__ import annotations

from dotenv import load_dotenv
import streamlit as st

load_dotenv()


def inject_css() -> None:
    """Inject the global StudyBoost CSS into the current Streamlit page."""
    st.markdown(
        """
        <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        header {visibility: hidden;}

        .gradient-title {
            font-size: 2.8rem;
            font-weight: 900;
            background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 50%, #EC4899 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-align: center;
            line-height: 1.2;
        }

        .card {
            background: linear-gradient(145deg, #FFFFFF, #F0F4FF);
            border: 1px solid #E2E8F0;
            border-radius: 20px;
            padding: 2rem;
            margin: 0.8rem 0;
            box-shadow: 0 2px 15px rgba(79, 70, 229, 0.06);
            transition: all 0.3s ease;
        }
        .card:hover {
            transform: translateY(-4px);
            box-shadow: 0 12px 30px rgba(79, 70, 229, 0.15);
            border-color: #A5B4FC;
        }

        .badge {
            display: inline-block;
            background: linear-gradient(135deg, #4F46E5, #7C3AED);
            color: white;
            padding: 0.3rem 1rem;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.1em;
            text-transform: uppercase;
        }

        .step-card {
            background: #F8FAFC;
            border-radius: 16px;
            padding: 1.5rem;
            text-align: center;
            border: 1px solid #E2E8F0;
            height: 100%;
        }

        .privacy-box {
            background: #F0FDF4;
            border: 1px solid #86EFAC;
            border-radius: 12px;
            padding: 1.2rem 1.5rem;
            margin: 1rem 0;
        }

        .quota-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0.3rem 0;
            font-size: 0.85rem;
            color: #475569;
        }

        .tag {
            display: inline-block;
            background: #EEF2FF;
            color: #4F46E5;
            border-radius: 8px;
            padding: 0.2rem 0.7rem;
            font-size: 0.8rem;
            margin: 0.2rem;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_quota_sidebar(db, session_id: str, settings: dict[str, str]) -> None:
    """Render the quota panel in the Streamlit sidebar."""
    from services.session_manager import get_quota

    quotas = get_quota(db, session_id, settings)

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Tes quotas du jour")

    for key, label, color in (
        ("pdf", "Exports PDF", "#4F46E5"),
        ("chat", "Messages chat", "#7C3AED"),
        ("search", "Recherches web", "#EC4899"),
    ):
        used = quotas[key]["used"]
        limit = quotas[key]["limit"]
        remaining = quotas[key]["remaining"]
        pct = int((used / limit) * 100) if limit else 0
        st.sidebar.markdown(
            f"<div class='quota-row'><span>{label}</span><span>{used}/{limit}</span></div>",
            unsafe_allow_html=True,
        )
        st.sidebar.progress(min(pct, 100), text=f"{remaining} restant(s)")
