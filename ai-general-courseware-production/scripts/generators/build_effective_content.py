#!/usr/bin/env python3
"""Build every protected S5 projection directly from frozen S4."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any


CONTRACT = "RunS_V3.5.0-S1-S6-R36-20260731"
SCRIPT_ROOT = Path(__file__).resolve().parents[1]
VALIDATORS = SCRIPT_ROOT / "validators"
sys.path.insert(0, str(SCRIPT_ROOT))
sys.path.insert(0, str(VALIDATORS))

from page_type_contract import (  # noqa: E402
    POST_CLASS_CANONICAL_PAGE_TYPE,
    canonical_capsule,
    canonical_page_type,
)

from validate_v35_page_plan_question_boundaries import (  # noqa: E402
    JSON_FENCE_RE,
    parse_pages,
)
from validate_v35_effective_content import (  # noqa: E402
    NON_EFFECTIVE_STATUS_RE,
    ORDERED_PARAGRAPH_RE,
    parse_dynamic_source_blocks,
    source_block_ids,
)


def blocked(code: str) -> "NoReturn":
    raise SystemExit(f"BLOCKED:{code}")


def strip_status(value: str) -> str:
    return NON_EFFECTIVE_STATUS_RE.sub("", value).lstrip()


def project_summary_blocks(raw_markdown: str) -> list[dict[str, Any]]:
    projected: list[dict[str, Any]] = []
    for source_block in parse_dynamic_source_blocks(raw_markdown):
        block = copy.deepcopy(source_block)
        if block.get("type") == "paragraph":
            block["text"] = strip_status(str(block.get("text") or ""))
            block["markdown"] = strip_status(str(block.get("markdown") or ""))
            if not block["text"]:
                continue
        projected.append(block)
    if (
        not projected
        or projected[0].get("type") != "heading"
        or not isinstance(projected[0].get("text"), str)
        or not projected[0]["text"].strip()
    ):
        blocked("COURSE_SUMMARY_TITLE_MISSING")
    return projected


def project_post_class_task(raw_markdown: str) -> tuple[str, list[dict[str, Any]]]:
    """Compile a task page from frozen S4 source in exact block order.

    The task template consumes ``content.taskTitle`` and ``sections``.  Both are
    source-derived execution data, not authoring choices.  Every source block
    after the title becomes exactly one ordered section so S6 never has to
    reconstruct or globally regroup the task body.
    """
    blocks = parse_dynamic_source_blocks(raw_markdown)
    if (
        not blocks
        or blocks[0].get("type") != "heading"
        or not isinstance(blocks[0].get("text"), str)
        or not blocks[0]["text"].strip()
    ):
        blocked("POST_CLASS_TASK_TITLE_MISSING")

    title = blocks[0]["text"].strip()
    projected: list[dict[str, Any]] = []
    first_body = True
    fact_prefix = re.compile(r"^\*\*(.+?)[：:]\*\*\s*(.+)$", re.S)
    step_prefix = re.compile(r"^(?:第?\s*\d+\s*[步格]|步骤\s*\d+|先|然后|接着|最后)")
    fallback_prefix = re.compile(r"^(?:如果|若|暂时|无法|没有合适)")
    body_blocks = blocks[1:]

    def is_checklist_prompt(value: str) -> bool:
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        field_lines = sum(
            1
            for line in lines
            if re.match(r"^[^：:\n]{1,12}[：:]", line)
        )
        return len(lines) >= 3 and field_lines >= 2

    def next_code_text(index: int) -> str:
        if index + 1 >= len(body_blocks):
            return ""
        next_block = body_blocks[index + 1]
        if next_block.get("type") != "code_block":
            return ""
        return str(next_block.get("text") or "")

    review_tokens = ("检查", "核对", "确认", "听一遍", "复核", "填写", "责任卡")
    for block_index, block in enumerate(body_blocks):
        source_markdown = str(block.get("markdown") or "")
        block_type = block.get("type")
        if block_type == "code_block":
            text = str(block.get("text") or "")
            previous = projected[-1] if projected else {}
            previous_text = str(previous.get("text") or "")
            if previous.get("role") == "condition":
                role = "correctivePrompt"
                label = "修正提示词"
            elif is_checklist_prompt(text):
                role = "checklist"
                label = "责任卡" if "责任卡" in previous_text else "检查清单"
            else:
                role = "prompt"
                label = "提示词"
            projected.append(
                {
                    "type": "prompt",
                    "role": role,
                    "label": label,
                    "text": text,
                    "sourceMarkdown": source_markdown,
                }
            )
            first_body = False
            continue
        if block_type in {"ordered_list", "unordered_list"}:
            projected.append(
                {
                    "type": "facts",
                    "role": "preflight",
                    "label": "任务要点",
                    "items": list(block.get("items") or []),
                    "sourceMarkdown": source_markdown,
                }
            )
            first_body = False
            continue

        text = str(block.get("text") or source_markdown)
        following_code = next_code_text(block_index)
        fact_match = fact_prefix.fullmatch(text)
        if fact_match:
            projected.append(
                {
                    "type": "facts",
                    "role": "preflight",
                    "label": fact_match.group(1).strip(),
                    "text": fact_match.group(2).strip(),
                    "sourceMarkdown": source_markdown,
                }
            )
        elif first_body:
            projected.append(
                {
                    "type": "task",
                    "role": "lead",
                    "label": "任务",
                    "text": text,
                    "sourceMarkdown": source_markdown,
                }
            )
        elif step_prefix.search(text):
            projected.append(
                {
                    "type": "step",
                    "role": "action",
                    "text": text,
                    "sourceMarkdown": source_markdown,
                }
            )
        elif fallback_prefix.search(text) and following_code:
            projected.append(
                {
                    "type": "fallback",
                    "role": "condition",
                    "text": text,
                    "sourceMarkdown": source_markdown,
                }
            )
        elif "检查" in text and any(token in text for token in ("决定", "确认", "是否")):
            projected.append(
                {
                    "type": "decision",
                    "role": "decision",
                    "text": text,
                    "sourceMarkdown": source_markdown,
                }
            )
        elif any(
            token in text
            for token in ("安全", "隐私", "不得", "不要上传", "不上传", "不模仿")
        ):
            projected.append(
                {
                    "type": "safety",
                    "role": "safetyFallback",
                    "text": text,
                    "sourceMarkdown": source_markdown,
                }
            )
        elif following_code and any(token in text for token in review_tokens):
            projected.append(
                {
                    "type": "paragraph",
                    "role": "review",
                    "text": text,
                    "sourceMarkdown": source_markdown,
                }
            )
        elif following_code:
            projected.append(
                {
                    "type": "paragraph",
                    "role": "action",
                    "text": text,
                    "sourceMarkdown": source_markdown,
                }
            )
        elif fallback_prefix.search(text):
            projected.append(
                {
                    "type": "fallback",
                    "role": "fallback",
                    "text": text,
                    "sourceMarkdown": source_markdown,
                }
            )
        elif any(token in text for token in review_tokens):
            projected.append(
                {
                    "type": "paragraph",
                    "role": "review",
                    "text": text,
                    "sourceMarkdown": source_markdown,
                }
            )
        else:
            projected.append(
                {
                    "type": "paragraph",
                    "role": "note",
                    "text": text,
                    "sourceMarkdown": source_markdown,
                }
            )
        first_body = False

    if not projected:
        blocked("POST_CLASS_TASK_BODY_MISSING")
    return title, projected


def summary_content_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        if block.get("type") == "paragraph" and ORDERED_PARAGRAPH_RE.match(
            str(block.get("text") or "")
        ):
            numbered: list[str] = []
            while index < len(blocks):
                numbered_block = blocks[index]
                text = numbered_block.get("text") if isinstance(numbered_block, dict) else None
                if (
                    numbered_block.get("type") != "paragraph"
                    or not isinstance(text, str)
                    or not ORDERED_PARAGRAPH_RE.match(text)
                ):
                    break
                numbered.append(text)
                index += 1
            if len(numbered) >= 2:
                result.append(
                    {"type": "orderedList", "items": numbered, "sourceNumbered": True}
                )
            else:
                result.append(block)
            continue
        if block.get("type") == "ordered_list":
            result.append({"type": "orderedList", "items": block.get("items", [])})
        elif block.get("type") == "code_block":
            result.append(
                {
                    "type": "codeBlock",
                    "text": block.get("text", ""),
                    "language": block.get("language", ""),
                }
            )
        else:
            result.append(copy.deepcopy(block))
        index += 1
    return result


COMPARISON_RE = re.compile(r"(?:方案|选项|方法)\s*[A-Za-zＡ-Ｚ0-9一二三四甲乙丙丁]")
PROCESS_RE = re.compile(r"(?:先|首先).{0,80}(?:再|然后|接着|最后|完成.{0,12}后)")
EXAMPLE_RE = re.compile(r"(?:例如|比如|在这个|以.+为例)")
JUDGMENT_RE = re.compile(r"(?:关键是|仍要由人判断|最终是否|因此|所以|结论)")
ROLE_DISTRIBUTION_RE = re.compile(r"(?:文字|图片|图像|声音|音频).{0,40}负责")
QUOTED_TEXT_RE = re.compile(r"“([^”]+)”|\"([^\"]+)\"")
TIME_TEXT_RE = re.compile(r"\d{1,2}:\d{2}")

SURFACE_POLICY = {
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
COLOR_ROLES = {
    "primaryEmphasis": "runs_purple_inline",
    "conflictEvidence": "warm_amber_inline",
    "supportingInformation": "cool_blue_tint",
    "conclusionSurface": "light_purple_tint",
    "bodyText": "dark_neutral",
    "inlineHighlightOnly": True,
}
SPACE_BALANCE = {
    "readingAreaTarget": "60_to_75_percent",
    "maximumUnusedLowerAreaPercent": 12,
    "forbidTopHeavyComposition": True,
}
ALIGNMENT_POLICY = {
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
COMPARISON_LAYOUT_POLICY = {
    "sideBySideAllowed": True,
    "sideBySideMaxCharsPerPeer": 80,
    "sideBySideMaxCombinedChars": 150,
    "withinLimitLayout": "aligned_equal_width_columns",
    "overLimitLayout": "vertical_full_width_stack",
    "verticalStackSharedLeftEdge": True,
}
HIGHLIGHT_POLICY = {
    "maximumSegmentsPerPage": 3,
    "sameSemanticCategoryUsesSameStyle": True,
    "shortHighlightNoWrapMaxChars": 12,
    "shortHighlightMoveWholeToNextLine": True,
    "forbidOrphanTailCharsMax": 2,
    "forbid": ["multicolorSameCategory", "oneOrTwoCharacterHighlightedTail"],
}
GROUP_PRESENTATION = {
    "intro": ("open_reading_band", "open_background", "supporting"),
    "context": ("open_body_flow", "open_background", "normal"),
    "comparison": ("aligned_comparison", "split_soft_tints", "primary"),
    "process": ("left_aligned_process", "outlined_light_surface", "primary"),
    "example": ("role_distribution_cluster", "mixed_light_tints", "primary"),
    "judgment": ("soft_conclusion_anchor", "light_accent_tint", "primary"),
}


def _reading_text(block: dict[str, Any]) -> str:
    if isinstance(block.get("text"), str):
        return block["text"]
    items = block.get("items")
    return "".join(item for item in items if isinstance(item, str)) if isinstance(items, list) else ""


def _semantic_role(text: str, index: int) -> str:
    if COMPARISON_RE.search(text) and (
        index > 1
        or re.search(r"(?:方案|选项|方法)\s*[A-Za-zＡ-Ｚ0-9一二三四甲乙丙丁]中", text)
        or "两个方案" in text
    ):
        return "comparison"
    quoted = [left or right for left, right in QUOTED_TEXT_RE.findall(text)]
    if (
        len(quoted) >= 2
        and len({TIME_TEXT_RE.search(value).group(0) for value in quoted if TIME_TEXT_RE.search(value)}) >= 2
        and any(token in text for token in ("文字", "图片", "图像"))
        and any(token in text for token in ("语音", "声音", "音频"))
    ):
        return "comparison"
    if PROCESS_RE.search(text):
        return "process"
    if ROLE_DISTRIBUTION_RE.search(text) or EXAMPLE_RE.search(text):
        return "example"
    if JUDGMENT_RE.search(text):
        return "judgment"
    return "intro" if index == 1 else "context"


def _layout_archetype(roles: list[str], short_page: bool) -> str:
    if short_page:
        return "two_layer_open_reading"
    role_set = set(roles)
    if "comparison" in role_set and "process" in role_set:
        return "evidence_comparison_then_resolution"
    if "comparison" in role_set:
        return "aligned_evidence_comparison"
    if "process" in role_set and "example" in role_set:
        return "guided_process_with_role_distribution"
    if "process" in role_set:
        return "left_aligned_process"
    if "example" in role_set:
        return "role_distribution_with_judgment"
    if "judgment" in role_set:
        return "open_explanation_with_light_anchor"
    return "open_explanation"


def _group_presentation(
    groups: list[dict[str, Any]], reading_blocks: list[dict[str, Any]]
) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for group in groups:
        role = str(group.get("role") or "context")
        geometry, surface, weight = GROUP_PRESENTATION.get(
            role, GROUP_PRESENTATION["context"]
        )
        indexes = group.get("blockIndexes") if isinstance(group.get("blockIndexes"), list) else []
        if role == "comparison" and any(
            1 <= index <= len(reading_blocks)
            and _conflict_fragments(_reading_text(reading_blocks[index - 1]))
            for index in indexes
        ):
            geometry = "inline_evidence_comparison"
            surface = "open_with_inline_highlights"
        if role == "example" and any(
            1 <= index <= len(reading_blocks)
            and _role_distribution_highlights(_reading_text(reading_blocks[index - 1]))
            for index in indexes
        ):
            geometry = "inline_role_distribution"
            surface = "open_with_inline_highlights"
        result.append(
            {
                "groupId": str(group.get("id") or ""),
                "geometry": geometry,
                "surfaceRole": surface,
                "visualWeight": weight,
            }
        )
    return result


def _group_id_for_block(groups: list[dict[str, Any]], block_index: int) -> str:
    for group in groups:
        indexes = group.get("blockIndexes")
        if isinstance(indexes, list) and block_index in indexes:
            return str(group.get("id") or "open_region")
    return "open_region"


def _conflict_fragments(text: str) -> list[dict[str, str]] | None:
    matches = list(QUOTED_TEXT_RE.finditer(text))
    quoted = [next(value for value in match.groups() if value is not None) for match in matches]
    times = [TIME_TEXT_RE.search(value) for value in quoted]
    if (
        len(matches) < 2
        or len({match.group(0) for match in times if match}) < 2
        or not any(token in text for token in ("文字", "图片", "图像"))
        or not any(token in text for token in ("语音", "声音", "音频"))
    ):
        return None
    first, second = matches[:2]
    between = text[first.end() : second.start()]
    attribution_matches = list(
        re.finditer(r"(?:语音|声音|音频).{0,6}(?:却?说|显示|写着)", between)
    )
    second_unit_start = (
        first.end() + attribution_matches[-1].start()
        if attribution_matches
        else second.start()
    )
    return [
        {"text": text[: first.end()], "region": "inline_evidence_a"},
        {"text": text[first.end() : second_unit_start], "region": "inline_shared_context"},
        {"text": text[second_unit_start:], "region": "inline_evidence_b"},
    ]


def _sentence_fragments(text: str) -> list[dict[str, str]] | None:
    parts = [part for part in re.findall(r".+?[。！？!?](?=.|$)|.+$", text) if part]
    if len(parts) < 2 or "".join(parts) != text:
        return None
    return [
        {"text": part, "region": f"step_{index}"}
        for index, part in enumerate(parts, start=1)
    ]


def _role_distribution_highlights(text: str) -> list[dict[str, str]] | None:
    media_tokens = ("文字", "图片", "图像", "声音", "音频")
    targets: list[dict[str, str]] = []
    for match in re.finditer(r"[^，。！？；,!?;]+[，。！？；,!?;]?", text):
        clause = match.group(0)
        exact = clause.rstrip("，。！？；,!?;")
        token = next((item for item in media_tokens if exact.startswith(item)), None)
        if not token or not exact:
            continue
        targets.append(
            {
                "exactText": exact,
                "colorRole": f"media_{token}",
            }
        )
    return targets if len(targets) >= 2 else None


def _role_for_block(groups: list[dict[str, Any]], block_index: int) -> str:
    for group in groups:
        indexes = group.get("blockIndexes")
        if isinstance(indexes, list) and block_index in indexes:
            return str(group.get("role") or "context")
    return "context"


def _source_projection_plan(
    reading_blocks: list[dict[str, Any]], groups: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []
    for block_index, block in enumerate(reading_blocks, start=1):
        text = _reading_text(block)
        fragments = _conflict_fragments(text)
        if fragments:
            plan.append(
                {
                    "blockIndex": block_index,
                    "mode": "inline_conflict_evidence",
                    "renderMode": "continuous_inline_flow",
                    "fragments": fragments,
                    "concatenatedTextMustEqualSource": True,
                }
            )
        elif _role_for_block(groups, block_index) == "process" and (fragments := _sentence_fragments(text)):
            plan.append(
                {
                    "blockIndex": block_index,
                    "mode": "sentence_sequence",
                    "renderMode": "single_section_flat_steps",
                    "fragments": fragments,
                    "concatenatedTextMustEqualSource": True,
                }
            )
        elif _role_for_block(groups, block_index) == "example" and (targets := _role_distribution_highlights(text)):
            plan.append(
                {
                    "blockIndex": block_index,
                    "mode": "role_distribution_inline",
                    "renderMode": "continuous_inline_highlights",
                    "highlightTargets": targets,
                    "preserveSourceAsSingleTextFlow": True,
                }
            )
        else:
            plan.append(
                {
                    "blockIndex": block_index,
                    "mode": "single_region",
                    "region": _group_id_for_block(groups, block_index),
                }
            )
    return plan


def _emphasis_targets(
    reading_blocks: list[dict[str, Any]], maximum: int = 3
) -> list[dict[str, Any]]:
    if maximum <= 0:
        return []
    targets: list[dict[str, Any]] = []
    for block_index, block in enumerate(reading_blocks, start=1):
        text = _reading_text(block)
        fragments = _conflict_fragments(text)
        if fragments:
            for match, color_role in zip(QUOTED_TEXT_RE.finditer(text), ("conflict_a", "conflict_b")):
                targets.append(
                    {
                        "blockIndex": block_index,
                        "exactText": next(value for value in match.groups() if value is not None),
                        "colorRole": color_role,
                    }
                )
    # Select only source-derived semantic markers.  Course-specific phrases
    # must never become a hidden cross-course design template.
    existing = {row["exactText"] for row in targets}
    for block_index, block in enumerate(reading_blocks, start=1):
        if len(targets) >= maximum:
            break
        text = _reading_text(block)
        role = _semantic_role(text, block_index)
        if role == "judgment":
            match = JUDGMENT_RE.search(text)
            candidates = [(match.group(0), "judgment")] if match else []
        elif role == "comparison":
            candidates = [
                (match.group(0), "comparison")
                for match in COMPARISON_RE.finditer(text)
            ]
        else:
            candidates = []
        for exact_text, color_role in candidates:
            if len(targets) >= maximum:
                break
            if not exact_text or exact_text in existing:
                continue
            targets.append(
                {
                    "blockIndex": block_index,
                    "exactText": exact_text,
                    "colorRole": color_role,
                }
            )
            existing.add(exact_text)
    return targets[:maximum]


def _is_two_layer_reading(reading_blocks: list[dict[str, Any]]) -> bool:
    """Detect the bounded two-short-block composition without a draft seed."""
    if len(reading_blocks) != 2:
        return False
    if any(block.get("type") in {"ordered_list", "unordered_list", "code_block"} for block in reading_blocks):
        return False
    lengths = [len(_reading_text(block).strip()) for block in reading_blocks]
    return all(0 < length <= 120 for length in lengths) and sum(lengths) <= 200


def normalize_dynamic_design_brief(
    blocks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Derive executable design relationships only from frozen source blocks."""
    brief: dict[str, Any] = {}
    reading_blocks = [block for block in blocks if block.get("type") != "heading"]
    brief["nonRenderable"] = True
    brief["teachingAction"] = (
        "按冻结原文的真实顺序组织阅读，并突出其中已有的概念、关系或判断。"
    )
    reading_chars = sum(len(_reading_text(block)) for block in reading_blocks)
    if len(reading_blocks) >= 6 or reading_chars >= 520:
        density = "dense"
    elif len(reading_blocks) >= 5 or (len(reading_blocks) >= 3 and reading_chars >= 120):
        density = "medium"
    else:
        density = "light"
    brief["density"] = density

    roles = [_semantic_role(_reading_text(block), index) for index, block in enumerate(reading_blocks, start=1)]
    groups: list[dict[str, Any]] = []
    id_counts: dict[str, int] = {}
    for index, role in enumerate(roles, start=1):
        if groups and groups[-1]["role"] == role:
            groups[-1]["blockIndexes"].append(index)
            continue
        id_counts[role] = id_counts.get(role, 0) + 1
        group_id = role if id_counts[role] == 1 else f"{role}_{id_counts[role]}"
        groups.append({
            "id": group_id,
            "role": role,
            "blockIndexes": [index],
            "purpose": {
                "intro": "承接冻结原文的引入信息",
                "context": "承接冻结原文的背景或说明",
                "comparison": "并列呈现冻结原文中的对比对象",
                "process": "呈现冻结原文中的步骤或先后关系",
                "example": "呈现冻结原文中的实例或媒介分工",
                "judgment": "突出冻结原文中的判断或边界",
            }[role],
        })

    short_page = _is_two_layer_reading(reading_blocks)
    if short_page:
        brief["shortPageComposition"] = "two_layer_reading"
        brief["semanticGroups"] = [
            {
                "id": "primary_reading" if index == 1 else "supporting_result",
                "role": "intro" if index == 1 else "context",
                "blockIndexes": [index],
                "purpose": "主阅读层" if index == 1 else "弱结果层",
            }
            for index in range(1, 3)
        ]
        brief["hierarchyFocus"] = ["primary_reading", "supporting_result"]
        brief["contentShape"] = "continuous_explanation"
        brief["rhythmRole"] = "narrative"
        brief["readingFlow"] = ["按原序阅读主阅读层", "按原序阅读弱结果层"]
        brief["layoutFreedom"] = "仅用无文字留白组织两条短原文；不得补写连接、步骤或结论。"
    elif groups:
        brief["semanticGroups"] = groups
        brief["hierarchyFocus"] = [group["id"] for group in groups if group["role"] != "context"] or [groups[0]["id"]]
        if "comparison" in roles:
            brief["contentShape"] = "parallel_comparison"
            brief["rhythmRole"] = "contrast"
            relation = "对比"
        elif "process" in roles:
            brief["contentShape"] = "process_or_sequence"
            brief["rhythmRole"] = "structured"
            relation = "步骤、实例与判断"
        else:
            brief["contentShape"] = "claim_to_evidence_to_judgment"
            brief["rhythmRole"] = "statement"
            relation = "引入、实例与判断"
        brief["readingFlow"] = [
            "按冻结原文顺序进入本页主题",
            f"用真实语义分组表达{relation}关系",
            "以冻结原文的结尾内容完成收束",
        ]
        brief["layoutFreedom"] = f"必须把冻结原文中的{relation}关系转化为不同阅读重量和空间组织；不得退化为等宽、等色、等间距的段落卡堆叠。"
    active_groups = brief.get("semanticGroups") if isinstance(brief.get("semanticGroups"), list) else groups
    active_roles = [str(group.get("role") or "context") for group in active_groups if isinstance(group, dict)]
    brief["layoutArchetype"] = _layout_archetype(active_roles or roles, short_page)
    if any(_conflict_fragments(_reading_text(block)) for block in reading_blocks):
        brief["layoutArchetype"] = "inline_evidence_then_resolution"
    brief["groupPresentation"] = _group_presentation(active_groups, reading_blocks)
    brief["sourceProjectionPlan"] = _source_projection_plan(reading_blocks, active_groups)
    relation_highlights = sum(
        len(row.get("highlightTargets", []))
        for row in brief["sourceProjectionPlan"]
        if isinstance(row, dict) and isinstance(row.get("highlightTargets"), list)
    )
    brief["emphasisTargets"] = _emphasis_targets(
        reading_blocks,
        max(0, HIGHLIGHT_POLICY["maximumSegmentsPerPage"] - relation_highlights),
    )
    brief["surfacePolicy"] = copy.deepcopy(SURFACE_POLICY)
    brief["colorRoles"] = copy.deepcopy(COLOR_ROLES)
    brief["spaceBalance"] = copy.deepcopy(SPACE_BALANCE)
    brief["alignmentPolicy"] = copy.deepcopy(ALIGNMENT_POLICY)
    brief["comparisonLayoutPolicy"] = copy.deepcopy(COMPARISON_LAYOUT_POLICY)
    brief["highlightPolicy"] = copy.deepcopy(HIGHLIGHT_POLICY)
    brief["visualSystem"] = (
        "浅色主导的RunS紫蓝系统；开放正文与柔和表面形成层级；"
        "非代码内容禁止大面积近黑背景；重点只在原句原位置使用语义色标记。"
    )
    brief["visibleCopyPolicy"] = (
        "学生可见文字只来自冻结effective_content；按sourceProjectionPlan逐块单次投影，"
        "emphasisTargets仅在原句原位置标色，不抽取、不复制、不改写。"
    )
    return brief


def split_knowledge_points(raw_value: str) -> list[str]:
    """Project the verbatim field into ordered items without changing the source."""
    points: list[str] = []
    for value in re.split(r"[;；\n]+", raw_value):
        normalized = re.sub(r"^\s*(?:[-*•]|\d+[.．、)）:：])\s*", "", value).strip()
        if normalized:
            points.append(normalized)
    if not points:
        blocked("COURSE_INTRO_KNOWLEDGE_POINTS_EMPTY")
    return points


def project_course_intro(raw_markdown: str) -> tuple[dict[str, str], dict[str, Any], list[dict[str, Any]]]:
    labels = ("课包名称", "单元名称", "课程编号", "课程标题", "课程目标", "知识点")
    values: dict[str, str] = {}
    label_union = "|".join(map(re.escape, labels))
    for label in labels:
        match = re.search(
            rf"(?:^|\n)(?:-\s*)?{re.escape(label)}：\s*(.*?)"
            rf"(?=\n(?:-\s*)?(?:{label_union})：|\Z)",
            raw_markdown,
            re.S,
        )
        if not match:
            blocked("COURSE_INTRO_SIX_FIELDS_MISSING")
        values[label] = match.group(1).strip()
    lesson_match = re.search(r"第\s*(\d+)\s*课", values["课程编号"])
    if not lesson_match:
        blocked("COURSE_INTRO_LESSON_NUMBER_INVALID")
    knowledge_points = split_knowledge_points(values["知识点"])
    content = {
        "packageName": values["课包名称"],
        "unitName": values["单元名称"],
        "lessonNumber": int(lesson_match.group(1)),
        "courseName": values["课程标题"],
        "courseIntroduction": values["课程目标"],
        "knowledgePoints": knowledge_points,
    }
    sections = []
    for label in labels:
        section = {"type": "course_info", "label": label, "text": values[label]}
        if label == "知识点":
            section["items"] = copy.deepcopy(knowledge_points)
        sections.append(section)
    return values, content, sections


def protected_page(plan: dict[str, str]) -> dict[str, Any]:
    page: dict[str, Any] = {}
    source_page_type = plan["page_type"]
    page_type = canonical_page_type(source_page_type)
    page.update(
        {
            "page_no": plan["page_no"],
            "page_type": page_type,
            "capsule": canonical_capsule(source_page_type, plan["capsule"]),
            "page_action": plan["action"],
            "source_block_ids": source_block_ids(plan["source_block"]),
        }
    )
    if page_type == "互动题目":
        match = JSON_FENCE_RE.fullmatch(plan["body"])
        if not match:
            blocked("S4_INTERACTION_JSON_INVALID")
        try:
            component = json.loads(match.group("json"))
        except json.JSONDecodeError:
            blocked("S4_INTERACTION_JSON_INVALID")
        page["effective_content"] = component
        page["component_type"] = component.get("type")
        page["layout_plan"] = {"layout": "question"}
        return page

    raw_markdown = plan["body"]
    page["source"] = {"rawMarkdown": raw_markdown}
    if page_type == "课程开篇":
        effective, content, sections = project_course_intro(raw_markdown)
        page["effective_content"] = effective
        page["content"] = content
        page["sections"] = sections
        page["display_hints"] = {"layout": "course_intro"}
    elif page_type in {"场景引入", "知识讲解", "案例分析"}:
        blocks = parse_dynamic_source_blocks(raw_markdown)
        page["effective_content"] = {"blocks": blocks}
        page["content"] = {"blocks": copy.deepcopy(blocks)}
        page["sections"] = copy.deepcopy(blocks)
        page["display_hints"] = {"layout": "reading"}
        if page_type in {"知识讲解", "案例分析"}:
            page["design_brief"] = normalize_dynamic_design_brief(blocks)
    elif page_type == "课程小结":
        blocks = project_summary_blocks(raw_markdown)
        page["effective_content"] = {"blocks": copy.deepcopy(blocks)}
        page["content"] = {"contentBlocks": summary_content_blocks(blocks)}
        page["sections"] = copy.deepcopy(blocks)
        page.setdefault("display_hints", {"layout": "reading"})
    elif page_type == POST_CLASS_CANONICAL_PAGE_TYPE:
        title, sections = project_post_class_task(raw_markdown)
        page["effective_content"] = {"text": POST_CLASS_CANONICAL_PAGE_TYPE}
        page["content"] = {"taskTitle": title}
        page["sections"] = sections
        page.setdefault("display_hints", {"layout": "task"})
    return page


def build(
    lesson_id: str,
    page_plan: Path,
) -> dict[str, Any]:
    plans = parse_pages(page_plan.read_text(encoding="utf-8"))
    if not plans:
        blocked("S4_PAGE_PLAN_EMPTY")

    return {
        "lesson_id": lesson_id,
        "sop_version": CONTRACT,
        "source_page_plan": str(page_plan.resolve()),
        "pages": [protected_page(plan) for plan in plans],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="从冻结 S4 确定性生成完整 S5 effective_content_full.json"
    )
    parser.add_argument("--lesson-id", required=True)
    parser.add_argument("--page-plan", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = build(
        args.lesson_id,
        args.page_plan.resolve(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
