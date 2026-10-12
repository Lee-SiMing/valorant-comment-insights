import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from run_scraper import normalize_outputs, read_urls  # noqa: E402


class ScraperWrapperTests(unittest.TestCase):
    def test_crawl_requires_platform_authorization(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            source = Path(tmp) / "urls.txt"
            output = Path(tmp) / "run"
            source.write_text("https://www.bilibili.com/video/BV1c14y147g6\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(ROOT / "scripts" / "run_scraper.py"), "--urls", str(source), "--output-dir", str(output)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("prior written permission", result.stderr)
            self.assertFalse(output.exists())

    def test_url_validation_and_deduplication(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            source = Path(tmp) / "urls.txt"
            source.write_text("https://www.bilibili.com/video/BV1c14y147g6?spm=abc\nhttps://www.bilibili.com/video/BV1c14y147g6\n", encoding="utf-8")
            self.assertEqual(read_urls(source), [("BV1c14y147g6", "https://www.bilibili.com/video/BV1c14y147g6")])
            source.write_text("https://example.com/video/BV1c14y147g6\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_urls(source)

    def test_normalization_and_missing_video(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            run_dir = Path(tmp)
            with (run_dir / "BV1c14y147g6.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["评论ID", "根评论ID", "父评论ID", "隶属关系", "评论内容", "发布时间", "点赞数"])
                writer.writeheader()
                writer.writerow({"评论ID": "123", "根评论ID": "", "父评论ID": "", "隶属关系": "一级评论", "评论内容": "皮肤很好看，但我不会买", "发布时间": "2026-10-12", "点赞数": "3"})
            videos = [("BV1c14y147g6", "https://www.bilibili.com/video/BV1c14y147g6"), ("BV17M41117eg", "https://www.bilibili.com/video/BV17M41117eg")]
            manifest = normalize_outputs(run_dir, videos)
            self.assertEqual([item["status"] for item in manifest], ["ok", "no_csv"])
            with (run_dir / "comments_normalized.csv").open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["comment_key"], "123")
            self.assertEqual(rows[0]["comment_id"], "123")
            self.assertEqual(rows[0]["comment_text"], "皮肤很好看，但我不会买")


if __name__ == "__main__":
    unittest.main()
