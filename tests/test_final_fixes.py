"""Transactional failure cases and consistent administration metrics."""
import ast
import copy
import json
import logging
import types
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch
from services.admin_auth import authenticate_admin

ROOT=Path(__file__).resolve().parents[1]

def functions(names,env):
    tree=ast.parse((ROOT/"services/database.py").read_text(encoding="utf-8"))
    nodes=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name in names]
    for node in nodes: node.decorator_list=[]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),"database-tests","exec"),env)

class Transaction:
    def __init__(self,fail_delete=False,auto="true",last=None):
        self.state={"auto_cleanup_enabled":auto,"retention_days":"7"};self.commands=[];self.fail_delete=fail_delete;self.rollbacks=0
        if last:self.state["last_cleanup"]=last
    def __enter__(self):self.before=copy.deepcopy(self.state);return self
    def __exit__(self,error,*args):
        if error:self.state=self.before;self.rollbacks+=1
    def cursor(self,**kwargs):return Cursor(self)
class Cursor:
    def __init__(self,conn):self.conn=conn;self.result=None
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def execute(self,query,params=None):
        self.conn.commands.append((query,params))
        if "pg_try_advisory" in query:self.result={"acquired":True}
        elif "SELECT key,value" in query:self.result=[dict(key=k,value=v) for k,v in self.conn.state.items()]
        elif "SELECT value" in query:self.result={"value":self.conn.state["security:admin_login"]} if "security:admin_login" in self.conn.state else None
        elif query.startswith("DELETE"):
            if self.conn.fail_delete and "activity_logs" in query:raise RuntimeError("test failure")
            self.conn.state["deleted"]=True
        elif "last_cleanup',%s" in query:self.conn.state["last_cleanup"]=params[0]
        elif "security:admin_login',%s" in query:self.conn.state["security:admin_login"]=params[0]
    def fetchone(self):return self.result
    def fetchall(self):return self.result

class FinalFixTests(unittest.TestCase):
    def cleanup(self,conn,force=False):
        returned=[];env={"get_db":lambda:conn,"release_db":returned.append,"datetime":datetime,"timezone":timezone,"timedelta":timedelta,"logger":logging.getLogger("cleanup-test"),"psycopg2":types.SimpleNamespace(extras=types.SimpleNamespace(RealDictCursor=object))}
        functions(["cleanup_old_data"],env)
        result=env["cleanup_old_data"](force=force)
        self.assertEqual(returned,[conn]);return result
    def test_failed_cleanup_rolls_back_and_does_not_mark_success(self):
        conn=Transaction(fail_delete=True)
        self.assertFalse(self.cleanup(conn))
        self.assertNotIn("last_cleanup",conn.state);self.assertNotIn("deleted",conn.state)
        self.assertEqual(conn.rollbacks,1)
    def test_manual_cleanup_works_when_auto_disabled(self):
        conn=Transaction(auto="false")
        self.assertIsNone(self.cleanup(conn))
        self.assertTrue(self.cleanup(conn,force=True));self.assertIn("last_cleanup",conn.state)
    def test_recent_cleanup_is_skipped(self):
        conn=Transaction(last=datetime.now(timezone.utc).isoformat())
        self.assertIsNone(self.cleanup(conn));self.assertNotIn("deleted",conn.state)
    def test_delete_reports_failure_without_claiming_success(self):
        def fail(*args):raise RuntimeError("offline")
        messages=[];env={"_execute":fail,"st":types.SimpleNamespace(error=messages.append),"logger":logging.getLogger("delete-test")}
        functions(["clear_chat_history"],env)
        self.assertFalse(env["clear_chat_history"]("A"));self.assertTrue(messages)
        env["_execute"]=lambda *a:0
        self.assertTrue(env["clear_chat_history"]("A"))
    def test_admin_lock_survives_new_sessions(self):
        conn=Transaction();fake=types.SimpleNamespace(get_db=lambda:conn,release_db=lambda c:None)
        with patch.dict("sys.modules",{"services.database":fake}):
            for _ in range(5):self.assertFalse(authenticate_admin("wrong","correct")[0])
            # A completely new browser/session hits the same database lock.
            self.assertFalse(authenticate_admin("correct","correct")[0])
            state=json.loads(conn.state["security:admin_login"]);state["locked_until"]=0;state["last_attempt"]=0
            conn.state["security:admin_login"]=json.dumps(state)
            self.assertTrue(authenticate_admin("correct","correct")[0])
        self.assertNotIn("correct",json.dumps(conn.state))
    def test_statistics_totals_are_not_limited_to_list_size(self):
        queries=[]
        def one(query,params=None):
            queries.append((query,params))
            return {"cnt":12} if "FROM sessions" in query else {"cnt":650,"avg_rating":4.2,"emails":300}
        def many(query,params=None):
            queries.append((query,params))
            if "GROUP BY day" in query:return [{"day":"2026-11-02","cnt":15,"active":3}]
            return []
        env={"_fetchone":one,"_fetchall":many,"datetime":datetime,"timezone":timezone,"timedelta":timedelta,"logger":logging.getLogger("stats-test")}
        functions(["admin_get_stats"],env);stats=env["admin_get_stats"](7)
        self.assertFalse(stats["load_failed"]);self.assertEqual(stats["feedbacks"],650);self.assertEqual(stats["email_count"],300)
        for query,params in queries:
            if "FROM feedbacks" in query:self.assertIn("created_at >= %s",query);self.assertIsNotNone(params)

if __name__=="__main__":unittest.main()
