"""Manually copy one complete Live A Hero data snapshot from a MuMu device."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).parent.parent
DEFAULT_ADB = Path(r"E:\Program Files\Netease\MuMu\nx_main\adb.exe")
DEFAULT_OUTPUT_DIR = ROOT / "data" / "cache" / "lah-localization"
PACKAGE_DIR = "/sdcard/Android/data/jp.co.lifewonders.liveahero/files/datas"
SOURCES = {
    "ChineseSimplified": f"{PACKAGE_DIR}/catalog/ChineseSimplified.json",
    "CardMaster": f"{PACKAGE_DIR}/master/CardMaster",
    "SidekickMaster": f"{PACKAGE_DIR}/master/SidekickMaster",
    "SkillMaster": f"{PACKAGE_DIR}/master/SkillMaster",
}


def import_snapshot(adb: Path, serial: str, output_dir: Path, tag: str) -> list[Path]:
    if not adb.is_file():
        raise FileNotFoundError(f"未找到 MuMu adb：{adb}")
    output_dir.mkdir(parents=True, exist_ok=True)
    captured: list[tuple[str, bytes]] = []
    parsed: dict[str, object] = {}
    for name, remote_path in SOURCES.items():
        result = subprocess.run(
            [str(adb), "-s", serial, "exec-out", "cat", remote_path],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0 or not result.stdout:
            raise RuntimeError(f"无法读取 {name}：{result.stderr.decode(errors='replace').strip()}")
        try:
            parsed[name] = json.loads(result.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RuntimeError(f"{name} 不是有效 JSON") from error
        captured.append((name, result.stdout))

    _validate_snapshot(parsed)
    written = []
    for name, content in captured:
        suffix = ".json" if name == "ChineseSimplified" else ""
        target = output_dir / f"{name}-{tag}{suffix}"
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(target)
        written.append(target)
    return written


def _validate_snapshot(snapshot: dict[str, object]) -> None:
    localized = snapshot["ChineseSimplified"]
    if not isinstance(localized, dict) or not localized:
        raise RuntimeError("ChineseSimplified 缺少本地化条目")

    skills = _index_entries(snapshot["SkillMaster"], "skillId", "SkillMaster")
    heroes = _index_entries(snapshot["CardMaster"], "heroCardId", "CardMaster")
    sidekicks = _index_entries(snapshot["SidekickMaster"], "sidekickCardId", "SidekickMaster")
    for card_type, cards in (("CardMaster", heroes), ("SidekickMaster", sidekicks)):
        for card in cards.values():
            if not card.get("resourceName"):
                raise RuntimeError(f"{card_type} card missing resourceName")
            skill_ids = [*(card.get("skillIds") or [])]
            if card_type == "SidekickMaster":
                skill_ids.extend(card.get("equipmentSkills") or [])
            missing = [skill_id for skill_id in skill_ids if str(skill_id) not in skills]
            if missing:
                raise RuntimeError(f"{card_type} card references missing skill: {missing[0]}")


def _index_entries(data: object, id_field: str, source: str) -> dict[str, dict]:
    if not isinstance(data, dict):
        raise RuntimeError(f"{source} 根结构不是对象")
    result = {}
    for entry in data.values():
        if not isinstance(entry, dict) or entry.get(id_field) is None:
            raise RuntimeError(f"{source} entry missing {id_field}")
        result[str(entry[id_field])] = entry
    if not result:
        raise RuntimeError(f"{source} 没有记录")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="从 MuMu 手动导入 Live A Hero 本地数据快照")
    parser.add_argument("--serial", required=True, help="adb devices 中状态为 device 的设备序列号")
    parser.add_argument("--adb", type=Path, default=DEFAULT_ADB)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--tag", default=datetime.now().strftime("%Y%m%d"))
    args = parser.parse_args()
    paths = import_snapshot(args.adb, args.serial, args.output_dir, args.tag)
    print("已导入：")
    for path in paths:
        print(f"- {path}")


if __name__ == "__main__":
    main()
