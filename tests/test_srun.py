import unittest
from unittest.mock import Mock

from szu_guardian.srun import (
    SrunClient,
    hmac_md5,
    srun_base64,
    xencode,
)


def response(text, url="https://net.szu.edu.cn/"):
    value = Mock()
    value.status_code = 200
    value.text = text
    value.url = url
    value.headers = {}
    value.raise_for_status.return_value = None
    return value


class SrunCryptoTests(unittest.TestCase):
    def test_custom_base64_matches_upstream_vector(self):
        self.assertEqual(srun_base64(b"E99p1ant"), "hFYeMJiTWq+=")

    def test_xencode_matches_upstream_vector(self):
        self.assertEqual(
            xencode("aaaaaaaaaaaa", "bbbbbbbbbbbb"),
            bytes.fromhex("d4eb3234a6e57d455fdca5bcbefb3ad1"),
        )

    def test_hmac_md5_matches_upstream_vector(self):
        self.assertEqual(
            hmac_md5(
                "123",
                "a765ff3138693dbfa6888f05726588de53db72e1679a9341f04f9195d2ee3b8e",
            ),
            "b4cc9d0fcff069fcd31afae0b7001434",
        )


class SrunClientTests(unittest.TestCase):
    def test_login_requires_explicit_success_response(self):
        session = Mock()
        session.headers = {}
        session.get.side_effect = [
            response('<meta http-equiv="refresh" content="0;url=/srun_portal_pc?ac_id=1">'),
            response(
                '_({"challenge":"abc123","client_ip":"172.30.1.2",'
                '"error":"ok","res":"ok"})'
            ),
            response('_({"error":"ok","res":"ok","st":1})'),
        ]
        client = SrunClient("user", "password", session=session)

        result = client.login()

        self.assertTrue(result.success)
        portal_params = session.get.call_args_list[-1].kwargs["params"]
        self.assertEqual(portal_params["ac_id"], "1")
        self.assertEqual(portal_params["password"][:5], "{MD5}")
        self.assertTrue(portal_params["info"].startswith("{SRBX1}"))


if __name__ == "__main__":
    unittest.main()
