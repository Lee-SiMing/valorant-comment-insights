"""Fetch Bilibili video replies after the bundled crawler's interactive login."""

import argparse
import csv
import json
import pickle
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests


API = "https://api.bilibili.com"
FIELDS = ["评论ID", "根评论ID", "父评论ID", "隶属关系", "昵称", "用户ID", "评论内容", "发布时间", "点赞数"]


def get_data(session, path, params):
    for attempt in range(3):
        response = session.get(API + path, params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") == 0:
            return payload["data"] or {}
        if attempt == 2:
            raise RuntimeError(f"Bilibili API {path}: code={payload.get('code')}, message={payload.get('message')}")
        time.sleep(2 * (attempt + 1))
    raise RuntimeError("Unreachable retry state")


def row_for(reply, level):
    member = reply.get("member") or {}
    content = reply.get("content") or {}
    ctime = reply.get("ctime")
    return {
        "评论ID": str(reply.get("rpid") or ""),
        "根评论ID": str(reply.get("root") or ""),
        "父评论ID": str(reply.get("parent") or ""),
        "隶属关系": level,
        "昵称": member.get("uname") or "",
        "用户ID": str(reply.get("mid") or ""),
        "评论内容": content.get("message") or "",
        "发布时间": datetime.fromtimestamp(ctime).astimezone().isoformat(timespec="seconds") if ctime else "",
        "点赞数": reply.get("like") or 0,
    }


def crawl_video(session, video_id, output_dir):
    video = get_data(session, "/x/web-interface/view", {"bvid": video_id})
    oid = video.get("aid")
    if not oid:
        raise RuntimeError(f"No aid for {video_id}")
    print(f"{video_id}: {video.get('title')} (aid={oid})", flush=True)
    all_rows = {}
    page = 1
    expected_parents = None
    while True:
        data = get_data(session, "/x/v2/reply", {"pn": page, "type": 1, "oid": oid, "sort": 2})
        expected_parents = (data.get("page") or {}).get("count", expected_parents)
        parents = data.get("replies") or []
        if not parents:
            break
        for parent in parents:
            parent_id = str(parent["rpid"])
            all_rows[parent_id] = row_for(parent, "一级评论")
            sub_count = parent.get("rcount") or 0
            if sub_count:
                sub_page = 1
                while True:
                    sub_data = get_data(session, "/x/v2/reply/reply", {"type": 1, "oid": oid, "root": parent_id, "pn": sub_page, "ps": 20})
                    subs = sub_data.get("replies") or []
                    for sub in subs:
                        all_rows[str(sub["rpid"])] = row_for(sub, "二级评论")
                    if not subs or sub_page * 20 >= (sub_data.get("page") or {}).get("count", 0):
                        break
                    sub_page += 1
                    time.sleep(0.15)
            time.sleep(0.15)
        print(f"{video_id}: 一级评论页 {page}，累计 {len(all_rows)} 条评论", flush=True)
        if page * 20 >= expected_parents:
            break
        page += 1
    csv_path = output_dir / f"{video_id}.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(all_rows.values())
    return {"video_id": video_id, "title": video.get("title"), "aid": oid, "reported_parent_count": expected_parents, "collected_count": len(all_rows)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    session = requests.Session()
    with (run_dir / "cookies.pkl").open("rb") as handle:
        cookies = pickle.load(handle)
    for cookie in cookies:
        session.cookies.set(cookie["name"], cookie["value"], domain=cookie.get("domain", ".bilibili.com"), path=cookie.get("path", "/"))
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://www.bilibili.com/"})
    results = []
    for url in (run_dir / "video_list.txt").read_text(encoding="utf-8").splitlines():
        video_id = urlparse(url).path.strip("/").split("/")[-1]
        results.append(crawl_video(session, video_id, run_dir))
    (run_dir / "video_metadata.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, requests.RequestException, ValueError, RuntimeError) as exc:
        print(f"评论采集失败: {exc}", file=sys.stderr)
        raise SystemExit(1)
