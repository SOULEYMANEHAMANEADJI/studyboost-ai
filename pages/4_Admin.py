"""StudyBoost AI - Admin dashboard."""
from __future__ import annotations

import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from services.database import (
    get_db,
    get_settings,
    update_setting,
    admin_get_stats,
    cleanup_old_data,
    log_activity,
)
from services.session_manager import get_session_id
from services.ui import inject_css


st.set_page_config(page_title="Admin - StudyBoost AI", page_icon="⚙️", layout="wide")


def _check_password():
    """Returns True if admin is authenticated."""
    if st.session_state.get("admin_authenticated", False):
        return True

    try:
        admin_pw = st.secrets.get("ADMIN_PASSWORD", "")
    except Exception:
        admin_pw = os.environ.get("ADMIN_PASSWORD", "")

    with st.form("admin_login"):
        st.markdown("### 🔐 Accès administrateur")
        password = st.text_input("Mot de passe", type="password")
        if st.form_submit_button("Connexion", use_container_width=True):
            if password == admin_pw:
                st.session_state["admin_authenticated"] = True
                st.rerun()
            else:
                st.error("Mot de passe incorrect.")
    return False


def main():
    inject_css()
    db = get_db()

    if not _check_password():
        st.stop()

    settings = get_settings(db)
    session_id = get_session_id()
    period = st.sidebar.selectbox("Période", [7, 14, 30], index=0)
    stats = admin_get_stats(db, days=period)

    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Déconnexion", use_container_width=True):
        st.session_state["admin_authenticated"] = False
        st.rerun()

    st.markdown("<h1 class='gradient-title'>⚙️ Admin Dashboard</h1>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Vue globale", "🎯 Activité", "💬 Feedbacks", "⚙️ Paramètres"
    ])

    # --- TAB 1: Overview ---
    with tab1:
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Sessions totales", stats["total_sessions"])
        with col2:
            st.metric("Actions (période)", stats["actions_period"])
        with col3:
            st.metric("Feedbacks", stats["feedbacks"])
        with col4:
            avg = stats["average_rating"]
            stars = "⭐" * int(round(avg)) if avg else "N/A"
            st.metric("Note moyenne", f"{avg:.1f} {stars}" if avg else "N/A")
        with col5:
            st.metric("Emails collectés", len(stats["emails_collected"]))

        st.markdown("---")

        # Active users per day
        if stats["active_users_by_day"]:
            df_users = pd.DataFrame(
                list(stats["active_users_by_day"].items()),
                columns=["Date", "Utilisateurs actifs"],
            ).sort_values("Date")
            fig_users = px.line(
                df_users, x="Date", y="Utilisateurs actifs",
                title="Utilisateurs actifs par jour",
                markers=True, color_discrete_sequence=["#4F46E5"],
            )
            st.plotly_chart(fig_users, use_container_width=True)

        # Actions per day
        if stats["actions_by_day"]:
            df_actions = pd.DataFrame(
                list(stats["actions_by_day"].items()),
                columns=["Date", "Actions"],
            ).sort_values("Date")
            fig_actions = px.bar(
                df_actions, x="Date", y="Actions",
                title="Actions par jour",
                color_discrete_sequence=["#7C3AED"],
            )
            st.plotly_chart(fig_actions, use_container_width=True)

    # --- TAB 2: Activity ---
    with tab2:
        col_left, col_right = st.columns(2)
        with col_left:
            if stats["actions_by_type"]:
                df_types = pd.DataFrame(
                    list(stats["actions_by_type"].items()),
                    columns=["Type", "Nombre"],
                ).sort_values("Nombre", ascending=False)
                fig_pie = px.pie(
                    df_types, names="Type", values="Nombre",
                    title="Répartition des actions",
                    color_discrete_sequence=px.colors.sequential.Viridis,
                )
                st.plotly_chart(fig_pie, use_container_width=True)

        with col_right:
            if stats["actions_by_type"]:
                df_types_bar = pd.DataFrame(
                    list(stats["actions_by_type"].items()),
                    columns=["Type", "Nombre"],
                ).sort_values("Nombre", ascending=True)
                fig_bar = px.bar(
                    df_types_bar, y="Type", x="Nombre",
                    title="Actions par type",
                    orientation="h",
                    color_discrete_sequence=["#EC4899"],
                )
                st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("---")
        st.markdown("### 📋 30 dernières actions")
        if stats["recent_actions"]:
            df_recent = pd.DataFrame(stats["recent_actions"])
            df_recent["session_anon"] = df_recent["session_id"].apply(
                lambda x: x[:8] + "..." if x else "inconnu"
            )
            df_recent["date"] = df_recent["created_at"].apply(
                lambda x: str(x)[:19] if x else ""
            )
            st.dataframe(
                df_recent[["session_anon", "action_type", "action_detail", "date"]],
                column_config={
                    "session_anon": "Session (anonymisée)",
                    "action_type": "Type",
                    "action_detail": "Détail",
                    "date": "Date",
                },
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Aucune activité sur cette période.")

    # --- TAB 3: Feedback ---
    with tab3:
        col_a, col_b = st.columns(2)
        with col_a:
            avg_rating = stats["average_rating"]
            full = int(round(avg_rating)) if avg_rating else 0
            star_display = "⭐" * full + "☆" * (5 - full)
            st.markdown(
                f"<h2 style='text-align:center;'>{avg_rating:.1f}/5</h2>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<p style='text-align:center; font-size:2rem;'>{star_display}</p>",
                unsafe_allow_html=True,
            )
            st.metric("Total feedbacks", stats["feedbacks"])

        with col_b:
            if stats["rating_distribution"]:
                df_ratings = pd.DataFrame(
                    list(stats["rating_distribution"].items()),
                    columns=["Note", "Nombre"],
                )
                fig_rating = px.bar(
                    df_ratings, x="Note", y="Nombre",
                    title="Distribution des notes",
                    color_discrete_sequence=["#4F46E5"],
                )
                st.plotly_chart(fig_rating, use_container_width=True)

        st.markdown("---")

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            if stats["feature_requests"]:
                df_features = pd.DataFrame(
                    list(stats["feature_requests"].items()),
                    columns=["Fonctionnalité", "Demandes"],
                ).sort_values("Demandes", ascending=True)
                fig_features = px.bar(
                    df_features, y="Fonctionnalité", x="Demandes",
                    title="Fonctionnalités les plus demandées",
                    orientation="h",
                    color_discrete_sequence=["#7C3AED"],
                )
                st.plotly_chart(fig_features, use_container_width=True)

        with col_f2:
            if stats["emails_collected"]:
                df_emails = pd.DataFrame(stats["emails_collected"])
                df_emails["date"] = df_emails["created_at"].apply(
                    lambda x: str(x)[:10] if x else ""
                )
                st.markdown("### 📧 Emails collectés")
                st.dataframe(
                    df_emails[["email", "rating", "date"]],
                    column_config={
                        "email": "Email",
                        "rating": "Note",
                        "date": "Date",
                    },
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("Aucun email collecté.")

        st.markdown("---")
        st.markdown("### 💬 Liste des feedbacks")
        if stats["feedbacks_list"]:
            for fb in stats["feedbacks_list"]:
                with st.expander(
                    f"⭐ {'⭐' * (fb.get('rating', 0) or 0)} "
                    f"— {str(fb.get('created_at', ''))[:10]}"
                ):
                    st.markdown(f"**Commentaire :** {fb.get('comment', '—')}")
                    st.markdown(f"**Fonctionnalités :** {fb.get('feature_request', '—')}")
                    st.markdown(f"**Autre idée :** {fb.get('other_idea', '—')}")
                    st.markdown(f"**Email :** {fb.get('email', '—')}")
                    st.markdown(f"**Session :** `{str(fb.get('session_id', ''))[:16]}...`")
        else:
            st.info("Aucun feedback reçu.")

    # --- TAB 4: Settings ---
    with tab4:
        st.markdown("### 🚩 Feature Flags")
        feature_flags = {
            "Chat IA activé": ("feature_chat_enabled", True),
            "Recherche web activée": ("feature_search_enabled", True),
            "Export PDF activé": ("feature_pdf_enabled", True),
            "Export Markdown activé": ("feature_md_enabled", True),
            "Suppression auto des données": ("auto_cleanup_enabled", True),
            "Mode maintenance": ("maintenance_mode", False),
        }

        col_ff1, col_ff2 = st.columns(2)
        for i, (label, (key, default)) in enumerate(feature_flags.items()):
            current = settings.get(key, "false").lower() == "true"
            col = col_ff1 if i % 2 == 0 else col_ff2
            with col:
                new_val = st.toggle(
                    label,
                    value=current,
                    key=f"flag_{key}",
                )
                if new_val != current:
                    update_setting(db, key, new_val)
                    st.success(f"{label} mis à jour.")

        st.markdown("---")
        st.markdown("### 📊 Quotas")

        quota_keys = {
            "PDF par jour": "quota_pdf_per_day",
            "Messages chat par jour": "quota_chat_per_day",
            "Recherches web par jour": "quota_search_per_day",
        }

        col_q1, col_q2, col_q3 = st.columns(3)
        quota_changed = False
        with col_q1:
            pdf_q = st.number_input(
                "PDF par jour",
                min_value=0, max_value=100,
                value=int(settings.get("quota_pdf_per_day", "10")),
                key="q_pdf",
            )
        with col_q2:
            chat_q = st.number_input(
                "Messages chat par jour",
                min_value=0, max_value=100,
                value=int(settings.get("quota_chat_per_day", "15")),
                key="q_chat",
            )
        with col_q3:
            search_q = st.number_input(
                "Recherches web par jour",
                min_value=0, max_value=100,
                value=int(settings.get("quota_search_per_day", "15")),
                key="q_search",
            )

        if st.button("💾 Sauvegarder les quotas", use_container_width=True):
            update_setting(db, "quota_pdf_per_day", pdf_q)
            update_setting(db, "quota_chat_per_day", chat_q)
            update_setting(db, "quota_search_per_day", search_q)
            st.success("Quotas mis à jour !")

        st.markdown("---")
        st.markdown("### 📢 Message global")

        current_msg = settings.get("global_message", "")
        new_msg = st.text_area(
            "Message affiché sur la page d'accueil",
            value=current_msg,
            height=100,
            placeholder="Écris un message à afficher à tous les utilisateurs...",
        )

        col_pub, col_clear = st.columns(2)
        with col_pub:
            if st.button("📢 Publier", use_container_width=True):
                update_setting(db, "global_message", new_msg)
                st.success("Message publié !")
        with col_clear:
            if st.button("🗑️ Effacer", use_container_width=True):
                update_setting(db, "global_message", "")
                st.success("Message effacé.")

        st.markdown("---")
        st.markdown("### 🧹 Nettoyage manuel")

        if stats.get("oldest_data"):
            st.info(f"Données les plus anciennes : {stats['oldest_data']}")

        if st.button("🧹 Lancer le nettoyage maintenant", use_container_width=True):
            with st.spinner("Nettoyage en cours..."):
                result = cleanup_old_data(db)
                st.success(
                    f"Nettoyage terminé : {result['chat_deleted']} messages supprimés, "
                    f"{result['sessions_deleted']} sessions supprimées."
                )
                log_activity(
                    db, session_id, "admin_cleanup",
                    f"chat={result['chat_deleted']}, sessions={result['sessions_deleted']}"
                )


if __name__ == "__main__":
    main()
