import unittest

from szu_guardian.models import AppConfig
from szu_guardian.monitor import MonitorController
from szu_guardian.network import ConnectionResult


class _FakeClient:
    def __init__(self, result):
        self.result = result

    def ensure_connected(self, config, progress_callback=None):
        return self.result


class MonitorControllerTests(unittest.TestCase):
    def test_failed_check_refreshes_client_before_next_cycle(self):
        clients = []
        results = [
            ConnectionResult(False, "offline"),
            ConnectionResult(True, "online"),
        ]

        def factory():
            client = _FakeClient(results[len(clients)])
            clients.append(client)
            return client

        controller = MonitorController(lambda event: None, client_factory=factory)
        controller._wait_until_next_check = lambda interval: "stop"

        controller._run_loop(AppConfig(username="u", password="p"))

        self.assertEqual(len(clients), 2)

    def test_resume_refreshes_client_immediately(self):
        clients = []

        def factory():
            client = _FakeClient(ConnectionResult(True, "online"))
            clients.append(client)
            return client

        controller = MonitorController(lambda event: None, client_factory=factory)
        wait_reasons = iter(("resume", "stop"))
        controller._wait_until_next_check = lambda interval: next(wait_reasons)

        controller._run_loop(AppConfig(username="u", password="p"))

        self.assertEqual(len(clients), 2)


if __name__ == "__main__":
    unittest.main()
