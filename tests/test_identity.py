"""Isolation checks using synthetic data only."""
import hashlib
import logging
import runpy
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
class Stop(BaseException): pass
class Rerun(BaseException): pass

class Cursor:
    def __init__(self, db): self.db = db
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, query, params):
        self.db.queries.append((query, params))
        self.id = params[0]
        if query.startswith("INSERT"):
            self.db.rows.setdefault(self.id, dict(id=self.id, alias_display=params[5], last_active=datetime.now(timezone.utc)))
    def fetchone(self): return self.db.rows.get(self.id)

class DB:
    def __init__(self): self.rows = {}; self.queries = []; self.commits = 0; self.rollbacks = 0
    def cursor(self, **kwargs): return Cursor(self)
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1

class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.db = DB(); self.released = []; self.errors = []
        self.st = types.ModuleType("streamlit")
        self.st.session_state = {}; self.st.query_params = {}
        self.st.info = lambda message: None
        self.st.error = self.errors.append
        self.st.stop = lambda: (_ for _ in ()).throw(Stop())
        self.st.rerun = lambda: (_ for _ in ()).throw(Rerun())
        self.browser = {"token": "a" * 64, "rotation": ""}
        self.database = types.SimpleNamespace(get_db=lambda: self.db, release_db=self.released.append, get_settings=lambda: {"retention_days": "7"})
        self.modules = {
            "streamlit": self.st,
            "streamlit.components": types.ModuleType("streamlit.components"),
            "streamlit.components.v1": types.SimpleNamespace(declare_component=lambda *a, **k: lambda **kw: self.browser),
            "psycopg2": types.SimpleNamespace(extras=types.SimpleNamespace(RealDictCursor=object)),
            "psycopg2.extras": types.ModuleType("psycopg2.extras"),
            "services.logger": types.SimpleNamespace(get_logger=lambda name: logging.getLogger("identity-test")),
            "services.database": self.database,
        }
        with patch.dict("sys.modules", self.modules):
            self.api = runpy.run_path(str(ROOT / "services/identity.py"))

    def init(self):
        with patch.dict("sys.modules", self.modules): return self.api["init_user_identity"]()

    def test_url_never_selects_identity(self):
        self.st.query_params["sid"] = "another-users-id"
        user = self.init()
        self.assertEqual(user["id"], hashlib.sha256(("a" * 64).encode()).hexdigest())
        self.assertNotIn("sid", self.st.query_params)
        self.assertTrue(all("another-users-id" not in params for _, params in self.db.queries))
        self.assertEqual(len(self.released), 1)

    def test_two_browsers_and_reload(self):
        first = self.init()["id"]
        self.st.session_state = {}
        self.browser = {"token": "b" * 64, "rotation": ""}
        second = self.init()["id"]
        self.assertNotEqual(first, second)
        self.st.session_state = {}
        self.browser = {"token": "a" * 64, "rotation": ""}
        user = self.init()
        self.assertEqual(user["id"], first)
        self.assertTrue(user["is_returning"])

    def test_identity_change_clears_private_state(self):
        self.init()
        self.st.session_state.update(messages=["secret A"], editor_text="draft A", admin_auth=True)
        self.browser = {"token": "b" * 64, "rotation": ""}
        with self.assertRaises(Rerun): self.init()
        self.init()
        for key in ["messages", "editor_text", "admin_auth"]:
            self.assertNotIn(key, self.st.session_state)

    def test_missing_or_invalid_browser_token_stops_before_database(self):
        for value in [None, {"token":"short","rotation":""}, {"error":"blocked","rotation":""}]:
            self.browser = value
            with self.assertRaises(Stop): self.init()
        self.assertEqual(self.db.queries, [])

    def test_database_failure_does_not_create_fake_session(self):
        self.database.get_db = lambda: (_ for _ in ()).throw(RuntimeError("offline"))
        with self.assertRaises(Stop): self.init()
        self.assertNotIn("user_data", self.st.session_state)
        self.assertTrue(self.errors)

    def test_logout_requires_browser_rotation_ack(self):
        first = self.init()["id"]
        self.st.query_params["sid"] = first
        with self.assertRaises(Rerun): self.api["logout"]()
        self.assertNotIn("user_data", self.st.session_state)
        self.assertNotIn("sid", self.st.query_params)
        with self.assertRaises(Stop): self.init()
        self.browser = {"token":"c"*64, "rotation":self.st.session_state["identity_rotation"]}
        self.assertNotEqual(self.init()["id"], first)


if __name__ == "__main__": unittest.main()
