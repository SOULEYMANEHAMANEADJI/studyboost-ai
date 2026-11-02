"""Admin Dashboard — accès par URL directe uniquement."""
import os
import time

from dotenv import load_dotenv; load_dotenv()
import pandas as pd
import plotly.express as px
import streamlit as st

from services.ai import AVAILABLE_MODELS
from services.database import (
    get_settings, update_setting, admin_get_stats, cleanup_old_data, log_activity, check_database_health,
)
from services.identity import get_user_id, init_user_identity
from services.ui_helpers import inject_css

st.set_page_config(page_title="Admin", page_icon="🔧")
st.markdown(
    """<style>[data-testid="stSidebarNav"] a[href*="admin"] {display: none !important;}</style>""",
    unsafe_allow_html=True,
)

def _check_password():
    now = time.time()
    if st.session_state.get("admin_auth") and now < st.session_state.get("admin_auth_until",0):
        return True
    st.session_state["admin_auth"] = False
    try:
        password = st.secrets.get("ADMIN_PASSWORD") or os.environ.get("ADMIN_PASSWORD", "")
    except (FileNotFoundError, KeyError):
        password = os.environ.get("ADMIN_PASSWORD", "")
    with st.form("admin_login"):
        st.subheader("Accès administrateur")
        entered = st.text_input("Mot de passe",type="password",key="admin_password_input")
        if st.form_submit_button("Connexion",type="primary"):
            from services.admin_auth import authenticate_admin
            ok,message = authenticate_admin(entered,password)
            if ok:
                st.session_state["admin_auth"] = True
                st.session_state["admin_auth_until"] = now+1800
                st.session_state.pop("admin_password_input",None)
                st.rerun()
            st.error(message)
    return False


def main():
    inject_css()
    if not _check_password():
        st.stop()

    if st.button("🔌 Vérifier la connexion et le schéma Neon"):
        if check_database_health():
            st.success("Connexion PostgreSQL et schéma attendus : OK. Aucun contenu utilisateur lu ou modifié.")
        else:
            st.error("Connexion ou schéma invalide. Vérifie DATABASE_URL et les logs Cloud.")
    settings = get_settings()
    init_user_identity()
    user_id = get_user_id()
    period = st.sidebar.selectbox("📊 Période", [7, 14, 30], index=0)
    stats = admin_get_stats(days=period)
    if stats.get("load_failed"):
        st.warning("Certaines statistiques n'ont pas pu être chargées. Les valeurs partielles ne constituent pas un bilan complet.")
    st.caption(f"Activités et avis des {period} derniers jours · listes limitées aux 100 derniers résultats · horaires UTC")

    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Déconnexion", width="stretch"):
        st.session_state["admin_auth"] = False
        st.rerun()

    st.markdown("<h1 class='gradient-title'>⚙️ Admin Dashboard</h1>", unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Vue globale", "🎯 Activité", "💬 Feedbacks", "⚙️ Paramètres", "🤖 Modèles"])

    with tab1:
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: st.metric("Espaces conservés", stats["total_sessions"])
        with c2: st.metric("Actions (période)", stats["actions_period"])
        with c3: st.metric("Feedbacks", stats["feedbacks"])
        avg = stats["average_rating"]
        with c4: st.metric("Note moyenne", f"{avg:.1f}" if avg else "N/A")
        with c5: st.metric("Emails", stats.get("email_count",len(stats["emails_collected"])))
        st.markdown("---")
        if stats["active_users_by_day"]:
            df = pd.DataFrame(list(stats["active_users_by_day"].items()), columns=["Date", "Actifs"]).sort_values("Date")
            st.plotly_chart(px.line(df, x="Date", y="Actifs", markers=True, color_discrete_sequence=["#4F46E5"]), width="stretch")
        if stats["actions_by_day"]:
            df2 = pd.DataFrame(list(stats["actions_by_day"].items()), columns=["Date", "Actions"]).sort_values("Date")
            st.plotly_chart(px.bar(df2, x="Date", y="Actions", color_discrete_sequence=["#7C3AED"]), width="stretch")

    with tab2:
        col_l, col_r = st.columns(2)
        with col_l:
            if stats["actions_by_type"]:
                df = pd.DataFrame(list(stats["actions_by_type"].items()), columns=["Type", "Nombre"]).sort_values("Nombre", ascending=False)
                st.plotly_chart(px.pie(df, names="Type", values="Nombre"), width="stretch")
        with col_r:
            if stats["actions_by_type"]:
                df = pd.DataFrame(list(stats["actions_by_type"].items()), columns=["Type", "Nombre"]).sort_values("Nombre", ascending=True)
                st.plotly_chart(px.bar(df, y="Type", x="Nombre", orientation="h", color_discrete_sequence=["#EC4899"]), width="stretch")
        st.markdown("---")
        st.markdown("### 📋 30 dernières actions")
        if stats["recent_actions"]:
            df = pd.DataFrame(stats["recent_actions"])
            df["session"] = df["session_id"].apply(lambda x: str(x)[:8] + "…")
            df["date"] = df["created_at"].apply(lambda x: str(x)[:19])
            st.dataframe(df[["session", "action_type", "action_detail", "date"]], width="stretch", hide_index=True)

    with tab3:
        ca, cb = st.columns(2)
        with ca:
            avg_r = stats["average_rating"]
            stars = "⭐" * int(round(avg_r)) if avg_r else ""
            st.markdown(f"<h2 style='text-align:center'>{avg_r:.1f}/5</h2>", unsafe_allow_html=True)
            st.markdown(f"<p style='text-align:center;font-size:2rem'>{stars}</p>", unsafe_allow_html=True)
        with cb:
            if stats["rating_distribution"]:
                df = pd.DataFrame(list(stats["rating_distribution"].items()), columns=["Note", "Nombre"])
                st.plotly_chart(px.bar(df, x="Note", y="Nombre", color_discrete_sequence=["#4F46E5"]), width="stretch")
        st.markdown("---")
        if stats["feature_requests"]:
            df = pd.DataFrame(list(stats["feature_requests"].items()), columns=["Fonctionnalité", "Demandes"]).sort_values("Demandes", ascending=True)
            st.plotly_chart(px.bar(df, y="Fonctionnalité", x="Demandes", orientation="h", color_discrete_sequence=["#7C3AED"]), width="stretch")
        if stats["emails_collected"]:
            st.markdown("### 📧 Emails")
            df = pd.DataFrame(stats["emails_collected"])
            df["date"] = df["created_at"].apply(lambda x: str(x)[:10])
            st.dataframe(df[["email", "rating", "date"]], width="stretch", hide_index=True)
        st.markdown("---")
        st.markdown("### 💬 Feedbacks")
        for fb in stats.get("feedbacks_list", []):
            with st.expander(f"⭐ {'⭐' * (fb.get('rating', 0) or 0)} — {str(fb.get('created_at', ''))[:10]}"):
                st.markdown(f"**Commentaire :** {fb.get('comment', '—')}")
                st.markdown(f"**Fonctionnalités :** {fb.get('feature_request', '—')}")
                st.markdown(f"**Autre idée :** {fb.get('other_idea', '—')}")
                st.markdown(f"**Email :** {fb.get('email', '—')}")
                st.markdown(f"**Session :** `{str(fb.get('session_id', ''))[:16]}…`")

    with tab4:
        st.markdown("### 🚩 Feature Flags")
        flags = {
            "Chat IA activé": ("feature_chat_enabled", True),
            "Recherche web activée": ("feature_search_enabled", True),
            "Export PDF activé": ("feature_pdf_enabled", True),
            "Export Markdown activé": ("feature_md_enabled", True),
            "Suppression auto données": ("auto_cleanup_enabled", True),
            "Mode maintenance": ("maintenance_mode", False),
        }
        cols = st.columns(2)
        for i, (label, (key, default)) in enumerate(flags.items()):
            cur = settings.get(key, "false").lower() == "true"
            with cols[i % 2]:
                new = st.toggle(label, value=cur, key=f"flag_{key}")
                if new != cur:
                    update_setting(key, new)
                    st.success(f"{label} mis à jour.")

        st.markdown("---")
        st.markdown("### 📊 Quotas")
        c1, c2, c3, c4 = st.columns(4)
        with c1: pdf_q = st.number_input("PDF/jour", 0, 100, int(settings.get("quota_pdf_per_day", "10")), key="q_pdf")
        with c2: chat_q = st.number_input("Messages/jour", 0, 100, int(settings.get("quota_chat_per_day", "20")), key="q_chat")
        with c3: search_q = st.number_input("Recherches/jour", 0, 100, int(settings.get("quota_search_per_day", "10")), key="q_search")
        with c4: ai_q = st.number_input("IA/jour", 0, 100, int(settings.get("quota_ai_per_day", "15")), key="q_ai")
        if st.button("💾 Sauvegarder", width="stretch", type="primary"):
            update_setting("quota_pdf_per_day", pdf_q)
            update_setting("quota_chat_per_day", chat_q)
            update_setting("quota_search_per_day", search_q)
            update_setting("quota_ai_per_day", ai_q)
            st.success("Quotas mis à jour !")

        st.markdown("---")
        st.markdown("### Protection du budget IA partagé")
        global_daily = st.number_input("Demandes IA maximum par jour pour toute l'application", 0, 10000, int(settings.get("quota_ai_global_per_day", "50")), key="global_ai_day")
        global_minute = st.number_input("Demandes IA maximum par minute pour toute l'application", 0, 100, int(settings.get("quota_ai_global_per_minute", "20")), key="global_ai_minute")
        user_minute = st.number_input("Demandes IA maximum par minute et par espace", 0, 20, int(settings.get("quota_ai_user_per_minute", "3")), key="user_ai_minute")
        st.caption("Ces plafonds comptent les tentatives, y compris les appels refusés par le fournisseur. Le plafond global s'applique aussi aux administrateurs.")
        if st.button("Enregistrer les protections IA", key="save_global_ai"):
            results = [
                update_setting("quota_ai_global_per_day", global_daily),
                update_setting("quota_ai_global_per_minute", global_minute),
                update_setting("quota_ai_user_per_minute", user_minute),
            ]
            if all(results): st.success("Protections IA enregistrées.")
        st.markdown("---")
        st.markdown("### 📢 Message global")
        msg = settings.get("global_message", "")
        new_msg = st.text_area("Message affiché sur l'accueil", value=msg, height=80)
        col_p, col_c = st.columns(2)
        with col_p:
            if st.button("📢 Publier", width="stretch", type="primary"):
                update_setting("global_message", new_msg)
                st.success("Publié !")
        with col_c:
            if st.button("🗑️ Effacer", width="stretch"):
                update_setting("global_message", "")
                st.success("Effacé.")

        st.markdown("---")
        st.markdown("### 🗑️ Rétention des données")
        current_retention = int(settings.get("retention_days", "7"))
        retention = st.select_slider(
            "Durée de rétention des données utilisateur",
            options=[3, 7, 14, 30],
            value=current_retention,
            format_func=lambda x: f"{x} jours",
        )
        if retention != current_retention:
            update_setting("retention_days", retention)
            st.success(f"Rétention mise à jour : {retention} jours")

        st.markdown("---")
        st.markdown("### 🧹 Nettoyage")
        if st.button("🧹 Nettoyer maintenant", width="stretch", type="primary"):
            with st.spinner("Nettoyage…"):
                result = cleanup_old_data(force=True)
                if result is True:
                    st.success("Nettoyage effectué.")
                    log_activity(user_id,"admin_cleanup")
                elif result is None:
                    st.info("Un nettoyage est déjà en cours.")
                else:
                    st.error("Le nettoyage a échoué. Les suppressions ont été annulées ; consulte les logs.")

    with tab5:
        st.markdown("### 🤖 Gestion des modèles")
        st.markdown("Active / désactive chaque modèle et fixe son quota journalier.")
        st.markdown("---")

        model_keys = list(AVAILABLE_MODELS.keys())
        for i in range(0, len(model_keys), 2):
            cols = st.columns(2)
            for j in range(2):
                idx = i + j
                if idx >= len(model_keys):
                    break
                label = model_keys[idx]
                mid = AVAILABLE_MODELS[label]
                with cols[j]:
                    st.markdown(f"**{label}**")
                    st.caption(f"`{mid}`")
                    cur_enabled = settings.get(f"model_enabled_{mid}", "true").lower() == "true"
                    new_enabled = st.toggle("Activé", value=cur_enabled, key=f"me_{mid}")
                    if new_enabled != cur_enabled:
                        update_setting(f"model_enabled_{mid}", new_enabled)
                    cur_quota = int(settings.get(f"model_quota_{mid}", "20"))
                    new_quota = st.number_input("Quota/jour", 1, 200, cur_quota, key=f"mq_{mid}")
                    if new_quota != cur_quota:
                        update_setting(f"model_quota_{mid}", new_quota)
                    st.markdown("---")


if __name__ == "__main__":
    main()
