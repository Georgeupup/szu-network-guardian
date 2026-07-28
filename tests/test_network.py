import unittest
from unittest.mock import Mock

from szu_guardian.models import AppConfig
from szu_guardian.network import NetworkClient


def response(url, status=200, text=""):
    value = Mock()
    value.url = url
    value.status_code = status
    value.text = text
    value.raise_for_status.return_value = None
    return value


class NetworkClientTests(unittest.TestCase):
    def test_online_does_not_send_login(self):
        session = Mock()
        session.headers = {}
        session.get.return_value = response(
            "https://www.baidu.com/favicon.ico"
        )
        client = NetworkClient(
            session=session,
            portal_session=session,
            sleeper=lambda _: None,
        )

        result = client.ensure_connected(
            AppConfig(username="user", password="password")
        )

        self.assertTrue(result.connected)
        session.post.assert_not_called()

    def test_offline_sends_login_and_verifies(self):
        session = Mock()
        session.headers = {}
        session.get.side_effect = [
            response("http://portal.local", text="login"),
            response("http://portal.local", text="login"),
            response(
                "http://172.30.255.42:801/eportal/portal/login/",
                text='jsonpReturn({"result":1,"msg":"认证成功"});',
            ),
            response("https://www.baidu.com/favicon.ico"),
        ]
        client = NetworkClient(
            session=session,
            portal_session=session,
            sleeper=lambda _: None,
            verify_delays=(0,),
        )

        result = client.ensure_connected(
            AppConfig(
                username="user",
                password="password",
                zone="dormitory",
            )
        )

        self.assertTrue(result.connected)
        self.assertIn("自动重连", result.message)

    def test_auto_zone_prefers_dormitory_when_gateway_is_reachable(self):
        session = Mock()
        session.headers = {}
        session.get.side_effect = [
            response("http://172.30.255.42/"),
            response("https://net.szu.edu.cn/"),
        ]
        client = NetworkClient(session=session, portal_session=session)

        self.assertEqual(client.detect_zone(), "dormitory")


if __name__ == "__main__":
    unittest.main()
