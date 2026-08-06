#!/usr/bin/env python3
"""Bind S1 teacher anchors to a passed, unchanged S4 page plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))
from page_type_contract import canonical_capsule, canonical_page_type  # noqa: E402
from visual_placement_contract import (  # noqa: E402
    courseware_page_requires_review,
    courseware_render_placement,
)

CONTRACT = "RunS_V3.5.0-S1-S6-R36-20260731"
ANCHOR_FRAGMENT_MIN_LENGTH = 12


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def blocked(code: str) -> int:
    print(f"BLOCKED:{code}", file=sys.stderr)
    return 1


def load_json(path: Path, code: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(code) from exc
    if not isinstance(payload, dict):
        raise ValueError(code)
    return payload


def parse_pages(text: str) -> list[dict[str, str]]:
    matches = list(re.finditer(r"(?m)^##\s+(P\d+)\s*$", text))
    if not matches:
        raise ValueError("VISUAL_PAGE_PLAN_EMPTY")
    pages: list[dict[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = text[match.start():end]
        page_type_match = re.search(r"(?m)^- 页面类型：(.+?)\s*$", block)
        capsule_match = re.search(r"(?m)^- 胶囊文案：(.+?)\s*$", block)
        content_match = re.search(r"(?m)^### 有效内容\s*$", block)
        if not page_type_match or not capsule_match or not content_match:
            raise ValueError("VISUAL_PAGE_PLAN_INVALID")
        raw_type = page_type_match.group(1).strip()
        raw_capsule = capsule_match.group(1).strip()
        page_type = canonical_page_type(raw_type)
        capsule = canonical_capsule(raw_type, raw_capsule)
        pages.append(
            {
                "pageNo": match.group(1),
                "pageType": str(page_type),
                "capsule": str(capsule),
                "body": block[content_match.end():].strip(),
                "block": block,
            }
        )
    return pages


def verify_s4_receipt(path: Path, lesson_id: str, page_plan: Path) -> dict[str, Any]:
    receipt = load_json(path, "S4_RECEIPT_INVALID")
    if receipt.get("contract") != CONTRACT:
        raise ValueError("S4_RECEIPT_CONTRACT_MISMATCH")
    if receipt.get("lesson_id") != lesson_id or receipt.get("stage") != "S4":
        raise ValueError("S4_RECEIPT_STAGE_MISMATCH")
    if receipt.get("status") != "PASS":
        raise ValueError("S4_GATE_NOT_PASS")
    if "visualMode" in receipt and receipt.get("visualMode") != "visual_enhanced":
        raise ValueError("VISUAL_MODE_DRIFT")
    output = receipt.get("output")
    if not isinstance(output, dict):
        raise ValueError("S4_RECEIPT_OUTPUT_MISSING")
    resolved_plan = page_plan.resolve()
    if output.get("path") != str(resolved_plan):
        raise ValueError("S4_RECEIPT_OUTPUT_PATH_MISMATCH")
    if output.get("sha256") != sha256(resolved_plan):
        raise ValueError("S4_RECEIPT_OUTPUT_HASH_MISMATCH")
    return receipt


def unique_asset_ids(placements: list[dict[str, Any]]) -> list[str]:
    ordered: list[str] = []
    for placement in sorted(placements, key=lambda item: (item.get("groupId") or "", item.get("order") or 0, item.get("assetId") or "")):
        asset_id = str(placement.get("assetId") or "")
        if asset_id and asset_id not in ordered:
            ordered.append(asset_id)
    return ordered


def anchor_fragments(text: str) -> list[str]:
    fragments = [item.strip() for item in re.split(r"[。！？!?；;\n]+", text) if item.strip()]
    return [item for item in fragments if len(item) >= ANCHOR_FRAGMENT_MIN_LENGTH]


def unique_interaction_candidate(
    before: str,
    after: str,
    pages: list[dict[str, str]],
) -> dict[str, str] | None:
    fragments = anchor_fragments(before) + anchor_fragments(after)
    if not fragments:
        return None
    candidates = [
        page
        for page in pages
        if page["pageType"] == "互动题目" and any(fragment in page["body"] for fragment in fragments)
    ]
    return candidates[0] if len(candidates) == 1 else None


def unique_surviving_anchor_candidate(
    before: str,
    after: str,
    pages: list[dict[str, str]],
) -> dict[str, str] | None:
    before_candidates = [page for page in pages if before and before in page["body"]]
    after_candidates = [page for page in pages if after and after in page["body"]]
    if len(before_candidates) == 1 and not after_candidates:
        return before_candidates[0]
    if len(after_candidates) == 1 and not before_candidates:
        return after_candidates[0]
    return None


def bind_manifest(
    lesson_id: str,
    initial_path: Path,
    page_plan_path: Path,
    s4_receipt_path: Path,
) -> dict[str, Any]:
    initial_path = initial_path.resolve()
    page_plan_path = page_plan_path.resolve()
    s4_receipt_path = s4_receipt_path.resolve()
    initial = load_json(initial_path, "VISUAL_INITIAL_MANIFEST_INVALID")
    if initial.get("lessonId") != lesson_id or initial.get("lifecycleState") != "initial":
        raise ValueError("VISUAL_INITIAL_MANIFEST_INVALID")
    if initial.get("visualMode") != "visual_enhanced":
        raise ValueError("VISUAL_MODE_DRIFT")
    verify_s4_receipt(s4_receipt_path, lesson_id, page_plan_path)
    pages = parse_pages(page_plan_path.read_text(encoding="utf-8"))

    payload = deepcopy(initial)
    placements = payload.get("placements") or []
    for placement in placements:
        anchor = placement.get("sourceAnchor") or {}
        before = str(anchor.get("beforeText") or "")
        after = str(anchor.get("afterText") or "")
        candidates = [page for page in pages if before in page["body"] and after in page["body"]]
        page = candidates[0] if len(candidates) == 1 else unique_surviving_anchor_candidate(before, after, pages)
        if page is None:
            page = unique_interaction_candidate(before, after, pages)
        if page is None:
            raise ValueError("LESSON_PLAN_IMAGE_ANCHOR_INVALID")
        placement["pageNo"] = page["pageNo"]
        if page["pageType"] == "互动题目":
            placement["placementStatus"] = "suppressed_on_interaction_page"
            placement["suppressionReason"] = "interaction_component_contract_forbids_course_images"
            continue
        placement["placementStatus"] = "active"

    placements_by_page: dict[str, list[dict[str, Any]]] = {}
    for placement in placements:
        if placement.get("placementStatus") == "suppressed_on_interaction_page":
            continue
        placements_by_page.setdefault(str(placement["pageNo"]), []).append(placement)

    assets: list[dict[str, Any]] = payload.get("assets") or []
    decisions: list[dict[str, Any]] = []
    for page in pages:
        page_no = page["pageNo"]
        teacher_placements = placements_by_page.get(page_no, [])
        if teacher_placements:
            asset_ids = unique_asset_ids(teacher_placements)
            decisions.append(
                {
                    "pageNo": page_no,
                    "pageType": page["pageType"],
                    "decision": "lesson_plan_image",
                    "reason": "teacher_visual_script_anchor_bound_to_page",
                    "requiredAssetCount": len(asset_ids),
                    "assetIds": asset_ids,
                    "status": "ready",
                }
            )
        elif page["pageType"] == "互动题目":
            decisions.append(
                {
                    "pageNo": page_no,
                    "pageType": page["pageType"],
                    "decision": "interaction_no_image",
                    "reason": "interaction_component_contract_forbids_course_images",
                    "requiredAssetCount": 0,
                    "assetIds": [],
                    "status": "not_applicable",
                }
            )
        else:
            asset_id = f"{lesson_id.upper()}-{page_no}-C01"
            assets.append(
                {
                    "assetId": asset_id,
                    "imageType": "courseware_image",
                    "url": None,
                    "width": None,
                    "height": None,
                    "alt": None,
                    "teachingPurpose": None,
                    "sourceAuthority": "external_courseware_return",
                    "assetStatus": "awaiting_external_return",
                }
            )
            requires_review = courseware_page_requires_review(page["pageType"])
            placements.append(
                {
                    "placementId": f"{asset_id}-AT-{page_no}",
                    "assetId": asset_id,
                    "sourceAnchor": None,
                    "sourceLocationText": None,
                    "sourceLocationDetail": None,
                    "renderPlacement": courseware_render_placement(page["pageType"]),
                    "pageNo": page_no,
                    "displayMode": "single",
                    "groupId": None,
                    "order": None,
                    "displayLabel": None,
                    "placementStatus": "pending_visual_review" if requires_review else "active",
                }
            )
            decisions.append(
                {
                    "pageNo": page_no,
                    "pageType": page["pageType"],
                    "decision": "courseware_image",
                    "reason": "non_interactive_without_lesson_plan_image",
                    "requiredAssetCount": 1,
                    "assetIds": [asset_id],
                    "status": "awaiting_external_return",
                }
            )

    payload["lifecycleState"] = "request"
    payload["sourcePagePlan"] = {
        "path": str(page_plan_path),
        "sha256": sha256(page_plan_path),
        "receiptPath": str(s4_receipt_path),
        "receiptSha256": sha256(s4_receipt_path),
    }
    payload["externalReturn"] = None
    payload["assets"] = assets
    payload["placements"] = placements
    payload["pageDecisions"] = decisions
    payload["checks"] = {
        **(payload.get("checks") or {}),
        "s4ReceiptPass": True,
        "teacherAnchorsBoundUniquely": True,
        "interactionTeacherPlacementsSuppressed": True,
        "everyS4PageHasOneDecision": True,
        "interactionPagesHaveNoImages": True,
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Bind the S1 initial visual manifest to a frozen S4 plan")
    parser.add_argument("--lesson-id", required=True)
    parser.add_argument("--initial-manifest", required=True, type=Path)
    parser.add_argument("--page-plan", required=True, type=Path)
    parser.add_argument("--s4-receipt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        payload = bind_manifest(args.lesson_id, args.initial_manifest, args.page_plan, args.s4_receipt)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as exc:
        return blocked(str(exc))
    print(json.dumps({"status": "PASS", "output": str(args.output.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
