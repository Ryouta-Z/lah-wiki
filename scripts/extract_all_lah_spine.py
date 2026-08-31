"""Download and extract every official Live A Hero character Spine package except 1-star soldiers."""

from __future__ import annotations

import argparse
import json
import re
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
import UnityPy

try:
    from scripts.extract_lah_spine import ExtractionError, _validate_package, extract
except ModuleNotFoundError:
    from extract_lah_spine import ExtractionError, _validate_package, extract


ROOT = Path(__file__).parent.parent
CHAR_MAP = ROOT / "data" / "char_map.json"
DEFAULT_CACHE_DIR = ROOT / "data" / "cache" / "lah-spine-bundles"
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "lah-spine" / "characters"
CDN = "https://d1itvxfdul6wxg.cloudfront.net/4.13.2/Assetbundle/Android/"
USER_AGENT = {"User-Agent": "UnityPlayer"}
ONE_STAR_SOLDIER_PREFIXES = (
    "androidsoldier",
    "apprentice",
    "diver",
    "guardman",
    "localidol",
    "mercenary",
    "trainee",
    "wrestler",
    "wolfman",
)
SAFE_PATH_COMPONENT = re.compile(r"^[A-Za-z0-9_.-]+$")


def _targets(char_map: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [
        (code, entry)
        for code, entry in sorted(char_map.items())
        if entry.get("bundle") and not code.lower().startswith(ONE_STAR_SOLDIER_PREFIXES)
    ]


def _skeleton_names(bundle_path: Path) -> list[str]:
    names = []
    for obj in UnityPy.load(str(bundle_path)).objects:
        if obj.type.name != "MonoBehaviour":
            continue
        tree = obj.read_typetree()
        if "skeletonJSON" in tree and "atlasAssets" in tree and tree.get("m_Name"):
            names.append(tree["m_Name"])
    return sorted(set(names))


def _download(client: httpx.Client, bundle_name: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            response = client.get(CDN + bundle_name)
            response.raise_for_status()
            with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
                temporary.write(response.content)
                temporary_path = Path(temporary.name)
            temporary_path.replace(destination)
            return
        except httpx.HTTPError:
            if attempt == 2:
                raise
            time.sleep(1)
    raise RuntimeError("Unreachable")


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _resume_report(report_path: Path, target_count: int, excluded: list[str]) -> dict[str, Any]:
    report: dict[str, Any] = {
        "target_count": target_count,
        "excluded_one_star_soldiers": excluded,
        "completed": [],
        "skipped": [],
        "failed": [],
    }
    if not report_path.is_file():
        return report

    previous = json.loads(report_path.read_text(encoding="utf-8"))
    if (
        previous.get("target_count") != target_count
        or previous.get("excluded_one_star_soldiers") != excluded
    ):
        return report
    for key in ("completed", "skipped", "failed"):
        if isinstance(previous.get(key), list):
            report[key] = previous[key]
    return report


def _output_is_complete(item: dict[str, Any], output_dir: Path) -> bool:
    output_root = output_dir.resolve()
    outputs = item.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        return False
    try:
        for output in outputs:
            directory = (output_dir / output["directory"]).resolve()
            if not directory.is_relative_to(output_root):
                return False
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            files = [manifest["skeleton"]["file"]]
            files.extend(atlas["file"] for atlas in manifest["atlases"])
            files.extend(texture["file"] for texture in manifest["textures"])
            if not all(isinstance(file, str) and SAFE_PATH_COMPONENT.fullmatch(file) for file in files):
                return False
            if not all((directory / file).is_file() for file in files):
                return False
            _validate_package(directory)
    except (ExtractionError, KeyError, OSError, TypeError, json.JSONDecodeError):
        return False
    return True


def _remove_failure(report: dict[str, Any], code: str) -> None:
    report["failed"] = [item for item in report["failed"] if item.get("code") != code]


def extract_all(
    char_map: dict[str, Any],
    cache_dir: Path = DEFAULT_CACHE_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    limit: int | None = None,
) -> dict[str, Any]:
    """Download, resume, and export all catalogued non-soldier character bundles."""
    targets = _targets(char_map)
    if limit is not None:
        targets = targets[:limit]
    report_path = output_dir / "report.json"
    excluded = sorted(code for code in char_map if code.lower().startswith(ONE_STAR_SOLDIER_PREFIXES))
    report = _resume_report(report_path, len(targets), excluded)
    report["not_exportable"] = [
        {"code": code, "reason": "no_bundle"}
        for code, entry in sorted(char_map.items())
        if not entry.get("bundle") and not code.lower().startswith(ONE_STAR_SOLDIER_PREFIXES)
    ]
    report["completed"] = [
        item for item in report["completed"] if _output_is_complete(item, output_dir)
    ]
    completed_or_skipped = {
        item["code"] for key in ("completed", "skipped") for item in report[key] if "code" in item
    }
    targets = [(code, entry) for code, entry in targets if code not in completed_or_skipped]
    _write_report(report_path, report)
    with httpx.Client(headers=USER_AGENT, timeout=90, follow_redirects=True) as client:
        for index, (code, entry) in enumerate(targets, 1):
            try:
                bundle_name = entry["bundle"]
                if not SAFE_PATH_COMPONENT.fullmatch(code):
                    raise ValueError(f"Unsafe character code: {code!r}")
                if not SAFE_PATH_COMPONENT.fullmatch(bundle_name):
                    raise ValueError(f"Unsafe bundle name: {bundle_name!r}")
                bundle_path = cache_dir / bundle_name
                if not bundle_path.is_file():
                    _download(client, bundle_name, bundle_path)
                skeletons = _skeleton_names(bundle_path)
                if not skeletons:
                    report["skipped"].append({"code": code, "reason": "no_spine_skeleton"})
                    _remove_failure(report, code)
                else:
                    outputs = []
                    for skeleton_name in skeletons:
                        if not SAFE_PATH_COMPONENT.fullmatch(skeleton_name):
                            raise ValueError(f"Unsafe SkeletonData name: {skeleton_name!r}")
                        destination = output_dir / code
                        if len(skeletons) > 1:
                            destination /= skeleton_name
                        result = extract(bundle_path, destination, skeleton_name)
                        outputs.append(
                            {
                                "skeleton_name": skeleton_name,
                                "directory": result.output_dir.relative_to(output_dir).as_posix(),
                                "animations": list(result.animations),
                            }
                        )
                    report["completed"].append({"code": code, "cn": entry.get("cn"), "outputs": outputs})
                    _remove_failure(report, code)
            except Exception as error:
                _remove_failure(report, code)
                report["failed"].append({"code": code, "reason": str(error)})
            _write_report(report_path, report)
            print(f"[{index}/{len(targets)} remaining] {code}: done={len(report['completed'])} failed={len(report['failed'])}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    char_map = json.loads(CHAR_MAP.read_text(encoding="utf-8"))
    report = extract_all(char_map, args.cache_dir, args.output_dir, args.limit)
    print(
        f"Finished: {len(report['completed'])} completed, "
        f"{len(report['skipped'])} skipped, {len(report['failed'])} failed"
    )


if __name__ == "__main__":
    main()
