import datetime as dt
import tempfile
import unittest
from pathlib import Path

from szu_guardian.local_log import LocalLog


class LocalLogTests(unittest.TestCase):
    def test_writes_daily_log_and_removes_files_older_than_seven_days(self):
        with tempfile.TemporaryDirectory() as directory:
            log_dir = Path(directory)
            old_file = log_dir / "guardian-2026-07-01.log"
            old_file.write_text("old", encoding="utf-8")
            log = LocalLog(log_dir)

            log.cleanup(dt.datetime(2026, 7, 28, 10, 0, 0))
            log.write("network ok")

            self.assertFalse(old_file.exists())
            today_files = list(log_dir.glob(f"guardian-{dt.date.today():%Y-%m-%d}.log"))
            self.assertEqual(len(today_files), 1)
            self.assertIn("network ok", today_files[0].read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
