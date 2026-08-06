#!/usr/bin/env python3
"""Validate one immutable S1 visual-manifest lifecycle snapshot."""

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
from visual_placement_contract import (  # noqa: E402
    courseware_page_requires_review,
    courseware_render_placement,
    lesson_plan_render_placement,
)

ALLOWED_STATES = {"initial", "request", "resolved"}
DECISIONS = {"lesson_plan_image", "courseware_image", "interaction_no_image"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def issue(code: str, message: str | None = None) -> dict[str, str]:
    return {"issue_type": code, "message": message or code}


def validate_source(source: object, code: str, *, readback: bool = True) -> list[dict[str, str]]:
    if not isinstance(source, dict):
        return [issue(code)]
    path_value, digest = source.get("path"), source.get("sha256")
    if not isinstance(path_value, str) or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        return [issue(code)]
    if readback:
        path = Path(path_value)
        if not path.is_file() or sha256(path) != digest:
            return [issue(code)]
    return []


def validate_manifest(payload: object, phase: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not isinstance(payload, dict):
        return [issue("VISUAL_MANIFEST_INVALID")]
    if payload.get("schemaVersion") != "1.1" or payload.get("ownerStage") != "S1":
        issues.append(issue("VISUAL_MANIFEST_SCHEMA_INVALID"))
    lesson_id = payload.get("lessonId")
    if not isinstance(lesson_id, str) or not re.fullmatch(r"lesson\d{3,}", lesson_id):
        issues.append(issue("VISUAL_MANIFEST_LESSON_ID_INVALID"))
    if payload.get("visualMode") != "visual_enhanced":
        issues.append(issue("VISUAL_MODE_DRIFT"))
    if phase not in ALLOWED_STATES or payload.get("lifecycleState") != phase:
        issues.append(issue("VISUAL_MANIFEST_LIFECYCLE_INVALID"))
    issues.extend(validate_source(payload.get("sourceTeacherFinal"), "VISUAL_MANIFEST_TEACHER_SOURCE_INVALID", readback=phase == "initial"))
    issues.extend(validate_source(payload.get("sourceTeacherVisualScript"), "VISUAL_MANIFEST_SCRIPT_SOURCE_INVALID", readback=phase == "initial"))

    source_page_plan = payload.get("sourcePagePlan")
    external_return = payload.get("externalReturn")
    if phase == "initial":
        if source_page_plan is not None or external_return is not None:
            issues.append(issue("VISUAL_INITIAL_PROVENANCE_INVALID"))
        if payload.get("pageDecisions") not in ([], None):
            issues.append(issue("VISUAL_INITIAL_PAGE_DECISIONS_FORBIDDEN"))
    else:
        issues.extend(validate_source(source_page_plan, "VISUAL_MANIFEST_PAGE_PLAN_INVALID"))
        if phase == "request" and external_return is not None:
            issues.append(issue("VISUAL_REQUEST_EXTERNAL_RETURN_FORBIDDEN"))
        if phase == "resolved":
            # The external file is provenance, not a downstream input. Do not open it here.
            issues.extend(validate_source(external_return, "VISUAL_MANIFEST_EXTERNAL_PROVENANCE_INVALID", readback=False))
            placement_review = payload.get("placementReview")
            if placement_review is not None:
                issues.extend(validate_source(placement_review, "VISUAL_PLACEMENT_REVIEW_SOURCE_INVALID", readback=False))

    assets = payload.get("assets")
    placements = payload.get("placements")
    decisions = payload.get("pageDecisions")
    if not isinstance(assets, list) or not isinstance(placements, list) or not isinstance(decisions, list):
        return issues + [issue("VISUAL_MANIFEST_COLLECTIONS_INVALID")]
    asset_ids: set[str] = set()
    assets_by_id: dict[str, dict[str, Any]] = {}
    for asset in assets:
        if not isinstance(asset, dict):
            issues.append(issue("VISUAL_ASSET_INVALID"))
            continue
        asset_id = str(asset.get("assetId") or "")
        if not asset_id or asset_id in asset_ids:
            issues.append(issue("LESSON_PLAN_IMAGE_ID_DUPLICATE"))
            continue
        asset_ids.add(asset_id)
        assets_by_id[asset_id] = asset
        image_type = asset.get("imageType")
        authority = asset.get("sourceAuthority")
        if image_type == "lesson_plan_image":
            if authority != "teacher_visual_script" or not str(asset.get("url") or "").startswith("https://"):
                issues.append(issue("LESSON_PLAN_IMAGE_URL_MISSING"))
        elif image_type == "courseware_image":
            if authority != "external_courseware_return":
                issues.append(issue("COURSEWARE_IMAGE_AUTHORITY_INVALID"))
            if phase == "resolved" and not str(asset.get("url") or "").startswith("https://"):
                issues.append(issue("COURSEWARE_IMAGE_URL_MISSING"))
        else:
            issues.append(issue("VISUAL_IMAGE_TYPE_INVALID"))

    group_orders: dict[str, list[int]] = {}
    page_types_by_no = {
        str(decision.get("pageNo") or ""): decision.get("pageType")
        for decision in decisions
        if isinstance(decision, dict)
    }
    for placement in placements:
        if not isinstance(placement, dict) or placement.get("assetId") not in asset_ids:
            issues.append(issue("VISUAL_PLACEMENT_ASSET_INVALID"))
            continue
        if phase == "initial" and placement.get("pageNo") is not None:
            issues.append(issue("VISUAL_INITIAL_PAGE_BINDING_FORBIDDEN"))
        if phase != "initial" and not re.fullmatch(r"P\d{2,}", str(placement.get("pageNo") or "")):
            issues.append(issue("LESSON_PLAN_IMAGE_ANCHOR_INVALID"))
        if phase != "initial" and page_types_by_no.get(str(placement.get("pageNo") or "")) == "互动题目":
            if placement.get("placementStatus") != "suppressed_on_interaction_page":
                issues.append(issue("EXTERNAL_RETURN_INTERACTION_IMAGE_FORBIDDEN"))
        source_anchor = placement.get("sourceAnchor")
        render_placement = placement.get("renderPlacement")
        image_type = assets_by_id[str(placement.get("assetId"))].get("imageType")
        if image_type == "lesson_plan_image":
            if not isinstance(source_anchor, dict) or not source_anchor.get("beforeText") or not source_anchor.get("afterText"):
                issues.append(issue("LESSON_PLAN_IMAGE_ANCHOR_INVALID"))
            elif (
                not isinstance(placement.get("sourceLocationText"), str)
                or not placement.get("sourceLocationText")
                or not isinstance(placement.get("sourceLocationDetail"), str)
                or render_placement
                != lesson_plan_render_placement(
                    str(source_anchor.get("beforeText")),
                    str(source_anchor.get("afterText")),
                )
            ):
                issues.append(issue("LESSON_PLAN_IMAGE_PLACEMENT_INVALID"))
        elif image_type == "courseware_image":
            page_type = page_types_by_no.get(str(placement.get("pageNo") or ""))
            try:
                expected_render_placement = courseware_render_placement(str(page_type or ""))
                requires_review = courseware_page_requires_review(str(page_type or ""))
            except ValueError:
                expected_render_placement = None
                requires_review = False
            common_invalid = (
                phase == "initial"
                or placement.get("sourceAnchor") is not None
                or placement.get("sourceLocationText") is not None
                or placement.get("sourceLocationDetail") is not None
            )
            if common_invalid:
                issues.append(issue("COURSEWARE_IMAGE_PLACEMENT_INVALID"))
            elif phase == "request":
                expected_status = "pending_visual_review" if requires_review else "active"
                if render_placement != expected_render_placement or placement.get("placementStatus") != expected_status:
                    issues.append(issue("COURSEWARE_IMAGE_PLACEMENT_INVALID"))
            elif phase == "resolved" and requires_review:
                review = placement.get("visualReview")
                if (
                    placement.get("placementStatus") != "reviewed"
                    or not isinstance(review, dict)
                    or review.get("imageReviewed") is not True
                    or not isinstance(render_placement, dict)
                    or render_placement.get("authority") != "model_visual_review"
                    or render_placement.get("anchorType") != "reviewed_semantic_anchor"
                    or render_placement.get("terminalPlacementForbidden") is not True
                ):
                    issues.append(issue("COURSEWARE_IMAGE_PLACEMENT_REVIEW_INVALID"))
            elif phase == "resolved":
                if render_placement != expected_render_placement or placement.get("placementStatus") != "active":
                    issues.append(issue("COURSEWARE_IMAGE_PLACEMENT_INVALID"))
        if placement.get("displayMode") == "group_item":
            group_id = str(placement.get("groupId") or "")
            order = placement.get("order")
            if not group_id or not isinstance(order, int):
                issues.append(issue("LESSON_PLAN_IMAGE_GROUP_ORDER_INVALID"))
            else:
                group_orders.setdefault(group_id, []).append(order)
    for orders in group_orders.values():
        if sorted(orders) != list(range(1, len(orders) + 1)):
            issues.append(issue("LESSON_PLAN_IMAGE_GROUP_ORDER_INVALID"))

    if phase != "initial":
        seen_pages: set[str] = set()
        for decision in decisions:
            if not isinstance(decision, dict):
                issues.append(issue("VISUAL_PAGE_DECISION_INVALID"))
                continue
            page_no = str(decision.get("pageNo") or "")
            if page_no in seen_pages or not re.fullmatch(r"P\d{2,}", page_no):
                issues.append(issue("VISUAL_PAGE_DECISION_INVALID"))
            seen_pages.add(page_no)
            choice = decision.get("decision")
            decision_assets = decision.get("assetIds") or []
            if choice not in DECISIONS or any(asset_id not in asset_ids for asset_id in decision_assets):
                issues.append(issue("VISUAL_PAGE_DECISION_INVALID"))
            if choice == "interaction_no_image" and decision_assets:
                issues.append(issue("EXTERNAL_RETURN_INTERACTION_IMAGE_FORBIDDEN"))
            if phase == "resolved" and choice == "courseware_image":
                if len(decision_assets) != 1 or assets_by_id.get(decision_assets[0], {}).get("assetStatus") != "ready":
                    issues.append(issue("COURSEWARE_IMAGE_URL_MISSING"))
    if payload.get("blockingPoints") not in ([], None):
        issues.append(issue("VISUAL_MANIFEST_BLOCKING_POINTS_NOT_EMPTY"))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an S1 visual asset manifest snapshot")
    parser.add_argument("--phase", required=True, choices=tuple(sorted(ALLOWED_STATES)))
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    try:
        payload = json.loads(args.manifest.read_text(encoding="utf-8"))
        issues = validate_manifest(payload, args.phase)
    except (OSError, UnicodeError, json.JSONDecodeError):
        issues = [issue("VISUAL_MANIFEST_INVALID")]
    report = {"status": "PASS" if not issues else "BLOCKED", "phase": args.phase, "issues": issues}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
