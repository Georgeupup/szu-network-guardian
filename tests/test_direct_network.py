import socket
import unittest
from unittest.mock import patch

from szu_guardian.direct_network import DirectRoute, local_ipv4_candidates


class DirectNetworkTests(unittest.TestCase):
    def test_fake_ip_and_link_local_addresses_are_excluded(self):
        with patch.object(
            socket,
            "gethostbyname_ex",
            return_value=(
                "test-pc",
                [],
                ["198.18.0.1", "169.254.1.2", "172.30.8.9", "192.168.1.8"],
            ),
        ):
            result = local_ipv4_candidates()

        self.assertEqual(result, ["172.30.8.9", "192.168.1.8"])

    def test_rewrite_url_uses_direct_dns_result_and_preserves_host(self):
        route = DirectRoute("172.30.8.9")
        route._cache["net.szu.edu.cn"] = ["172.31.63.36"]

        url, host = route.rewrite_url(
            "https://net.szu.edu.cn/cgi-bin/get_challenge?callback=_"
        )

        self.assertEqual(host, "net.szu.edu.cn")
        self.assertEqual(
            url,
            "https://172.31.63.36/cgi-bin/get_challenge?callback=_",
        )


if __name__ == "__main__":
    unittest.main()
