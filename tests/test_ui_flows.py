"""Actual Streamlit widget runs; only database, browser identity and AI are faked."""
import types
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
import streamlit as st
from streamlit.testing.v1 import AppTest
from services.ai import AVAILABLE_MODELS, StudyBoostAIError
from services.quotas import QuotaError

ROOT = Path(__file__).resolve().parents[1]

class UIFlowTests(unittest.TestCase):
    def setUp(self):
        self.saved=[]; self.saved_titles=[]; self.reservations=[]; self.messages=[]
        settings={"retention_days":"7", "maintenance_mode":"false", "feature_chat_enabled":"true", "feature_search_enabled":"true", "feature_pdf_enabled":"true", "feature_md_enabled":"true"}
        quotas={kind:dict(used=0,limit=20) for kind in ("pdf","chat","ai","search")}
        self.quotas=quotas
        def init():
            st.session_state["user_data"]={"id":"synthetic-user", "alias":{"display":"Espace test", "emoji":"X"}, "is_returning":False}
            return st.session_state["user_data"]
        identity=types.SimpleNamespace(init_user_identity=init,logout=lambda:None,get_user_id=lambda:"synthetic-user",is_admin=lambda:False,get_user_alias=lambda:{"display":"Espace test","emoji":"X"})
        def save(user,text,model=None,title=None): self.saved.append(text); self.saved_titles.append(title); return True
        database=types.SimpleNamespace(get_settings=lambda:settings,_fetchone=lambda *a,**k:None,cleanup_old_data=lambda **k:None,get_user_quotas=lambda *a,**k:quotas,log_activity=lambda *a,**k:None,save_draft=save,load_draft=lambda user:("Brouillon initial " * 5, "openrouter/free","Titre initial"),save_chat_message=lambda u,r,c:self.messages.append((r,c)),get_chat_history=lambda u:[],clear_chat_history=lambda u:True)
        self.database=database
        self.ai=types.SimpleNamespace(AVAILABLE_MODELS=AVAILABLE_MODELS,StudyBoostAIError=StudyBoostAIError,format_text=lambda *a,**k:"Texte transforme "*5,chat_response=lambda *a,**k:"Reponse test",chat_with_search=lambda *a,**k:"Reponse web test")
        quotas_module=types.SimpleNamespace(reserve_quota=lambda *a,**k:self.reservations.append((a,k)),QuotaError=QuotaError)
        self.patch=patch.dict("sys.modules",{"services.identity":identity,"services.database":database,"services.ai":self.ai,"services.quotas":quotas_module,"services.search":types.SimpleNamespace(search_web=lambda *a,**k:[],format_results=lambda r:"")})
        self.patch.start()
    def tearDown(self): self.patch.stop()
    def assert_clean(self, app):
        self.assertEqual(list(app.exception),[],str(app.exception))

    def test_editor_transform_survives_rerun_and_manual_edit(self):
        app=AppTest.from_file(str(ROOT / "app.py"),default_timeout=10).run().switch_page("pages/1_Editeur.py").run()
        self.assert_clean(app)
        self.assertEqual(app.text_area(key="editor_textarea").value,"Brouillon initial "*5)
        app.button(key="transform_submit").click().run()
        self.assert_clean(app)
        self.assertEqual(app.text_area(key="editor_textarea").value,"Texte transforme "*5)
        app.text_area(key="editor_textarea").input("Modification manuelle "*5).run()
        self.assert_clean(app)
        self.assertEqual(self.saved[-1],"Modification manuelle "*5)
        self.assertEqual(self.reservations[0][0][1],"ai")

    def test_pdf_preparation_is_explicit_and_reserved_once(self):
        app=AppTest.from_file(str(ROOT / "app.py"),default_timeout=10).run().switch_page("pages/1_Editeur.py").run()
        app.selectbox(key="download_format").select("📄 .PDF").run()
        self.assert_clean(app)
        self.assertEqual(self.reservations,[])
        app.button(key="prepare_pdf").click().run()
        self.assert_clean(app)
        self.assertEqual(len(self.reservations),1)
        self.assertEqual(self.reservations[0][0][1],"pdf")
        self.quotas["pdf"]["used"] = 20
        app.run(); self.assert_clean(app)
        self.assertEqual(len(self.reservations),1)
        self.assertEqual(len(app.get("download_button")),1)

    def test_clear_requires_confirmation_and_preserves_messages_on_failure(self):
        app=AppTest.from_file(str(ROOT / "app.py"),default_timeout=10).run().switch_page("pages/2_Chat.py").run()
        app.chat_input[0].set_value("Message a conserver").run()
        original=list(app.session_state["messages"])
        app.button(key="request_clear").click().run()
        self.assertEqual(app.session_state["messages"],original)
        self.database.clear_chat_history=lambda user:False
        app.button(key="confirm_clear").click().run();self.assert_clean(app)
        self.assertEqual(app.session_state["messages"],original)
        self.database.clear_chat_history=lambda user:True
        app.button(key="confirm_clear").click().run();self.assert_clean(app)
        self.assertEqual(app.session_state["messages"],[])

    def test_title_is_restored_and_saved_even_in_preview(self):
        app=AppTest.from_file(str(ROOT / "app.py"),default_timeout=10).run().switch_page("pages/1_Editeur.py").run()
        self.assertEqual(app.text_input(key="doc_title_input").value,"Titre initial")
        app.radio(key="editor_view").set_value("Aperçu").run()
        app.text_input(key="doc_title_input").input("Nouveau titre").run();self.assert_clean(app)
        self.assertEqual(self.saved_titles[-1],"Nouveau titre")
        app.radio(key="editor_view").set_value("Écrire").run();self.assert_clean(app)
        self.assertEqual(app.text_area(key="editor_textarea").value,"Brouillon initial "*5)

    def test_admin_login_clears_password_and_shows_dashboard(self):
        stats={"total_sessions":2,"actions_period":0,"feedbacks":0,"average_rating":0,"email_count":0,"emails_collected":[],"active_users_by_day":{},"actions_by_day":{},"actions_by_type":{},"recent_actions":[],"rating_distribution":{},"feature_requests":{},"feedbacks_list":[]}
        self.database.admin_get_stats=lambda **kwargs:stats
        self.database.update_setting=lambda *a:True
        self.database.check_database_health=lambda:True
        auth_events=[]
        def authenticate(candidate,expected):
            auth_events.append(candidate=="correct")
            return candidate=="correct", "Mot de passe incorrect"
        fake_auth=types.SimpleNamespace(authenticate_admin=authenticate)
        with patch.dict("sys.modules",{"services.admin_auth":fake_auth}):
            app=AppTest.from_file(str(ROOT / "app.py"),default_timeout=10)
            app.secrets["ADMIN_PASSWORD"]="correct"
            app.run().switch_page("pages/admin_secret_access.py").run()
            self.assert_clean(app)
            app.text_input(key="admin_password_input").input("correct")
            next(button for button in app.button if button.label=="Connexion").click().run()
            self.assert_clean(app)
            self.assertTrue(app.session_state["admin_auth"],f"events={auth_events}, errors={[e.value for e in app.error]}")
            self.assertTrue(any(metric.label=="Espaces conservés" for metric in app.metric))
            self.assertNotIn("admin_password_input",app.session_state)

    def test_chat_retry_does_not_duplicate_user_message(self):
        def fail(*a,**k): raise StudyBoostAIError("temporarily unavailable","unavailable")
        self.ai.chat_response=fail
        app=AppTest.from_file(str(ROOT / "app.py"),default_timeout=10).run().switch_page("pages/2_Chat.py").run()
        app.chat_input[0].set_value("Bonjour").run()
        self.assert_clean(app)
        self.ai.chat_response=lambda *a,**k:"Reponse apres reprise"
        app.button(key="retry_chat_question").click().run()
        self.assert_clean(app)
        self.assertEqual([m for m in self.messages if m[0]=="user"],[("user","Bonjour")])
        self.assertIn(("assistant","Reponse apres reprise"),self.messages)
        self.assertEqual(len(self.reservations),2)

if __name__ == "__main__": unittest.main()
