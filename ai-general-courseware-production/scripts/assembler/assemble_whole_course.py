#!/usr/bin/env python3
"""Deterministically assemble the governed V3.5 S6 model-input JSON.

This is deliberately the sole assembler.  It consumes only frozen S5 and the
registered OneShot/Demo assets; it never invents student content or uses an
old whole-course JSON as input.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from page_type_contract import (  # noqa: E402
    POST_CLASS_CANONICAL_PAGE_TYPE,
    canonical_capsule,
    canonical_page_type,
)

ONESHOTS = ROOT / "templates" / "oneshots"
TASK_DEMO = ROOT / "templates" / "demos" / "post_class_task_demo.html"
VISUAL_DEMOS = ROOT / "templates" / "demos" / "visual_enhanced"
OUTER_ONESHOT = ONESHOTS / "02_整课JSON_完整外层OneShot.md"
TASK_CONTRACT = "RunS-PostClassTask-Compact-Direct-OneShot-Contract-v1.11-20260805"
TASK_ASSET_SHA256 = "79d9a7fdad4701c784a9e0e6cfbbbdfaeb727211ce26b8eda7e9a5e46effba98"
SOP_CONTRACT_VERSION = "RunS_V3.5.0-S1-S6-R36-20260731"
PROMPT_VERSION_PLACEHOLDER = "__PROMPT_VERSION__"
PROMPT_VERSION_SUFFIX = "R36-20260731"

FIXED = {
    "课程开篇": ("course_intro", "05_课程开篇页_固定模板OneShot.md", "COURSE_INTRO_VARIABLES", "RunS-CourseIntro-FixedTemplate-OneShot-v1.9", "9cf6b757e7bc635189c89d585ea65b54efbc6605c57d061726d0aac45ca6b1b8", "48b56b0fcb700da149078b7ef95b412081bb14937334a31ef24d375d79045090", "2ad388fffc2fea884354b32429cf648ffc189cd39402c5c849b190636f463012"),
    "场景引入": ("scene_intro", "06_场景引入页_固定模板OneShot.md", "SCENE_INTRO_VARIABLES", "RunS-SceneIntro-FixedTemplate-OneShot-v1.6", "e4c2ce909288b84c2fa3ab72a273e5b0f2979c0b149a0eed233a9d6c86fa67e9", "a5134a0e4dd526eca584009e0430372015a8fe9c0200bbbcbdc7b9772dd2876d", "8315cf8d264b68a93e58a8d5f07c639f2a698dbfe626953e8033dddb7b9578fc"),
    "课程小结": ("course_summary", "04_课程小结页_固定模板OneShot.md", "COURSE_SUMMARY_VARIABLES", "RunS-CourseSummary-FixedTemplate-OneShot-v1.11", "95f033f32583035fb846732e9092d868ede638a8aa837c9fd41bf20d1aaee142", "52310103bf4db235c39b94f1393b6a1f8436a32794b4b42aee1580d44ee51d8c", "80570336e03205383a7a296d07b00e57d15e745b7f53f90ac6660d9221efa356"),
}
DYNAMIC = {
    "知识讲解": ("knowledge_explanation", "07_知识讲解页_动态生成OneShot.md", "RunS-Knowledge-Dynamic-OneShot-v1.19", "71ec5e5f3aefeb37c03102eb86a04f13e7177a21fb69b27006966fe0c4576fc1"),
    "案例分析": ("case_analysis", "08_案例分析页_动态生成OneShot.md", "RunS-CaseAnalysis-Dynamic-OneShot-v1.18", "35ee30c45d3b7757b771c785039c6888584b12e3fa66fd7ed9a9c1184305f433"),
}
VISUAL_FIXED = {
    "课程开篇": ("course_intro", "09_课程开篇页_配图增强OneShot.md", "COURSE_INTRO_VARIABLES", "RunS-CourseIntro-VisualEnhanced-OneShot-v1.1", "27fad071461415610848acfbf0c82a0c81ad5f25772f7c4c91669845925637fc", "2e99eb9d7b4374d8ba8d0309df157ef43d4f68c40e0a9c35e7fce52c1bfc75d1", "6b2482e401f36e8178e5d38861e8ada2dd1ae26cd0253de13e23ee9a16e8c1e9"),
    "场景引入": ("scene_intro", "10_场景引入页_配图增强OneShot.md", "SCENE_INTRO_VARIABLES", "RunS-SceneIntro-VisualEnhanced-OneShot-v1.1", "ec635077f50001a342b1113966ba7d3a9b8603ea53b6bc5bf9cdf8a3090fcc2e", "e48c478b2c952b59e8d1a6f320ac7ec9efe4aaa51ae6da15abc90fa34fffe3b3", "03861baad2455a482d77820464ee3d85a937efe2fca85c89ace6d4f2d5d56447"),
    "课程小结": ("course_summary", "13_课程小结页_配图增强OneShot.md", "COURSE_SUMMARY_VARIABLES", "RunS-CourseSummary-VisualEnhanced-OneShot-v1.1", "a28f94cde053f681f06787190f4d299abb8f253880846a4ccb708c2ecf7f5a8d", "08a4d61d14e6669019b1dc64c7c2a8e0fcc0ea770d8ebcb581273fd440fe56e0", "5d8297a61af841da5e943e71ed246434083edf21dd66c4dbf16166a944e07502"),
}
VISUAL_DYNAMIC = {
    "知识讲解": ("knowledge_explanation", "11_知识讲解页_配图增强OneShot.md", "RunS-Knowledge-VisualEnhanced-OneShot-v1.2", "4f8662b08570ec69ec77eb43c5598f04882fd5a378ee096a1079cc1a2b78d3f7"),
    "案例分析": ("case_analysis", "12_案例分析页_配图增强OneShot.md", "RunS-CaseAnalysis-VisualEnhanced-OneShot-v1.2", "ddee8287fa0c930ab4733150f275f872d1fc859ed050fc462a8729e675244b7b"),
}
VISUAL_TASK_CONTRACT = "RunS-PostClassTask-VisualEnhanced-OneShot-v1.1"
VISUAL_TASK_ASSET_SHA256 = "c9f78ed240270a0b6ecfa457a5c5cba6673d4d8e6cd82d3a5e30f2b895cd3e02"
WEBVIEW_COMPATIBILITY_CONTRACT = {
    "baseline": "Android System WebView Chrome 68",
    "untranspiledSource": True,
    "modernFeaturesEnhancementOnly": True,
    "forbidJavaScriptSyntax": ["nullishCoalescing", "optionalChaining", "logicalAssignment", "classFields", "topLevelAwait"],
    "forbidDomApis": ["replaceChildren", "toggleAttribute", "queueMicrotask", "structuredClone", "crypto.randomUUID"],
    "forbidCssFeatures": ["minFunction", "maxFunction", "clampFunction", "dynamicViewportUnits", "aspectRatio", "insetShorthand", "flexGap", "textWrap", "backdropFilter", "logicalProperties", "modernColorFunctions"],
    "requiredFallbacks": ["height100Percent", "physicalSpacingProperties", "widthPlusMaxWidth", "guardedObservers", "visibleStaticFirstScreen"],
}

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def text_block(filename):
    match = re.search(r"```text\n(.*?)\n```", (ONESHOTS / filename).read_text(encoding="utf-8"), re.S)
    if not match:
        raise ValueError(f"ONESHOT_CODE_BLOCK_MISSING:{filename}")
    return match.group(1)

def prompt_version(contract, asset_sha256, prompt_sha256, lesson_id, page_no):
    return (
        f"{contract}-asset-{asset_sha256[:12]}-prompt-{prompt_sha256[:12]}-"
        f"{lesson_id}-{page_no}-{PROMPT_VERSION_SUFFIX}"
    )

def normalize_prompt_version(prompt):
    normalized, count = re.subn(
        r"提示词版本号：[^\n]+",
        f"提示词版本号：{PROMPT_VERSION_PLACEHOLDER}",
        prompt,
        count=1,
    )
    if count != 1:
        raise ValueError("PROMPT_VERSION_LINE_MISSING")
    return normalized

def finalize_prompt_version(prompt, contract, asset_sha256, lesson_id, page_no):
    normalized = normalize_prompt_version(prompt)
    prompt_sha256 = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    version = prompt_version(
        contract, asset_sha256, prompt_sha256, lesson_id, page_no
    )
    finalized = normalized.replace(PROMPT_VERSION_PLACEHOLDER, version, 1)
    return finalized, version, prompt_sha256

def rebind_page_context(prompt, context):
    line = (
        f"适用页面：{context['lesson_id']}｜{context['page_no']}｜"
        f"第 {context['page_index']}/{context['page_count']} 页｜{context['page_label']}页。"
    )
    prompt, count = re.subn(r"适用页面：[^\n]+", line, prompt, count=1)
    if count != 1:
        raise ValueError("PROMPT_PAGE_CONTEXT_NOT_FOUND")
    return prompt

def prompt_from_asset(filename, variable, values, context, visual_values=None):
    prompt = text_block(filename)
    prompt = rebind_page_context(prompt, context)
    replacement = f"const {variable} = Object.freeze({canonical(values)});"
    prompt, count = re.subn(rf"const\s+{variable}\s*=\s*Object\.freeze\(\{{.*?\}}\);", lambda _: replacement, prompt, count=1, flags=re.S)
    if count != 1:
        raise ValueError(f"VARIABLE_REGION_NOT_FOUND:{variable}")
    if visual_values is not None:
        visual_replacement = f"const VISUAL_DATA = Object.freeze({canonical(visual_values)});"
        prompt, visual_count = re.subn(
            r"const\s+VISUAL_DATA\s*=\s*Object\.freeze\(\{.*?\}\);",
            lambda _: visual_replacement,
            prompt,
            count=1,
            flags=re.S,
        )
        if visual_count != 1:
            raise ValueError("VISUAL_DATA_REGION_NOT_FOUND")
    if variable == "COURSE_SUMMARY_VARIABLES":
        page_action = values.get("pageAction")
        if page_action not in {"next", "complete"}:
            raise ValueError("COURSE_SUMMARY_PAGE_ACTION_INVALID")
        static_label = "继续学习" if page_action == "next" else "完成学习"
        prompt, button_count = re.subn(
            r'(<button\b[^>]*\bid="completeButton"[^>]*>).*?(</button>)',
            lambda match: f"{match.group(1)}{static_label}{match.group(2)}",
            prompt,
            count=1,
            flags=re.S,
        )
        prompt, action_count = re.subn(
            r"本实例冻结动作为 (?:next|complete)",
            f"本实例冻结动作为 {page_action}",
            prompt,
            count=1,
        )
        if button_count != 1 or action_count != 1:
            raise ValueError("COURSE_SUMMARY_STATIC_ACTION_REGION_MISSING")
    return prompt


def visual_page_projection(page):
    visual = page.get("visual")
    if not isinstance(visual, dict):
        return {}
    assets = visual.get("assets")
    display_mode = visual.get("displayMode")
    image_type = visual.get("imageType")
    if display_mode not in {"single", "group"} or image_type not in {"lesson_plan_image", "courseware_image"}:
        raise ValueError("S5_VISUAL_CONTRACT_INVALID")
    if not isinstance(assets, list) or not assets or any(not isinstance(asset, dict) for asset in assets):
        raise ValueError("S5_VISUAL_ASSETS_INVALID")
    projected = []
    presentation = visual.get("presentation")
    if not isinstance(presentation, dict) or presentation.get("thumbnailForbidden") is not True:
        raise ValueError("S5_VISUAL_PRESENTATION_INVALID")
    for asset in assets:
        url = asset.get("url")
        alt = asset.get("alt")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError("S5_VISUAL_URL_INVALID")
        if alt is None:
            alt = ""
        if not isinstance(alt, str):
            raise ValueError("S5_VISUAL_ALT_INVALID")
        row = {
            "assetId": asset.get("assetId"),
            "imageType": image_type,
            "url": url,
            "width": asset.get("width"),
            "height": asset.get("height"),
            "alt": alt,
            "placement": copy.deepcopy(asset.get("placement")),
            "visualReview": copy.deepcopy(asset.get("visualReview")),
        }
        if not isinstance(row["placement"], dict):
            raise ValueError("S5_VISUAL_PLACEMENT_INVALID")
        if asset.get("displayLabel") is not None:
            row["displayLabel"] = asset.get("displayLabel")
        if asset.get("order") is not None:
            row["order"] = asset.get("order")
        if asset.get("pairedStudentText") is not None:
            row["pairedStudentText"] = asset.get("pairedStudentText")
        if asset.get("pairedSource") is not None:
            row["pairedSource"] = copy.deepcopy(asset.get("pairedSource"))
        projected.append(row)
    if display_mode == "single":
        if len(projected) != 1:
            raise ValueError("S5_VISUAL_SINGLE_CARDINALITY_INVALID")
        return {"visualAsset": projected[0], "visualPresentation": copy.deepcopy(presentation)}
    if len(projected) < 2:
        raise ValueError("S5_VISUAL_GROUP_CARDINALITY_INVALID")
    return {"planVisualAssets": projected, "visualPresentation": copy.deepcopy(presentation)}

def intro_values(page, action):
    content = page.get("content")
    if not isinstance(content, dict):
        raise ValueError("COURSE_INTRO_CONTENT_MISSING")
    points = content.get("knowledgePoints")
    values = {key: content.get(key) for key in ("packageName", "unitName", "lessonNumber", "courseName", "courseIntroduction")}
    values["knowledgePoints"] = points
    missing = [key for key in ("packageName", "unitName", "courseName", "courseIntroduction") if not isinstance(values[key], str) or not values[key].strip()]
    if not isinstance(values["lessonNumber"], int) or values["lessonNumber"] < 1:
        missing.append("lessonNumber")
    if not isinstance(points, list) or not points or not all(isinstance(x, str) and x.strip() for x in points):
        missing.append("knowledgePoints")
    if missing:
        raise ValueError("COURSE_INTRO_VARIABLES_INVALID:" + ",".join(missing))
    return values

def whole_course_task_title(intro):
    """The import task name is the root title, never a per-page title."""
    lesson_number = intro["lessonNumber"]
    course_name = intro["courseName"].strip()
    return f"第{lesson_number}课｜{course_name}｜{SOP_CONTRACT_VERSION}"

def dynamic_visual_recipe_plan(blocks, design_brief, page_kind):
    """Return non-renderable R36 layout instructions from frozen S5 structure.

    The plan deliberately names *presentation recipes*, not new student copy.
    The page model receives the exact source blocks plus this deterministic
    selection, so it cannot default every semantic group to the same white
    card while S6 remains forbidden from editing S5 content.
    """
    brief = design_brief if isinstance(design_brief, dict) else {}
    groups = brief.get("semanticGroups") if isinstance(brief.get("semanticGroups"), list) else []
    group_ids = [group.get("id") for group in groups if isinstance(group, dict) and isinstance(group.get("id"), str)]
    non_heading = [block for block in blocks if block.get("type") != "heading"]
    ordered_list_indexes = [
        index
        for index, block in enumerate(blocks, start=1)
        if block.get("type") == "ordered_list"
    ]
    unordered_list_indexes = [
        index
        for index, block in enumerate(blocks, start=1)
        if block.get("type") == "unordered_list"
    ]
    presentations = brief.get("groupPresentation") if isinstance(brief.get("groupPresentation"), list) else []
    presentation_recipe = {
        "open_reading_band": "intro_observation_band",
        "open_body_flow": "open_body_flow",
        "aligned_comparison": "comparison_split",
        "inline_evidence_comparison": "inline_conflict_evidence",
        "left_aligned_process": "process_steps",
        "role_distribution_cluster": "role_distribution_inline",
        "inline_role_distribution": "role_distribution_inline",
        "soft_conclusion_anchor": "analysis_conclusion_emphasis",
    }
    recipes = []
    for presentation in presentations:
        if not isinstance(presentation, dict):
            continue
        geometry = presentation.get("geometry")
        recipe = presentation_recipe.get(geometry)
        if not recipe:
            continue
        recipes.append({
            "recipe": recipe,
            "groupId": presentation.get("groupId"),
            "source": "s5_group_presentation",
            "geometry": geometry,
            "visualTreatment": presentation.get("surfaceRole"),
            "visualWeight": presentation.get("visualWeight"),
        })
    executable_design = bool(presentations and brief.get("sourceProjectionPlan"))
    if not recipes and non_heading:
        recipes.append({
            "recipe": "intro_observation_band",
            "groupId": group_ids[0] if group_ids else None,
            "source": "first_real_reading_group",
            "geometry": "wide_shallow_band",
            "visualTreatment": "soft_tinted_band_with_css_accent",
        })
    if ordered_list_indexes or unordered_list_indexes:
        recipes.append({
            "recipe": "list_or_option_compact",
            "blockIndexes": ordered_list_indexes + unordered_list_indexes,
            "source": "frozen_list_blocks",
            "geometry": "compact_item_cluster",
            "visualTreatment": "structured_compact_items",
        })
    blockquote_indexes = [
        index
        for index, block in enumerate(non_heading, start=1)
        if block.get("type") == "blockquote"
    ]
    if blockquote_indexes:
        recipes.append({
            "recipe": "evidence_quote_focus",
            "blockIndexes": blockquote_indexes,
            "source": "frozen_blockquote_evidence",
            "geometry": "warm_evidence_quote_surface",
            "visualTreatment": "warm_alert_contrast",
        })
    comparison_group = next((group.get("id") for group in groups if isinstance(group, dict) and group.get("role") == "comparison"), None)
    process_group = next((group.get("id") for group in groups if isinstance(group, dict) and group.get("role") == "process"), None)
    role_distribution_indexes = [
        index
        for index, block in enumerate(non_heading, start=1)
        if sum(token in str(block.get("text") or "") for token in ("文字", "图片", "图像", "声音", "音频")) >= 2
        and "负责" in str(block.get("text") or "")
    ]
    if comparison_group and not any(row.get("recipe") == "comparison_split" for row in recipes):
        recipes.append({
            "recipe": "comparison_split",
            "groupId": comparison_group,
            "source": "frozen_parallel_comparison",
            "geometry": "aligned_equal_peer_pair",
            "visualTreatment": "split_tone_contrast",
        })
    if (
        process_group or (brief.get("contentShape") == "process_or_sequence" and len(non_heading) >= 3)
    ) and not any(row.get("recipe") == "process_steps" for row in recipes):
        recipes.append({
            "recipe": "process_steps",
            "groupId": process_group or (group_ids[1] if len(group_ids) > 1 else None),
            "source": "frozen_process_relationship",
            "geometry": "left_aligned_step_sequence",
            "visualTreatment": "consistent_aligned_progression",
        })
    if role_distribution_indexes and not any(row.get("recipe") == "role_distribution_inline" for row in recipes):
        recipes.append({
            "recipe": "role_distribution_inline",
            "blockIndexes": role_distribution_indexes,
            "source": "frozen_media_role_relationship",
            "geometry": "continuous_inline_role_flow",
            "visualTreatment": "in_place_typographic_highlights",
        })
    if len(non_heading) >= 2 and not any(row.get("recipe") == "analysis_conclusion_emphasis" for row in recipes):
        recipes.append({
            "recipe": "analysis_conclusion_emphasis",
            "groupId": group_ids[-1] if group_ids else None,
            "source": "last_real_reading_group",
            "geometry": "single_weighted_anchor",
            "visualTreatment": "light_accent_tint",
        })
    # Deduplicate recipe names without changing source ordering.
    seen = set()
    recipes = [recipe for recipe in recipes if not (recipe["recipe"] in seen or seen.add(recipe["recipe"]))]
    medium = (
        page_kind == "knowledge_explanation"
        and brief.get("density") == "medium"
        and len(non_heading) >= 3
        and brief.get("shortPageComposition") != "two_layer_reading"
    )
    ordered_list_ordinal_contract = {
        "required": bool(ordered_list_indexes),
        "source": "items[]",
        "startAt": 1,
        "displayExpression": "itemIndex + 1",
        "forbid": ["contentBlockIndex", "globalCounter", "doubleNumbering"],
    }
    return {
        "nonRenderable": True,
        "recipeContract": "R36_REUSABLE_DYNAMIC_VISUAL_RECIPES",
        "recipes": recipes,
        "mediumReadingAreaBalance": {
            "required": medium,
            "target": "60_to_75_percent_of_available_reading_area",
            "method": "distributed_real_groups_card_density_and_spacing",
            "forbidFillers": True,
        },
        "orderedListOrdinalContract": ordered_list_ordinal_contract,
        "unorderedListPresentationContract": {
            "required": bool(unordered_list_indexes),
            "source": "items[]",
            "preserveExistingLabels": True,
            "forbid": ["numericBadge", "autoOrdinal", "doubleNumbering"],
        },
        "semanticCompositionContract": {
            "required": True,
            "relationshipDriven": True,
            "preserveContinuousExplanation": True,
            "preserveListsAsLists": True,
            "punctuatedClausesUseInlineFlow": True,
            "forbid": [
                "sameWhiteCardStack",
                "positionOnlyDifferentiation",
                "decorationFirstComposition",
                "surfaceCountForRichness",
                "splitContinuousSentenceForVariety",
            ],
        },
        "alignmentContract": copy.deepcopy(brief.get("alignmentPolicy")),
        "comparisonLayoutContract": copy.deepcopy(brief.get("comparisonLayoutPolicy")),
        "highlightContract": copy.deepcopy(brief.get("highlightPolicy")),
        "webViewCompatibilityContract": copy.deepcopy(WEBVIEW_COMPATIBILITY_CONTRACT),
        "sourceTextProjectionContract": {
            "required": True,
            "visibleOccurrencesPerBlock": 1,
            "allowContiguousDomFragments": True,
            "concatenatedTextMustEqualSource": True,
            "forbidFullBlockPlusDerivedFragments": True,
            "forbidParaphrasedLabels": True,
        },
        "visualHierarchyContract": {
            "required": len(non_heading) >= 3 and brief.get("shortPageComposition") != "two_layer_reading",
            "semanticHierarchyFirst": True,
            "priorityOrder": [
                "source_fidelity",
                "semantic_relationship",
                "reading_clarity",
                "typographic_elegance",
                "decoration",
            ],
            "minimumReadingAreaCoveragePercent": 60 if brief.get("density") == "medium" else 45,
            "requireOpenOrNonCardRegion": True,
            "maximumIndependentContentSurfaces": 4,
            "sourceSubstringHighlight": {
                "allowed": True,
                "exactSourceOnly": True,
                "maximumSegments": 3,
                "forbidDuplicateText": True,
                "preferredStyles": ["font_weight", "underline", "soft_background"],
            },
            "decorativeElements": {
                "minimum": 0,
                "maximum": 2,
                "optional": True,
                "cssOnly": True,
                "ariaHidden": True,
                "forbidText": True,
                "forbidGeneratedEmoji": True,
            },
            "forbid": [
                "allWhiteCards",
                "allEqualRadius",
                "allEqualWidthVerticalStack",
                "inventedBadgeCopy",
                "decorationFirstComposition",
                "surfaceCountForRichness",
                "largeUnusedLowerArea",
                "topHeavyComposition",
            ],
        },
        "designExecutionContract": {
            "required": executable_design,
            "source": "S5.design_brief",
            "layoutArchetype": brief.get("layoutArchetype"),
            "groupPresentation": copy.deepcopy(brief.get("groupPresentation")),
            "sourceProjectionPlan": copy.deepcopy(brief.get("sourceProjectionPlan")),
            "emphasisTargets": copy.deepcopy(brief.get("emphasisTargets")),
            "surfacePolicy": copy.deepcopy(brief.get("surfacePolicy")),
            "colorRoles": copy.deepcopy(brief.get("colorRoles")),
            "spaceBalance": copy.deepcopy(brief.get("spaceBalance")),
            "alignmentPolicy": copy.deepcopy(brief.get("alignmentPolicy")),
            "comparisonLayoutPolicy": copy.deepcopy(brief.get("comparisonLayoutPolicy")),
            "highlightPolicy": copy.deepcopy(brief.get("highlightPolicy")),
        },
    }


def dynamic_page_data(page, lesson_id, page_index, page_count, page_kind, action):
    effective = page.get("effective_content")
    blocks = effective.get("blocks") if isinstance(effective, dict) else None
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("DYNAMIC_VISIBLE_BLOCKS_MISSING")
    if any(not isinstance(block, dict) for block in blocks):
        raise ValueError("DYNAMIC_VISIBLE_BLOCK_INVALID")
    # R33 passes the exact S5 structured source blocks through one field.  The
    # OneShot derives student-visible headings/lists from these records; S6
    # must not collapse them to ``type/text`` pairs or a Markdown blob.
    page_action = "complete" if action == "complete" else "next"
    data = {"lessonId": lesson_id, "pageId": page.get("page_no"), "pageIndex": page_index, "pageCount": page_count, "pageType": page_kind, "contentBlocks": copy.deepcopy(blocks), "pageAction": page_action}
    data["visualRecipePlan"] = dynamic_visual_recipe_plan(blocks, page.get("design_brief"), page_kind)
    data["footerContract"] = {
        "required": True,
        "footerClass": "knowledge-footer" if page_kind == "knowledge_explanation" else "case-footer",
        "buttonClass": "knowledge-primary-button" if page_kind == "knowledge_explanation" else "case-primary-button",
        "buttonText": "完成学习" if page_action == "complete" else "继续学习",
    }
    if page_kind == "knowledge_explanation":
        data.update(transitionText="", transitionPlacement="none")
    else:
        data["linkedQuestionPageId"] = None
    data.update(visual_page_projection(page))
    return data

def dynamic_prompt_from_asset(filename, page_data, design_brief, context):
    prompt = text_block(filename)
    prompt = rebind_page_context(prompt, context)
    for tag, value in (("PAGE_DATA", page_data), ("DESIGN_BRIEF", design_brief)):
        replacement = f"<{tag}>\n{json.dumps(value, ensure_ascii=False, indent=2)}\n</{tag}>"
        prompt, count = re.subn(rf"<{tag}>\s*\{{.*?\}}\s*</{tag}>", lambda _: replacement, prompt, count=1, flags=re.S)
        if count != 1:
            raise ValueError(f"{tag}_REGION_NOT_FOUND:{filename}")
    return prompt

def task_sections(page):
    sections = page.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("POST_CLASS_TASK_SECTIONS_MISSING")
    allowed = {
        "paragraph", "task", "facts", "step", "prompt", "decision",
        "safety", "fallback", "section_heading", "composite",
    }
    allowed_roles = {
        "lead", "preflight", "action", "prompt", "review", "checklist",
        "condition", "correctivePrompt", "decision", "safetyFallback",
        "fallback", "note", "storySequenceHeading", "storySequence",
        "composite",
    }
    if any(not isinstance(x, dict) or x.get("type") not in allowed for x in sections):
        raise ValueError("POST_CLASS_TASK_SECTIONS_INVALID")
    if any(x.get("role") not in allowed_roles for x in sections):
        raise ValueError("POST_CLASS_TASK_SECTION_ROLES_INVALID")
    # A single raw Markdown blob is not an R18 section projection; guessing it
    # again in S6 would silently change the frozen S5 contract.
    if len(sections) == 1 and sections[0].get("type") == "task" and "```" in str(sections[0].get("text", "")):
        raise ValueError("POST_CLASS_TASK_SECTIONS_UNSTRUCTURED")
    return sections

def esc(value):
    # S5 retains Markdown for provenance.  S6 compiles student-facing static
    # DOM, so syntax-only emphasis delimiters must not leak as visible copy.
    text = str(value).replace("**", "").replace("__", "")
    return html.escape(text, quote=True)

def task_section_role(block):
    role = block.get("role")
    if isinstance(role, str) and role:
        return role
    return {
        "task": "lead",
        "facts": "preflight",
        "step": "action",
        "prompt": "prompt",
        "decision": "decision",
        "safety": "safetyFallback",
        "fallback": "fallback",
        "paragraph": "note",
    }.get(block.get("type"), "note")

def checklist_html(block, index):
    lines = [line.strip() for line in str(block.get("text") or "").splitlines() if line.strip()]
    rows = []
    for line in lines:
        match = re.match(r"^([^：:]{1,12})([：:])(.*)$", line)
        if match:
            rows.append(
                '<div class="checklist-row">'
                f'<span class="checklist-key">{esc(match.group(1) + match.group(2))}</span>'
                f'<span class="checklist-value">{esc(match.group(3))}</span></div>'
            )
        else:
            rows.append(f'<div class="checklist-row checklist-row-full">{esc(line)}</div>')
    return (
        f'<section class="checklist-block" data-section-role="checklist" '
        f'data-source-section-index="{index}">'
        f'<div class="checklist-label">{esc(block.get("label") or "检查清单")}</div>'
        + "".join(rows)
        + "</section>"
    )

def visual_html_bundle(visual_projection):
    if not visual_projection:
        return "", "", ""
    assets = (
        [visual_projection["visualAsset"]]
        if "visualAsset" in visual_projection
        else visual_projection.get("planVisualAssets", [])
    )
    figures = []
    for asset in assets:
        label = asset.get("displayLabel")
        caption = f'<figcaption class="visual-caption">{esc(label)}</figcaption>' if isinstance(label, str) and label else ""
        figures.append(
            '<figure class="visual-figure">'
            '<button type="button" class="image-zoom-trigger" aria-label="放大查看配图">'
            f'<img class="visual-image" src="{esc(asset["url"])}" alt="{esc(asset["alt"])}">'
            '</button>' + caption + '</figure>'
        )
    style = '''
:root{--runs-type-h1-size:28px;--runs-type-h1-line:1.3;--runs-type-h1-weight:800;--runs-type-h2-size:20px;--runs-type-h2-line:1.4;--runs-type-h2-weight:700;--runs-type-body-size:17px;--runs-type-body-line:1.7;--runs-type-body-weight:500;--runs-type-list-size:16px;--runs-type-list-line:1.6;--runs-type-list-weight:600;--runs-type-caption-size:14px;--runs-type-caption-line:1.55;--runs-type-caption-weight:500;}
.post-task-page h1{font-size:var(--runs-type-h1-size);line-height:var(--runs-type-h1-line);font-weight:var(--runs-type-h1-weight);text-align:center;}
.post-task-page h2{font-size:var(--runs-type-h2-size);line-height:var(--runs-type-h2-line);font-weight:var(--runs-type-h2-weight);text-align:left;}
.post-task-page p,.completion-check,.support-note{font-size:var(--runs-type-body-size);line-height:var(--runs-type-body-line);font-weight:var(--runs-type-body-weight);text-align:left;}
.post-task-page li{font-size:var(--runs-type-list-size);line-height:var(--runs-type-list-line);font-weight:var(--runs-type-list-weight);text-align:left;}
.task-intro,.card-heading,.action-title{text-align:left;}
.story-sequence-card{padding:17px;}
.story-sequence-list{display:grid;gap:9px;margin:0;padding-left:24px;}
.completion-check,.support-note{margin-left:45px;padding:13px 15px;border-radius:16px;}
.completion-check{background:rgba(255,255,255,.72);color:#403a50;}
.support-note{background:var(--yellow-soft);color:#5c4a28;}
.visual-gallery{width:100%;max-width:920px;margin:16px auto;}
.visual-figure{margin:0 0 16px 0;}
.image-zoom-trigger{display:block;width:100%;padding:0;overflow:hidden;border:0;border-radius:16px;background:transparent;cursor:zoom-in;}
.visual-image{display:block;width:100%;max-width:920px;height:auto;object-fit: contain;}
.visual-caption{margin-top:8px;text-align:center;font-size:var(--runs-type-caption-size);line-height:var(--runs-type-caption-line);font-weight:var(--runs-type-caption-weight);}
.visual-lightbox[hidden]{display:none;}
.visual-lightbox{position:fixed;left:0;top:0;right:0;bottom:0;z-index:9999;background:rgba(10,18,30,.88);}
.visual-lightbox-dialog{position:relative;width:100%;height:100%;margin:0;}
.visual-lightbox-stage{position:absolute;left:0;top:0;right:0;bottom:0;display:flex;align-items:center;justify-content:center;overflow:hidden;touch-action:none;}
.visual-lightbox-image{display:block;width:92%;height:auto;max-height:72%;object-fit:contain;transform-origin:center center;}
.visual-lightbox-close{position:fixed;left:50%;top:82%;z-index:2;width:46px;height:46px;padding:0;transform:translateX(-50%);border:0;border-radius:50%;color:#fff;background:rgba(255,255,255,.24);font-size:28px;line-height:46px;}
'''
    markup = (
        '<section class="visual-gallery" data-visual-group-layout="vertical_stack" '
        'data-visual-placement-terminal="forbidden" aria-label="课程配图">'
        + "".join(figures) + '</section>'
        '<div class="visual-lightbox" hidden aria-hidden="true"><div class="visual-lightbox-dialog">'
        '<div class="visual-lightbox-stage"><img class="visual-lightbox-image" alt=""></div>'
        '<button type="button" class="visual-lightbox-close" aria-label="关闭大图"><span aria-hidden="true">×</span></button></div></div>'
    )
    script = '''
(function(){
var lightbox=document.querySelector(".visual-lightbox");
var lightboxImage=document.querySelector(".visual-lightbox-image");
var triggers=document.querySelectorAll(".image-zoom-trigger");
var closeButton=document.querySelector(".visual-lightbox-close");
var stage=document.querySelector(".visual-lightbox-stage");
var scale=1,translateX=0,translateY=0,startDistance=0,startScale=1,startX=0,startY=0,bodyOverflow="";
function applyVisualTransform(){lightboxImage.style.transform="translate("+translateX+"px,"+translateY+"px) scale("+scale+")";}
function resetVisualTransform(){scale=1;translateX=0;translateY=0;applyVisualTransform();}
function touchDistance(touches){var dx=touches[0].clientX-touches[1].clientX;var dy=touches[0].clientY-touches[1].clientY;return Math.sqrt(dx*dx+dy*dy);}
function positionVisualClose(){var viewportHeight=window.innerHeight||document.documentElement.clientHeight;var imageRect=lightboxImage.getBoundingClientRect();var lowerSpace=Math.max(0,viewportHeight-imageRect.bottom);closeButton.style.top=Math.round(imageRect.bottom+lowerSpace/2-23)+"px";}
function closeVisualLightbox(){resetVisualTransform();lightbox.hidden=true;lightbox.setAttribute("aria-hidden","true");document.body.style.overflow=bodyOverflow;}
for(var i=0;i<triggers.length;i+=1){triggers[i].addEventListener("click",function(){var source=this.querySelector("img");lightboxImage.src=source.src;lightboxImage.alt=source.alt;resetVisualTransform();bodyOverflow=document.body.style.overflow;document.body.style.overflow="hidden";lightbox.hidden=false;lightbox.setAttribute("aria-hidden","false");window.requestAnimationFrame(positionVisualClose);});}
lightboxImage.onload=positionVisualClose;
stage.addEventListener("touchstart",function(event){if(event.touches.length===2){startDistance=touchDistance(event.touches);startScale=scale;event.preventDefault();}else if(event.touches.length===1&&scale>1){startX=event.touches[0].clientX-translateX;startY=event.touches[0].clientY-translateY;}},{passive:false});
stage.addEventListener("touchmove",function(event){if(event.touches.length===2&&startDistance>0){scale=Math.max(1,Math.min(4,startScale*touchDistance(event.touches)/startDistance));if(scale<=1){translateX=0;translateY=0;}applyVisualTransform();event.preventDefault();}else if(event.touches.length===1&&scale>1){translateX=event.touches[0].clientX-startX;translateY=event.touches[0].clientY-startY;applyVisualTransform();event.preventDefault();}},{passive:false});
stage.addEventListener("touchend",function(){startDistance=0;if(scale<=1)resetVisualTransform();});
closeButton.addEventListener("click",closeVisualLightbox);
lightbox.addEventListener("click",function(event){if(event.target===lightbox)closeVisualLightbox();});
stage.addEventListener("click",function(event){if(event.target===stage)closeVisualLightbox();});
document.addEventListener("keydown",function(event){if(event.key==="Escape")closeVisualLightbox();});
window.addEventListener("resize",function(){if(!lightbox.hidden)positionVisualClose();});
}());
'''
    return style, markup, script


def task_html(title, sections, action, visual_projection=None):
    demo = TASK_DEMO.read_text(encoding="utf-8")
    prefix = demo.split("  <script>", 1)[0]
    visual_style, visual_markup, visual_script = visual_html_bundle(visual_projection or {})
    if visual_style:
        prefix = prefix.replace("</style>", visual_style + "</style>", 1)
    prefix = prefix.replace('<h1 id="taskTitle"></h1>', f'<h1 id="taskTitle">{esc(title)}</h1>')
    prefix = prefix.replace('>完成任务</button>', f'>{"完成学习" if action == "complete" else "继续学习"}</button>')
    chunks = []
    index = 0
    action_number = 0
    workflow_roles = {"action", "prompt", "review", "checklist", "condition", "correctivePrompt", "decision", "composite"}
    workflow_indexes = [
        position
        for position, section in enumerate(sections)
        if task_section_role(section) in workflow_roles
    ]
    workflow_start = min(workflow_indexes) if workflow_indexes else -1
    workflow_end = max(workflow_indexes) if workflow_indexes else -1

    def is_workflow_section(position):
        section_role = task_section_role(sections[position])
        return section_role in workflow_roles or (
            section_role == "note" and workflow_start <= position <= workflow_end
        )

    while index < len(sections):
        block = sections[index]
        typ, value = block["type"], block.get("text", "")
        role = task_section_role(block)
        marker = f'data-source-section-index="{index}"'
        role_marker = f'data-section-role="{esc(role)}"'
        if role == "lead":
            chunks.append(f'<p class="task-intro task-lead" {role_marker} {marker}>{esc(value)}</p>')
            index += 1
            continue
        if role == "storySequenceHeading":
            following = sections[index + 1] if index + 1 < len(sections) else None
            if not isinstance(following, dict) or task_section_role(following) != "storySequence":
                raise ValueError("POST_CLASS_TASK_STORY_SEQUENCE_INVALID")
            items = following.get("items")
            if not isinstance(items, list) or not all(
                isinstance(item, str) and item.strip() for item in items
            ):
                raise ValueError("POST_CLASS_TASK_STORY_SEQUENCE_INVALID")
            chunks.append(
                f'<section class="glass-card story-sequence-card" {role_marker}>'
                f'<div class="card-heading" {marker}><h2>{esc(value.replace("**", "").replace("__", ""))}</h2></div>'
                f'<ol class="story-sequence-list" data-section-role="storySequence" data-source-section-index="{index + 1}">'
                + "".join(f"<li>{esc(item)}</li>" for item in items)
                + "</ol></section>"
            )
            index += 2
            continue
        if typ == "paragraph" and role == "note" and not is_workflow_section(index):
            chunks.append(f'<p class="task-intro" {role_marker} {marker}>{esc(value)}</p>')
            index += 1
            continue
        if typ == "facts":
            items = block.get("items")
            if not isinstance(items, list) or not items:
                items = [value] if isinstance(value, str) and value.strip() else []
            if not all(isinstance(item, str) and item.strip() for item in items):
                raise ValueError("POST_CLASS_TASK_FACTS_INVALID")
            chunks.append(f'<section class="glass-card facts-card" {role_marker}><div class="card-heading"><span class="card-symbol">✓</span><h2>{esc(block.get("label", "固定材料"))}</h2></div><ul class="facts-grid" {marker}>' + "".join(f"<li>{esc(item)}</li>" for item in items) + "</ul></section>")
            index += 1
            continue
        if is_workflow_section(index):
            action_chunks = []
            while index < len(sections) and is_workflow_section(index):
                current = sections[index]
                current_role = task_section_role(current)
                action_number += 1
                pair_for = {
                    "action": "prompt",
                    "review": "checklist",
                    "condition": "correctivePrompt",
                }
                paired_role = pair_for.get(current_role)
                paired = (
                    sections[index + 1]
                    if paired_role
                    and index + 1 < len(sections)
                    and task_section_role(sections[index + 1]) == paired_role
                    else None
                )
                if current_role in {"action", "review", "condition"}:
                    inner = f'<p class="step-lead" data-section-role="{esc(current_role)}" data-source-section-index="{index}">{esc(current.get("text", ""))}</p>'
                    if paired and paired_role == "checklist":
                        inner += checklist_html(paired, index + 1)
                        index += 1
                    elif paired:
                        inner += f'<div class="prompt-block" data-section-role="{esc(paired_role)}"><div class="prompt-label">{esc(paired.get("label") or paired.get("promptLabel") or "PROMPT")}</div><pre data-source-section-index="{index + 1}"><code>{esc(paired.get("text", ""))}</code></pre></div>'
                        index += 1
                    step_number = current.get("stepNumber") or str(action_number).zfill(2)
                    pair_marker = f' data-task-group-pair="{current_role}-{paired_role}"' if paired else ""
                elif current_role == "checklist":
                    inner = checklist_html(current, index)
                    step_number = str(action_number).zfill(2)
                    pair_marker = ""
                elif current_role == "decision":
                    inner = f'<p class="step-lead" data-section-role="decision" data-source-section-index="{index}">{esc(current.get("text", ""))}</p>'
                    step_number = str(action_number).zfill(2)
                    pair_marker = ""
                elif current_role == "composite":
                    segments = current.get("segments")
                    if (
                        not isinstance(segments, list)
                        or [segment.get("role") for segment in segments]
                        != ["action", "completionCheck", "supportNote"]
                    ):
                        raise ValueError("POST_CLASS_TASK_COMPOSITE_INVALID")
                    inner = (
                        f'<p class="step-lead" data-section-role="composite" data-source-section-index="{index}">{esc(segments[0].get("text", ""))}</p>'
                    )
                    step_number = str(action_number).zfill(2)
                    pair_marker = ""
                    trailing = (
                        f'<div class="completion-check">{esc(segments[1].get("text", ""))}</div>'
                        f'<div class="support-note">{esc(segments[2].get("text", ""))}</div>'
                    )
                elif current_role == "note":
                    inner = f'<p class="step-lead step-note" data-section-role="note" data-source-section-index="{index}">{esc(current.get("text", ""))}</p>'
                    step_number = str(action_number).zfill(2)
                    pair_marker = ""
                else:
                    inner = f'<div class="prompt-block" data-section-role="{esc(current_role)}"><div class="prompt-label">{esc(current.get("label") or current.get("promptLabel") or "PROMPT")}</div><pre data-source-section-index="{index}"><code>{esc(current.get("text", ""))}</code></pre></div>'
                    step_number = str(action_number).zfill(2)
                    pair_marker = ""
                action_chunks.append(
                    f'<article class="step-group"{pair_marker}><span class="step-index">{esc(step_number)}</span><section class="glass-card step-card">{inner}</section></article>'
                    + (trailing if current_role == "composite" else "")
                )
                index += 1
            chunks.append('<section class="action-section"><div class="action-title"><h2>操作步骤</h2></div>' + "".join(action_chunks) + '</section>')
            continue
        if typ == "decision":
            chunks.append(f'<section class="glass-card decision-card" {role_marker}><div class="card-heading"><span class="card-symbol">?</span><h2>检查与决定</h2></div><p {marker}>{esc(value)}</p></section>')
        else:
            chunks.append(f'<section class="support-stack" {role_marker}><div class="support-row" data-support-type="{typ}"><span class="support-mark">{"!" if typ == "safety" else "↗"}</span><p class="support-copy" {marker}>{esc(value)}</p></div></section>')
        index += 1
    if visual_markup:
        assets = (
            [visual_projection["visualAsset"]]
            if isinstance(visual_projection, dict) and "visualAsset" in visual_projection
            else visual_projection.get("planVisualAssets", [])
        )
        placement = assets[0].get("placement") if assets and isinstance(assets[0], dict) else {}
        if not isinstance(placement, dict):
            placement = {}
        insert_index = 1 if chunks else 0
        if isinstance(placement, dict) and placement.get("insertAfter") == "story_sequence_or_task_goal":
            story_indexes = [i for i, chunk in enumerate(chunks) if 'story-sequence-card"' in chunk]
            if story_indexes:
                insert_index = story_indexes[-1] + 1
        elif isinstance(placement, dict) and placement.get("insertAfterText"):
            anchor = esc(placement.get("insertAfterText"))
            matching_indexes = [i for i, chunk in enumerate(chunks) if anchor in chunk]
            if matching_indexes:
                insert_index = matching_indexes[-1] + 1
        if placement.get("terminalPlacementForbidden") is True and insert_index >= len(chunks):
            raise ValueError("VISUAL_TERMINAL_PLACEMENT_FORBIDDEN")
        chunks.insert(insert_index, visual_markup)
    content = "".join(chunks)
    prefix = prefix.replace('<section class="task-content" id="taskContent" aria-label="拓展练习内容"></section>', f'<section class="task-content" id="taskContent" aria-label="拓展练习内容">{content}</section>')
    handler = "safeComplete" if action == "complete" else "safeNextPage"
    return prefix + f'''  <script>
function safeNextPage() {{ if (window.CreatorReviewSDK && (!CreatorReviewSDK.isAvailable || CreatorReviewSDK.isAvailable()) && typeof CreatorReviewSDK.nextPage === "function") CreatorReviewSDK.nextPage(); }}
function safeComplete() {{ if (window.CreatorReviewSDK && (!CreatorReviewSDK.isAvailable || CreatorReviewSDK.isAvailable()) && typeof CreatorReviewSDK.complete === "function") CreatorReviewSDK.complete(); }}
{visual_script}
function syncFooterReserve() {{ const footer=document.querySelector(".task-footer"); if (footer) document.documentElement.style.setProperty("--footer-h", Math.ceil(footer.getBoundingClientRect().height || 92) + "px"); }}
syncFooterReserve(); if ("ResizeObserver" in window) new ResizeObserver(syncFooterReserve).observe(document.querySelector(".task-footer")); window.addEventListener("resize", syncFooterReserve, {{passive:true}}); document.getElementById("taskButton").addEventListener("click", {handler});
  </script>\n</body>\n</html>'''

def task_prompt(page, lesson_id, action, page_index, page_count, visual_mode="text_only"):
    sections = task_sections(page)
    content = page.get("content")
    title = content.get("taskTitle") if isinstance(content, dict) else None
    if not isinstance(title, str) or not title.strip():
        raise ValueError("POST_CLASS_TASK_TITLE_MISSING")
    visual_projection = visual_page_projection(page) if visual_mode == "visual_enhanced" else {}
    document = task_html(title, sections, action, visual_projection)
    task_contract = VISUAL_TASK_CONTRACT if visual_mode == "visual_enhanced" else TASK_CONTRACT
    task_asset_sha256 = VISUAL_TASK_ASSET_SHA256 if visual_mode == "visual_enhanced" else TASK_ASSET_SHA256
    visual_rules = (
        "\n\n配图是正文主配图，禁止缩略图、小装饰条或图标尺寸；按内容区宽度、自然比例、"
        "object-fit: contain、16px 圆角和 16px 上下间距呈现。按 extension_contextual_image "
        "放在故事顺序或任务目标之后、操作提示词之前；无法唯一判断时放在第一块正文之后。"
        if visual_mode == "visual_enhanced"
        else ""
    )
    prompt = f'''提示词版本号：{PROMPT_VERSION_PLACEHOLDER}

适用页面：{lesson_id}｜{page["page_no"]}｜第 {page_index}/{page_count} 页｜拓展练习页。

这是一次性完整 Compact-OneShot，没有任何外部上下文。当前合同：{task_contract}。学生正文已按冻结 sections 预编译为静态富卡片 DOM；不得改写、删减、调序或用 JavaScript 重建正文。{visual_rules}

最终回复必须且只能包含下方从 <!doctype html> 到 </html> 的完整 HTML，不得输出解释、Markdown 围栏、版本说明、提示词正文、PAGE_DATA 或字段名。

请原样输出下方完整代码：

{document}'''
    return finalize_prompt_version(
        prompt, task_contract, task_asset_sha256, lesson_id, page["page_no"]
    )

def summary_values(page, action):
    content = page.get("content")
    blocks = content.get("contentBlocks") if isinstance(content, dict) else None
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("COURSE_SUMMARY_CONTENT_BLOCKS_MISSING")
    title = ""
    effective = page.get("effective_content")
    effective_blocks = effective.get("blocks") if isinstance(effective, dict) else None
    if isinstance(effective_blocks, list):
        for block in effective_blocks:
            if isinstance(block, dict) and block.get("type") == "heading" and isinstance(block.get("text"), str):
                title = re.sub(r"^#{1,6}\s+", "", block["text"]).strip()
                if title:
                    break
    if not title:
        for block in blocks:
            if isinstance(block, dict) and block.get("type") == "heading" and isinstance(block.get("text"), str):
                title = re.sub(r"^#{1,6}\s+", "", block["text"]).strip()
                if title:
                    break
    if not title:
        raise ValueError("COURSE_SUMMARY_TITLE_MISSING")
    if not all(isinstance(block, dict) for block in blocks):
        raise ValueError("COURSE_SUMMARY_CONTENT_BLOCKS_INVALID")
    visible_blocks = [block for block in blocks if block.get("type") != "heading"]
    if not visible_blocks:
        raise ValueError("COURSE_SUMMARY_CONTENT_BLOCKS_EMPTY")
    return {
        "completionTitle": "恭喜你完成本节课程！" if action == "complete" else "本课重点回顾",
        "summaryTitle": title,
        "contentBlocks": visible_blocks,
        "nextLessonPreview": "",
        "pageAction": "next" if action == "next" else "complete",
    }

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--lesson-id", required=True); parser.add_argument("--effective-content", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    if not OUTER_ONESHOT.is_file() or "整课 JSON" not in OUTER_ONESHOT.read_text(encoding="utf-8"):
        raise SystemExit("BLOCKED:WHOLE_COURSE_ONESHOT_ASSET_INVALID")
    data = json.loads(args.effective_content.read_text(encoding="utf-8")); pages = data.get("pages")
    if not isinstance(pages, list) or not pages: raise SystemExit("BLOCKED:EFFECTIVE_CONTENT_PAGES_MISSING")
    visual_mode = data.get("visualMode", "text_only")
    if visual_mode not in {"text_only", "visual_enhanced"}:
        raise SystemExit("BLOCKED:VISUAL_MODE_INVALID")
    result = []
    try:
        for i, page in enumerate(pages):
            source_typ, no = page.get("page_type"), page.get("page_no"); typ = canonical_page_type(source_typ); action = "complete" if i == len(pages) - 1 else "nextpage"
            base = {"page_no": no, "tag": canonical_capsule(source_typ, page.get("capsule")), "title": typ, "summary": "S5 frozen effective-content projection", "sdk_action": action, "is_last_page": i == len(pages)-1, "page_data": {"source_block_ids": page.get("source_block_ids"), "effective_content_sha256": digest(page.get("effective_content")), "assembly_mode": "model_oneshot_prompt_control", "expected_model_output": "pure_complete_html", "model_output_status": "NOT_GENERATED", "whole_course_oneshot": OUTER_ONESHOT.name}}
            visual_projection = visual_page_projection(page)
            if visual_mode == "text_only" and visual_projection:
                raise ValueError(f"TEXT_ONLY_VISUAL_PRESENT:{no}")
            if visual_mode == "visual_enhanced" and typ != "互动题目" and not visual_projection:
                raise ValueError(f"VISUAL_ENHANCED_PAGE_ASSET_MISSING:{no}")
            if typ == "互动题目":
                if visual_projection:
                    raise ValueError(f"INTERACTION_IMAGE_UNSUPPORTED:{no}")
                base.update(page_kind="question_component_page", runtime_type="component", prompt="", components=[page.get("effective_content")]); result.append(base); continue
            if visual_projection:
                base["page_data"].update(copy.deepcopy(visual_projection))
            if typ == POST_CLASS_CANONICAL_PAGE_TYPE:
                prompt, version, prompt_sha = task_prompt(page, args.lesson_id, "complete" if action == "complete" else "next", i + 1, len(pages), visual_mode)
                task_contract = VISUAL_TASK_CONTRACT if visual_mode == "visual_enhanced" else TASK_CONTRACT
                task_asset_sha256 = VISUAL_TASK_ASSET_SHA256 if visual_mode == "visual_enhanced" else TASK_ASSET_SHA256
                base["page_data"].update(route="compact_direct_oneshot", oneshot_contract_version=task_contract, oneshot_asset_sha256=task_asset_sha256, prompt_version=version, prompt_instance_sha256=prompt_sha)
                base.update(page_kind="post_class_task", runtime_type="html", components=[], prompt=prompt); result.append(base); continue
            dynamic_contracts = VISUAL_DYNAMIC if visual_mode == "visual_enhanced" else DYNAMIC
            if typ in dynamic_contracts:
                kind, filename, contract, sha = dynamic_contracts[typ]; brief = page.get("design_brief")
                if not isinstance(brief, dict) or brief.get("nonRenderable") is not True: raise ValueError(f"DYNAMIC_DESIGN_BRIEF_INVALID:{no}")
                pdata = dynamic_page_data(page, args.lesson_id, i+1, len(pages), kind, "complete" if action == "complete" else "next")
                if kind == "case_analysis" and i+1 < len(pages): pdata["linkedQuestionPageId"] = pages[i+1].get("page_no")
                context = {"lesson_id": args.lesson_id, "page_no": no, "page_index": i + 1, "page_count": len(pages), "page_label": typ}
                raw_prompt = dynamic_prompt_from_asset(filename, pdata, brief, context)
                prompt, version, prompt_sha = finalize_prompt_version(raw_prompt, contract, sha, args.lesson_id, no)
                base["page_data"].update(route="dynamic_oneshot", oneshot_contract_version=contract, oneshot_asset_sha256=sha, design_brief=brief, visualRecipePlan=pdata["visualRecipePlan"], footerContract=pdata["footerContract"], prompt_version=version, prompt_instance_sha256=prompt_sha)
                base.update(page_kind=kind, runtime_type="html", components=[], prompt=prompt); result.append(base); continue
            fixed_contracts = VISUAL_FIXED if visual_mode == "visual_enhanced" else FIXED
            if typ not in fixed_contracts: raise ValueError(f"UNSUPPORTED_PAGE_TYPE:{typ}")
            kind, filename, variable, contract, sha, template_sha, nonvar_sha = fixed_contracts[typ]
            if typ == "课程开篇":
                values = intro_values(page, action)
                base["page_data"]["introDensityContract"] = {
                    "required": True,
                    "source": "S5.content.knowledgePoints",
                    "knowledgePointCount": len(values["knowledgePoints"]),
                    "oneUnlockRowPerSourceItem": True,
                    "forbidMergedDelimitedString": True,
                    "minimumUnlockRowHeightPx": 44,
                    "visualStatus": "STATIC_LAYOUT_CONTRACT_ONLY",
                }
            elif typ == "场景引入":
                lines = [x for x in str(page.get("source", {}).get("rawMarkdown", "")).split("\n\n") if x and not x.startswith("#")]; values = {"sceneParagraphs": lines[:-1], "lessonLead": lines[-1] if lines else "", "pageAction": "next" if action == "nextpage" else "complete"}
            else:
                values = summary_values(page, "next" if action == "nextpage" else "complete")
            context = {"lesson_id": args.lesson_id, "page_no": no, "page_index": i + 1, "page_count": len(pages), "page_label": typ}
            raw_prompt = prompt_from_asset(filename, variable, values, context, visual_projection if visual_mode == "visual_enhanced" else None)
            prompt, version, prompt_sha = finalize_prompt_version(raw_prompt, contract, sha, args.lesson_id, no)
            base["page_data"].update(route="fixed_template", template=variable, oneshot_contract_version=contract, oneshot_asset_sha256=sha, template_sha256=template_sha, non_variable_sha256=nonvar_sha, template_outside_variable_region_unchanged=True, prompt_version=version, prompt_instance_sha256=prompt_sha)
            base.update(page_kind=kind, runtime_type="html", components=[], prompt=prompt); result.append(base)
    except ValueError as exc:
        raise SystemExit(f"BLOCKED:{exc}")
    intro_page = next((page for page in pages if page.get("page_type") == "课程开篇"), {})
    intro_content = intro_page.get("content") if isinstance(intro_page, dict) else {}
    if not isinstance(intro_content, dict):
        raise SystemExit("BLOCKED:COURSE_TITLE_MISSING")
    try:
        task_title = whole_course_task_title(intro_values(intro_page, "next"))
    except ValueError as exc:
        raise SystemExit(f"BLOCKED:{exc}")
    output = {"version":"V3.5.0-R36", "course_id":args.lesson_id, "title":task_title, "description":"S6 static assembly from frozen S5", "source":{"effective_content":str(args.effective_content.resolve()), "whole_course_oneshot":str(OUTER_ONESHOT.resolve())}, "workflow":"S1-S6-R36", "pages":result}
    if visual_mode == "visual_enhanced":
        output["visualMode"] = visual_mode
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

if __name__ == "__main__": main()
