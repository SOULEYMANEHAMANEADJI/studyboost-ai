import ast
import logging
import os
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "services/database.py"
def functions(names, env):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    for node in nodes: node.decorator_list = []
    env.setdefault("ensure_draft_schema",lambda:None)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE), "exec"), env)

class DatabaseTests(unittest.TestCase):
    def test_neon_config_never_uses_legacy_supabase(self):
        env = {"st":types.SimpleNamespace(secrets={"SUPABASE_URL":"https://legacy.invalid"}), "os":os}
        functions(["_get_db_url"], env)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError): env["_get_db_url"]()
            with patch.dict(os.environ, {"DATABASE_URL":"postgresql://example/db"}):
                self.assertEqual(env["_get_db_url"](), "postgresql://example/db")
        env["st"].secrets["DATABASE_URL"] = "postgresql://configured/db"
        self.assertEqual(env["_get_db_url"](), "postgresql://configured/db")

    def test_history_and_draft_queries_scope_by_owner(self):
        queries = []
        def fetch(query, params):
            queries.append((query, params))
            if "chat_history" in query:
                return [{"role":"user", "content":"private-" + params[0]}]
            return {"draft_text":"draft-"+params[0], "preferred_model":"openrouter/free"}
        env = {"_fetchall":fetch, "_fetchone":fetch, "logger":logging.getLogger("test-db")}
        functions(["get_chat_history", "load_draft"], env)
        for user in ["A", "B"]:
            self.assertEqual(env["get_chat_history"](user)[0]["content"], "private-"+user)
            self.assertEqual(env["load_draft"](user)[0], "draft-"+user)
        for query, params in queries:
            self.assertIn("WHERE",query)
            self.assertEqual(len(params), 1)

    def test_health_is_read_only_and_releases_connection(self):
        queries, returned = [], []
        class Conn:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def cursor(self): return self
            def execute(self, query): queries.append(query)
            def fetchone(self): return (1,)
        conn = Conn()
        env = {"get_db":lambda: conn, "release_db":returned.append, "logger":logging.getLogger("test-db")}
        functions(["check_database_health"], env)
        self.assertTrue(env["check_database_health"]())
        self.assertEqual(returned, [conn])
        self.assertTrue(all(query.startswith("SELECT") for query in queries))
        self.assertTrue(all(query == "SELECT 1" or query.endswith("LIMIT 0") for query in queries))

if __name__ == "__main__": unittest.main()
