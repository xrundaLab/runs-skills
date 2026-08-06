#!/usr/bin/env python3
"""Validate the formal RunS V3.5 S5 effective-content JSON contract.

The validator is read-only. It compares one ``effective_content_full.json``
with its explicitly declared frozen S4 ``page_plan_full.md`` and never reads
earlier lesson artifacts. It does not generate or repair JSON.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from page_type_contract import (  # noqa: E402
    POST_CLASS_CANONICAL_PAGE_TYPE,
    canonical_capsule,
    canonical_page_type,
)
from visual_placement_contract import courseware_page_requires_review, visual_presentation  # noqa: E402

from validate_v35_page_plan_question_boundaries import JSON_FENCE_RE, parse_pages


PAGE_BASE_FIELDS = (
    "page_no",
    "page_type",
    "capsule",
    "page_action",
    "source_block_ids",
    "effective_content",
)
P01_EFFECTIVE_FIELDS = (
    "课包名称",
    "单元名称",
    "课程编号",
    "课程标题",
    "课程目标",
    "知识点",
)
P01_CONTENT_FIELDS = (
    "packageName",
    "unitName",
    "lessonNumber",
    "courseName",
    "courseIntroduction",
    "knowledgePoints",
)
POST_CLASS_SECTION_TYPES = {
    "paragraph",
    "task",
    "facts",
    "step",
    "prompt",
    "decision",
    "safety",
    "fallback",
    "section_heading",
    "composite",
}
POST_CLASS_SECTION_ROLES = {
    "lead",
    "preflight",
    "action",
    "prompt",
    "review",
    "checklist",
    "condition",
    "correctivePrompt",
    "decision",
    "safetyFallback",
    "fallback",
    "note",
    "storySequenceHeading",
    "storySequence",
    "composite",
}
FORBIDDEN_DOWNSTREAM_FIELDS = {"prompt", "components", "sdk_action", "is_last_page"}
LESSON_NUMBER_RE = re.compile(r"(\d+)")
TRANSITION_PLACEMENTS = {"before_title", "after_content"}
DESIGN_BRIEF_PAGE_TYPES = {"知识讲解", "案例分析"}
DESIGN_BRIEF_CONTENT_SHAPES = {
    "claim_to_evidence_to_judgment",
    "concept_to_example_to_boundary",
    "problem_to_method_to_result",
    "example_to_comparison_to_boundary",
    "parallel_comparison",
    "process_or_sequence",
    "continuous_explanation",
}
DESIGN_BRIEF_DENSITIES = {"light", "medium", "dense"}
DESIGN_BRIEF_RHYTHM_ROLES = {
    "statement",
    "structured",
    "contrast",
    "narrative",
    "dense_reference",
}
SHORT_PAGE_COMPOSITIONS = {"two_layer_reading"}
DESIGN_LAYOUT_ARCHETYPES = {
    "two_layer_open_reading",
    "evidence_comparison_then_resolution",
    "aligned_evidence_comparison",
    "guided_process_with_role_distribution",
    "left_aligned_process",
    "role_distribution_with_judgment",
    "open_explanation_with_light_anchor",
    "open_explanation",
    "inline_evidence_then_resolution",
}
DESIGN_GEOMETRIES = {
    "open_reading_band",
    "open_body_flow",
    "aligned_comparison",
    "left_aligned_process",
    "role_distribution_cluster",
    "inline_role_distribution",
    "soft_conclusion_anchor",
    "inline_evidence_comparison",
}
DESIGN_SURFACE_ROLES = {
    "open_background",
    "split_soft_tints",
    "outlined_light_surface",
    "mixed_light_tints",
    "light_accent_tint",
    "open_with_inline_highlights",
}
DESIGN_VISUAL_WEIGHTS = {"supporting", "normal", "primary"}
EXPECTED_SURFACE_POLICY = {
    "lightDominant": True,
    "allowLargeDarkSurface": False,
    "nonCodeDarkSurfaceAreaPercentMax": 0,
    "minimumOpenRegions": 1,
    "maximumTopLevelVisualRegions": 4,
    "nestedItemStyle": "flat_subregion",
    "nestedItemsUseIndependentShadow": False,
    "punctuatedClausesUseInlineFlow": True,
    "maximumDecorativeGroups": 2,
    "forbid": [
        "largeNearBlackContentPanel",
        "allContentInsideCards",
        "uniformRoundedCardStack",
    ],
}
EXPECTED_COLOR_ROLES = {
    "primaryEmphasis": "runs_purple_inline",
    "conflictEvidence": "warm_amber_inline",
    "supportingInformation": "cool_blue_tint",
    "conclusionSurface": "light_purple_tint",
    "bodyText": "dark_neutral",
    "inlineHighlightOnly": True,
}
EXPECTED_SPACE_BALANCE = {
    "readingAreaTarget": "60_to_75_percent",
    "maximumUnusedLowerAreaPercent": 12,
    "forbidTopHeavyComposition": True,
}
EXPECTED_ALIGNMENT_POLICY = {
    "priority": [
        "shared_left_edge",
        "shared_top_edge",
        "consistent_width",
        "semantic_asymmetry",
    ],
    "sameSemanticLevelSharedLeftEdge": True,
    "comparisonPeersTopAligned": True,
    "comparisonPeersEqualWidth": True,
    "sequenceItemsSharedLeftEdge": True,
    "asymmetryOnlyForExplicitPrimarySupporting": True,
    "forbid": ["randomIndent", "randomWidth", "staggerForVariety"],
}
EXPECTED_COMPARISON_LAYOUT_POLICY = {
    "sideBySideAllowed": True,
    "sideBySideMaxCharsPerPeer": 80,
    "sideBySideMaxCombinedChars": 150,
    "withinLimitLayout": "aligned_equal_width_columns",
    "overLimitLayout": "vertical_full_width_stack",
    "verticalStackSharedLeftEdge": True,
}
EXPECTED_HIGHLIGHT_POLICY = {
    "maximumSegmentsPerPage": 3,
    "sameSemanticCategoryUsesSameStyle": True,
    "shortHighlightNoWrapMaxChars": 12,
    "shortHighlightMoveWholeToNextLine": True,
    "forbidOrphanTailCharsMax": 2,
    "forbid": ["multicolorSameCategory", "oneOrTwoCharacterHighlightedTail"],
}
ORDERED_PARAGRAPH_RE = re.compile(
    r"^(?:第[一二三四五六七八九十百]+[，、：:]|[一二三四五六七八九十]+[、.]|\d+[、.])"
)
NON_EFFECTIVE_STATUS_RE = re.compile(r"本课没有(?:课后练习|课后任务|拓展练习)[^。\n]*[。.]?")
DYNAMIC_STRUCTURED_BLOCK_TYPES = {
    "heading",
    "paragraph",
    "ordered_list",
    "unordered_list",
    "blockquote",
    "code_block",
}
HEADING_BLOCK_RE = re.compile(r"^(#{1,6})\s+(.+)$")
ORDERED_LIST_ITEM_RE = re.compile(r"^\s*\d+[.)、]\s+(.+)$")
UNORDERED_LIST_ITEM_RE = re.compile(r"^\s*[-*+]\s+(.+)$")
BLOCKQUOTE_LINE_RE = re.compile(r"^> ?(.*)$")


def contains_key(value: Any, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(contains_key(item, key) for item in value)
    return False


def contains_non_effective_status(value: Any) -> bool:
    if isinstance(value, str):
        return bool(NON_EFFECTIVE_STATUS_RE.search(value))
    if isinstance(value, dict):
        return any(contains_non_effective_status(item) for item in value.values())
    if isinstance(value, list):
        return any(contains_non_effective_status(item) for item in value)
    return False


def ordered_equal(left: Any, right: Any) -> bool:
    """Compare JSON values while preserving object-key and array order."""

    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return list(left) == list(right) and all(
            ordered_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            ordered_equal(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    return left == right


def visual_without_pair_bindings(value: Any) -> Any:
    """Return the manifest projection after removing S5-derived text bindings."""

    projected = copy.deepcopy(value)
    if not isinstance(projected, dict):
        return projected
    assets = projected.get("assets")
    if isinstance(assets, list):
        for asset in assets:
            if isinstance(asset, dict):
                asset.pop("pairedStudentText", None)
                asset.pop("pairedSource", None)
    return projected


def normalized_visual_label(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", "", normalized).rstrip("：:")


def validate_visual_pair_bindings(
    page: dict[str, Any],
    issues: list[dict[str, str]],
    page_no: str,
) -> None:
    """Validate optional exact source bindings for a multi-image group.

    Missing bindings remain compatible and non-blocking.  Once S5 emits any
    binding, however, the complete group must be an exact, one-to-one
    projection of one labelled unordered-list item per asset.
    """

    visual = page.get("visual")
    assets = visual.get("assets") if isinstance(visual, dict) else None
    if not isinstance(assets, list) or len(assets) < 2:
        return
    has_binding = [
        isinstance(asset, dict)
        and ("pairedStudentText" in asset or "pairedSource" in asset)
        for asset in assets
    ]
    if not any(has_binding):
        return
    sections = page.get("sections")
    invalid = not isinstance(sections, list) or not all(has_binding)
    seen_sources: set[tuple[int, int]] = set()
    for asset in assets:
        if not isinstance(asset, dict):
            invalid = True
            continue
        text = asset.get("pairedStudentText")
        source = asset.get("pairedSource")
        label = asset.get("displayLabel")
        if (
            not isinstance(text, str)
            or not text
            or not isinstance(source, dict)
            or not isinstance(label, str)
            or source.get("blockType") != "unordered_list"
        ):
            invalid = True
            continue
        block_index = source.get("blockIndex")
        item_index = source.get("itemIndex")
        coordinate = (block_index, item_index)
        if (
            not isinstance(block_index, int)
            or isinstance(block_index, bool)
            or not isinstance(item_index, int)
            or isinstance(item_index, bool)
            or coordinate in seen_sources
            or not isinstance(sections, list)
            or not (0 <= block_index < len(sections))
        ):
            invalid = True
            continue
        seen_sources.add(coordinate)
        block = sections[block_index]
        items = block.get("items") if isinstance(block, dict) else None
        if (
            not isinstance(block, dict)
            or block.get("type") != "unordered_list"
            or not isinstance(items, list)
            or not (0 <= item_index < len(items))
            or items[item_index] != text
        ):
            invalid = True
            continue
        match = re.match(r"^\s*([^：:]{1,24})[：:]", text)
        if not match or normalized_visual_label(match.group(1)) != normalized_visual_label(label):
            invalid = True
    if invalid:
        add_issue(
            issues,
            "V35_S5_VISUAL_TEXT_PAIRING_INVALID",
            "多图 pairedStudentText 必须完整、一一对应且逐字引用同一 unordered_list 中与 displayLabel 匹配的原文项；缺少绑定本身不阻断。",
            page_no,
        )


def source_block_ids(source_block: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,，、]", source_block) if item.strip()]


def parse_dynamic_source_blocks(raw_markdown: str) -> list[dict[str, Any]]:
    """Project frozen dynamic-page Markdown into ordered, source-faithful blocks.

    This is deliberately a structural projection, not a text transformation:
    every block retains its exact source fragment in ``markdown``.  The source
    audit field remains the authoritative record for inter-block whitespace.
    """

    if not isinstance(raw_markdown, str) or not raw_markdown.strip():
        return []
    chunks = [chunk for chunk in re.split(r"\n[ \t]*\n+", raw_markdown) if chunk]
    blocks: list[dict[str, Any]] = []
    for markdown in chunks:
        lines = markdown.splitlines()
        heading = HEADING_BLOCK_RE.fullmatch(markdown)
        if heading:
            blocks.append(
                {
                    "type": "heading",
                    "level": len(heading.group(1)),
                    "text": heading.group(2),
                    "markdown": markdown,
                }
            )
            continue
        ordered_items = [ORDERED_LIST_ITEM_RE.fullmatch(line) for line in lines]
        if lines and all(ordered_items):
            blocks.append(
                {
                    "type": "ordered_list",
                    "items": [match.group(1) for match in ordered_items if match],
                    "markdown": markdown,
                }
            )
            continue
        unordered_items = [UNORDERED_LIST_ITEM_RE.fullmatch(line) for line in lines]
        if lines and all(unordered_items):
            blocks.append(
                {
                    "type": "unordered_list",
                    "items": [match.group(1) for match in unordered_items if match],
                    "markdown": markdown,
                }
            )
            continue
        quoted_lines = [BLOCKQUOTE_LINE_RE.fullmatch(line) for line in lines]
        if lines and all(quoted_lines):
            blocks.append(
                {
                    "type": "blockquote",
                    "text": "\n".join(match.group(1) for match in quoted_lines if match),
                    "markdown": markdown,
                }
            )
            continue
        if len(lines) >= 2 and lines[0].startswith("```") and lines[-1] == "```":
            blocks.append(
                {
                    "type": "code_block",
                    "language": lines[0][3:].strip(),
                    "text": "\n".join(lines[1:-1]),
                    "markdown": markdown,
                }
            )
            continue
        blocks.append({"type": "paragraph", "text": markdown, "markdown": markdown})
    return blocks


def validate_dynamic_structured_block_projection(
    page: dict[str, Any], issues: list[dict[str, str]]
) -> None:
    """Reject a Markdown blob or altered block projection on dynamic pages."""

    page_no = str(page.get("page_no") or "")
    source = page.get("source")
    raw_markdown = source.get("rawMarkdown") if isinstance(source, dict) else None
    effective = page.get("effective_content")
    actual_blocks = effective.get("blocks") if isinstance(effective, dict) else None
    expected_blocks = parse_dynamic_source_blocks(raw_markdown) if isinstance(raw_markdown, str) else []
    invalid = (
        not expected_blocks
        or not isinstance(actual_blocks, list)
        or actual_blocks != expected_blocks
        or any(
            not isinstance(block, dict)
            or block.get("type") not in DYNAMIC_STRUCTURED_BLOCK_TYPES
            for block in actual_blocks or []
        )
    )
    content = page.get("content")
    content_blocks = content.get("blocks") if isinstance(content, dict) else None
    if content_blocks is not None and content_blocks != actual_blocks:
        invalid = True
    if invalid:
        add_issue(
            issues,
            "V35_DYNAMIC_STRUCTURED_BLOCK_PROJECTION_INVALID",
            "知识讲解/案例分析的 effective_content.blocks 必须由 source.rawMarkdown 确定性拆为有序 heading、段落、列表、引用或代码块；每块 markdown 必须逐字保真，禁止单个 markdown 整段回退、删改或调序。",
            page_no,
        )


def add_issue(
    issues: list[dict[str, str]],
    code: str,
    message: str,
    page_no: str | None = None,
) -> None:
    issue = {"issue_type": code, "severity": "BLOCKER", "message": message}
    if page_no:
        issue["page_no"] = page_no
    issues.append(issue)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_visuals(
    lesson_id: str,
    page_plan: Path,
    visual_manifest: Path | None,
    issues: list[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    if visual_manifest is None or not visual_manifest.is_file():
        add_issue(issues, "V35_S5_VISUAL_MANIFEST_MISSING", "visual_enhanced S5 缺少 resolved visual manifest。")
        return {}
    try:
        manifest = json.loads(visual_manifest.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        add_issue(issues, "V35_S5_VISUAL_MANIFEST_INVALID", "resolved visual manifest 无法解析。")
        return {}
    if not isinstance(manifest, dict) or manifest.get("lifecycleState") != "resolved":
        add_issue(issues, "V35_S5_VISUAL_MANIFEST_INVALID", "S5 只接受 resolved visual manifest。")
        return {}
    if manifest.get("lessonId") != lesson_id or manifest.get("visualMode") != "visual_enhanced":
        add_issue(issues, "VISUAL_MODE_DRIFT", "resolved manifest 的课程或 visualMode 与 S5 不一致。")
    source_plan = manifest.get("sourcePagePlan")
    if not isinstance(source_plan, dict) or source_plan.get("path") != str(page_plan.resolve()) or source_plan.get("sha256") != sha256(page_plan):
        add_issue(issues, "V35_S5_VISUAL_PAGE_PLAN_MISMATCH", "resolved manifest 未绑定当前原始 S4 路径与 SHA。")

    assets = manifest.get("assets") or []
    placements = manifest.get("placements") or []
    decisions = manifest.get("pageDecisions") or []
    assets_by_id = {str(item.get("assetId")): item for item in assets if isinstance(item, dict) and item.get("assetId")}
    expected: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        if not isinstance(decision, dict):
            continue
        page_no = str(decision.get("pageNo") or "")
        choice = decision.get("decision")
        asset_ids = decision.get("assetIds") or []
        if choice == "interaction_no_image":
            expected[page_no] = {"interaction": True}
            continue
        projected_assets: list[dict[str, Any]] = []
        for asset_id in asset_ids:
            asset = assets_by_id.get(str(asset_id))
            matches = [item for item in placements if isinstance(item, dict) and item.get("pageNo") == page_no and item.get("assetId") == asset_id]
            if not isinstance(asset, dict) or len(matches) != 1 or asset.get("imageType") != choice:
                add_issue(issues, "V35_S5_VISUAL_MANIFEST_INVALID", "图片资产、分类与 placement 不一致。", page_no)
                continue
            placement = matches[0]
            visual_review = placement.get("visualReview")
            if choice == "courseware_image" and courseware_page_requires_review(str(decision.get("pageType") or "")):
                render_placement = placement.get("renderPlacement")
                if (
                    placement.get("placementStatus") != "reviewed"
                    or not isinstance(visual_review, dict)
                    or visual_review.get("imageReviewed") is not True
                    or not isinstance(render_placement, dict)
                    or render_placement.get("terminalPlacementForbidden") is not True
                ):
                    add_issue(
                        issues,
                        "COURSEWARE_IMAGE_PLACEMENT_REVIEW_MISSING",
                        "需看图的课件配图未冻结模型审阅与最终 placement。",
                        page_no,
                    )
            projected_assets.append(
                {
                    "assetId": str(asset_id),
                    "url": asset.get("url"),
                    "width": asset.get("width"),
                    "height": asset.get("height"),
                    "alt": asset.get("alt"),
                    "order": placement.get("order"),
                    "displayLabel": placement.get("displayLabel"),
                    "placement": placement.get("renderPlacement"),
                    "visualReview": visual_review if isinstance(visual_review, dict) else None,
                }
            )
        projected_assets.sort(key=lambda item: (item.get("order") is None, item.get("order") or 0, item["assetId"]))
        expected[page_no] = {
            "imageType": choice,
            "displayMode": "group" if len(projected_assets) > 1 else "single",
            "assets": projected_assets,
            "placementMode": "per_asset",
            "presentation": visual_presentation(),
        }
    return expected


def split_course_intro_knowledge_points(raw_value: str) -> list[str]:
    points: list[str] = []
    for value in re.split(r"[;；\n]+", raw_value):
        normalized = re.sub(r"^\s*(?:[-*•]|\d+[.．、)）:：])\s*", "", value).strip()
        if normalized:
            points.append(normalized)
    return points


def validate_p01(
    page: dict[str, Any],
    plan_body: str,
    issues: list[dict[str, str]],
) -> None:
    page_no = str(page.get("page_no") or "")
    effective = page.get("effective_content")
    content = page.get("content")
    if not isinstance(effective, dict) or list(effective) != list(P01_EFFECTIVE_FIELDS):
        add_issue(
            issues,
            "V35_S2E_P01_SIX_FIELDS_INVALID",
            "P01 effective_content 必须按固定顺序完整包含六项课程信息。",
            page_no,
        )
        return
    if not isinstance(content, dict) or list(content) != list(P01_CONTENT_FIELDS):
        add_issue(
            issues,
            "V35_S2E_P01_SIX_FIELDS_INVALID",
            "P01 content 必须按固定顺序提供六个课程开篇变量。",
            page_no,
        )
        return
    lesson_match = LESSON_NUMBER_RE.search(str(effective["课程编号"]))
    expected_lesson_number = int(lesson_match.group(1)) if lesson_match else None
    expected_content = {
        "packageName": effective["课包名称"],
        "unitName": effective["单元名称"],
        "lessonNumber": expected_lesson_number,
        "courseName": effective["课程标题"],
        "courseIntroduction": effective["课程目标"],
        "knowledgePoints": split_course_intro_knowledge_points(
            str(effective["知识点"])
        ),
    }
    if any(
        content.get(key) != expected_content[key]
        for key in P01_CONTENT_FIELDS[:-1]
    ):
        add_issue(
            issues,
            "V35_S2E_P01_SIX_FIELDS_INVALID",
            "P01 前五个模板变量不是课程信息字段的确定性投影。",
            page_no,
        )
    if content.get("knowledgePoints") != expected_content["knowledgePoints"]:
        add_issue(
            issues,
            "V35_S2E_P01_KNOWLEDGE_POINTS_PROJECTION_INVALID",
            "P01 必须保留知识点原始字段，并按分号或换行确定性投影为非空有序 knowledgePoints list。",
            page_no,
        )
    if any(f"{label}：" not in plan_body for label in P01_EFFECTIVE_FIELDS):
        add_issue(
            issues,
            "V35_S2E_P01_SIX_FIELDS_INVALID",
            "上游 P01 页面规划缺少六项课程信息。",
            page_no,
        )


def dynamic_visible_block_count(page: dict[str, Any]) -> int:
    """Return the number of student-visible source blocks addressable by a brief."""

    effective = page.get("effective_content")
    if isinstance(effective, dict) and isinstance(effective.get("blocks"), list):
        blocks = effective["blocks"]
    else:
        content = page.get("content")
        blocks = content.get("blocks") if isinstance(content, dict) else []
    layout = page.get("display_hints") or page.get("layout_plan")
    transition_text = (
        layout.get("transitionText") if isinstance(layout, dict) else None
    )
    return sum(
        1
        for block in blocks
        if isinstance(block, dict)
        and block.get("type") != "heading"
        and not (
            isinstance(transition_text, str)
            and block.get("text") == transition_text
        )
    )


def dynamic_visible_blocks(page: dict[str, Any]) -> list[dict[str, Any]]:
    effective = page.get("effective_content")
    if isinstance(effective, dict) and isinstance(effective.get("blocks"), list):
        blocks = effective["blocks"]
    else:
        content = page.get("content")
        blocks = content.get("blocks") if isinstance(content, dict) else []
    layout = page.get("display_hints") or page.get("layout_plan")
    transition_text = layout.get("transitionText") if isinstance(layout, dict) else None
    return [
        block
        for block in blocks
        if isinstance(block, dict)
        and block.get("type") != "heading"
        and not (
            isinstance(transition_text, str)
            and block.get("text") == transition_text
        )
    ]


def dynamic_block_text(block: dict[str, Any]) -> str:
    if isinstance(block.get("text"), str):
        return block["text"]
    items = block.get("items")
    return "".join(item for item in items if isinstance(item, str)) if isinstance(items, list) else ""


def validate_dynamic_design_brief(
    page: dict[str, Any],
    issues: list[dict[str, str]],
    *,
    required: bool,
) -> None:
    """Validate the non-renderable dynamic-layout contract for R6 pages."""

    page_no = str(page.get("page_no") or "")
    brief = page.get("design_brief")
    if brief is None and not required:
        return
    if not isinstance(brief, dict):
        add_issue(
            issues,
            "V35_DYNAMIC_DESIGN_BRIEF_INVALID",
            "R6 知识讲解页和案例分析页必须提供非渲染 design_brief 对象。",
            page_no,
        )
        return

    required_strings = (
        "teachingAction",
        "layoutFreedom",
        "visualSystem",
        "visibleCopyPolicy",
    )
    invalid_base = (
        brief.get("nonRenderable") is not True
        or any(
            not isinstance(brief.get(field), str) or not brief[field].strip()
            for field in required_strings
        )
        or brief.get("contentShape") not in DESIGN_BRIEF_CONTENT_SHAPES
        or brief.get("density") not in DESIGN_BRIEF_DENSITIES
        or brief.get("rhythmRole") not in DESIGN_BRIEF_RHYTHM_ROLES
        or not isinstance(brief.get("readingFlow"), list)
        or not brief["readingFlow"]
        or any(
            not isinstance(item, str) or not item.strip()
            for item in brief.get("readingFlow", [])
        )
        or not isinstance(brief.get("hierarchyFocus"), list)
        or not brief["hierarchyFocus"]
        or any(
            not isinstance(item, str) or not item.strip()
            for item in brief.get("hierarchyFocus", [])
        )
        or (
            "shortPageComposition" in brief
            and brief.get("shortPageComposition") not in SHORT_PAGE_COMPOSITIONS
        )
    )
    if invalid_base:
        add_issue(
            issues,
            "V35_DYNAMIC_DESIGN_BRIEF_INVALID",
            "design_brief 缺少受控字段、枚举值无效，或 nonRenderable 不为 true。",
            page_no,
        )

    semantic_groups = brief.get("semanticGroups")
    visible_count = dynamic_visible_block_count(page)
    if not isinstance(semantic_groups, list) or not semantic_groups:
        add_issue(
            issues,
            "V35_DYNAMIC_SEMANTIC_GROUP_INVALID",
            "design_brief.semanticGroups 必须是非空有序数组。",
            page_no,
        )
        return

    group_ids: list[str] = []
    used_indexes: list[int] = []
    groups_invalid = visible_count < 1
    for group in semantic_groups:
        if not isinstance(group, dict):
            groups_invalid = True
            continue
        group_id = group.get("id")
        indexes = group.get("blockIndexes")
        purpose = group.get("purpose")
        if (
            not isinstance(group_id, str)
            or not group_id.strip()
            or group_id in group_ids
            or not isinstance(purpose, str)
            or not purpose.strip()
            or not isinstance(indexes, list)
            or not indexes
            or any(type(index) is not int for index in indexes)
            or indexes != sorted(set(indexes))
            or any(index < 1 or index > visible_count for index in indexes)
        ):
            groups_invalid = True
            continue
        group_ids.append(group_id)
        used_indexes.extend(indexes)

    if (
        len(used_indexes) != len(set(used_indexes))
        or sorted(used_indexes) != list(range(1, visible_count + 1))
        or (visible_count >= 3 and len(semantic_groups) < 2)
        or any(
            focus not in group_ids for focus in brief.get("hierarchyFocus", [])
        )
    ):
        groups_invalid = True
    if brief.get("shortPageComposition") == "two_layer_reading":
        # The composition has exactly two independent source blocks.  Two
        # ordered groups prevent S6 from manufacturing a third reading layer.
        if (
            visible_count != 2
            or len(semantic_groups) != 2
            or [group.get("blockIndexes") for group in semantic_groups if isinstance(group, dict)] != [[1], [2]]
        ):
            groups_invalid = True
    if groups_invalid:
        add_issue(
            issues,
            "V35_DYNAMIC_SEMANTIC_GROUP_INVALID",
            "semanticGroups 必须以 1-based blockIndexes 无重叠覆盖全部可见内容块；三块及以上内容至少用两个真实语义组表达阅读层级，且 hierarchyFocus 只能引用现有分组。",
            page_no,
        )

    visible_blocks = dynamic_visible_blocks(page)
    executable_invalid = brief.get("layoutArchetype") not in DESIGN_LAYOUT_ARCHETYPES

    presentations = brief.get("groupPresentation")
    if (
        not isinstance(presentations, list)
        or [row.get("groupId") for row in presentations if isinstance(row, dict)] != group_ids
        or any(
            not isinstance(row, dict)
            or row.get("geometry") not in DESIGN_GEOMETRIES
            or row.get("surfaceRole") not in DESIGN_SURFACE_ROLES
            or row.get("visualWeight") not in DESIGN_VISUAL_WEIGHTS
            for row in presentations or []
        )
    ):
        executable_invalid = True

    projection = brief.get("sourceProjectionPlan")
    projection_linguistic_invalid = False
    punctuated_clause_split = False
    if (
        not isinstance(projection, list)
        or [row.get("blockIndex") for row in projection if isinstance(row, dict)]
        != list(range(1, len(visible_blocks) + 1))
    ):
        executable_invalid = True
    else:
        for row, block in zip(projection, visible_blocks):
            if not isinstance(row, dict):
                executable_invalid = True
                continue
            mode = row.get("mode")
            source_text = dynamic_block_text(block)
            if mode == "single_region":
                if not isinstance(row.get("region"), str) or not row["region"].strip():
                    executable_invalid = True
            elif mode == "role_distribution_flow":
                punctuated_clause_split = True
                executable_invalid = True
            elif mode in {
                "inline_conflict_evidence",
                "sentence_sequence",
            }:
                fragments = row.get("fragments")
                allowed_regions = {
                    "inline_conflict_evidence": {
                        "inline_evidence_a",
                        "inline_shared_context",
                        "inline_evidence_b",
                    },
                    "sentence_sequence": {
                        f"step_{index}" for index in range(1, 20)
                    },
                }[mode]
                if (
                    row.get("concatenatedTextMustEqualSource") is not True
                    or not isinstance(fragments, list)
                    or not fragments
                    or any(
                        not isinstance(fragment, dict)
                        or not isinstance(fragment.get("text"), str)
                        or not fragment["text"]
                        or fragment.get("region") not in allowed_regions
                        for fragment in fragments or []
                    )
                    or "".join(fragment["text"] for fragment in fragments) != source_text
                ):
                    executable_invalid = True
                elif mode == "inline_conflict_evidence":
                    if (
                        row.get("renderMode") != "continuous_inline_flow"
                        or len(fragments) != 3
                        or [fragment["region"] for fragment in fragments]
                        != [
                            "inline_evidence_a",
                            "inline_shared_context",
                            "inline_evidence_b",
                        ]
                        or not any(token in fragments[0]["text"] for token in ("写着", "显示", "文字"))
                        or not any(token in fragments[2]["text"] for token in ("说", "语音", "声音"))
                        or any(
                            re.fullmatch(r"[，。！？；：,.!?;:]+", fragment["text"].strip())
                            for fragment in fragments
                        )
                    ):
                        projection_linguistic_invalid = True
                elif mode == "sentence_sequence":
                    if (
                        row.get("renderMode") != "single_section_flat_steps"
                        or len(fragments) < 2
                        or [fragment["region"] for fragment in fragments]
                        != [f"step_{index}" for index in range(1, len(fragments) + 1)]
                        or any(not re.search(r"[。！？!?]$", fragment["text"]) for fragment in fragments)
                    ):
                        projection_linguistic_invalid = True
            elif mode == "role_distribution_inline":
                targets = row.get("highlightTargets")
                if (
                    row.get("renderMode") != "continuous_inline_highlights"
                    or row.get("preserveSourceAsSingleTextFlow") is not True
                    or not isinstance(targets, list)
                    or len(targets) < 2
                ):
                    projection_linguistic_invalid = True
                else:
                    cursor = 0
                    for target in targets:
                        exact = target.get("exactText") if isinstance(target, dict) else None
                        if (
                            not isinstance(exact, str)
                            or not exact
                            or re.search(r"[，。！？；：、,.!?;:]$", exact)
                            or (position := source_text.find(exact, cursor)) < cursor
                        ):
                            projection_linguistic_invalid = True
                            break
                        cursor = position + len(exact)
            else:
                executable_invalid = True

    if punctuated_clause_split:
        add_issue(
            issues,
            "V35_DYNAMIC_PUNCTUATED_CLAUSE_BLOCK_SPLIT",
            "同一来源句中以逗号或分号连接的并列分句必须保持连续文本流，只允许原位下划线、字重或浅底色强调。",
            page_no,
        )

    if projection_linguistic_invalid:
        add_issue(
            issues,
            "V35_DYNAMIC_PROJECTION_LINGUISTIC_UNIT_INVALID",
            "sourceProjectionPlan 必须以完整句子或自然分句为单位；禁止孤立标点、引导词与引用分离，块内冲突必须保持连续行内阅读。",
            page_no,
        )
        executable_invalid = True

    emphasis = brief.get("emphasisTargets")
    relation_highlight_count = sum(
        len(row.get("highlightTargets", []))
        for row in projection or []
        if isinstance(row, dict) and isinstance(row.get("highlightTargets"), list)
    )
    if (
        not isinstance(emphasis, list)
        or relation_highlight_count + len(emphasis) > 3
    ):
        executable_invalid = True
    else:
        seen_targets: set[tuple[int, str]] = set()
        for target in emphasis:
            if not isinstance(target, dict):
                executable_invalid = True
                continue
            block_index = target.get("blockIndex")
            exact_text = target.get("exactText")
            marker = (block_index, exact_text) if isinstance(block_index, int) and isinstance(exact_text, str) else None
            if (
                marker is None
                or marker in seen_targets
                or block_index < 1
                or block_index > len(visible_blocks)
                or not exact_text
                or exact_text not in dynamic_block_text(visible_blocks[block_index - 1])
                or not isinstance(target.get("colorRole"), str)
                or not target["colorRole"].strip()
            ):
                executable_invalid = True
            elif marker is not None:
                seen_targets.add(marker)

    if (
        brief.get("surfacePolicy") != EXPECTED_SURFACE_POLICY
        or brief.get("colorRoles") != EXPECTED_COLOR_ROLES
        or brief.get("spaceBalance") != EXPECTED_SPACE_BALANCE
        or brief.get("alignmentPolicy") != EXPECTED_ALIGNMENT_POLICY
        or brief.get("comparisonLayoutPolicy") != EXPECTED_COMPARISON_LAYOUT_POLICY
        or brief.get("highlightPolicy") != EXPECTED_HIGHLIGHT_POLICY
        or "浅色主导" not in str(brief.get("visualSystem") or "")
        or "禁止大面积近黑背景" not in str(brief.get("visualSystem") or "")
        or "sourceProjectionPlan" not in str(brief.get("visibleCopyPolicy") or "")
    ):
        executable_invalid = True

    if executable_invalid:
        add_issue(
            issues,
            "V35_DYNAMIC_EXECUTABLE_DESIGN_MISSING",
            "design_brief 必须冻结可执行构图、逐块单次投影、原句强调、浅色表面策略与空间平衡；非代码内容禁止大面积近黑背景。",
            page_no,
        )


def validate_template_preflight(
    page: dict[str, Any],
    issues: list[dict[str, str]],
) -> None:
    page_no = str(page.get("page_no") or "")
    page_type = canonical_page_type(page.get("page_type"))
    if page_type == "互动题目":
        if not isinstance(page.get("layout_plan"), dict) or not page["layout_plan"]:
            add_issue(
                issues,
                "V35_S2E_TEMPLATE_PREFLIGHT_INVALID",
                "互动题页面必须保留非空 layout_plan。",
                page_no,
            )
        return

    content = page.get("content")
    sections = page.get("sections")
    source = page.get("source")
    layout = page.get("display_hints") or page.get("layout_plan")
    if not isinstance(content, dict) or not content:
        add_issue(
            issues,
            "V35_S2E_TEMPLATE_PREFLIGHT_INVALID",
            "非互动页面必须提供非空 content。",
            page_no,
        )
    if not isinstance(sections, list) or not sections:
        add_issue(
            issues,
            "V35_S2E_TEMPLATE_PREFLIGHT_INVALID",
            "非互动页面必须提供有序 sections。",
            page_no,
        )
    if not isinstance(layout, dict) or not layout:
        add_issue(
            issues,
            "V35_S2E_TEMPLATE_PREFLIGHT_INVALID",
            "非互动页面必须提供 display_hints 或等价 layout_plan。",
            page_no,
        )
    if not isinstance(source, dict) or not isinstance(source.get("rawMarkdown"), str):
        add_issue(
            issues,
            "V35_S2E_TEMPLATE_PREFLIGHT_INVALID",
            "非互动页面必须保留 source.rawMarkdown 审计真源。",
            page_no,
        )

    if page_type in DESIGN_BRIEF_PAGE_TYPES:
        validate_dynamic_structured_block_projection(page, issues)

    if page_type == POST_CLASS_CANONICAL_PAGE_TYPE and isinstance(sections, list):
        invalid_types = sorted(
            {
                str(section.get("type"))
                for section in sections
                if not isinstance(section, dict)
                or section.get("type") not in POST_CLASS_SECTION_TYPES
            }
        )
        if invalid_types:
            add_issue(
                issues,
                "V35_S2E_POST_CLASS_TASK_SECTION_INVALID",
                "拓展练习 sections 只允许登记的受控块：" + "、".join(sorted(POST_CLASS_SECTION_TYPES)),
                page_no,
            )
        invalid_roles = sorted(
            {
                str(section.get("role"))
                for section in sections
                if not isinstance(section, dict)
                or section.get("role") not in POST_CLASS_SECTION_ROLES
            }
        )
        if invalid_roles:
            add_issue(
                issues,
                "V35_S2E_POST_CLASS_TASK_ROLE_INVALID",
                "拓展练习 sections 必须携带受控语义 role，以供 S6 原位组合："
                + "、".join(sorted(POST_CLASS_SECTION_ROLES)),
                page_no,
            )
        for section in sections:
            if not isinstance(section, dict) or section.get("role") != "composite":
                continue
            segments = section.get("segments")
            segment_roles = (
                [segment.get("role") for segment in segments]
                if isinstance(segments, list)
                and all(isinstance(segment, dict) for segment in segments)
                else []
            )
            segment_text = (
                "".join(str(segment.get("text") or "") for segment in segments)
                if isinstance(segments, list)
                else ""
            )
            if (
                segment_roles != ["action", "completionCheck", "supportNote"]
                or segment_text != section.get("text")
            ):
                add_issue(
                    issues,
                    "V35_S2E_POST_CLASS_TASK_COMPOSITE_INVALID",
                    "复合任务段必须逐字拆为 action、completionCheck、supportNote，拼接后与原文完全一致。",
                    page_no,
                )
        raw_markdown = source.get("rawMarkdown") if isinstance(source, dict) else None
        source_blocks = (
            parse_dynamic_source_blocks(raw_markdown)
            if isinstance(raw_markdown, str)
            else []
        )
        expected_title = (
            source_blocks[0].get("text")
            if source_blocks and source_blocks[0].get("type") == "heading"
            else None
        )
        actual_title = content.get("taskTitle") if isinstance(content, dict) else None
        if (
            not isinstance(expected_title, str)
            or not expected_title.strip()
            or actual_title != expected_title.strip()
        ):
            add_issue(
                issues,
                "V35_S2E_POST_CLASS_TASK_TITLE_INVALID",
                "拓展练习 content.taskTitle 必须由 source.rawMarkdown 的首个标题逐字投影。",
                page_no,
            )
        expected_source = [str(block.get("markdown") or "") for block in source_blocks[1:]]
        actual_source = [
            section.get("sourceMarkdown") if isinstance(section, dict) else None
            for section in sections
        ]
        if not expected_source or actual_source != expected_source:
            add_issue(
                issues,
                "V35_S2E_POST_CLASS_TASK_SOURCE_PROJECTION_INVALID",
                "拓展练习 sections 必须逐块、按原序完整覆盖 source.rawMarkdown 的标题后全部正文，不得漏段、重排或仅保留首段。",
                page_no,
            )

    if page_type == "课程小结" and isinstance(content, dict) and isinstance(layout, dict):
        content_blocks = content.get("contentBlocks")
        effective = page.get("effective_content")
        effective_blocks = (
            effective.get("blocks") if isinstance(effective, dict) else None
        )
        summary_sequences = (effective_blocks, content_blocks, sections)
        headings: list[dict[str, Any] | None] = []
        for sequence in summary_sequences:
            heading = (
                sequence[0]
                if isinstance(sequence, list)
                and sequence
                and isinstance(sequence[0], dict)
                and sequence[0].get("type") == "heading"
                else None
            )
            headings.append(heading)
        if any(
            heading is None
            or not isinstance(heading.get("text"), str)
            or not heading["text"].strip()
            for heading in headings
        ):
            add_issue(
                issues,
                "COURSE_SUMMARY_TITLE_MISSING",
                "课程小结必须在 effective_content.blocks、content.contentBlocks 与 sections 的首块保留同一个非空 heading，供 S6 逐字投影 summaryTitle。",
                page_no,
            )
        elif not (headings[0] == headings[1] == headings[2]):
            add_issue(
                issues,
                "COURSE_SUMMARY_TITLE_PROJECTION_INVALID",
                "课程小结 heading 在三个 S5 结构投影中必须逐字一致。",
                page_no,
            )
        else:
            title = headings[0]["text"]
            duplicate = any(
                isinstance(block, dict)
                and block.get("type") != "heading"
                and block.get("text") == title
                for sequence in summary_sequences
                for block in (sequence[1:] if isinstance(sequence, list) else [])
            )
            if duplicate:
                add_issue(
                    issues,
                    "COURSE_SUMMARY_TITLE_DUPLICATED",
                    "课程小结 heading 只能作为 summaryTitle 真源，不得再次作为学生正文块重复输出。",
                    page_no,
                )
        styled_lists = [
            block
            for block in content_blocks or []
            if isinstance(block, dict) and block.get("type") == "orderedList"
        ]
        source_has_ordered_list = any(
            isinstance(section, dict) and section.get("type") == "ordered_list"
            for section in sections or []
        )
        source_has_numbered_paragraphs = (
            sum(
                1
                for section in sections or []
                if isinstance(section, dict)
                and section.get("type") == "paragraph"
                and isinstance(section.get("text"), str)
                and ORDERED_PARAGRAPH_RE.match(section["text"])
            )
            >= 2
        )
        if source_has_ordered_list or source_has_numbered_paragraphs:
            if not styled_lists:
                add_issue(
                    issues,
                    "SUMMARY_CONTENT_BLOCK_TYPE_INVALID",
                    "课程小结原文包含有序列表或连续编号条目，但 contentBlocks 未使用 orderedList。",
                    page_no,
                )
        for block in styled_lists:
            items = block.get("items")
            if (
                not isinstance(items, list)
                or not items
                or any(not isinstance(item, str) or not item.strip() for item in items)
                or (
                    "sourceNumbered" in block
                    and not isinstance(block.get("sourceNumbered"), bool)
                )
            ):
                add_issue(
                    issues,
                    "SUMMARY_CONTENT_BLOCK_TYPE_INVALID",
                    "orderedList 必须保留非空原文 items；sourceNumbered 如存在只能是布尔值。",
                    page_no,
                )

    if page_type == "知识讲解" and isinstance(layout, dict):
        transition_text = layout.get("transitionText")
        transition_placement = layout.get("transitionPlacement")
        if transition_text is not None or transition_placement is not None:
            raw_markdown = source.get("rawMarkdown") if isinstance(source, dict) else ""
            blocks = (
                page.get("effective_content", {}).get("blocks")
                if isinstance(page.get("effective_content"), dict)
                else None
            )
            block_texts = [
                block.get("text")
                for block in blocks or []
                if isinstance(block, dict) and isinstance(block.get("text"), str)
            ]
            expected_edge = (
                block_texts[0]
                if transition_placement == "before_title" and block_texts
                else block_texts[-1]
                if transition_placement == "after_content" and block_texts
                else None
            )
            if (
                not isinstance(transition_text, str)
                or not transition_text.strip()
                or transition_placement not in TRANSITION_PLACEMENTS
                or not isinstance(raw_markdown, str)
                or raw_markdown.count(transition_text) != 1
                or expected_edge != transition_text
            ):
                add_issue(
                    issues,
                    "V35_S2E_KNOWLEDGE_TRANSITION_INVALID",
                    "知识页过渡句必须逐字来自冻结原文，并按 before_title / after_content 位于页面首尾。",
                    page_no,
                )


def validate_effective_content(
    path: Path,
    page_plan: Path | None = None,
    visual_mode: str = "text_only",
    visual_manifest: Path | None = None,
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as exc:
        return {
            "file": str(path),
            "status": "BLOCKED",
            "page_count": 0,
            "interaction_json_count": 0,
            "issues": [
                {
                    "issue_type": "V35_S2E_JSON_PARSE_FAIL",
                    "severity": "BLOCKER",
                    "message": f"effective_content_full.json 无法解析：{exc}",
                }
            ],
        }

    if not isinstance(payload, dict):
        add_issue(issues, "V35_S2E_TOP_LEVEL_INVALID", "顶层必须是 JSON 对象。")
        payload = {}
    pages = payload.get("pages")
    if not isinstance(pages, list) or not pages:
        add_issue(issues, "V35_S2E_TOP_LEVEL_INVALID", "顶层 pages 必须是非空数组。")
        pages = []

    plan_path = page_plan or path.with_name("page_plan_full.md")
    declared_plan = payload.get("source_page_plan")
    if not isinstance(declared_plan, str) or not declared_plan:
        add_issue(
            issues,
            "V35_S2E_UPSTREAM_UNAVAILABLE",
            "缺少唯一 source_page_plan。",
        )
    elif Path(declared_plan).expanduser().resolve() != plan_path.resolve():
        add_issue(
            issues,
            "V35_S2E_UPSTREAM_UNAVAILABLE",
            "source_page_plan 必须逐字指向声明的唯一冻结 page_plan_full.md。",
        )

    if not plan_path.is_file():
        add_issue(
            issues,
            "V35_S2E_UPSTREAM_UNAVAILABLE",
            "唯一上游 page_plan_full.md 不存在。",
        )
        plan_pages: list[dict[str, str]] = []
    else:
        plan_pages = parse_pages(plan_path.read_text(encoding="utf-8"))
        if not plan_pages:
            add_issue(
                issues,
                "V35_S2E_UPSTREAM_UNAVAILABLE",
                "page_plan_full.md 未解析出页面。",
            )

    lesson_id = str(payload.get("lesson_id") or "")
    visual_expectations: dict[str, dict[str, Any]] = {}
    if visual_mode == "text_only":
        if any(key in payload for key in ("visualMode", "sourceVisualManifest", "sourceVisualManifestSha256")):
            add_issue(issues, "V35_S5_TEXT_ONLY_VISUAL_FIELD_FORBIDDEN", "text_only S5 顶层不得出现视觉字段。")
    elif visual_mode == "visual_enhanced":
        resolved_visual = visual_manifest.resolve() if visual_manifest else None
        if payload.get("visualMode") != "visual_enhanced":
            add_issue(issues, "V35_S5_VISUAL_MODE_INVALID", "visual_enhanced S5 顶层必须登记 visualMode。")
        if resolved_visual is None or payload.get("sourceVisualManifest") != str(resolved_visual):
            add_issue(issues, "V35_S5_VISUAL_MANIFEST_SOURCE_INVALID", "S5 未登记唯一 resolved manifest 绝对路径。")
        elif payload.get("sourceVisualManifestSha256") != sha256(resolved_visual):
            add_issue(issues, "V35_S5_VISUAL_MANIFEST_SOURCE_INVALID", "S5 resolved manifest SHA 不一致。")
        visual_expectations = expected_visuals(lesson_id, plan_path, resolved_visual, issues)
    else:
        add_issue(issues, "VISUAL_MODE_INVALID", "visualMode 只允许 text_only 或 visual_enhanced。")

    if len(pages) != len(plan_pages):
        add_issue(
            issues,
            "V35_S2E_PAGE_COUNT_MISMATCH",
            f"有效内容 JSON 与最终页面规划页数不一致：{len(pages)} != {len(plan_pages)}。",
        )

    interaction_count = 0
    sop_version = str(payload.get("sop_version") or "")
    require_r6_design_brief = (
        "-R6-" in sop_version
        or sop_version.startswith("RunS_V3.5.0-S1-S6-")
    )
    for index, (page, plan_page) in enumerate(zip(pages, plan_pages)):
        expected_no = f"P{index + 1:02d}"
        if not isinstance(page, dict):
            add_issue(
                issues,
                "V35_S2E_PAGE_BASE_FIELDS_INVALID",
                "页面必须是 JSON 对象。",
                expected_no,
            )
            continue
        page_no = str(page.get("page_no") or expected_no)
        if visual_mode == "text_only":
            if any(key in page for key in ("visual", "visualAsset", "planVisualAssets")):
                add_issue(issues, "V35_S5_TEXT_ONLY_VISUAL_FIELD_FORBIDDEN", "text_only 页面不得出现图片字段。", page_no)
        elif visual_mode == "visual_enhanced":
            expected_visual = visual_expectations.get(page_no)
            if page.get("page_type") == "互动题目":
                if any(key in page for key in ("visual", "visualAsset", "planVisualAssets")):
                    add_issue(issues, "V35_S5_INTERACTION_IMAGE_FORBIDDEN", "互动组件页禁止图片投影。", page_no)
                if expected_visual != {"interaction": True}:
                    add_issue(issues, "V35_S5_INTERACTION_IMAGE_FORBIDDEN", "resolved manifest 的互动页决策必须为 interaction_no_image。", page_no)
            elif not ordered_equal(
                visual_without_pair_bindings(page.get("visual")),
                expected_visual,
            ):
                add_issue(issues, "V35_S5_VISUAL_PROJECTION_INVALID", "S5 visual 不是 resolved manifest 的有序无损投影。", page_no)
            else:
                validate_visual_pair_bindings(page, issues, page_no)
        missing = [field for field in PAGE_BASE_FIELDS if field not in page]
        if missing:
            add_issue(
                issues,
                "V35_S2E_PAGE_BASE_FIELDS_INVALID",
                "页面缺少六个基础字段：" + "、".join(missing),
                page_no,
            )
        if page.get("page_no") != expected_no:
            add_issue(
                issues,
                "V35_S2E_PAGE_BASE_FIELDS_INVALID",
                f"页面编号必须连续；期望 {expected_no}。",
                page_no,
            )
        source_plan_page_type = plan_page["page_type"]
        expected_base = {
            "page_no": plan_page["page_no"],
            "page_type": canonical_page_type(source_plan_page_type),
            "capsule": canonical_capsule(source_plan_page_type, plan_page["capsule"]),
            "page_action": plan_page["action"],
            "source_block_ids": source_block_ids(plan_page["source_block"]),
        }
        actual_base = {key: page.get(key) for key in expected_base}
        if not ordered_equal(actual_base, expected_base):
            add_issue(
                issues,
                "V35_S2E_PAGE_BASE_FIELDS_INVALID",
                "页面编号、类型、胶囊、动作或来源块不是 page_plan_full.md 的有序确定性投影。",
                page_no,
            )

        expected_action = "complete" if index == len(pages) - 1 else "nextPage"
        if page.get("page_action") != expected_action:
            add_issue(
                issues,
                "V35_S2E_PAGE_ACTION_INVALID",
                f"页面动作应为 {expected_action}。",
                page_no,
            )
        content_action = page.get("content", {}).get("pageAction") if isinstance(page.get("content"), dict) else None
        if content_action is not None:
            expected_content_action = "complete" if expected_action == "complete" else "next"
            if content_action != expected_content_action:
                add_issue(
                    issues,
                    "V35_S2E_PAGE_ACTION_INVALID",
                    f"content.pageAction 应为 {expected_content_action}。",
                    page_no,
                )

        if any(field in page for field in FORBIDDEN_DOWNSTREAM_FIELDS):
            add_issue(
                issues,
                "V35_S2E_DOWNSTREAM_FIELD_FORBIDDEN",
                "S2E 不得提前生成 prompt、components、sdk_action 或 is_last_page。",
                page_no,
            )
        if contains_key(page.get("effective_content"), "background"):
            add_issue(
                issues,
                "QUESTION_BACKGROUND_FIELD_FORBIDDEN",
                "有效内容或题目 JSON 禁止独立 background 字段。",
                page_no,
            )

        if page.get("page_type") != "互动题目" and any(
            contains_non_effective_status(value)
            for value in (page.get("effective_content"), page.get("content"), page.get("sections"))
        ):
            add_issue(
                issues,
                "V35_S2E_STATUS_SENTENCE_NOT_FILTERED",
                "S5 是唯一有效内容筛除阶段；“本课没有课后练习/课后任务/拓展练习”等纯状态句必须保留在 source.rawMarkdown 审计真源中，不能进入 effective_content、content 或 sections。",
                page_no,
            )

        if page.get("page_type") == "互动题目":
            interaction_count += 1
            match = JSON_FENCE_RE.fullmatch(plan_page["body"])
            if not match:
                add_issue(
                    issues,
                    "V35_S2E_INTERACTION_JSON_NOT_ORDERED_PROJECTION",
                    "上游互动题有效内容不是唯一完整 JSON 代码块。",
                    page_no,
                )
            else:
                try:
                    expected_component = json.loads(match.group("json"))
                except json.JSONDecodeError:
                    expected_component = None
                if expected_component is None or not ordered_equal(
                    page.get("effective_content"), expected_component
                ):
                    add_issue(
                        issues,
                        "V35_S2E_INTERACTION_JSON_NOT_ORDERED_PROJECTION",
                        "互动题 effective_content 必须是上游完整 JSON 对象的有序投影，不得重组或调序。",
                        page_no,
                    )
            if page.get("component_type") != (
                page.get("effective_content", {}).get("type")
                if isinstance(page.get("effective_content"), dict)
                else None
            ):
                add_issue(
                    issues,
                    "V35_S2E_INTERACTION_JSON_NOT_ORDERED_PROJECTION",
                    "component_type 与互动题 JSON type 不一致。",
                    page_no,
                )
        else:
            raw_markdown = (
                page.get("source", {}).get("rawMarkdown")
                if isinstance(page.get("source"), dict)
                else None
            )
            if raw_markdown != plan_page["body"]:
                add_issue(
                    issues,
                    "V35_S2E_NON_INTERACTION_SOURCE_DRIFT",
                    "非互动页面 source.rawMarkdown 未逐字保留最终页面规划有效内容。",
                    page_no,
                )
            if page.get("page_type") == "课程开篇":
                validate_p01(page, plan_page["body"], issues)

        validate_template_preflight(page, issues)
        if page.get("page_type") in DESIGN_BRIEF_PAGE_TYPES:
            validate_dynamic_design_brief(
                page,
                issues,
                required=require_r6_design_brief,
            )

    return {
        "file": str(path),
        "page_plan": str(plan_path),
        "contract_mode": (
            "S1_S6"
            if sop_version.startswith("RunS_V3.5.0-S1-S6-")
            else "R6"
            if require_r6_design_brief
            else "pre-R6"
        ),
        "status": "BLOCKED" if issues else "PASS",
        "page_count": len(pages),
        "interaction_json_count": interaction_count,
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="只读校验 RunS V3.5 S5 effective_content_full.json"
    )
    parser.add_argument(
        "--page-plan",
        type=Path,
        help="显式指定唯一冻结的 S4 page_plan_full.md；省略时兼容同目录旧结构。",
    )
    parser.add_argument("--visual-mode", default="text_only")
    parser.add_argument("--visual-manifest", type=Path)
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    reports: list[dict[str, Any]] = []
    for path in args.files:
        reports.append(
            validate_effective_content(
                path.resolve(),
                args.page_plan.resolve() if args.page_plan else None,
                args.visual_mode,
                args.visual_manifest.resolve() if args.visual_manifest else None,
            )
        )
    blocked = any(report["status"] == "BLOCKED" for report in reports)
    totals = {
        "lessons": len(reports),
        "pages": sum(int(report["page_count"]) for report in reports),
        "interaction_json": sum(
            int(report["interaction_json_count"]) for report in reports
        ),
        "blocked": sum(report["status"] == "BLOCKED" for report in reports),
    }
    print(
        json.dumps(
            {
                "status": "BLOCKED" if blocked else "PASS",
                "contract": "RunS_V3.5.0-S1-S6-R36-20260731",
                "totals": totals,
                "reports": reports,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
