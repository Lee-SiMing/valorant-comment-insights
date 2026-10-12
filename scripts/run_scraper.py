"""Run the bundled Bilibili scraper from an isolated per-run directory."""

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
SCRAPER = ROOT / "vendor" / "bilibili-comment-scraper" / "Bilicomment.py"
API_SCRAPER = ROOT / "scripts" / "fetch_comments_api.py"
LOCAL_DEPS = ROOT / ".python_deps"
VIDEO_RE = re.compile(r"^BV[A-Za-z0-9]{10}$")
NORMALIZED_COLUMNS = ["comment_key", "video_id", "comment_id", "root_id", "parent_id", "comment_level", "comment_text", "published_at", "likes"]


def read_urls(path: Path) -> list[tuple[str, str]]:
    if not path.is_file():
        raise ValueError(f"URL file does not exist: {path}")
    results = []
    seen = set()
    for line_number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        parts = urlparse(value)
        path_parts = parts.path.strip("/").split("/")
        if parts.scheme != "https" or parts.netloc.lower() != "www.bilibili.com" or len(path_parts) != 2 or path_parts[0] != "video" or not VIDEO_RE.fullmatch(path_parts[1]):
            raise ValueError(f"Line {line_number}: expected https://www.bilibili.com/video/BV... URL")
        video_id = path_parts[1]
        if video_id in seen:
            continue
        seen.add(video_id)
        results.append((video_id, f"https://www.bilibili.com/video/{video_id}"))
    if not results:
        raise ValueError("No valid video URLs found")
    return results


def normalize_outputs(run_dir: Path, videos: list[tuple[str, str]]) -> list[dict]:
    manifest = []
    normalized_path = run_dir / "comments_normalized.csv"
    with normalized_path.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=NORMALIZED_COLUMNS)
        writer.writeheader()
        for video_id, url in videos:
            csv_path = run_dir / f"{video_id}.csv"
            entry = {"video_id": video_id, "url": url, "raw_csv": csv_path.name if csv_path.exists() else None, "rows": 0, "status": "no_csv"}
            if csv_path.exists():
                try:
                    with csv_path.open("r", encoding="utf-8-sig", newline="") as source:
                        reader = csv.DictReader(source)
                        if not reader.fieldnames or "评论内容" not in reader.fieldnames:
                            raise ValueError("CSV lacks 评论内容 column")
                        for row_number, row in enumerate(reader, 1):
                            content = (row.get("评论内容") or "").strip()
                            if not content:
                                continue
                            writer.writerow({
                                "comment_key": row.get("评论ID") or f"{video_id}:{row_number}",
                                "video_id": video_id,
                                "comment_id": row.get("评论ID") or "",
                                "root_id": row.get("根评论ID") or "",
                                "parent_id": row.get("父评论ID") or "",
                                "comment_level": row.get("隶属关系") or "",
                                "comment_text": content,
                                "published_at": row.get("发布时间") or "",
                                "likes": row.get("点赞数") or "",
                            })
                            entry["rows"] += 1
                    entry["status"] = "ok" if entry["rows"] else "empty_csv"
                except (OSError, UnicodeError, csv.Error, ValueError) as exc:
                    entry["status"] = "invalid_csv"
                    entry["error"] = str(exc)
            manifest.append(entry)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Bilibili URL TXT and run the bundled comment scraper")
    parser.add_argument("--urls", type=Path, required=True, help="UTF-8 TXT, one Bilibili BV video URL per line")
    parser.add_argument("--output-dir", type=Path, required=True, help="Private directory for this crawl and its login state")
    parser.add_argument("--resume", action="store_true", help="Resume an existing run with the same URL list")
    parser.add_argument("--check-only", action="store_true", help="Validate and print the URL list without crawling")
    parser.add_argument("--platform-authorized", action="store_true", help="Confirm that you have the platform's required prior written permission for automated collection")
    args = parser.parse_args()

    try:
        videos = read_urls(args.urls)
        if args.check_only:
            print(json.dumps({"video_count": len(videos), "videos": videos}, ensure_ascii=False, indent=2))
            return 0
        if not args.platform_authorized:
            raise ValueError("Automated collection requires the platform's prior written permission; pass --platform-authorized only after obtaining it")

        run_dir = args.output_dir.resolve()
        if run_dir.exists() and any(run_dir.iterdir()) and not args.resume:
            raise ValueError("Output directory is not empty; choose a new directory or use --resume")
        run_dir.mkdir(parents=True, exist_ok=True)
        wanted = "".join(url + "\n" for _, url in videos)
        list_path = run_dir / "video_list.txt"
        if args.resume and list_path.exists() and list_path.read_text(encoding="utf-8") != wanted:
            raise ValueError("Resume URL list differs from the original run")
        if args.resume and not list_path.exists() and any(run_dir.iterdir()):
            raise ValueError("Cannot resume: video_list.txt is missing")
        list_path.write_text(wanted, encoding="utf-8")
        local_scraper = run_dir / "Bilicomment.py"
        shutil.copy2(SCRAPER, local_scraper)
        print(f"Running {len(videos)} videos in {run_dir}", flush=True)
        child_env = os.environ.copy()
        child_env.pop("BILIBILI_ANONYMOUS", None)
        if LOCAL_DEPS.is_dir():
            child_env["PYTHONPATH"] = str(LOCAL_DEPS) + os.pathsep + child_env.get("PYTHONPATH", "")
        child_env["BILIBILI_LOGIN_ONLY"] = "1"
        login_result = subprocess.run([sys.executable, "-u", str(local_scraper)], cwd=run_dir, env=child_env, check=False)
        if login_result.returncode:
            raise RuntimeError(f"Bilibili login step failed with exit code {login_result.returncode}")
        result = subprocess.run([sys.executable, "-u", str(API_SCRAPER), "--run-dir", str(run_dir)], cwd=run_dir, env=child_env, check=False)
        entries = normalize_outputs(run_dir, videos)
        manifest = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_code": [str(SCRAPER), str(API_SCRAPER)],
            "exit_code": result.returncode,
            "videos": entries,
            "normalized_csv": "comments_normalized.csv",
            "note": "Comments are read through Bilibili's reply interface after interactive browser login. Native comment, root and parent IDs are retained when available.",
        }
        (run_dir / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"exit_code": result.returncode, "ok_videos": sum(x["status"] == "ok" for x in entries), "video_count": len(entries), "normalized_csv": str(run_dir / "comments_normalized.csv")}, ensure_ascii=False))
        return 0 if result.returncode == 0 and all(x["status"] == "ok" for x in entries) else 1
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
