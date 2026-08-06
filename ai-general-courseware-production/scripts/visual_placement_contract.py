"""Deterministic visual placement and minimal presentation contracts."""

from __future__ import annotations

from copy import deepcopy

from page_type_contract import canonical_page_type


VISUAL_PRESENTATION = {
    "sizeRole": "primary_content_image",
    "widthPolicy": "content_width",
    "heightPolicy": "natural_ratio",
    "objectFit": "contain",
    "borderRadiusPx": 16,
    "verticalSpacingPx": 16,
    "thumbnailForbidden": True,
    "standaloneCard": False,
    "lightboxRequired": True,
    "groupLayout": "vertical_stack",
    "terminalPlacementForbidden": True,
}


FIXED_COURSEWARE_PAGE_TYPES = {"课程开篇", "场景引入", "课程小结"}
REVIEWED_COURSEWARE_PAGE_TYPES = {"知识讲解", "案例分析", "拓展练习"}


COURSEWARE_PLACEMENTS = {
    "课程开篇": {
        "authority": "page_type_contract",
        "anchorType": "page_type_rule",
        "rule": "course_intro_primary_image",
        "inside": "course_overview",
        "insertBefore": "lesson_chip",
        "replaces": "existing_intro_decorative_image_slot",
        "fallback": "before_course_title",
        "decisionStatus": "final_fixed",
        "terminalPlacementForbidden": True,
    },
    "场景引入": {
        "authority": "page_type_contract",
        "anchorType": "page_type_rule",
        "rule": "scene_context_image",
        "inside": "scene_script_paper",
        "insertAfter": "scene_context_paragraphs",
        "insertBefore": "director_cue",
        "fallback": "before_director_cue",
        "decisionStatus": "final_fixed",
        "terminalPlacementForbidden": True,
    },
    "知识讲解": {
        "authority": "page_type_contract",
        "anchorType": "page_type_rule",
        "rule": "knowledge_inline_image",
        "insertAfter": "related_concept_list_or_process",
        "fallback": "after_page_title",
        "decisionStatus": "candidate_only",
        "terminalPlacementForbidden": True,
    },
    "案例分析": {
        "authority": "page_type_contract",
        "anchorType": "page_type_rule",
        "rule": "case_title_image",
        "insertAfter": "page_title",
        "fallback": "after_page_title",
        "decisionStatus": "candidate_only",
        "terminalPlacementForbidden": True,
    },
    "课程小结": {
        "authority": "page_type_contract",
        "anchorType": "page_type_rule",
        "rule": "summary_card_image",
        "inside": "summary_card",
        "insertAfter": "summary_title",
        "insertBefore": "summary_body",
        "fallback": "before_summary_body",
        "decisionStatus": "final_fixed",
        "terminalPlacementForbidden": True,
    },
    "拓展练习": {
        "authority": "page_type_contract",
        "anchorType": "page_type_rule",
        "rule": "extension_contextual_image",
        "insertAfter": "story_sequence_or_task_goal",
        "insertBefore": "prompt_instructions",
        "fallback": "after_first_text_block",
        "decisionStatus": "candidate_only",
        "terminalPlacementForbidden": True,
    },
}


def lesson_plan_render_placement(before_text: str, after_text: str) -> dict[str, object]:
    return {
        "authority": "teacher_visual_script",
        "anchorType": "teacher_source_anchor",
        "insertAfterText": before_text,
        "insertBeforeText": after_text,
        "fallback": "none",
    }


def courseware_render_placement(page_type: str) -> dict[str, object]:
    canonical = canonical_page_type(page_type)
    if canonical == "互动题目":
        raise ValueError("EXTERNAL_RETURN_INTERACTION_IMAGE_FORBIDDEN")
    placement = COURSEWARE_PLACEMENTS.get(canonical)
    if placement is None:
        raise ValueError("VISUAL_PAGE_TYPE_PLACEMENT_UNSUPPORTED")
    return deepcopy(placement)


def courseware_page_requires_review(page_type: str) -> bool:
    canonical = canonical_page_type(page_type)
    if canonical in FIXED_COURSEWARE_PAGE_TYPES:
        return False
    if canonical in REVIEWED_COURSEWARE_PAGE_TYPES:
        return True
    if canonical == "互动题目":
        raise ValueError("EXTERNAL_RETURN_INTERACTION_IMAGE_FORBIDDEN")
    raise ValueError("VISUAL_PAGE_TYPE_PLACEMENT_UNSUPPORTED")


def visual_presentation() -> dict[str, object]:
    return deepcopy(VISUAL_PRESENTATION)
