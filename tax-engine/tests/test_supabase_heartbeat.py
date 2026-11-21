"""Offline regression tests for DocuFiscal's isolated Supabase heartbeat.

Run from tax-engine/: python -m unittest discover -s tests -v
No live HTTP, Supabase, email, reminders, or payment APIs are used.
"""
from __future__ import annotations

import os
import sys
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main  # noqa: E402


class FakeResponse:
    def __init__(self, status: int):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class SupabaseKeepaliveTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(
            os.environ,
            {"SUPABASE_URL": "https://example.invalid", "SUPABASE_KEY": "unit-test-key"},
            clear=True,
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_http_200_and_204_are_success(self):
        for status in (200, 204):
            with self.subTest(status=status), mock.patch.object(
                main.urllib.request, "urlopen", return_value=FakeResponse(status)
            ) as urlopen:
                result = main.supabase_keepalive()
                self.assertEqual(result["ok"], True)
                self.assertEqual(result["http_status"], status)
                request = urlopen.call_args.args[0]
                self.assertEqual(request.get_method(), "GET")
                self.assertEqual(urlopen.call_args.kwargs["timeout"], 8)

    def test_http_401_403_404_and_500_are_failures(self):
        for status in (401, 403, 404, 500):
            error = urllib.error.HTTPError(
                "https://example.invalid/rest/v1/", status, "test", None, None
            )
            with self.subTest(status=status), mock.patch.object(
                main.urllib.request, "urlopen", side_effect=error
            ):
                result = main.supabase_keepalive()
                self.assertEqual(result["ok"], False)
                self.assertEqual(result["supabase"], "http_error")
                self.assertEqual(result["http_status"], status)

    def test_timeout_is_reported_as_failure(self):
        with mock.patch.object(main.urllib.request, "urlopen", side_effect=TimeoutError()):
            result = main.supabase_keepalive()
        self.assertEqual(result, {"supabase": "unreachable", "ok": False})

    def test_connection_failure_is_reported_as_failure(self):
        with mock.patch.object(
            main.urllib.request, "urlopen", side_effect=urllib.error.URLError("offline")
        ):
            result = main.supabase_keepalive()
        self.assertEqual(result, {"supabase": "unreachable", "ok": False})

    def test_missing_url_or_key_fails_closed_without_network(self):
        for values in ({"SUPABASE_KEY": "unit-test-key"}, {"SUPABASE_URL": "https://example.invalid"}, {}):
            with self.subTest(values=values), mock.patch.dict(os.environ, values, clear=True), mock.patch.object(
                main.urllib.request, "urlopen"
            ) as urlopen:
                result = main.supabase_keepalive()
                self.assertEqual(result, {"supabase": "not_configured", "ok": False})
                urlopen.assert_not_called()

    def test_configured_table_is_used_without_mutating_requests(self):
        os.environ["SUPABASE_KEEPALIVE_TABLE"] = "heartbeat_probe"
        with mock.patch.object(
            main.urllib.request, "urlopen", return_value=FakeResponse(200)
        ) as urlopen:
            main.supabase_keepalive()
        request = urlopen.call_args.args[0]
        self.assertIn("/rest/v1/heartbeat_probe?select=*&limit=1", request.full_url)
        self.assertEqual(request.get_method(), "GET")


class HeartbeatAuthenticationAndIsolationTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_missing_server_auth_configuration_returns_503(self):
        with self.assertRaises(main.HTTPException) as caught:
            main.require_cron_or_api_key()
        self.assertEqual(caught.exception.status_code, 503)

    def test_missing_or_invalid_credentials_return_401(self):
        os.environ["CRON_SECRET"] = "cron-test-secret"
        for authorization, api_key in ((None, None), ("Bearer wrong", None), (None, "wrong")):
            with self.subTest(authorization=authorization, api_key=api_key), self.assertRaises(main.HTTPException) as caught:
                main.require_cron_or_api_key(authorization=authorization, x_api_key=api_key)
            self.assertEqual(caught.exception.status_code, 401)

    def test_valid_cron_bearer_and_admin_key_are_accepted(self):
        os.environ["CRON_SECRET"] = "cron-test-secret"
        os.environ["ADMIN_API_KEY"] = "admin-test-key"
        self.assertIsNone(main.require_cron_or_api_key(authorization="Bearer cron-test-secret"))
        self.assertIsNone(main.require_cron_or_api_key(x_api_key="admin-test-key"))

    def test_heartbeat_route_is_authenticated_and_does_not_run_reminders(self):
        route = next(r for r in main.app.routes if getattr(r, "path", None) == "/api/supabase/heartbeat")
        self.assertTrue(any(dep.call is main.require_cron_or_api_key for dep in route.dependencies))
        with mock.patch.object(main, "supabase_keepalive", return_value={"ok": True, "supabase": "pinged"}), \
             mock.patch.object(main, "state_txn", side_effect=AssertionError("state transaction must not run")), \
             mock.patch.object(main, "dispatch_due_reminders", side_effect=AssertionError("reminders must not run")):
            result = main.supabase_heartbeat()
        self.assertEqual(result["status"], "ok")

    def test_heartbeat_failure_is_503_and_still_does_not_run_reminders(self):
        with mock.patch.object(main, "supabase_keepalive", return_value={"ok": False, "supabase": "unreachable"}), \
             mock.patch.object(main, "state_txn", side_effect=AssertionError("state transaction must not run")), \
             mock.patch.object(main, "dispatch_due_reminders", side_effect=AssertionError("reminders must not run")):
            with self.assertRaises(main.HTTPException) as caught:
                main.supabase_heartbeat()
        self.assertEqual(caught.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
