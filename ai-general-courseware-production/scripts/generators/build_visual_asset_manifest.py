#!/usr/bin/env python3
"""Freeze teacher-owned visual assets into the S1 initial manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))
from visual_placement_contract import lesson_plan_render_placement  # noqa: E402


POLICY = {
    "lessonPlanImagePriority": True,
    "coursewareImageOnlyWithoutLessonPlanImage": True,
    "coursewareImageOnInteractionPage": False,
    "maximumCoursewareImagesPerPage": 1,
    "missingUrlFallbackAllowed": False,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def blocked(code: str) -> int:
    print(f"BLOCKED:{code}", file=sys.stderr)
    return 1


def lesson_number(lesson_id: str) -> int:
    match = re.fullmatch(r"lesson(\d{3,})", lesson_id)
    if not match:
        raise ValueError("VISUAL_MANIFEST_LESSON_ID_INVALID")
    return int(match.group(1))


def lesson_section(text: str, number: int) -> str:
    pattern = re.compile(
        rf"(?ms)^##\s+\d+\.\s+第0*{number}课\s*$\n(.*?)(?=^##\s+\d+\.\s+|\Z)"
    )
    match = pattern.search(text)
    if not match:
        raise ValueError("TEACHER_VISUAL_SCRIPT_LESSON_MISSING")
    return match.group(1)


def parse_table(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in block.splitlines():
        match = re.match(r"^\|\s*([^|]+?)\s*\|\s*(.*?)\s*\|\s*$", line)
        if not match:
            continue
        key, value = match.groups()
        if key not in {"字段", "---"} and not set(key) <= {"-", ":"}:
            fields[key.strip()] = value.strip()
    return fields


def next_nonempty(lines: list[str], start: int) -> str:
    for line in lines[start:]:
        if line.strip():
            return line.strip()
    return ""


def ordinal(value: str) -> int | None:
    mapping = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    match = re.search(r"第([一二三四五六七八九十\d]+)位", value)
    if not match:
        return None
    token = match.group(1)
    return int(token) if token.isdigit() else mapping.get(token)


def display_labels(lines: list[str], line_number: int) -> list[str]:
    window = "\n".join(lines[max(0, line_number - 1): line_number + 16])
    labels: list[str] = []
    for match in re.finditer(r"画面\s*([A-Z])", window, re.IGNORECASE):
        label = f"画面 {match.group(1).upper()}"
        if label not in labels:
            labels.append(label)
    return labels


def build_manifest(lesson_id: str, teacher_final: Path, visual_script: Path) -> dict[str, Any]:
    teacher_final = teacher_final.resolve()
    visual_script = visual_script.resolve()
    if not teacher_final.is_file():
        raise ValueError("TEACHER_FINAL_MISSING")
    if not visual_script.is_file():
        raise ValueError("TEACHER_VISUAL_SCRIPT_MISSING")

    number = lesson_number(lesson_id)
    teacher_sha = sha256(teacher_final)
    script_text = visual_script.read_text(encoding="utf-8")
    section = lesson_section(script_text, number)
    sha_match = re.search(r"SHA-256：`?([0-9a-f]{64})`?", section)
    if not sha_match:
        raise ValueError("TEACHER_VISUAL_SCRIPT_TEACHER_SHA_MISSING")
    if sha_match.group(1) != teacher_sha:
        raise ValueError("TEACHER_VISUAL_SCRIPT_TEACHER_SHA_MISMATCH")

    teacher_lines = teacher_final.read_text(encoding="utf-8").splitlines()
    asset_matches = list(re.finditer(r"(?m)^###\s+`([^`]+)`\s+(.+?)\s*$", section))
    if not asset_matches:
        raise ValueError("TEACHER_VISUAL_SCRIPT_ASSETS_MISSING")

    assets: list[dict[str, Any]] = []
    placements: list[dict[str, Any]] = []
    seen_assets: set[str] = set()
    for index, match in enumerate(asset_matches):
        asset_id, title = match.group(1).strip(), match.group(2).strip()
        if asset_id in seen_assets:
            raise ValueError("LESSON_PLAN_IMAGE_ID_DUPLICATE")
        seen_assets.add(asset_id)
        end = asset_matches[index + 1].start() if index + 1 < len(asset_matches) else len(section)
        fields = parse_table(section[match.end():end])
        url = fields.get("图片地址", "").strip()
        if not url.startswith("https://"):
            raise ValueError("LESSON_PLAN_IMAGE_URL_MISSING")
        assets.append(
            {
                "assetId": asset_id,
                "imageType": "lesson_plan_image",
                "url": url,
                "width": None,
                "height": None,
                "alt": title,
                "teachingPurpose": fields.get("图片用途") or None,
                "sourceAuthority": "teacher_visual_script",
                "assetStatus": "ready",
            }
        )
        location = fields.get("教案位置", "")
        location_matches = list(re.finditer(r"第(\d+)行后([^；;]*)", location))
        if not location_matches:
            raise ValueError("LESSON_PLAN_IMAGE_ANCHOR_INVALID")
        for location_match in location_matches:
            line_number = int(location_match.group(1))
            detail = location_match.group(2).strip()
            if line_number < 1 or line_number > len(teacher_lines):
                raise ValueError("LESSON_PLAN_IMAGE_ANCHOR_INVALID")
            before = teacher_lines[line_number - 1].strip()
            before_line_match = re.search(r"第(\d+)行前", detail)
            if before_line_match:
                before_line_number = int(before_line_match.group(1))
                if before_line_number <= line_number or before_line_number > len(teacher_lines):
                    raise ValueError("LESSON_PLAN_IMAGE_ANCHOR_INVALID")
                after = teacher_lines[before_line_number - 1].strip()
            else:
                after = next_nonempty(teacher_lines, line_number)
            if not before or not after:
                raise ValueError("LESSON_PLAN_IMAGE_ANCHOR_INVALID")
            placements.append(
                {
                    "placementId": f"{asset_id}-AT-L{line_number}",
                    "assetId": asset_id,
                    "sourceAnchor": {
                        "teacherLineAfter": line_number,
                        "beforeText": before,
                        "afterText": after,
                    },
                    "sourceLocationText": location,
                    "sourceLocationDetail": detail,
                    "renderPlacement": lesson_plan_render_placement(before, after),
                    "pageNo": None,
                    "displayMode": "group_item" if ("一起" in detail or "排在" in detail) else "single",
                    "groupId": None,
                    "order": ordinal(detail),
                    "displayLabel": None,
                }
            )

    by_line: dict[int, list[dict[str, Any]]] = {}
    for placement in placements:
        by_line.setdefault(placement["sourceAnchor"]["teacherLineAfter"], []).append(placement)
    for line_number, group in by_line.items():
        if len(group) == 1 and group[0]["displayMode"] == "single":
            group[0]["order"] = None
            continue
        group_id = f"L{number:03d}-L{line_number}-GROUP"
        ordered = sorted(group, key=lambda item: (item["order"] is None, item["order"] or 999, item["assetId"]))
        labels = display_labels(teacher_lines, line_number)
        for position, placement in enumerate(ordered, start=1):
            placement["displayMode"] = "group_item"
            placement["groupId"] = group_id
            placement["order"] = position
            if len(labels) == len(ordered):
                placement["displayLabel"] = labels[position - 1]

    return {
        "schemaVersion": "1.1",
        "lessonId": lesson_id,
        "visualMode": "visual_enhanced",
        "ownerStage": "S1",
        "lifecycleState": "initial",
        "sourceTeacherFinal": {"path": str(teacher_final), "sha256": teacher_sha},
        "sourceTeacherVisualScript": {"path": str(visual_script), "sha256": sha256(visual_script)},
        "sourcePagePlan": None,
        "externalReturn": None,
        "policy": dict(POLICY),
        "assets": assets,
        "placements": placements,
        "pageDecisions": [],
        "checks": {
            "teacherFinalShaMatchesVisualScript": True,
            "lessonPlanAssetIdsUnique": True,
            "lessonPlanUrlsComplete": True,
            "sourceAnchorsComplete": True,
            "sourceLocationTextFrozen": True,
            "renderPlacementsComplete": True,
        },
        "blockingPoints": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an immutable S1 visual asset manifest initial snapshot")
    parser.add_argument("--lesson-id", required=True)
    parser.add_argument("--teacher-final", required=True, type=Path)
    parser.add_argument("--teacher-visual-script", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        payload = build_manifest(args.lesson_id, args.teacher_final, args.teacher_visual_script)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as exc:
        return blocked(str(exc))
    print(json.dumps({"status": "PASS", "output": str(args.output.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
