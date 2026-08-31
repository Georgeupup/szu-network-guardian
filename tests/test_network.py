import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from szu_guardian.models import AppConfig, ZONE_AUTO, ZONE_DORMITORY
from szu_guardian.network import ConnectionResult, NetworkClient


def response(url, status=200, text=""):
    value = Mock()
    value.url = url
    value.status_code = status
    value.text = text
    value.headers = {}
    value.raise_for_status.return_value = None
    return value


def connected_probe_response(url, **kwargs):
    if "msftconnecttest.com" in url:
        return response(url, text="Microsoft Connect Test")
    token = parse_qs(urlparse(url).query)["wd"][0]
    value = response(url, status=302, text=token)
    value.headers = {"Location": "https://wappass.baidu.com/captcha"}
    return value


class NetworkClientTests(unittest.TestCase):
    def test_online_does_not_send_login(self):
        session = Mock()
        session.headers = {}
        session.get.side_effect = connected_probe_response
        client = NetworkClient(
            session=session,
            portal_session=session,
            sleeper=lambda _: None,
        )

        result = client.ensure_connected(
            AppConfig(
                username="user",
                password="password",
                zone=ZONE_DORMITORY,
            )
        )

        self.assertTrue(result.connected)
        session.post.assert_not_called()

    def test_expired_teaching_session_reconnects_even_when_web_is_reachable(self):
        session = Mock()
        session.headers = {}
        client = NetworkClient(
            session=session,
            portal_session=session,
            sleeper=lambda _: None,
            verify_delays=(0,),
        )
        config = AppConfig(username="user", password="password")

        with (
            patch.object(client, "_teaching_online_status", return_value=False),
            patch.object(
                client,
                "check_connection",
                return_value=ConnectionResult(True, "网络连接正常"),
            ) as check,
            patch.object(client, "send_login", return_value="认证成功") as login,
        ):
            result = client.ensure_connected(config)

        self.assertTrue(result.connected)
        login.assert_called_once_with(config, None)
        check.assert_called_once_with()

    def test_offline_sends_login_and_verifies(self):
        session = Mock()
        session.headers = {}
        calls = 0

        def offline_then_login_then_online(url, **kwargs):
            nonlocal calls
            calls += 1
            if calls <= 2:
                return response("http://portal.local", text="login")
            if calls == 3:
                return response(
                    "http://172.30.255.42:801/eportal/portal/login/",
                    text='jsonpReturn({"result":1,"msg":"认证成功"});',
                )
            return connected_probe_response(url)

        session.get.side_effect = offline_then_login_then_online
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
