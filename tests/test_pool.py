import ast
import threading
import types
import unittest
from pathlib import Path

class OfflineError(Exception): pass
class Connection:
    def __init__(self, fail=False): self.fail=fail; self.closed=False
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def cursor(self): return self
    def execute(self,query):
        if self.fail: raise OfflineError()

class PoolTests(unittest.TestCase):
    def make_pool(self, connections):
        returned=[]
        class Raw:
            def getconn(self): return connections.pop(0)
            def putconn(self,conn,close=False): returned.append((conn,close))
        env={"threading":threading,"psycopg2":types.SimpleNamespace(OperationalError=OfflineError,InterfaceError=OfflineError,pool=types.SimpleNamespace(ThreadedConnectionPool=lambda *a,**k:Raw()))}
        tree=ast.parse((Path(__file__).resolve().parents[1]/"services/database.py").read_text(encoding="utf-8"))
        node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="ManagedPool")
        exec(compile(ast.Module(body=[node],type_ignores=[]),"pool", "exec"),env)
        return env["ManagedPool"]("postgresql://test", maximum=1,wait_seconds=0.02),returned

    def test_exhaustion_is_bounded_and_slot_is_released(self):
        first=Connection(); second=Connection()
        pool,_=self.make_pool([first,second])
        self.assertIs(pool.getconn(),first)
        with self.assertRaises(RuntimeError): pool.getconn()
        pool.putconn(first)
        self.assertIs(pool.getconn(),second)
        pool.putconn(second)

    def test_stale_connection_is_discarded_before_use(self):
        stale=Connection(fail=True); live=Connection()
        pool,returned=self.make_pool([stale,live])
        self.assertIs(pool.getconn(),live)
        self.assertEqual(returned,[(stale,True)])
        pool.putconn(live)
        with self.assertRaises(RuntimeError): pool.putconn(live)

    def test_failed_validation_does_not_leak_slot(self):
        pool,_=self.make_pool([Connection(True),Connection(True),Connection()])
        with self.assertRaises(OfflineError): pool.getconn()
        conn=pool.getconn(); pool.putconn(conn)

if __name__ == "__main__": unittest.main()
