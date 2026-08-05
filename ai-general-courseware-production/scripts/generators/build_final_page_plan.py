#!/usr/bin/env python3
"""Deterministically merge frozen S2 pages with approved S3 question JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
VALIDATORS = SCRIPT_ROOT / "validators"
sys.path.insert(0, str(VALIDATORS))

from validate_v35_page_plan_question_boundaries import (  # noqa: E402
    ANY_JSON_FENCE_RE,
    parse_pages,
    parse_s2_page_manifest,
)


def blocked(code: str) -> "NoReturn":
    raise SystemExit(f"BLOCKED:{code}")


def render_page(
    index: int,
    page_count: int,
    manifest: dict[str, str],
    body: str,
) -> str:
    page_type = manifest["页面类型"]
    lines = [
        f"## {manifest['页号']}",
        f"- 页面类型：{page_type}",
        f"- 胶囊文案：{manifest['胶囊文案']}",
        f"- 页面动作：{'complete' if index == page_count - 1 else 'nextPage'}",
        f"- 来源块：{manifest['来源块']}",
        f"- 内容块类型：{manifest['内容块类型']}",
        f"- 布局意图：{manifest['布局意图']}",
        f"- 过渡句位置：{manifest['过渡句位置']}",
        f"- 过渡句原文：{manifest['过渡句原文']}",
    ]
    component_type = manifest.get("组件类型", "")
    if page_type == "互动题目":
        if not component_type or component_type == "无":
            blocked("S4_COMPONENT_TYPE_MISSING")
        lines.append(f"- 组件类型：{component_type}")
    return "\n".join(lines) + "\n\n### 有效内容\n\n" + body.strip()


def build(working_path: Path, question_path: Path) -> str:
    working_text = working_path.read_text(encoding="utf-8")
    question_text = question_path.read_text(encoding="utf-8")
    manifest_rows, manifest_errors = parse_s2_page_manifest(working_text)
    working_pages = parse_pages(working_text)
    question_pages = parse_pages(question_text)
    if manifest_errors or not manifest_rows:
        blocked("S2_PAGE_MANIFEST_INVALID")
    if not working_pages or len(working_pages) != len(manifest_rows):
        blocked("S2_PAGE_COUNT_MISMATCH")
    if len(question_pages) != len(working_pages):
        blocked("S3_PAGE_COUNT_MISMATCH")

    sections: list[str] = []
    for index, (manifest, working, question) in enumerate(
        zip(manifest_rows, working_pages, question_pages)
    ):
        expected_no = manifest["页号"]
        expected_type = manifest["页面类型"]
        expected_capsule = manifest["胶囊文案"]
        for page, stage in ((working, "S2"), (question, "S3")):
            if page["page_no"] != expected_no:
                blocked(f"{stage}_PAGE_ORDER_DRIFT")
            if page["page_type"] != expected_type or page["capsule"] != expected_capsule:
                blocked(f"{stage}_PAGE_METADATA_DRIFT")

        if expected_type == "互动题目":
            matches = list(ANY_JSON_FENCE_RE.finditer(question["body"]))
            if len(matches) != 1:
                blocked("S3_INTERACTION_JSON_COUNT_INVALID")
            frozen_body = working["body"].strip()
            question_body = question["body"].strip()
            if not question_body.startswith(frozen_body):
                blocked("S3_INTERACTION_NATURAL_LANGUAGE_DRIFT")
            appended = question_body[len(frozen_body) :].strip()
            required_evidence = (
                "#### 互动编号：",
                "##### 题目数据（自然语言版）",
                "##### 题目数据（JSON版）",
            )
            if any(marker not in appended for marker in required_evidence):
                blocked("S3_INTERACTION_EVIDENCE_MISSING")
            raw_json = matches[0].group(1)
            try:
                component = json.loads(raw_json)
            except json.JSONDecodeError:
                blocked("S3_INTERACTION_JSON_INVALID")
            if component.get("type") != manifest.get("组件类型"):
                blocked("S3_COMPONENT_TYPE_DRIFT")
            body = f"```json\n{raw_json}\n```"
        else:
            if question["body"].strip() != working["body"].strip():
                blocked("S3_NON_INTERACTION_BODY_DRIFT")
            body = working["body"]
        sections.append(render_page(index, len(manifest_rows), manifest, body))
    return "\n\n".join(sections) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="从冻结 S2 与已批准 S3 确定性生成 S4 page_plan_full.md"
    )
    parser.add_argument("--working-plan", required=True, type=Path)
    parser.add_argument("--question-processed", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build(args.working_plan.resolve(), args.question_processed.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
