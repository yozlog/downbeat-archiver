import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from downbeat_archiver.cli import _next_run
from downbeat_archiver.core import infer_year, is_valid_pdf, parse_archive


class CoreTests(unittest.TestCase):
    def test_year_formats(self):
        cases = {
            "DB0908": 2008,
            "DB1009": 2009,
            "DB201310": 2013,
            "DB1408": 2014,
            "DB20_01": 2020,
            "DB24_07_Historical": 2024,
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(infer_year(name), expected)

    def test_archive_direct_legacy_and_viewer_fallback(self):
        page = """
        <td><a href='https://archive.maherpublications.com/view/123'>
        <img src='https://www.downbeat.com/digitaledition/magazinecovers/2025/DB25_08.jpg'></a>
        <a href='http://www.downbeat.com/digitaledition/2025/DB25_08/DB25_08.pdf'>PDF</a></td>
        <a href='http://www.downbeat.com/digitaledition/2009/DB1009/default.html'>October 2009</a>
        """
        issues = {issue.name: issue for issue in parse_archive(page)}
        self.assertEqual(set(issues), {"DB1009", "DB25_08"})
        self.assertEqual(issues["DB1009"].year, 2009)
        self.assertEqual(issues["DB25_08"].fallback_viewer_url, "https://archive.maherpublications.com/view/123")

    def test_archive_ignores_mismatched_year_typo(self):
        page = """
        <a href='http://www.downbeat.com/digitaledition/2012/DB201302/default.html'>bad</a>
        <a href='http://www.downbeat.com/digitaledition/2013/DB201302/default.html'>good</a>
        """
        issues = parse_archive(page)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].year, 2013)
        self.assertIn("/2013/", issues[0].source_url)

    def test_pdf_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "issue.pdf"
            path.write_bytes(b"%PDF-1.7\n" + b"x" * 2048)
            self.assertTrue(is_valid_pdf(path))
            self.assertFalse(is_valid_pdf(path, expected_size=1))

    def test_next_month(self):
        zone = ZoneInfo("UTC")
        now = datetime(2026, 8, 15, 12, tzinfo=zone)
        self.assertEqual(_next_run(now, 1, 3), datetime(2026, 9, 1, 3, tzinfo=zone))


if __name__ == "__main__":
    unittest.main()
