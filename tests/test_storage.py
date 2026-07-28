import json
import tempfile
import unittest
from pathlib import Path

from szu_guardian.models import AppConfig
from szu_guardian.storage import ConfigStore


class ConfigStoreTests(unittest.TestCase):
    @unittest.skipUnless(__import__("sys").platform == "win32", "Windows DPAPI only")
    def test_password_is_encrypted_at_rest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            store = ConfigStore(path)
            original = AppConfig(
                username="123456",
                password="very-private-password",
                interval_minutes=3,
            )

            store.save(original)
            raw = path.read_text(encoding="utf-8")
            payload = json.loads(raw)
            restored = store.load()

            self.assertNotIn(original.password, raw)
            self.assertTrue(payload["password_dpapi"])
            self.assertEqual(restored.password, original.password)


if __name__ == "__main__":
    unittest.main()
