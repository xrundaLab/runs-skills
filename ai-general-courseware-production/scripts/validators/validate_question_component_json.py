#!/usr/bin/env python3
"""Validate question JSON blocks embedded in lesson question-summary Markdown."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


FORBIDDEN_KEYS = {
    "background",
    "rawMarkdownLines",
    "sourceInteractionBlock",
    "parsedSource",
    "qaStatus",
    "reviewStatus",
    "reviewNote",
    "sourceTextExcerpt",
    "sourceSegmentId",
    "interactionId",
    "sourceRelation",
    "knowledgeAnchor",
    "jsonLayer",
}

STAGE3_NATURAL_HEADING_RE = re.compile(
    r"^#{1,6}\s+题目数据（自然语言版）\s*$",
    flags=re.M,
)
STAGE3_JSON_HEADING_RE = re.compile(
    r"^#{1,6}\s+题目数据（JSON版）\s*$",
    flags=re.M,
)
NO_QUESTION_PROCESSING_MARKER = "NO_QUESTION_PROCESSING_REQUIRED"
S3_INPUT_FREEZE_RE = re.compile(
    r"<!--\s*S3_INPUT_FREEZE\s*\n"
    r"page_plan_working_full:\s*(?P<path>.+)\n"
    r"bytes:\s*(?P<bytes>\d+)\n"
    r"sha256:\s*(?P<sha>[0-9a-f]{64})\s*\n-->",
    flags=re.I,
)
S3_BASELINE_MARKER = "--- 冻结页面规划原文（只读基底） ---"
WORKING_PAGE_MARKER_RE = re.compile(
    r"^<mark>页面块 (?P<page_no>P\d+)｜页面类型：(?P<page_type>[^｜]+)｜胶囊文案：[^<]+</mark>\n?",
    flags=re.M,
)

REQUIRED_WRAPPER_KEYS = {
    "questionId",
    "lessonId",
    "lessonTitle",
    "packName",
    "unitName",
    "componentType",
    "componentKey",
}

DIRECT_COMPONENT_TYPES = {
    "galaxy_select_question",
    "matching_question",
    "categorization_question",
    "ordering_question",
}

STANDALONE_COMPONENT_KEYS = {"type", "componentId", "content"}

UNSUPPORTED_MATCHING_RENDER_KEYS = {
    "randomizeRight",
    "rightColumnDisplayOrder",
    "rightOptionOrder",
    "right_column_display_order",
    "shuffle",
    "shuffleRight",
}


def normalize_matching_option_text(value: str) -> str:
    """Normalize visible matching text for same-side duplicate detection."""
    without_label = re.sub(r"^\s*(?:\d+|[A-Z])\s*[.．、:：]\s*", "", value)
    return re.sub(r"\s+", " ", without_label).strip()


def iter_json_blocks(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    blocks: list[tuple[int, str]] = []
    for match in re.finditer(r"```json\n(.*?)\n```", text, flags=re.S):
        line_no = text[: match.start()].count("\n") + 1
        blocks.append((line_no, match.group(1)))
    return blocks


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def split_working_pages(text: str) -> tuple[str, list[tuple[str, str, str, str]]]:
    """Return S2 prefix and ordered (page_no, type, marker, body) tuples."""
    matches = list(WORKING_PAGE_MARKER_RE.finditer(text))
    if not matches:
        return text, []
    pages = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        pages.append((match.group("page_no"), match.group("page_type"), match.group(0), text[match.end() : end]))
    return text[: matches[0].start()], pages


def validate_stage3_inheritance(text: str, document_path: Path) -> list[str]:
    """Enforce complete S2 inheritance with additions only inside interaction pages."""
    errors: list[str] = []
    freeze = S3_INPUT_FREEZE_RE.search(text)
    if not freeze:
        return ["stage3 document must declare S3_INPUT_FREEZE for page_plan_working_full.md"]
    source_path = Path(freeze.group("path")).expanduser()
    if not source_path.is_file():
        return ["S3_INPUT_FREEZE page_plan_working_full.md does not exist"]
    source_bytes = source_path.read_bytes()
    if len(source_bytes) != int(freeze.group("bytes")) or sha256_bytes(source_bytes) != freeze.group("sha").lower():
        return ["S3_INPUT_FREEZE bytes or SHA-256 does not match page_plan_working_full.md"]
    marker_index = text.find(S3_BASELINE_MARKER, freeze.end())
    if marker_index < 0:
        return ["stage3 document must contain the frozen page-plan baseline marker"]
    inherited = text[marker_index + len(S3_BASELINE_MARKER) :].lstrip("\n")
    source = source_bytes.decode("utf-8")
    source_prefix, source_pages = split_working_pages(source)
    inherited_prefix, inherited_pages = split_working_pages(inherited)
    if not source_pages:
        errors.append("frozen page_plan_working_full.md has no recognized page blocks")
        return errors
    if inherited_prefix != source_prefix:
        errors.append("stage3 must preserve the complete S2 metadata and pre-page baseline verbatim")
    source_identity = [(no, kind, marker) for no, kind, marker, _ in source_pages]
    inherited_identity = [(no, kind, marker) for no, kind, marker, _ in inherited_pages]
    if source_identity != inherited_identity:
        errors.append("stage3 page blocks must preserve S2 page number, type, capsule, and order verbatim")
        return errors
    interaction_count = 0
    for source_page, inherited_page in zip(source_pages, inherited_pages):
        page_no, page_type, _, source_body = source_page
        _, _, _, inherited_body = inherited_page
        if page_type != "互动题目":
            if inherited_body != source_body:
                errors.append(f"{page_no} non-interaction body must remain verbatim from S2")
            continue
        interaction_count += 1
        baseline = source_body.rstrip()
        if not inherited_body.startswith(baseline):
            errors.append(f"{page_no} interaction baseline must remain verbatim before question data")
            continue
        addition = inherited_body[len(baseline) :].strip()
        if len(STAGE3_NATURAL_HEADING_RE.findall(addition)) != 1 or len(STAGE3_JSON_HEADING_RE.findall(addition)) != 1:
            errors.append(f"{page_no} must append exactly one paired natural-language/JSON question-data block")
    if interaction_count != len(STAGE3_NATURAL_HEADING_RE.findall(inherited)):
        errors.append("stage3 must append one paired question-data block inside every S2 interaction page")
    return errors


def validate_stage3_document_text(text: str, document_path: Path | None = None) -> list[str]:
    """Validate the paired natural-language/JSON evidence contract for S2Q."""
    errors: list[str] = []
    natural_headings = list(STAGE3_NATURAL_HEADING_RE.finditer(text))
    json_headings = list(STAGE3_JSON_HEADING_RE.finditer(text))
    json_blocks = list(re.finditer(r"```json\n(.*?)\n```", text, flags=re.S))

    if not natural_headings and not json_headings and not json_blocks:
        if NO_QUESTION_PROCESSING_MARKER not in text:
            errors.append(
                "question_processed_full.md must contain paired 题目数据（自然语言版）/"
                "题目数据（JSON版） sections or NO_QUESTION_PROCESSING_REQUIRED"
            )
        return errors

    require(
        len(natural_headings) == len(json_headings) == len(json_blocks),
        errors,
        "stage3 evidence counts must match: one natural-language section and one JSON block per question",
    )

    for index, natural_heading in enumerate(natural_headings):
        segment_end = (
            natural_headings[index + 1].start()
            if index + 1 < len(natural_headings)
            else len(text)
        )
        segment = text[natural_heading.end() : segment_end]
        segment_json_headings = list(STAGE3_JSON_HEADING_RE.finditer(segment))
        segment_json_blocks = list(re.finditer(r"```json\n(.*?)\n```", segment, flags=re.S))
        require(
            len(segment_json_headings) == 1 and len(segment_json_blocks) == 1,
            errors,
            f"stage3 question section {index + 1} must contain exactly one 题目数据（JSON版） heading and JSON block",
        )

    if document_path is not None:
        errors.extend(validate_stage3_inheritance(text, document_path))
    return errors


def find_forbidden_keys(value: Any, prefix: str = "$") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{prefix}.{key}"
            if key in FORBIDDEN_KEYS:
                errors.append(child_path)
            errors.extend(find_forbidden_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            errors.extend(find_forbidden_keys(child, f"{prefix}[{index}]"))
    return errors


def require(condition: bool, errors: list[str], message: str) -> None:
    if not condition:
        errors.append(message)


def find_keys(value: Any, targets: set[str]) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in targets:
                found.add(key)
            found.update(find_keys(child, targets))
    elif isinstance(value, list):
        for child in value:
            found.update(find_keys(child, targets))
    return found


def validate_standalone_envelope(component: dict[str, Any], errors: list[str]) -> None:
    require(
        set(component.keys()) == STANDALONE_COMPONENT_KEYS,
        errors,
        "standalone component outer keys must be exactly ['componentId', 'content', 'type']",
    )


def validate_select(obj: dict[str, Any], errors: list[str]) -> None:
    require(obj.get("componentKey") == "galaxy_select_question", errors, "componentKey must be galaxy_select_question")
    component = obj.get("componentData")
    require(isinstance(component, dict), errors, "componentData must be an object")
    if not isinstance(component, dict):
        return

    require(component.get("type") == "galaxy_select_question", errors, "componentData.type must be galaxy_select_question")
    require(isinstance(component.get("componentId"), str) and bool(component.get("componentId")), errors, "componentData.componentId is required")

    flat_keys = {"question", "options", "answerIndex", "answer", "explanation", "isMultiple"}
    bad_flat = sorted(flat_keys & set(component.keys()))
    require(not bad_flat, errors, f"flat fields are not allowed directly under componentData: {bad_flat}")

    content = component.get("content")
    require(isinstance(content, dict), errors, "componentData.content must be an object")
    if not isinstance(content, dict):
        return

    bad_content_flat = sorted({"question", "options", "answerIndex", "answer", "explanation"} & set(content.keys()))
    require(not bad_content_flat, errors, f"flat fields are not allowed directly under content: {bad_content_flat}")

    questions = content.get("questions")
    require(isinstance(questions, list) and bool(questions), errors, "content.questions must be a non-empty list")
    if "correctButtonText" in content:
        require(isinstance(content.get("correctButtonText"), str), errors, "content.correctButtonText must be a string")
    if not isinstance(questions, list):
        return

    for q_index, question in enumerate(questions):
        q_path = f"content.questions[{q_index}]"
        require(isinstance(question, dict), errors, f"{q_path} must be an object")
        if not isinstance(question, dict):
            continue
        require(isinstance(question.get("question"), str) and bool(question.get("question")), errors, f"{q_path}.question is required")
        if "questionAudio" in question:
            require(isinstance(question.get("questionAudio"), str), errors, f"{q_path}.questionAudio must be a string")
        if "explanation" in question:
            require(isinstance(question.get("explanation"), str), errors, f"{q_path}.explanation must be a string")
        require(isinstance(question.get("isMultiple"), bool), errors, f"{q_path}.isMultiple must be boolean")
        options = question.get("options")
        require(isinstance(options, list) and len(options) >= 2, errors, f"{q_path}.options must contain at least 2 options")
        if not isinstance(options, list):
            continue
        option_texts: list[str] = []
        for opt_index, option in enumerate(options):
            opt_path = f"{q_path}.options[{opt_index}]"
            if isinstance(option, str):
                require(bool(option), errors, f"{opt_path} must be a non-empty string")
                option_texts.append(option)
                continue
            require(isinstance(option, dict), errors, f"{opt_path} must be a string or object")
            if not isinstance(option, dict):
                continue
            text = option.get("text")
            require(isinstance(text, str) and bool(text), errors, f"{opt_path}.text is required")
            if "audio" in option:
                require(isinstance(option.get("audio"), str), errors, f"{opt_path}.audio must be a string")
            if isinstance(text, str):
                option_texts.append(text)

        is_multiple = question.get("isMultiple")
        answer_index = question.get("answerIndex")
        answer = question.get("answer")
        if is_multiple in (True, False):
            require(isinstance(answer_index, list) and bool(answer_index), errors, f"{q_path}.answerIndex must be a non-empty number list")
            require(isinstance(answer, list) and bool(answer), errors, f"{q_path}.answer must be a non-empty string list")
            if is_multiple is False and isinstance(answer_index, list):
                require(len(answer_index) == 1, errors, f"{q_path}.answerIndex must contain exactly one item for single select")
            if isinstance(answer_index, list):
                require(all(isinstance(i, int) and 0 <= i < len(option_texts) for i in answer_index), errors, f"{q_path}.answerIndex contains invalid index")
                expected = [option_texts[i] for i in answer_index if isinstance(i, int) and 0 <= i < len(option_texts)]
                require(answer == expected, errors, f"{q_path}.answer must match options selected by answerIndex")


def validate_select_component(component: dict[str, Any], errors: list[str]) -> None:
    wrapped = {
        "componentType": "galaxy_select_question",
        "componentKey": "galaxy_select_question",
        "componentData": component,
        "questionId": "__direct_component__",
        "lessonId": "__direct_component__",
        "lessonTitle": "__direct_component__",
        "packName": "__direct_component__",
        "unitName": "__direct_component__",
    }
    validate_select(wrapped, errors)


def validate_matching_component(component: dict[str, Any], errors: list[str]) -> None:
    require(component.get("type") == "matching_question", errors, "type must be matching_question")
    require(isinstance(component.get("componentId"), str) and bool(component.get("componentId")), errors, "componentId is required")
    content = component.get("content")
    require(isinstance(content, dict), errors, "content must be an object")
    if not isinstance(content, dict):
        return
    unsupported_render_keys = sorted(find_keys(content, UNSUPPORTED_MATCHING_RENDER_KEYS))
    require(
        not unsupported_render_keys,
        errors,
        f"matching component contains unsupported render-control keys: {unsupported_render_keys}",
    )
    questions = content.get("questions")
    require(isinstance(questions, list) and bool(questions), errors, "content.questions must be a non-empty list")
    if "correctButtonText" in content:
        require(isinstance(content.get("correctButtonText"), str), errors, "content.correctButtonText must be a string")
    if not isinstance(questions, list):
        return
    for q_index, question in enumerate(questions):
        q_path = f"content.questions[{q_index}]"
        require(isinstance(question, dict), errors, f"{q_path} must be an object")
        if not isinstance(question, dict):
            continue
        require(isinstance(question.get("id"), str) and bool(question.get("id")), errors, f"{q_path}.id is required")
        require(isinstance(question.get("stem"), str) and bool(question.get("stem")), errors, f"{q_path}.stem is required")
        if "explanation" in question:
            require(isinstance(question.get("explanation"), str), errors, f"{q_path}.explanation must be a string")
        pairs = question.get("pairs")
        require(isinstance(pairs, list) and bool(pairs), errors, f"{q_path}.pairs must be a non-empty list")
        if not isinstance(pairs, list):
            continue
        left_labels: dict[str, str] = {}
        right_labels: set[str] = set()
        left_option_paths: dict[str, str] = {}
        right_option_paths: dict[str, str] = {}
        for pair_index, pair in enumerate(pairs):
            pair_path = f"{q_path}.pairs[{pair_index}]"
            require(isinstance(pair, dict), errors, f"{pair_path} must be an object")
            if not isinstance(pair, dict):
                continue
            for key in ("id", "left", "right"):
                require(isinstance(pair.get(key), str) and bool(pair.get(key)), errors, f"{pair_path}.{key} is required")
            left = pair.get("left")
            right = pair.get("right")
            if isinstance(left, str):
                normalized_left = normalize_matching_option_text(left)
                if normalized_left:
                    first_left_path = left_option_paths.get(normalized_left)
                    require(
                        first_left_path is None,
                        errors,
                        f"{pair_path}.left duplicates visible matching option text from {first_left_path}",
                    )
                    if first_left_path is None:
                        left_option_paths[normalized_left] = f"{pair_path}.left"
                left_match = re.match(r"^\s*(\d+)\s*[.．、:：]\s*", left)
                if left_match and isinstance(right, str):
                    left_labels[left_match.group(1)] = right
            if isinstance(right, str):
                normalized_right = normalize_matching_option_text(right)
                if normalized_right:
                    first_right_path = right_option_paths.get(normalized_right)
                    require(
                        first_right_path is None,
                        errors,
                        f"{pair_path}.right duplicates visible matching option text from {first_right_path}",
                    )
                    if first_right_path is None:
                        right_option_paths[normalized_right] = f"{pair_path}.right"
                right_match = re.match(r"^\s*([A-Z])\s*[.．、:：]\s*", right)
                if right_match:
                    right_labels.add(right_match.group(1))

        explanation = question.get("explanation")
        if not isinstance(explanation, str):
            continue
        for left_label, right_label in re.findall(r"(\d+)\s*[—–-]\s*([A-Z])", explanation):
            require(
                left_label in left_labels,
                errors,
                f"{q_path}.explanation references left label {left_label} but no pair.left displays it",
            )
            require(
                right_label in right_labels,
                errors,
                f"{q_path}.explanation references right label {right_label} but no pair.right displays it",
            )
            pair_right = left_labels.get(left_label)
            if isinstance(pair_right, str):
                pair_right_match = re.match(r"^\s*([A-Z])\s*[.．、:：]\s*", pair_right)
                require(
                    bool(pair_right_match and pair_right_match.group(1) == right_label),
                    errors,
                    f"{q_path}.explanation mapping {left_label}—{right_label} does not match the pair data",
                )


def validate_categorization_component(component: dict[str, Any], errors: list[str]) -> None:
    require(component.get("type") == "categorization_question", errors, "type must be categorization_question")
    require(isinstance(component.get("componentId"), str) and bool(component.get("componentId")), errors, "componentId is required")
    content = component.get("content")
    require(isinstance(content, dict), errors, "content must be an object")
    if not isinstance(content, dict):
        return
    questions = content.get("questions")
    require(isinstance(questions, list) and bool(questions), errors, "content.questions must be a non-empty list")
    if "instruction" not in content:
        errors.append("content.instruction is required and must be an empty string")
    else:
        require(content.get("instruction") == "", errors, "content.instruction must be an empty string")
    if "nextButtonText" in content:
        require(isinstance(content.get("nextButtonText"), str), errors, "content.nextButtonText must be a string")
    if "finishButtonText" in content:
        require(isinstance(content.get("finishButtonText"), str), errors, "content.finishButtonText must be a string")
    if not isinstance(questions, list):
        return
    for q_index, question in enumerate(questions):
        q_path = f"content.questions[{q_index}]"
        require(isinstance(question, dict), errors, f"{q_path} must be an object")
        if not isinstance(question, dict):
            continue
        require(isinstance(question.get("id"), str) and bool(question.get("id")), errors, f"{q_path}.id is required")
        require(isinstance(question.get("stem"), str) and bool(question.get("stem")), errors, f"{q_path}.stem is required")
        if "explanation" in question:
            require(isinstance(question.get("explanation"), str), errors, f"{q_path}.explanation must be a string")
        groups = question.get("groups")
        require(isinstance(groups, list) and len(groups) >= 2, errors, f"{q_path}.groups must contain at least 2 groups")
        if not isinstance(groups, list):
            continue
        for group_index, group in enumerate(groups):
            group_path = f"{q_path}.groups[{group_index}]"
            require(isinstance(group, dict), errors, f"{group_path} must be an object")
            if not isinstance(group, dict):
                continue
            require(isinstance(group.get("name"), str) and bool(group.get("name")), errors, f"{group_path}.name is required")
            if "desc" in group:
                require(isinstance(group.get("desc"), str), errors, f"{group_path}.desc must be a string")
            options = group.get("options")
            require(isinstance(options, list) and bool(options), errors, f"{group_path}.options must be a non-empty list")
            if isinstance(options, list):
                require(all(isinstance(option, str) and bool(option) for option in options), errors, f"{group_path}.options must contain strings")


def validate_ordering_component(component: dict[str, Any], errors: list[str]) -> None:
    require(component.get("type") == "ordering_question", errors, "type must be ordering_question")
    require(isinstance(component.get("componentId"), str) and bool(component.get("componentId")), errors, "componentId is required")
    content = component.get("content")
    require(isinstance(content, dict), errors, "content must be an object")
    if not isinstance(content, dict):
        return
    questions = content.get("questions")
    require(isinstance(questions, list) and bool(questions), errors, "content.questions must be a non-empty list")
    if "nextButtonText" in content:
        require(isinstance(content.get("nextButtonText"), str), errors, "content.nextButtonText must be a string")
    if "finishButtonText" in content:
        require(isinstance(content.get("finishButtonText"), str), errors, "content.finishButtonText must be a string")
    if not isinstance(questions, list):
        return
    for q_index, question in enumerate(questions):
        q_path = f"content.questions[{q_index}]"
        require(isinstance(question, dict), errors, f"{q_path} must be an object")
        if not isinstance(question, dict):
            continue
        require(isinstance(question.get("id"), str) and bool(question.get("id")), errors, f"{q_path}.id is required")
        require(isinstance(question.get("stem"), str) and bool(question.get("stem")), errors, f"{q_path}.stem is required")
        if "instruction" not in question:
            errors.append(f"{q_path}.instruction is required and must be an empty string")
        else:
            require(question.get("instruction") == "", errors, f"{q_path}.instruction must be an empty string")
        if "explanation" in question:
            require(isinstance(question.get("explanation"), str), errors, f"{q_path}.explanation must be a string")
        items = question.get("items")
        require(isinstance(items, list) and len(items) >= 2, errors, f"{q_path}.items must contain at least 2 items")
        if not isinstance(items, list):
            continue
        for item_index, item in enumerate(items):
            item_path = f"{q_path}.items[{item_index}]"
            require(isinstance(item, dict), errors, f"{item_path} must be an object")
            if not isinstance(item, dict):
                continue
            require(isinstance(item.get("id"), str) and bool(item.get("id")), errors, f"{item_path}.id is required")
            require(isinstance(item.get("name"), str) and bool(item.get("name")), errors, f"{item_path}.name is required")
            if "desc" in item:
                require(isinstance(item.get("desc"), str), errors, f"{item_path}.desc must be a string")


def validate_wrapped_component(obj: dict[str, Any], errors: list[str]) -> bool:
    component = obj.get("componentData")
    if not isinstance(component, dict):
        return False
    component_type = obj.get("componentType") or obj.get("componentKey")
    if component_type == "galaxy_select_question":
        validate_select(obj, errors)
    elif component_type in {"matching_question", "MatchingQuestionSet"}:
        validate_matching_component(component, errors)
    elif component_type in {"categorization_question", "CategorizationQuestionSet"}:
        validate_categorization_component(component, errors)
    elif component_type == "ordering_question":
        validate_ordering_component(component, errors)
    else:
        errors.append(f"unsupported componentType: {component_type}")
    return True


def validate_obj(obj: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    forbidden = find_forbidden_keys(obj)
    require(not forbidden, errors, f"forbidden keys found: {forbidden}")

    if obj.get("type") in DIRECT_COMPONENT_TYPES and "componentType" not in obj:
        validate_standalone_envelope(obj, errors)

    if obj.get("type") == "galaxy_select_question" and "componentType" not in obj:
        validate_select_component(obj, errors)
        return errors
    if obj.get("type") == "categorization_question" and "componentType" not in obj:
        validate_categorization_component(obj, errors)
        return errors
    if obj.get("type") == "matching_question" and "componentType" not in obj:
        validate_matching_component(obj, errors)
        return errors
    if obj.get("type") == "ordering_question" and "componentType" not in obj:
        validate_ordering_component(obj, errors)
        return errors

    missing = sorted(REQUIRED_WRAPPER_KEYS - set(obj.keys()))
    require(not missing, errors, f"missing wrapper keys: {missing}")

    if not validate_wrapped_component(obj, errors):
        errors.append("componentData must be present for wrapped component JSON")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path, help="Markdown files to validate")
    parser.add_argument("--glob", default="lesson*_question_production_pilot_20260626/final/lesson*_题目汇总.md")
    parser.add_argument(
        "--stage3-contract",
        action="store_true",
        help="also require paired natural-language and JSON evidence for every question",
    )
    args = parser.parse_args()

    paths = args.paths or sorted(Path.cwd().glob(args.glob))
    if not paths:
        print("No files found.", file=sys.stderr)
        return 2

    total_blocks = 0
    failed = 0
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if args.stage3_contract or path.name == "question_processed_full.md":
            document_errors = validate_stage3_document_text(text, path)
            if document_errors:
                failed += 1
                print(f"FAIL {path}: stage3 document contract")
                for error in document_errors:
                    print(f"  - {error}")
        blocks = iter_json_blocks(path)
        total_blocks += len(blocks)
        for line_no, raw in blocks:
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError as exc:
                failed += 1
                print(f"FAIL {path}:{line_no}: invalid JSON: {exc}")
                continue
            errors = validate_obj(obj)
            if errors:
                failed += 1
                print(f"FAIL {path}:{line_no}: {obj.get('questionId', '<unknown>')}")
                for error in errors:
                    print(f"  - {error}")

    if failed:
        print(f"Checked {len(paths)} files, {total_blocks} JSON blocks, {failed} failed.")
        return 1
    print(f"PASS: checked {len(paths)} files, {total_blocks} JSON blocks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
