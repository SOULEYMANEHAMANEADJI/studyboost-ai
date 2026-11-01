"""Offline checks: no credentials, network, database or Streamlit server."""
import io
import json
import logging
import runpy
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError


class OpenRouterTests(unittest.TestCase):
    def setUp(self):
        modules = {
            "streamlit": types.SimpleNamespace(secrets={"OPENROUTER_API_KEY": "test-key"}),
            "dotenv": types.SimpleNamespace(load_dotenv=lambda: None),
            "services.logger": types.SimpleNamespace(get_logger=lambda name: logging.getLogger("test-ai")),
        }
        with patch.dict("sys.modules", modules):
            self.api = runpy.run_path(str(Path(__file__).resolve().parents[1] / "services/ai.py"))
        self.call = self.api["_call_openrouter"]
        self.env = self.call.__globals__
        self.error = self.api["StudyBoostAIError"]

    def response(self, payload):
        return io.BytesIO(json.dumps(payload).encode())

    def assert_code(self, code, effect):
        with patch.dict(self.env, {"urlopen": effect}):
            with self.assertRaises(self.error) as caught:
                self.call([{"role": "user", "content": "Bonjour"}])
        self.assertEqual(caught.exception.code, code)

    def test_success_and_request(self):
        def send(request, timeout):
            self.assertEqual(request.full_url, "https://openrouter.ai/api/v1/chat/completions")
            self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
            self.assertEqual(json.loads(request.data)["model"], "openrouter/free")
            return self.response({"choices": [{"message": {"content": " Bonjour "}}]})
        with patch.dict(self.env, {"urlopen": send}):
            self.assertEqual(self.call([]), "Bonjour")

    def test_each_menu_model_is_sent_unchanged(self):
        models = self.api["AVAILABLE_MODELS"]
        self.assertGreaterEqual(len(models), 3)
        for model in models.values():
            with self.subTest(model=model):
                self.assertTrue(model == "openrouter/free" or model.endswith(":free"))
                def send(request, timeout):
                    self.assertEqual(json.loads(request.data)["model"], model)
                    return self.response({"choices": [{"message": {"content": "OK"}}]})
                with patch.dict(self.env, {"urlopen": send}):
                    self.assertEqual(self.call([], model=model), "OK")

    def test_http_errors(self):
        for status, code in [(400,"bad_request"),(401,"auth"),(402,"credits"),(403,"permission"),(404,"model_unavailable"),(429,"rate_limit")]:
            with self.subTest(status=status):
                def fail(*args, **kwargs):
                    raise HTTPError("https://openrouter.ai", status, "error", {}, io.BytesIO())
                self.assert_code(code, fail)

    def test_embedded_error(self):
        self.assert_code("rate_limit", lambda *a, **k: self.response({"error": {"code": 429}}))

    def test_empty_and_malformed(self):
        self.assert_code("empty", lambda *a, **k: self.response({"choices": [{"message": {"content": None}}]}))
        self.assert_code("unknown", lambda *a, **k: self.response({}))

    def test_network_and_timeout(self):
        def network(*a, **k): raise URLError("offline")
        def timeout(*a, **k): raise TimeoutError()
        self.assert_code("network", network)
        self.assert_code("timeout", timeout)

    def test_missing_key_and_environment_fallback(self):
        with patch.dict(self.env, {"st": types.SimpleNamespace(secrets={})}), patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(self.error) as caught:
                self.call([])
            self.assertEqual(caught.exception.code, "config")
            with patch.dict("os.environ", {"OPENROUTER_API_KEY": " env-key "}):
                self.assertEqual(self.api["_get_key"]("OPENROUTER_API_KEY"), "env-key")

    def test_stale_or_paid_model_rejected(self):
        with self.assertRaises(self.error) as caught:
            self.call([], model="old-or-paid-model")
        self.assertEqual(caught.exception.code, "model_unavailable")

    def test_transient_failure_retried(self):
        calls = []
        def send(*a, **k):
            calls.append(1)
            if len(calls) == 1:
                raise HTTPError("https://openrouter.ai", 503, "unavailable", {}, io.BytesIO())
            return self.response({"choices": [{"message": {"content": "OK"}}]})
        with patch.dict(self.env, {"urlopen": send, "time": types.SimpleNamespace(sleep=lambda seconds: None)}):
            self.assertEqual(self.call([], max_retries=2), "OK")
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
