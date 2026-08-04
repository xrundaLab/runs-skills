#!/usr/bin/env python3
"""Build protected S5 projections from frozen S4 and a constrained draft."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any


CONTRACT = "RunS_V3.5.0-S1-S6-R36-20260731"
SCRIPT_ROOT = Path(__file__).resolve().parents[1]
VALIDATORS = SCRIPT_ROOT / "validators"
sys.path.insert(0, str(VALIDATORS))

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
                candidate = blocks[index]
                text = candidate.get("text") if isinstance(candidate, dict) else None
                if (
                    candidate.get("type") != "paragraph"
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


def protected_page(plan: dict[str, str], draft: dict[str, Any]) -> dict[str, Any]:
    page = copy.deepcopy(draft)
    page_type = plan["page_type"]
    page.update(
        {
            "page_no": plan["page_no"],
            "page_type": page_type,
            "capsule": plan["capsule"],
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
        for field in ("source", "content", "sections", "display_hints"):
            page.pop(field, None)
        return page

    raw_markdown = plan["body"]
    page["source"] = {"rawMarkdown": raw_markdown}
    if page_type in {"知识讲解", "案例分析"}:
        blocks = parse_dynamic_source_blocks(raw_markdown)
        page["effective_content"] = {"blocks": blocks}
        page["content"] = {"blocks": copy.deepcopy(blocks)}
        page["sections"] = copy.deepcopy(blocks)
    elif page_type == "课程小结":
        blocks = project_summary_blocks(raw_markdown)
        page["effective_content"] = {"blocks": copy.deepcopy(blocks)}
        page["content"] = {"contentBlocks": summary_content_blocks(blocks)}
        page["sections"] = copy.deepcopy(blocks)
        page.setdefault("display_hints", {"layout": "reading"})
    return page


def build(
    lesson_id: str,
    page_plan: Path,
    draft_path: Path,
) -> dict[str, Any]:
    plans = parse_pages(page_plan.read_text(encoding="utf-8"))
    try:
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        blocked("S5_DRAFT_JSON_INVALID")
    draft_pages = draft.get("pages") if isinstance(draft, dict) else None
    if not plans or not isinstance(draft_pages, list) or len(plans) != len(draft_pages):
        blocked("S5_DRAFT_PAGE_COUNT_MISMATCH")
    if draft.get("lesson_id") not in (None, lesson_id):
        blocked("S5_DRAFT_LESSON_ID_MISMATCH")
    for plan, draft_page in zip(plans, draft_pages):
        if not isinstance(draft_page, dict):
            blocked("S5_DRAFT_PAGE_INVALID")
        if draft_page.get("page_no") not in (None, plan["page_no"]):
            blocked("S5_DRAFT_PAGE_ORDER_DRIFT")

    result = copy.deepcopy(draft)
    result["lesson_id"] = lesson_id
    result["sop_version"] = CONTRACT
    result["source_page_plan"] = str(page_plan.resolve())
    result["pages"] = [
        protected_page(plan, draft_page)
        for plan, draft_page in zip(plans, draft_pages)
    ]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="从冻结 S4 与受约束 draft 确定性生成 S5 effective_content_full.json"
    )
    parser.add_argument("--lesson-id", required=True)
    parser.add_argument("--page-plan", required=True, type=Path)
    parser.add_argument("--draft", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = build(
        args.lesson_id,
        args.page_plan.resolve(),
        args.draft.resolve(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
