"""
core/tests/test_app_context_session.py

Basic unit tests for AppContext session API and observer mechanism.
Uses unittest to avoid external test dependencies.
"""

from __future__ import annotations

import unittest

from core.common.app_context import AppContext
from core.common.session_events import UserSessionEvent
from core.models.user import User


class TestAppContextSession(unittest.TestCase):
    def setUp(self) -> None:
        # Ensure we start clean for each test
        AppContext.clear_current_user(reason="test_setup")
        # Best-effort cleanup of observers
        # (unsubscribe may fail if weakref already dead)
        self._events: list[UserSessionEvent] = []

        def _cb(ev: UserSessionEvent) -> None:
            self._events.append(ev)

        self._cb = _cb
        AppContext.subscribe_user_session(self._cb)

    def tearDown(self) -> None:
        AppContext.unsubscribe_user_session(self._cb)
        AppContext.clear_current_user(reason="test_teardown")

    def test_login_event_emitted(self) -> None:
        u = User(id=1, username="alice", password_hash="x", email="a@example.com")
        AppContext.set_current_user(u, reason="login")
        self.assertEqual(AppContext.get_current_user(), u)
        self.assertTrue(self._events)
        ev = self._events[-1]
        self.assertEqual(ev.type, "login")
        self.assertIsNone(ev.old_user)
        self.assertEqual(ev.new_user.username, "alice")

    def test_logout_event_emitted(self) -> None:
        u = User(id=2, username="bob", password_hash="x", email="b@example.com")
        AppContext.set_current_user(u, reason="login")
        AppContext.clear_current_user(reason="logout")
        self.assertIsNone(AppContext.get_current_user())
        ev = self._events[-1]
        self.assertEqual(ev.type, "logout")
        self.assertIsNotNone(ev.old_user)
        self.assertIsNone(ev.new_user)

    def test_unsubscribe_stops_events(self) -> None:
        AppContext.unsubscribe_user_session(self._cb)
        self._events.clear()
        u = User(id=3, username="carol", password_hash="x", email="c@example.com")
        AppContext.set_current_user(u, reason="login")
        self.assertEqual(self._events, [])


if __name__ == "__main__":
    unittest.main()
