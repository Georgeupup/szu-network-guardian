import unittest

from szu_guardian.models import AppConfig


class AppConfigTests(unittest.TestCase):
    def test_valid_config(self):
        config = AppConfig(
            username=" 123456 ",
            password="secret",
            interval_minutes=5,
        )
        config.validate()
        self.assertEqual(config.username, "123456")

    def test_rejects_invalid_interval(self):
        config = AppConfig(username="1", password="2", interval_minutes=0)
        with self.assertRaisesRegex(ValueError, "1 到 1440"):
            config.validate()


if __name__ == "__main__":
    unittest.main()
