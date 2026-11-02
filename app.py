"""Explicit routes keep existing public URLs and a compact shared navigation."""
import streamlit as st

st.set_page_config(page_title="StudyBoost AI",page_icon="📚",layout="wide",initial_sidebar_state="expanded")
page=st.navigation([
    st.Page("pages/0_Accueil.py",title="Accueil",default=True),
    st.Page("pages/1_Editeur.py",title="Éditeur",url_path="Editeur"),
    st.Page("pages/2_Chat.py",title="Chat",url_path="Chat"),
    st.Page("pages/3_Feedback.py",title="Avis",url_path="Feedback"),
    st.Page("pages/admin_secret_access.py",title="Administration",url_path="admin_secret_access",visibility="hidden"),
],position="hidden")
page.run()
