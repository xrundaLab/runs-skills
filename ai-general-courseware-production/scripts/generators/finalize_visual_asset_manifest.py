#!/usr/bin/env python3
"""Validate an external courseware-image return and freeze the resolved snapshot."""

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
from page_type_contract import canonical_page_type  # noqa: E402
from visual_placement_contract import courseware_page_requires_review  # noqa: E402


ALLOWED_KEYS = {
    "课件配图地址": "url",
    "图片地址": "url",
    "课件配图宽度": "width",
    "图片宽度": "width",
    "课件配图高度": "height",
    "图片高度": "height",
    "课件配图 alt": "alt",
    "图片 alt": "alt",
    "课件配图生成版本": "generatedVersion",
    "图片生成版本": "generatedVersion",
}
META_RE = re.compile(r"^\s*-\s*([^：:]+?)\s*[：:]\s*(.*?)\s*$")
PAGE_RE = re.compile(r"(?m)^##\s+(P\d+)\s*$")
PAGE_TYPE_RE = re.compile(r"(?m)^- 页面类型：(.+?)\s*$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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


def split_pages(text: str) -> tuple[str, list[tuple[str, str]]]:
    matches = list(PAGE_RE.finditer(text))
    if not matches:
        raise ValueError("EXTERNAL_RETURN_PAGE_SET_MISMATCH")
    prefix = text[:matches[0].start()]
    pages: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        pages.append((match.group(1), text[match.start():end]))
    return prefix, pages


def strip_metadata(text: str) -> tuple[str, dict[str, dict[str, list[str]]], set[str]]:
    prefix, pages = split_pages(text)
    metadata: dict[str, dict[str, list[str]]] = {}
    lesson_override_pages: set[str] = set()
    stripped_pages: list[str] = []
    for page_no, block in pages:
        values: dict[str, list[str]] = {}
        kept: list[str] = []
        for line in block.splitlines():
            match = META_RE.match(line)
            if match:
                key, value = match.group(1).strip(), match.group(2).strip()
                if key in ALLOWED_KEYS:
                    values.setdefault(ALLOWED_KEYS[key], []).append(value)
                    continue
                if key in {"教案配图地址", "教案图片地址"}:
                    lesson_override_pages.add(page_no)
                    continue
            kept.append(line)
        metadata[page_no] = values
        stripped_pages.append("\n".join(kept).rstrip())
    normalized = prefix.rstrip() + ("\n" if prefix.strip() else "") + "\n\n".join(stripped_pages).rstrip() + "\n"
    return normalized, metadata, lesson_override_pages


def normalize_original(text: str) -> str:
    prefix, pages = split_pages(text)
    normalized_pages = [block.rstrip() for _, block in pages]
    return prefix.rstrip() + ("\n" if prefix.strip() else "") + "\n\n".join(normalized_pages).rstrip() + "\n"


def page_types(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for page_no, block in split_pages(text)[1]:
        match = PAGE_TYPE_RE.search(block)
        if not match:
            raise ValueError("EXTERNAL_RETURN_PAGE_TYPE_MISMATCH")
        try:
            result[page_no] = canonical_page_type(match.group(1).strip())
        except ValueError as exc:
            raise ValueError("EXTERNAL_RETURN_PAGE_TYPE_MISMATCH") from exc
    return result


def one_value(values: dict[str, list[str]], key: str) -> str | None:
    items = values.get(key) or []
    if len(items) > 1:
        raise ValueError("COURSEWARE_IMAGE_COUNT_INVALID")
    return items[0] if items else None


def positive_int(value: str | None, code: str) -> int | None:
    if value in (None, ""):
        return None
    if not value.isdigit() or int(value) < 1:
        raise ValueError(code)
    return int(value)


def reviewed_placements(
    lesson_id: str,
    review_path: Path | None,
    request_path: Path,
    external_path: Path,
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, str] | None]:
    if review_path is None:
        return {}, None
    review_path = review_path.resolve()
    review = load_json(review_path, "VISUAL_PLACEMENT_REVIEW_INVALID")
    if review.get("schemaVersion") != "1.0" or review.get("lessonId") != lesson_id:
        raise ValueError("VISUAL_PLACEMENT_REVIEW_INVALID")
    expected_sources = (
        ("sourceRequestManifest", request_path),
        ("sourceExternalReturn", external_path),
    )
    for key, expected_path in expected_sources:
        source = review.get(key)
        if not isinstance(source, dict) or source.get("path") != str(expected_path) or source.get("sha256") != sha256(expected_path):
            raise ValueError("VISUAL_PLACEMENT_REVIEW_SOURCE_MISMATCH")
    rows = review.get("reviews")
    if not isinstance(rows, list):
        raise ValueError("VISUAL_PLACEMENT_REVIEW_INVALID")
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("VISUAL_PLACEMENT_REVIEW_INVALID")
        key = (str(row.get("pageNo") or ""), str(row.get("assetId") or ""))
        if not all(key) or key in indexed:
            raise ValueError("VISUAL_PLACEMENT_REVIEW_INVALID")
        indexed[key] = row
    return indexed, {"path": str(review_path), "sha256": sha256(review_path)}


def freeze_reviewed_placement(
    placement: dict[str, Any],
    review: dict[str, Any],
    page_type: str,
    page_body: str,
) -> None:
    if review.get("imageReviewed") is not True or not str(review.get("semanticRelation") or "").strip():
        raise ValueError("COURSEWARE_IMAGE_PLACEMENT_REVIEW_INVALID")
    embedded_text_overlap = review.get(
        "embeddedTextOverlapDetected",
        review.get("embeddedTextConflict", False),
    )
    if not isinstance(embedded_text_overlap, bool):
        raise ValueError("COURSEWARE_IMAGE_PLACEMENT_REVIEW_INVALID")
    fallback_used = review.get("fallbackUsed")
    if not isinstance(fallback_used, bool):
        raise ValueError("COURSEWARE_IMAGE_PLACEMENT_REVIEW_INVALID")
    candidate = placement.get("renderPlacement")
    final = review.get("renderPlacement")
    if not isinstance(candidate, dict) or not isinstance(final, dict):
        raise ValueError("COURSEWARE_IMAGE_PLACEMENT_REVIEW_INVALID")
    expected_fallback = "after_first_text_block" if page_type == "拓展练习" else "after_page_title"
    if (
        final.get("authority") != "model_visual_review"
        or final.get("anchorType") != "reviewed_semantic_anchor"
        or final.get("rule") != candidate.get("rule")
        or final.get("fallback") != expected_fallback
        or final.get("terminalPlacementForbidden") is not True
    ):
        raise ValueError("COURSEWARE_IMAGE_PLACEMENT_REVIEW_INVALID")
    if fallback_used:
        expected_insert_after = "first_text_block" if page_type == "拓展练习" else "page_title"
        if final.get("insertAfter") != expected_insert_after:
            raise ValueError("COURSEWARE_IMAGE_PLACEMENT_REVIEW_INVALID")
    else:
        before = str(final.get("insertAfterText") or "")
        after = str(final.get("insertBeforeText") or "")
        if not before or before not in page_body or (after and after not in page_body):
            raise ValueError("COURSEWARE_IMAGE_PLACEMENT_REVIEW_INVALID")
        if after and page_body.index(before) >= page_body.index(after):
            raise ValueError("COURSEWARE_IMAGE_PLACEMENT_REVIEW_INVALID")
    placement["renderPlacement"] = deepcopy(final)
    placement["placementStatus"] = "reviewed"
    placement["visualReview"] = {
        "imageReviewed": True,
        "semanticRelation": str(review["semanticRelation"]),
        "embeddedTextOverlapDetected": embedded_text_overlap,
        "fallbackUsed": fallback_used,
    }


def finalize_manifest(
    lesson_id: str,
    request_path: Path,
    page_plan_path: Path,
    external_path: Path,
    placement_review_path: Path | None = None,
) -> dict[str, Any]:
    request_path = request_path.resolve()
    page_plan_path = page_plan_path.resolve()
    external_path = external_path.resolve()
    request = load_json(request_path, "VISUAL_REQUEST_MANIFEST_INVALID")
    if request.get("lessonId") != lesson_id or request.get("lifecycleState") != "request":
        raise ValueError("VISUAL_REQUEST_MANIFEST_INVALID")
    if request.get("visualMode") != "visual_enhanced":
        raise ValueError("VISUAL_MODE_DRIFT")
    source_page_plan = request.get("sourcePagePlan")
    if not isinstance(source_page_plan, dict):
        raise ValueError("VISUAL_REQUEST_PAGE_PLAN_MISSING")
    if source_page_plan.get("path") != str(page_plan_path):
        raise ValueError("VISUAL_REQUEST_PAGE_PLAN_PATH_MISMATCH")
    if source_page_plan.get("sha256") != sha256(page_plan_path):
        raise ValueError("VISUAL_REQUEST_PAGE_PLAN_HASH_MISMATCH")
    if not external_path.is_file():
        raise ValueError("EXTERNAL_RETURN_MISSING")

    original = page_plan_path.read_text(encoding="utf-8")
    external = external_path.read_text(encoding="utf-8")
    stripped, metadata, lesson_override_pages = strip_metadata(external)
    normalized_original = normalize_original(original)
    original_pages = [page_no for page_no, _ in split_pages(original)[1]]
    page_bodies = dict(split_pages(original)[1])
    if list(metadata) != original_pages:
        raise ValueError("EXTERNAL_RETURN_PAGE_SET_MISMATCH")
    if page_types(stripped) != page_types(normalized_original):
        raise ValueError("EXTERNAL_RETURN_PAGE_TYPE_MISMATCH")
    exact_page_plan = stripped == normalized_original

    payload = deepcopy(request)
    assets_by_id = {str(item.get("assetId")): item for item in payload.get("assets") or []}
    placements_by_asset = {
        str(item.get("assetId")): item
        for item in payload.get("placements") or []
        if isinstance(item, dict) and item.get("assetId")
    }
    reviews, review_source = reviewed_placements(
        lesson_id,
        placement_review_path,
        request_path,
        external_path,
    )
    consumed_reviews: set[tuple[str, str]] = set()
    decisions = payload.get("pageDecisions") or []
    seen_urls: set[str] = set()
    ignored_courseware_pages: list[str] = []
    for decision in decisions:
        page_no = str(decision.get("pageNo") or "")
        values = metadata.get(page_no) or {}
        has_metadata = any(values.values())
        choice = decision.get("decision")
        if page_no in lesson_override_pages:
            raise ValueError("EXTERNAL_RETURN_LESSON_PLAN_IMAGE_OVERRIDE")
        if choice == "interaction_no_image":
            if has_metadata:
                raise ValueError("EXTERNAL_RETURN_INTERACTION_IMAGE_FORBIDDEN")
            decision["status"] = "not_applicable"
            continue
        if choice == "lesson_plan_image":
            if has_metadata:
                ignored_courseware_pages.append(page_no)
            decision["status"] = "ready"
            continue
        if choice != "courseware_image":
            raise ValueError("VISUAL_PAGE_DECISION_INVALID")
        url = one_value(values, "url")
        if not url or not url.startswith("https://"):
            raise ValueError("COURSEWARE_IMAGE_URL_MISSING")
        if url in seen_urls:
            raise ValueError("COURSEWARE_IMAGE_URL_DUPLICATE")
        seen_urls.add(url)
        asset_ids = decision.get("assetIds") or []
        if len(asset_ids) != 1 or str(asset_ids[0]) not in assets_by_id:
            raise ValueError("COURSEWARE_IMAGE_COUNT_INVALID")
        asset = assets_by_id[str(asset_ids[0])]
        asset.update(
            {
                "url": url,
                "width": positive_int(one_value(values, "width"), "COURSEWARE_IMAGE_WIDTH_INVALID"),
                "height": positive_int(one_value(values, "height"), "COURSEWARE_IMAGE_HEIGHT_INVALID"),
                "alt": one_value(values, "alt"),
                "generatedVersion": one_value(values, "generatedVersion"),
                "sourceAuthority": "external_courseware_return",
                "assetStatus": "ready",
            }
        )
        placement = placements_by_asset.get(str(asset_ids[0]))
        if not isinstance(placement, dict):
            raise ValueError("COURSEWARE_IMAGE_PLACEMENT_INVALID")
        if courseware_page_requires_review(str(decision.get("pageType") or "")):
            review_key = (page_no, str(asset_ids[0]))
            review = reviews.get(review_key)
            if not isinstance(review, dict):
                raise ValueError("COURSEWARE_IMAGE_PLACEMENT_REVIEW_MISSING")
            freeze_reviewed_placement(
                placement,
                review,
                str(decision.get("pageType") or ""),
                page_bodies.get(page_no, ""),
            )
            consumed_reviews.add(review_key)
        else:
            placement["placementStatus"] = "active"
            placement["visualReview"] = {
                "imageReviewed": False,
                "reviewNotRequiredReason": "fixed_page_type_placement",
                "fallbackUsed": False,
            }
        decision["status"] = "resolved"

    requested_pages = {str(item.get("pageNo")) for item in decisions}
    for page_no, values in metadata.items():
        if any(values.values()) and page_no not in requested_pages:
            raise ValueError("COURSEWARE_IMAGE_UNREQUESTED_PAGE")
    if set(reviews) != consumed_reviews:
        raise ValueError("VISUAL_PLACEMENT_REVIEW_PAGE_SET_MISMATCH")

    payload["lifecycleState"] = "resolved"
    payload["sourceRequestManifest"] = {"path": str(request_path), "sha256": sha256(request_path)}
    payload["externalReturn"] = {
        "path": str(external_path),
        "sha256": sha256(external_path),
        "bindingMode": "exact_page_plan" if exact_page_plan else "cross_chain_page_metadata",
        "sourceBasePagePlanSha256": text_sha256(stripped),
        "targetPagePlanSha256": sha256(page_plan_path),
        "ignoredCoursewarePages": ignored_courseware_pages,
    }
    payload["placementReview"] = review_source
    payload["checks"] = {
        **(payload.get("checks") or {}),
        "externalReturnPagePlanExactAfterMetadataRemoval": exact_page_plan,
        "externalReturnPageSetAndTypesMatch": True,
        "externalReturnBodyUsedAsContentAuthority": False,
        "externalReturnAuthorityLimitedToCoursewareFields": True,
        "requiredCoursewareUrlsComplete": True,
        "lessonPlanAndInteractionPagesProtected": True,
        "lessonPlanImagePriorityApplied": True,
        "coursewarePlacementReviewComplete": True,
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze an authorized external return into the resolved S1 visual manifest")
    parser.add_argument("--lesson-id", required=True)
    parser.add_argument("--request-manifest", required=True, type=Path)
    parser.add_argument("--page-plan", required=True, type=Path)
    parser.add_argument("--external-return", required=True, type=Path)
    parser.add_argument("--placement-review", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        payload = finalize_manifest(
            args.lesson_id,
            args.request_manifest,
            args.page_plan,
            args.external_return,
            args.placement_review,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, UnicodeError, ValueError) as exc:
        return blocked(str(exc))
    print(json.dumps({"status": "PASS", "output": str(args.output.resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
