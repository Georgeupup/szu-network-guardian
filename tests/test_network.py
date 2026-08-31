import unittest
from unittest.mock import Mock, patch

from szu_guardian.models import AppConfig, ZONE_AUTO
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
            response(
                "http://www.msftconnecttest.com/connecttest.txt",
                text="Microsoft Connect Test",
            ),
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

    def test_auto_mode_tries_teaching_first(self):
        session = Mock()
        session.headers = {}
        client = NetworkClient(session=session, portal_session=session)
        config = AppConfig(
            username="user",
            password="password",
            zone=ZONE_AUTO,
        )

        with (
            patch.object(
                client,
                "_login_teaching",
                return_value="教学区认证成功",
            ) as teaching,
            patch.object(client, "_login_dormitory") as dormitory,
        ):
            result = client.send_login(config)

        self.assertEqual(result, "教学区认证成功")
        teaching.assert_called_once_with(config)
        dormitory.assert_not_called()

    def test_auto_mode_falls_back_to_dormitory(self):
        session = Mock()
        session.headers = {}
        client = NetworkClient(session=session, portal_session=session)
        config = AppConfig(
            username="user",
            password="password",
            zone=ZONE_AUTO,
        )

        with (
            patch.object(
                client,
                "_login_teaching",
                side_effect=ConnectionError("不在教学区"),
            ) as teaching,
            patch.object(
                client,
                "_login_dormitory",
                return_value="宿舍区认证成功",
            ) as dormitory,
        ):
            result = client.send_login(config)

        self.assertEqual(result, "宿舍区认证成功")
        teaching.assert_called_once_with(config)
        dormitory.assert_called_once_with(config)


if __name__ == "__main__":
    unittest.main()
