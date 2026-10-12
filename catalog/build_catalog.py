"""Build a dated weapon/skin name snapshot from the public Valorant-API."""

import csv
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


SOURCE_URL = "https://valorant-api.com/v1/weapons?language=zh-CN"
HERE = Path(__file__).resolve().parent


def main():
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "valorant-comment-insights/0.1"})
    with urllib.request.urlopen(req, timeout=30) as response:
        payload = json.load(response)
    weapons = payload.get("data")
    if not isinstance(weapons, list) or not weapons:
        raise ValueError("The source returned no weapons")

    weapon_rows = []
    skin_rows = []
    seen_weapon_ids = set()
    seen_skin_ids = set()
    for weapon in weapons:
        weapon_id = weapon.get("uuid", "")
        weapon_name = weapon.get("displayName", "")
        if not weapon_id or not weapon_name or weapon_id in seen_weapon_ids:
            raise ValueError(f"Invalid or duplicate weapon: {weapon_name!r}")
        seen_weapon_ids.add(weapon_id)
        weapon_rows.append({"weapon_uuid": weapon_id, "weapon_name_zh_cn": weapon_name})
        for skin in weapon.get("skins", []):
            skin_id = skin.get("uuid", "")
            skin_name = skin.get("displayName", "")
            if not skin_id or not skin_name or skin_id in seen_skin_ids:
                raise ValueError(f"Invalid or duplicate skin: {skin_name!r}")
            seen_skin_ids.add(skin_id)
            skin_rows.append({
                "skin_uuid": skin_id,
                "skin_name_zh_cn": skin_name,
                "weapon_uuid": weapon_id,
                "weapon_name_zh_cn": weapon_name,
                "theme_uuid": skin.get("themeUuid") or "",
                "levels_count": len(skin.get("levels") or []),
                "chromas_count": len(skin.get("chromas") or []),
            })

    weapon_rows.sort(key=lambda r: r["weapon_name_zh_cn"])
    skin_rows.sort(key=lambda r: (r["weapon_name_zh_cn"], r["skin_name_zh_cn"]))
    for name, fields, rows in [
        ("weapons_zh_cn.csv", ["weapon_uuid", "weapon_name_zh_cn"], weapon_rows),
        ("skins_zh_cn.csv", ["skin_uuid", "skin_name_zh_cn", "weapon_uuid", "weapon_name_zh_cn", "theme_uuid", "levels_count", "chromas_count"], skin_rows),
    ]:
        with (HERE / name).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    metadata = {
        "source_url": SOURCE_URL,
        "source_type": "community-maintained public API",
        "locale": "zh-CN",
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "weapon_count": len(weapon_rows),
        "skin_count": len(skin_rows),
        "scope_note": "API snapshot; Chinese names and availability for the China server are not independently verified. Includes default and other non-store entries returned by the API.",
    }
    (HERE / "source_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(weapon_rows)} weapons; {len(skin_rows)} skins")


if __name__ == "__main__":
    main()
