"""Exercise competing reservations against a transaction/lock test double.
PostgreSQL advisory-lock semantics still require an integration run on staging.
"""
import copy
import json
import threading
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import patch
from services.quotas import reserve_quota, QuotaError


class Store:
    def __init__(self):
        self.lock = threading.Lock()
        self.settings = {"quota_ai_user_per_minute":"100", "quota_ai_global_per_minute":"100", "quota_ai_global_per_day":"50"}
        self.users = {str(i):dict(pdf_count=0, chat_count=0, search_count=0, ai_count=0, quota_date=datetime.now(timezone.utc).strftime("%Y-%m-%d")) for i in range(30)}

class Connection:
    def __init__(self, store): self.store=store; self.locked=False
    def __enter__(self): return self
    def __exit__(self, error, *args):
        if self.locked:
            if error:
                self.store.users, self.store.settings = self.snapshot
            self.store.lock.release(); self.locked=False
    def cursor(self, **kwargs): return Cursor(self)

class Cursor:
    def __init__(self, conn): self.conn=conn; self.result=None
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, query, params=None):
        store=self.conn.store
        if "pg_advisory_xact_lock" in query:
            store.lock.acquire(); self.conn.locked=True
            self.conn.snapshot=copy.deepcopy((store.users,store.settings))
        elif query == "SELECT key, value FROM admin_settings":
            self.result=[dict(key=k,value=v) for k,v in store.settings.items()]
        elif "FROM sessions" in query:
            self.result=copy.deepcopy(store.users.get(params[0]))
        elif "SELECT value FROM admin_settings" in query:
            self.result={"value":store.settings[params[0]]} if params[0] in store.settings else None
        elif query.startswith("INSERT INTO admin_settings"):
            store.settings[params[0]]=params[1]
        elif query.startswith("UPDATE sessions"):
            pdf,chat,search,ai,date,user=params
            store.users[user].update(pdf_count=pdf,chat_count=chat,search_count=search,ai_count=ai,quota_date=date)
        else: raise AssertionError(query)
    def fetchone(self): return self.result
    def fetchall(self): return self.result

class QuotaTests(unittest.TestCase):
    def setUp(self):
        self.store=Store()
        self.database=types.SimpleNamespace(get_db=lambda:Connection(self.store),release_db=lambda conn:None)
        self.patch=patch.dict("sys.modules", {"services.database":self.database})
        self.patch.start()
    def tearDown(self): self.patch.stop()
    def attempt(self, user="0", kind="chat", model="openrouter/free"):
        try:
            reserve_quota(user,kind,model if kind in ("ai","chat") else None)
            return True
        except QuotaError: return False

    def test_competing_requests_cannot_exceed_user_limit(self):
        self.store.settings["quota_chat_per_day"]="3"
        with ThreadPoolExecutor(max_workers=12) as workers:
            results=list(workers.map(lambda _:self.attempt(),range(20)))
        self.assertEqual(sum(results),3)
        self.assertEqual(self.store.users["0"]["chat_count"],3)

    def test_new_identities_cannot_bypass_shared_budget(self):
        self.store.settings["quota_ai_global_per_day"]="5"
        with ThreadPoolExecutor(max_workers=12) as workers:
            results=list(workers.map(lambda i:self.attempt(str(i)),range(20)))
        self.assertEqual(sum(results),5)
        self.assertEqual(sum(row["chat_count"] for row in self.store.users.values()),5)

    def test_disabled_model_and_model_quota_block_before_consumption(self):
        self.store.settings["model_enabled_openrouter/free"]="false"
        self.assertFalse(self.attempt())
        self.assertEqual(self.store.users["0"]["chat_count"],0)
        self.store.settings["model_enabled_openrouter/free"]="true"
        self.store.settings["model_quota_openrouter/free"]="1"
        self.assertTrue(self.attempt()); self.assertFalse(self.attempt())

    def test_daily_reset_is_atomic_and_keeps_other_counters(self):
        self.store.users["0"].update(chat_count=99,pdf_count=99,quota_date="2000-01-01")
        self.assertTrue(self.attempt())
        self.assertEqual(self.store.users["0"]["pdf_count"],0)
        self.assertTrue(self.attempt(kind="pdf"))
        self.assertEqual(self.store.users["0"]["chat_count"],1)

    def test_user_and_shared_minute_limits(self):
        self.store.settings["quota_ai_user_per_minute"]="1"
        self.assertTrue(self.attempt()); self.assertFalse(self.attempt())
        self.store.settings["quota_ai_global_per_minute"]="1"
        self.assertFalse(self.attempt("1"))

    def test_invalid_config_and_unavailable_database_fail_closed(self):
        self.store.settings["quota_chat_per_day"]="broken"
        self.assertFalse(self.attempt())
        self.database.get_db=lambda:(_ for _ in ()).throw(RuntimeError("offline"))
        self.assertFalse(self.attempt())


if __name__ == "__main__": unittest.main()
