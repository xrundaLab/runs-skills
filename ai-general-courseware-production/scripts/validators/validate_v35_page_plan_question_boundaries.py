#!/usr/bin/env python3
"""Validate V3.5 page-plan boundaries and final effective-plan contracts.

The checker is read-only. Short required question background stays in the
interaction page. Background longer than 50 visible characters must be placed
in an immediately preceding ``案例分析`` page whose capsule is also
``案例分析``. ``--effective-plan-contract`` additionally freezes the final
``page_plan_full.md`` against its sibling working plan and approved question
JSON source.  The current working-plan contract verifies the executor's
per-question boundary audit rather than trying to infer lesson semantics from
topic-specific wording.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_ROOT))

from page_type_contract import (  # noqa: E402
    POST_CLASS_CANONICAL_PAGE_TYPE,
    POST_CLASS_INPUT_ALIASES,
)


MARKER_RE = re.compile(
    r"^<mark>页面块\s+(P\d+)｜页面类型：([^｜<]+)(?:｜[^<]*)?</mark>\s*$",
    re.MULTILINE,
)
FINAL_PAGE_RE = re.compile(r"^##\s+(P\d+)\s*$", re.MULTILINE)
FINAL_PAGE_TYPE_RE = re.compile(r"^- 页面类型：(.+?)\s*$", re.MULTILINE)
FINAL_CAPSULE_RE = re.compile(r"^- 胶囊文案：(.+?)\s*$", re.MULTILINE)
FINAL_ACTION_RE = re.compile(r"^- 页面动作：(.+?)\s*$", re.MULTILINE)
FINAL_SOURCE_BLOCK_RE = re.compile(r"^- 来源块：(.+?)\s*$", re.MULTILINE)
FINAL_CONTENT_BLOCK_TYPE_RE = re.compile(r"^- 内容块类型：(.+?)\s*$", re.MULTILINE)
FINAL_COMPONENT_TYPE_RE = re.compile(r"^- 组件类型：(.+?)\s*$", re.MULTILINE)
FINAL_LAYOUT_INTENT_RE = re.compile(r"^- 布局意图：(.+?)\s*$", re.MULTILINE)
FINAL_TRANSITION_PLACEMENT_RE = re.compile(
    r"^- 过渡句位置：(none|before_title|after_content)\s*$",
    re.MULTILINE,
)
FINAL_TRANSITION_TEXT_RE = re.compile(r"^- 过渡句原文：(.*?)\s*$", re.MULTILINE)
FINAL_EFFECTIVE_CONTENT_RE = re.compile(r"^###\s+有效内容\s*$", re.MULTILINE)
JSON_FENCE_RE = re.compile(r"^\s*```json\s*\n(?P<json>.*?)\n```\s*$", re.DOTALL)
ANY_JSON_FENCE_RE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)
TRIAL_RE = re.compile(r"^###\s+试一试[：:]", re.MULTILINE)
QUESTION_END_RE = re.compile(r"[？?]\s*$")
INSTRUCTION_RE = re.compile(
    r"^(?:请(?:选择|判断|找出|回答|填写).+|"
    r"现在选择.+|接下来[，,]选择.+|"
    r"把.+(?:连到|分到|分类|排序)|连到最适合.+|重新选择.+|完成.+(?:连线|分类|排序))[。！？?!]*\s*$"
)
ACTION_INSTRUCTION_RE = re.compile(
    r"^(?:"
    r"(?:下面|现在).*(?:选|判断|找出|回答|填写|连到|连线|分清|分类|排序|排好|练一次|确认一下).*|"
    r"接下来[，,]?\s*请.*(?:选|判断|找出|回答|填写|连到|连线|分清|分类|排序|排好).*|"
    r".*(?:我们来|我们用一道).*(?:选|判断|找出|回答|填写|连到|连线|分清|分类|排序|排好|练一次|确认一下).*|"
    r"先来(?:选|判断|找出|回答|填写|连到|连线|分清|分类|排序|排好).*|"
    r"先用一道.*(?:确认|判断|选择|连线|分清).*|"
    r"先找出(?:这|下列|下面).*|"
    r"先分清哪些.*后面才知道.*"
    r")[。！？?!]*\s*$"
)
STEM_COMPLETION_RE = re.compile(
    r"(?:"
    r"哪些.*被保留.*哪些.*发生了变化|"
    r"更容易执行|"
    r"第一张图|"
    r"事情发生的先后|"
    r"两个片段|"
    r"太空猫.*属于哪一种情况|"
    r"三种材料.*主要作用|"
    r"根据.*目标|"
    r"必须作为变量|"
    r"海报.*关键任务缺口"
    r")"
)
MARKDOWN_PREFIX_RE = re.compile(r"^(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+|>\s*)")
MARKDOWN_NOISE_RE = re.compile(r"[\s`*_~#>\[\](){}<>-]")
LONG_BACKGROUND_LIMIT = 50
ALLOWED_PAGE_TYPES = {
    "课程开篇",
    "场景引入",
    "知识讲解",
    "案例分析",
    "互动题目",
    POST_CLASS_CANONICAL_PAGE_TYPE,
    "课程小结",
}
FINAL_REQUIRED_METADATA = {
    "page_type": "页面类型",
    "capsule": "胶囊文案",
    "action": "页面动作",
    "source_block": "来源块",
    "content_block_type": "内容块类型",
    "layout_intent": "布局意图",
}
P01_COURSE_INFO_LABELS = (
    "课包名称",
    "单元名称",
    "课程编号",
    "课程标题",
    "课程目标",
    "知识点",
)
PROHIBITED_EFFECTIVE_CONTENT_RE = re.compile(
    r"(?:互动规格（研发可见）|研发备注|研发摘要|学生版辅助调教说明|来源对照|过程说明|冲突说明)"
)
S2_AUDIT_RE = re.compile(
    r"<!--\s*S2_INTERACTION_BOUNDARY_AUDIT\s*\n(?P<table>.*?)\n\s*-->",
    re.DOTALL,
)
S2_AUDIT_COLUMNS = (
    "互动页",
    "紧邻前页",
    "删除后对象",
    "删除后操作",
    "删除后判断标准",
    "路由结论",
)
S2_AUDIT_ROUTES = {"知识页保留", "并入互动题", "案例分析前置"}
S2_INPUT_FREEZE_RE = re.compile(
    r"<!--\s*S2_INPUT_FREEZE\s*\n"
    r"source_manifest:\s*(?P<manifest>.+)\n"
    r"final_preprocessed:\s*(?P<preprocessed>.+)\n"
    r"sha256:\s*(?P<sha>[0-9a-f]{64})\s*\n-->",
    re.DOTALL,
)
S2_PAGE_MANIFEST_RE = re.compile(
    r"<!--\s*S2_PAGE_MANIFEST\s*\n(?P<table>.*?)\n\s*-->",
    re.DOTALL,
)
S2_PAGE_MANIFEST_COLUMNS = (
    "页号", "页面类型", "胶囊文案", "来源块", "内容块类型", "布局意图",
    "过渡句位置", "过渡句原文", "互动编号", "组件类型",
)
S2_SOURCE_ROUTE_MANIFEST_RE = re.compile(
    r"<!--\s*S2_SOURCE_ROUTE_MANIFEST\s*\n(?P<table>.*?)\n\s*-->",
    re.DOTALL,
)
S2_SOURCE_ROUTE_MANIFEST_COLUMNS = ("来源块", "原始类型", "路由页", "路由说明")
SOURCE_STUDENT_BODY_RE = re.compile(
    r"<!--\s*学生正文开始\s*-->(?P<body>.*?)<!--\s*学生正文结束\s*-->",
    re.DOTALL,
)
SOURCE_CONTENT_BLOCK_RE = re.compile(
    r"<!--\s*内容块开始｜内容块编号：(?P<id>[^｜\n]+)｜类型：(?P<type>[^｜\n]+?)(?:｜[^\n]*)?\s*-->"
    r"(?P<body>.*?)<!--\s*内容块结束\s*-->",
    re.DOTALL,
)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
# S1 keeps interaction specifications inside an explicitly marked, developer-only
# comment block.  They are not student-visible source and therefore must not be
# required in the S2 routed page stream.
IMPLEMENTATION_COMMENT_BLOCK_RE = re.compile(
    r"<!--\s*互动规格开始.*?-->.*?<!--\s*互动规格结束\s*-->",
    re.DOTALL,
)
S2_COMPONENT_TYPES = {
    "galaxy_select_question", "matching_question", "categorization_question", "ordering_question",
}


def parse_pages(text: str) -> list[dict[str, str]]:
    matches = list(MARKER_RE.finditer(text))
    pages: list[dict[str, str]] = []
    if matches:
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            pages.append(
                {
                    "page_no": match.group(1),
                    "page_type": match.group(2).strip(),
                    "capsule": (
                        capsule.group(1).strip()
                        if (capsule := re.search(r"｜胶囊文案：([^｜<]+)", match.group(0)))
                        else ""
                    ),
                    "body": text[match.end() : end].strip(),
                    "format": "working",
                    "action": "",
                    "source_block": "",
                    "content_block_type": "",
                    "component_type": "",
                    "layout_intent": "",
                    "transition_placement": "",
                    "transition_text": "",
                }
            )
        return pages

    final_matches = list(FINAL_PAGE_RE.finditer(text))
    for index, match in enumerate(final_matches):
        end = final_matches[index + 1].start() if index + 1 < len(final_matches) else len(text)
        section = text[match.end() : end]
        effective_match = FINAL_EFFECTIVE_CONTENT_RE.search(section)
        metadata = section[: effective_match.start()] if effective_match else section
        body = section[effective_match.end() :] if effective_match else ""
        page_type_match = FINAL_PAGE_TYPE_RE.search(metadata)
        capsule_match = FINAL_CAPSULE_RE.search(metadata)
        action_match = FINAL_ACTION_RE.search(metadata)
        source_block_match = FINAL_SOURCE_BLOCK_RE.search(metadata)
        content_block_type_match = FINAL_CONTENT_BLOCK_TYPE_RE.search(metadata)
        component_type_match = FINAL_COMPONENT_TYPE_RE.search(metadata)
        layout_intent_match = FINAL_LAYOUT_INTENT_RE.search(metadata)
        transition_placement_match = FINAL_TRANSITION_PLACEMENT_RE.search(metadata)
        transition_text_match = FINAL_TRANSITION_TEXT_RE.search(metadata)
        pages.append(
            {
                "page_no": match.group(1),
                "page_type": page_type_match.group(1).strip() if page_type_match else "",
                "capsule": capsule_match.group(1).strip() if capsule_match else "",
                "body": body.strip(),
                "format": "final",
                "action": action_match.group(1).strip() if action_match else "",
                "source_block": source_block_match.group(1).strip() if source_block_match else "",
                "content_block_type": (
                    content_block_type_match.group(1).strip() if content_block_type_match else ""
                ),
                "component_type": (
                    component_type_match.group(1).strip() if component_type_match else ""
                ),
                "layout_intent": (
                    layout_intent_match.group(1).strip() if layout_intent_match else ""
                ),
                "transition_placement": (
                    transition_placement_match.group(1).strip()
                    if transition_placement_match
                    else ""
                ),
                "transition_text": (
                    transition_text_match.group(1).strip()
                    if transition_text_match
                    else ""
                ),
            }
        )
    return pages


def student_lines(body: str) -> list[str]:
    lines: list[str] = []
    in_comment = False
    for raw in body.splitlines():
        line = raw.strip()
        if line.startswith("<!--"):
            in_comment = True
        if not in_comment and line and not line.startswith("<mark>"):
            lines.append(line)
        if line.endswith("-->"):
            in_comment = False
    return lines


def is_question_or_instruction(line: str) -> bool:
    plain = MARKDOWN_PREFIX_RE.sub("", line).strip()
    return bool(
        QUESTION_END_RE.search(plain)
        or INSTRUCTION_RE.search(plain)
        or ACTION_INSTRUCTION_RE.search(plain)
    )


def visible_character_count(lines: list[str]) -> int:
    text = "".join(MARKDOWN_PREFIX_RE.sub("", line).strip() for line in lines)
    return len(MARKDOWN_NOISE_RE.sub("", text))


def interaction_background_lines(body: str) -> list[str]:
    before_trial = body.split("### 试一试", 1)[0]
    lines = student_lines(before_trial)
    lines = [line for line in lines if not line.startswith("#")]
    if lines and is_question_or_instruction(lines[-1]):
        lines = lines[:-1]
    return lines


def case_background_lines(body: str) -> list[str]:
    return [line for line in student_lines(body) if not line.startswith("#")]


def validate(path: Path, *, legacy_boundary_heuristic: bool = True) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    pages = parse_pages(text)
    issues: list[dict[str, str]] = []
    if not pages:
        issues.append(
            {
                "issue_type": "V35_PAGE_PLAN_FORMAT_UNRECOGNIZED",
                "severity": "BLOCKER",
                "message": "未识别到工作版 <mark> 页面块或最终版 ## Pxx 页面块；不得以 0 页结果通过校验。",
            }
        )
    for page in pages:
        post_class_metadata_present = (
            page["page_type"] in POST_CLASS_INPUT_ALIASES
            or page["capsule"] in POST_CLASS_INPUT_ALIASES
        )
        if post_class_metadata_present and (
            page["page_type"] != POST_CLASS_CANONICAL_PAGE_TYPE
            or page["capsule"] != POST_CLASS_CANONICAL_PAGE_TYPE
        ):
            issues.append(
                {
                    "issue_type": "POST_CLASS_PAGE_LABEL_NOT_CANONICAL",
                    "severity": "BLOCKER",
                    "page_no": page["page_no"],
                    "message": "拓展练习页的页面类型与胶囊文案必须统一为“拓展练习”；课后任务/课后练习只作为教师源输入别名。",
                }
            )
        elif page["page_type"] not in ALLOWED_PAGE_TYPES:
            issues.append(
                {
                    "issue_type": "PAGE_PLAN_UNSUPPORTED_PAGE_TYPE",
                    "severity": "BLOCKER",
                    "page_no": page["page_no"],
                    "message": "页面类型必须属于当前 R23 七类正式页面类型。",
                }
            )
    if legacy_boundary_heuristic:
        for current, following in zip(pages, pages[1:]):
            if current["page_type"] != "知识讲解" or following["page_type"] != "互动题目":
                continue
            if following["format"] == "working" and not TRIAL_RE.search(following["body"]):
                continue
            lines = student_lines(current["body"])
            if not lines:
                continue
            last = lines[-1]
            if is_question_or_instruction(last):
                plain_last = MARKDOWN_PREFIX_RE.sub("", last).strip()
                if ACTION_INSTRUCTION_RE.search(plain_last):
                    if not STEM_COMPLETION_RE.search(plain_last):
                        continue
                    issues.append(
                        {
                            "issue_type": "V35_INTERACTION_STEM_SPLIT_ACROSS_PAGES",
                            "severity": "BLOCKER",
                            "knowledge_page": current["page_no"],
                            "interaction_page": following["page_no"],
                            "background_visible_chars": "0",
                            "evidence": last,
                            "message": "上一页末句是下一道题的具体作答动作，不是知识过渡；应只把互动页起点前移到该句之前，保持原文和行文顺序不变。",
                        }
                    )
                    continue
                background_lines = [line for line in lines[:-1] if not line.startswith("#")]
                background_count = visible_character_count(background_lines)
                if background_count > LONG_BACKGROUND_LIMIT:
                    issues.append(
                        {
                            "issue_type": "V35_LONG_QUESTION_BACKGROUND_ROUTE_INVALID",
                            "severity": "BLOCKER",
                            "knowledge_page": current["page_no"],
                            "interaction_page": following["page_no"],
                            "background_visible_chars": str(background_count),
                            "evidence": last,
                            "message": "知识页实际承载超过50字的题目背景并以作答指令结束；应改为紧邻互动题的“案例分析”页，并把作答指令移入互动题。",
                        }
                    )
                    continue
                issues.append(
                    {
                        "issue_type": "V35_INTERACTION_STEM_SPLIT_ACROSS_PAGES",
                        "severity": "BLOCKER",
                        "knowledge_page": current["page_no"],
                        "interaction_page": following["page_no"],
                        "background_visible_chars": str(background_count),
                        "evidence": last,
                        "message": "知识页以作答问句或操作指令结束，下一页才出现对应试一试题块；应按原顺序合并为同一互动题页。",
                    }
                )

    for index, page in enumerate(pages):
        transition_placement = page.get("transition_placement", "")
        transition_text = page.get("transition_text", "")
        if transition_placement != "none" and (transition_placement or transition_text):
            lines = student_lines(page["body"])
            expected_edge = (
                lines[0]
                if transition_placement == "before_title" and lines
                else lines[-1]
                if transition_placement == "after_content" and lines
                else None
            )
            if (
                page["page_type"] != "知识讲解"
                or transition_placement not in {"before_title", "after_content"}
                or not transition_text
                or page["body"].count(transition_text) != 1
                or expected_edge != transition_text
            ):
                issues.append(
                    {
                        "issue_type": "V35_KNOWLEDGE_TRANSITION_INVALID",
                        "severity": "BLOCKER",
                        "page_no": page["page_no"],
                        "message": "过渡句元数据必须逐字匹配知识页有效内容，并按 before_title / after_content 位于页面首尾。",
                    }
                )

        if (
            legacy_boundary_heuristic
            and
            page["format"] == "working"
            and page["page_type"] == "互动题目"
            and TRIAL_RE.search(page["body"])
        ):
            background_count = visible_character_count(interaction_background_lines(page["body"]))
            if background_count > LONG_BACKGROUND_LIMIT:
                issues.append(
                    {
                        "issue_type": "V35_LONG_QUESTION_BACKGROUND_ROUTE_INVALID",
                        "severity": "BLOCKER",
                        "interaction_page": page["page_no"],
                        "background_visible_chars": str(background_count),
                        "message": "互动题的必要背景超过50字；应保持原文顺序，将背景单独规划为紧邻本题之前的“案例分析”页。",
                    }
                )

        if not legacy_boundary_heuristic or page["page_type"] != "案例分析":
            continue
        following = pages[index + 1] if index + 1 < len(pages) else None
        background_lines = case_background_lines(page["body"])
        background_count = visible_character_count(background_lines)
        invalid_reasons: list[str] = []
        if page["capsule"] != "案例分析":
            invalid_reasons.append("胶囊文案不是“案例分析”")
        if (
            following is None
            or following["page_type"] != "互动题目"
            or (
                following["format"] == "working"
                and not TRIAL_RE.search(following["body"])
            )
        ):
            invalid_reasons.append("下一页不是对应互动题目")
        if background_count <= LONG_BACKGROUND_LIMIT:
            invalid_reasons.append("背景不超过50字，应留在互动题干内")
        if background_lines and is_question_or_instruction(background_lines[-1]):
            invalid_reasons.append("案例分析页包含明确问句或作答指令")
        if TRIAL_RE.search(page["body"]):
            invalid_reasons.append("案例分析页包含试一试题块")
        if invalid_reasons:
            issues.append(
                {
                    "issue_type": "V35_LONG_QUESTION_BACKGROUND_ROUTE_INVALID",
                    "severity": "BLOCKER",
                    "case_page": page["page_no"],
                    "background_visible_chars": str(background_count),
                    "message": "；".join(invalid_reasons) + "。",
                }
            )
    return {
        "file": str(path),
        "status": "BLOCKED" if issues else "PASS",
        "page_count": len(pages),
        "issues": issues,
    }


def parse_s2_boundary_audit(text: str) -> tuple[list[dict[str, str]], list[str]]:
    match = S2_AUDIT_RE.search(text)
    if not match:
        return [], ["缺少 S2_INTERACTION_BOUNDARY_AUDIT 注释块"]
    rows = [line.strip() for line in match.group("table").splitlines() if line.strip()]
    if len(rows) < 3:
        return [], ["互动题边界决策表必须包含表头、分隔行和至少一条记录"]

    def cells(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    if tuple(cells(rows[0])) != S2_AUDIT_COLUMNS:
        return [], ["互动题边界决策表表头不符合当前合同"]
    if any(not re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells(rows[1])):
        return [], ["互动题边界决策表缺少合法 Markdown 分隔行"]
    audits: list[dict[str, str]] = []
    errors: list[str] = []
    for line in rows[2:]:
        values = cells(line)
        if len(values) != len(S2_AUDIT_COLUMNS):
            errors.append(f"互动题边界决策表列数错误：{line}")
            continue
        audits.append(dict(zip(S2_AUDIT_COLUMNS, values)))
    return audits, errors


def parse_markdown_table(match: re.Match[str] | None, columns: tuple[str, ...], label: str) -> tuple[list[dict[str, str]], list[str]]:
    if not match:
        return [], [f"缺少 {label} 注释块"]
    rows = [line.strip() for line in match.group("table").splitlines() if line.strip()]
    if len(rows) < 3:
        return [], [f"{label} 必须包含表头、分隔行和至少一条记录"]

    def cells(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    if tuple(cells(rows[0])) != columns:
        return [], [f"{label} 表头不符合当前合同"]
    if any(not re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells(rows[1])):
        return [], [f"{label} 缺少合法 Markdown 分隔行"]
    records: list[dict[str, str]] = []
    errors: list[str] = []
    for line in rows[2:]:
        values = cells(line)
        if len(values) != len(columns):
            errors.append(f"{label} 列数错误：{line}")
            continue
        records.append(dict(zip(columns, values)))
    return records, errors


def parse_s2_page_manifest(text: str) -> tuple[list[dict[str, str]], list[str]]:
    return parse_markdown_table(S2_PAGE_MANIFEST_RE.search(text), S2_PAGE_MANIFEST_COLUMNS, "S2_PAGE_MANIFEST")


def parse_s2_source_route_manifest(text: str) -> tuple[list[dict[str, str]], list[str]]:
    return parse_markdown_table(
        S2_SOURCE_ROUTE_MANIFEST_RE.search(text),
        S2_SOURCE_ROUTE_MANIFEST_COLUMNS,
        "S2_SOURCE_ROUTE_MANIFEST",
    )


def source_content_blocks(text: str) -> list[dict[str, str]]:
    """Read the explicitly marked student-visible blocks from frozen S1 text."""

    student_match = SOURCE_STUDENT_BODY_RE.search(text)
    student_text = student_match.group("body") if student_match else text
    return [
        {
            "source_block": match.group("id").strip(),
            "source_type": match.group("type").strip(),
            "body": match.group("body").strip(),
        }
        for match in SOURCE_CONTENT_BLOCK_RE.finditer(student_text)
    ]


def normalized_student_markdown(text: str) -> str:
    """Compare student-visible Markdown without S1/S2 implementation comments."""

    without_comments = IMPLEMENTATION_COMMENT_BLOCK_RE.sub("", text)
    without_comments = HTML_COMMENT_RE.sub("", without_comments)
    lines = [line.rstrip() for line in without_comments.splitlines()]
    collapsed = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return collapsed


def route_page_numbers(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[,，、]", value) if item.strip()]


def validate_working_plan_contract(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    pages = parse_pages(text)
    # S2 owns the only semantic decision about an interaction boundary.  The
    # audit table is evidence for that decision, not a substitute for checking
    # the actual frozen page text.
    base_report = validate(path, legacy_boundary_heuristic=True)
    issues = list(base_report["issues"])

    def add_issue(message: str, page_no: str = "") -> None:
        issue = {
            "issue_type": "V35_S2_BOUNDARY_AUDIT_INVALID",
            "severity": "BLOCKER",
            "message": message,
        }
        if page_no:
            issue["page_no"] = page_no
        issues.append(issue)

    def add_source_issue(message: str) -> None:
        issues.append(
            {
                "issue_type": "V35_S2_SOURCE_ROUTE_OR_FIDELITY_INVALID",
                "severity": "BLOCKER",
                "message": message,
            }
        )

    if not pages or any(page["format"] != "working" for page in pages):
        add_issue("S2 工作版必须统一使用 <mark> 页面块格式。")
    if pages:
        p01 = pages[0]
        if p01["page_no"] != "P01" or p01["page_type"] != "课程开篇":
            add_issue("P01 必须是课程开篇。", p01["page_no"])
        else:
            missing = [label for label in P01_COURSE_INFO_LABELS if f"{label}：" not in p01["body"]]
            if missing:
                add_issue("课程开篇缺少六项课程信息：" + "、".join(missing) + "。", "P01")

    frozen_source_blocks: list[dict[str, str]] = []
    freeze_match = S2_INPUT_FREEZE_RE.search(text)
    if not freeze_match:
        add_issue("缺少或格式错误的 S2_INPUT_FREEZE 声明。")
    else:
        manifest_path = Path(freeze_match.group("manifest").strip())
        preprocessed_path = Path(freeze_match.group("preprocessed").strip())
        declared_sha = freeze_match.group("sha")
        try:
            source_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            upstream = source_manifest["outputs"]["final_preprocessed"]
            actual_sha = hashlib.sha256(preprocessed_path.read_bytes()).hexdigest()
            if (
                str(preprocessed_path) != upstream.get("path")
                or declared_sha != upstream.get("sha256")
                or actual_sha != declared_sha
            ):
                add_issue("S2_INPUT_FREEZE 与 S1 source_manifest 或冻结文件的路径、SHA-256 不一致。")
            else:
                frozen_source_blocks = source_content_blocks(
                    preprocessed_path.read_text(encoding="utf-8")
                )
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            add_issue("S2_INPUT_FREEZE 指向的 S1 source_manifest 或 final_preprocessed 不可读取。")

    # R29 restores the pre-compression execution strategy: when S1 provides
    # explicit student content blocks, S2 must route every one before writing
    # pages and must carry their visible Markdown without summary/rewrite.
    source_routes, source_route_errors = parse_s2_source_route_manifest(text)
    if frozen_source_blocks:
        for error in source_route_errors:
            add_source_issue(error)
        expected_source_ids = [block["source_block"] for block in frozen_source_blocks]
        route_by_source: dict[str, list[dict[str, str]]] = {}
        for route in source_routes:
            source_id = route["来源块"]
            route_by_source.setdefault(source_id, []).append(route)
            if source_id not in expected_source_ids:
                add_source_issue("来源路由表包含冻结 S1 中不存在的来源块。")
                continue
            expected = next(block for block in frozen_source_blocks if block["source_block"] == source_id)
            if route["原始类型"] != expected["source_type"]:
                add_source_issue("来源路由表的原始类型必须逐字匹配冻结 S1 内容块类型。")
            if not route_page_numbers(route["路由页"]) or not route["路由说明"].strip():
                add_source_issue("来源路由表必须为每个来源块给出非空路由页和路由说明。")

        for source_id in expected_source_ids:
            if len(route_by_source.get(source_id, [])) != 1:
                add_source_issue("冻结 S1 的每个内容块必须在来源路由表中恰有一条记录。")

        pages_by_no = {page["page_no"]: page for page in pages}
        for block in frozen_source_blocks:
            routes = route_by_source.get(block["source_block"], [])
            if len(routes) != 1:
                continue
            routed_pages = route_page_numbers(routes[0]["路由页"])
            resolved_pages = [pages_by_no.get(page_no) for page_no in routed_pages]
            if any(page is None for page in resolved_pages):
                add_source_issue("来源路由表引用了不存在的页面。")
                continue
            if block["source_type"] == "开场" and not any(
                page and page["page_type"] == "场景引入" for page in resolved_pages
            ):
                add_source_issue(
                    "原始类型为“开场”的真实教学情境必须路由为场景引入页面，不能改写为知识讲解或省略。"
                )

        planned_student_stream = "\n\n".join(
            page["body"] for page in pages if page["page_type"] != "课程开篇"
        )
        source_student_stream = "\n\n".join(block["body"] for block in frozen_source_blocks)
        if normalized_student_markdown(planned_student_stream) != normalized_student_markdown(source_student_stream):
            add_source_issue(
                "S2 页面块未逐字、按原顺序完整承载冻结 S1 学生正文；不得在 S2 概括、删减、补写、重排或提前剔除干扰内容。"
            )

    page_manifest, page_manifest_errors = parse_s2_page_manifest(text)
    for error in page_manifest_errors:
        add_issue(error)
    page_manifest_by_no: dict[str, list[dict[str, str]]] = {}
    for record in page_manifest:
        page_no = record["页号"]
        page_manifest_by_no.setdefault(page_no, []).append(record)
        matching = next((page for page in pages if page["page_no"] == page_no), None)
        if matching is None:
            add_issue("页面交接清单页号不存在。", page_no)
            continue
        if record["页面类型"] != matching["page_type"] or record["胶囊文案"] != matching["capsule"]:
            add_issue("页面交接清单的页面类型或胶囊文案与页面块不一致。", page_no)
        if not record["来源块"] or not record["内容块类型"] or not record["布局意图"]:
            add_issue("页面交接清单的来源块、内容块类型和布局意图不得为空。", page_no)
        placement = record["过渡句位置"]
        transition = record["过渡句原文"]
        if placement not in {"none", "before_title", "after_content"} or (placement == "none") != (transition == "无"):
            add_issue("过渡句位置与原文必须按 none/无 或 before_title|after_content/逐字原文成对填写。", page_no)
        is_interaction = matching["page_type"] == "互动题目"
        interaction_id = record["互动编号"]
        component_type = record["组件类型"]
        if is_interaction and (interaction_id == "无" or not interaction_id or component_type not in S2_COMPONENT_TYPES):
            add_issue("互动题目必须登记稳定互动编号和四类正式组件类型。", page_no)
        if not is_interaction and (interaction_id != "无" or component_type != "无"):
            add_issue("非互动页面的互动编号和组件类型必须均为“无”。", page_no)

    for page in pages:
        if len(page_manifest_by_no.get(page["page_no"], [])) != 1:
            add_issue("每个页面块必须恰有一行页面交接清单。", page["page_no"])

    audits, errors = parse_s2_boundary_audit(text)
    for error in errors:
        add_issue(error)
    interaction_pages = {
        page["page_no"]: (index, page)
        for index, page in enumerate(pages)
        if page["format"] == "working" and page["page_type"] == "互动题目"
    }
    audits_by_page: dict[str, list[dict[str, str]]] = {}
    for audit in audits:
        page_no = audit["互动页"]
        audits_by_page.setdefault(page_no, []).append(audit)
        if page_no not in interaction_pages:
            add_issue("决策表互动页不存在，或对应页面不是互动题目。", page_no)
            continue
        index, page = interaction_pages[page_no]
        expected_previous = "无" if index == 0 else pages[index - 1]["page_no"]
        if audit["紧邻前页"] != expected_previous:
            add_issue(f"紧邻前页应为 {expected_previous}，实际为 {audit['紧邻前页']}。", page_no)
        if any(audit[column] not in {"是", "否"} for column in S2_AUDIT_COLUMNS[2:5]):
            add_issue("删除测试三项只能填写“是”或“否”。", page_no)
        route = audit["路由结论"]
        if route not in S2_AUDIT_ROUTES:
            add_issue("路由结论必须是知识页保留、并入互动题或案例分析前置。", page_no)
            continue
        all_complete = all(audit[column] == "是" for column in S2_AUDIT_COLUMNS[2:5])
        previous = pages[index - 1] if index else None
        if route == "知识页保留":
            if not all_complete:
                add_issue("知识页保留要求删除测试三项均为“是”。", page_no)
        elif route == "并入互动题":
            if all_complete:
                add_issue("并入互动题要求删除测试至少一项为“否”。", page_no)
            if previous and previous["page_type"] == "案例分析":
                add_issue("并入互动题不得以前置案例分析页作为紧邻前页。", page_no)
        else:
            if not previous or previous["page_type"] != "案例分析" or previous["capsule"] != "案例分析":
                add_issue("案例分析前置要求紧邻前页为胶囊同名的案例分析页。", page_no)
            elif visible_character_count(case_background_lines(previous["body"])) <= LONG_BACKGROUND_LIMIT:
                add_issue("案例分析前置要求实际必要背景超过 50 字。", page_no)

    for page_no, (_, page) in interaction_pages.items():
        records = audits_by_page.get(page_no, [])
        if len(records) != 1:
            add_issue("每个互动题目页面必须恰有一条边界决策记录。", page_no)
        if not TRIAL_RE.search(page["body"]):
            add_issue("互动题目页面必须包含 ### 试一试 题块。", page_no)

    return {
        "file": str(path),
        "status": "BLOCKED" if issues else "PASS",
        "page_count": len(pages),
        "issues": issues,
    }


def contains_key(value: object, forbidden_key: str) -> bool:
    if isinstance(value, dict):
        return forbidden_key in value or any(
            contains_key(child, forbidden_key) for child in value.values()
        )
    if isinstance(value, list):
        return any(contains_key(child, forbidden_key) for child in value)
    return False


def normalized_non_interaction_body(body: str) -> str:
    # S4 still preserves its frozen S2 student source.  Any authorized
    # exclusion of a pure status sentence happens only in S5 effective-content
    # projection, never by silently changing the S4 comparison target.
    return body.strip()


def validate_effective_plan_contract(
    path: Path,
    working_path: Path | None = None,
    question_path: Path | None = None,
) -> dict[str, object]:
    # S4 verifies only the deterministic projection of approved S2/S3 output.
    # Boundary semantics were decided and gated in S2; re-evaluating them here
    # would create a second, late owner for the same paging decision.
    base_report = validate(path, legacy_boundary_heuristic=False)
    pages = parse_pages(path.read_text(encoding="utf-8"))
    issues = list(base_report["issues"])
    interaction_json_blocks: list[str] = []
    component_ids: set[str] = set()

    def add_issue(issue_type: str, message: str, page_no: str = "") -> None:
        issue = {
            "issue_type": issue_type,
            "severity": "BLOCKER",
            "message": message,
        }
        if page_no:
            issue["page_no"] = page_no
        issues.append(issue)

    if pages and any(page["format"] != "final" for page in pages):
        add_issue(
            "V35_EFFECTIVE_PAGE_PLAN_CONTRACT_INVALID",
            "最终有效页面规划必须统一使用 ## Pxx 结构化格式，不得以工作版 <mark> 格式冻结。",
        )

    for index, page in enumerate(pages):
        expected_page_no = f"P{index + 1:02d}"
        if page["page_no"] != expected_page_no:
            add_issue(
                "V35_EFFECTIVE_PAGE_PLAN_CONTRACT_INVALID",
                f"页面编号必须连续；期望 {expected_page_no}，实际 {page['page_no']}。",
                page["page_no"],
            )
        for field, label in FINAL_REQUIRED_METADATA.items():
            if not page[field]:
                add_issue(
                    "V35_EFFECTIVE_PAGE_PLAN_CONTRACT_INVALID",
                    f"缺少必填页面元数据：{label}。",
                    page["page_no"],
                )
        expected_action = "complete" if index == len(pages) - 1 else "nextPage"
        if page["action"] != expected_action:
            add_issue(
                "V35_PAGE_ACTION_INVALID",
                f"页面动作应为 {expected_action}，实际为 {page['action'] or '空'}。",
                page["page_no"],
            )
        if not page["body"]:
            add_issue(
                "V35_EFFECTIVE_PAGE_PLAN_CONTRACT_INVALID",
                "### 有效内容不能为空。",
                page["page_no"],
            )
        if PROHIBITED_EFFECTIVE_CONTENT_RE.search(page["body"]):
            add_issue(
                "V35_EFFECTIVE_PAGE_PLAN_CONTRACT_INVALID",
                "有效内容含研发规格、过程说明或对照信息。",
                page["page_no"],
            )
        if page["page_type"] == "互动题目":
            if not page["component_type"]:
                add_issue(
                    "V35_EFFECTIVE_PAGE_PLAN_CONTRACT_INVALID",
                    "互动题页面必须登记组件类型。",
                    page["page_no"],
                )
            match = JSON_FENCE_RE.fullmatch(page["body"])
            if not match:
                add_issue(
                    "V35_EFFECTIVE_PAGE_PLAN_CONTRACT_INVALID",
                    "互动题 ### 有效内容只能包含一个完整 JSON 代码块，不得重复自然语言题目数据。",
                    page["page_no"],
                )
                continue
            raw_json = match.group("json")
            interaction_json_blocks.append(raw_json)
            try:
                component = json.loads(raw_json)
            except json.JSONDecodeError as exc:
                add_issue(
                    "V35_EFFECTIVE_PAGE_PLAN_CONTRACT_INVALID",
                    f"互动题 JSON 无法解析：{exc.msg}。",
                    page["page_no"],
                )
                continue
            if not isinstance(component, dict):
                add_issue(
                    "V35_EFFECTIVE_PAGE_PLAN_CONTRACT_INVALID",
                    "互动题 JSON 顶层必须是对象。",
                    page["page_no"],
                )
                continue
            if component.get("type") != page["component_type"]:
                add_issue(
                    "V35_EFFECTIVE_PAGE_PLAN_CONTRACT_INVALID",
                    "页面组件类型与题目 JSON type 不一致。",
                    page["page_no"],
                )
            component_id = component.get("componentId")
            if not isinstance(component_id, str) or not component_id:
                add_issue(
                    "V35_EFFECTIVE_PAGE_PLAN_CONTRACT_INVALID",
                    "题目 JSON 缺少非空 componentId。",
                    page["page_no"],
                )
            elif component_id in component_ids:
                add_issue(
                    "V35_EFFECTIVE_PAGE_PLAN_CONTRACT_INVALID",
                    f"componentId 重复：{component_id}。",
                    page["page_no"],
                )
            else:
                component_ids.add(component_id)
            if contains_key(component, "background"):
                add_issue(
                    "QUESTION_BACKGROUND_FIELD_FORBIDDEN",
                    "题目 JSON 禁止独立 background 字段。",
                    page["page_no"],
                )
        elif page["component_type"]:
            add_issue(
                "V35_EFFECTIVE_PAGE_PLAN_CONTRACT_INVALID",
                "非互动页面不得登记题目组件类型。",
                page["page_no"],
            )

    if pages:
        p01_body = pages[0]["body"]
        missing_labels = [
            label for label in P01_COURSE_INFO_LABELS if f"{label}：" not in p01_body
        ]
        if missing_labels:
            add_issue(
                "V35_EFFECTIVE_PAGE_PLAN_CONTRACT_INVALID",
                "P01 缺少六项课程信息：" + "、".join(missing_labels) + "。",
                pages[0]["page_no"],
            )

    working_path = working_path or path.with_name("page_plan_working_full.md")
    question_path = question_path or path.with_name("question_processed_full.md")
    if not working_path.is_file():
        add_issue(
            "V35_EFFECTIVE_PAGE_PLAN_UPSTREAM_DRIFT",
            "缺少声明的冻结 page_plan_working_full.md，无法核对页面一致性。",
        )
    else:
        working_pages = parse_pages(working_path.read_text(encoding="utf-8"))
        if len(working_pages) != len(pages):
            add_issue(
                "V35_EFFECTIVE_PAGE_PLAN_UPSTREAM_DRIFT",
                f"工作版与最终版页数不一致：{len(working_pages)} != {len(pages)}。",
            )
        for working_page, final_page in zip(working_pages, pages):
            comparable_fields = ("page_no", "page_type", "capsule")
            if any(working_page[field] != final_page[field] for field in comparable_fields):
                add_issue(
                    "V35_EFFECTIVE_PAGE_PLAN_UPSTREAM_DRIFT",
                    "页面编号、类型或胶囊与冻结工作版不一致。",
                    final_page["page_no"],
                )
            if (
                final_page["page_type"] != "互动题目"
                and normalized_non_interaction_body(working_page["body"])
                != normalized_non_interaction_body(final_page["body"])
            ):
                add_issue(
                    "V35_EFFECTIVE_PAGE_PLAN_UPSTREAM_DRIFT",
                    "非互动页面有效内容未逐字保留冻结工作版原文，或发生删除、改写、概括、补写、重排。",
                    final_page["page_no"],
                )

    if not question_path.is_file():
        add_issue(
            "V35_INTERACTION_JSON_NOT_VERBATIM",
            "缺少声明的已批准 question_processed_full.md，无法核对题目 JSON。",
        )
    else:
        approved_json_blocks = ANY_JSON_FENCE_RE.findall(
            question_path.read_text(encoding="utf-8")
        )
        remaining_approved = list(approved_json_blocks)
        for raw_json in interaction_json_blocks:
            if raw_json in remaining_approved:
                remaining_approved.remove(raw_json)
            else:
                add_issue(
                    "V35_INTERACTION_JSON_NOT_VERBATIM",
                    "最终规划中的互动题 JSON 不是上游已批准 JSON 的逐字副本。",
                )
        if len(interaction_json_blocks) != len(approved_json_blocks):
            add_issue(
                "V35_INTERACTION_JSON_NOT_VERBATIM",
                "最终规划互动题 JSON 数量与已批准题目 JSON 数量不一致。",
            )

    return {
        "file": str(path),
        "status": "BLOCKED" if issues else "PASS",
        "page_count": len(pages),
        "interaction_json_count": len(interaction_json_blocks),
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 V3.5 题干跨页拆分与超过50字的题目背景路由")
    parser.add_argument(
        "--effective-plan-contract",
        action="store_true",
        help="校验最终有效页面规划、上游工作版及已批准题目 JSON 的冻结一致性",
    )
    parser.add_argument(
        "--working-plan-contract",
        action="store_true",
        help="校验当前 S2 工作版的 P01 和逐互动题边界决策表一致性",
    )
    parser.add_argument(
        "--working-plan",
        type=Path,
        help="S4 校验时显式指定冻结的 S2 page_plan_working_full.md；省略时兼容同目录旧结构。",
    )
    parser.add_argument(
        "--question-processed",
        type=Path,
        help="S4 校验时显式指定批准的 S3 question_processed_full.md；省略时兼容同目录旧结构。",
    )
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args()
    reports: list[dict[str, object]] = []
    input_error = False
    for path in args.files:
        try:
            if not path.is_file():
                raise FileNotFoundError(path)
            if args.effective_plan_contract and args.working_plan_contract:
                raise ValueError("--effective-plan-contract 与 --working-plan-contract 不能同时使用")
            if (args.working_plan or args.question_processed) and not args.effective_plan_contract:
                raise ValueError("--working-plan / --question-processed 仅可配合 --effective-plan-contract 使用")
            validator = (
                validate_effective_plan_contract
                if args.effective_plan_contract
                else validate_working_plan_contract
                if args.working_plan_contract
                else validate
            )
            if args.effective_plan_contract:
                reports.append(
                    validate_effective_plan_contract(
                        path.resolve(),
                        args.working_plan.resolve() if args.working_plan else None,
                        args.question_processed.resolve() if args.question_processed else None,
                    )
                )
            else:
                reports.append(validator(path.resolve()))
        except (OSError, UnicodeError) as exc:
            input_error = True
            reports.append({"file": str(path), "status": "INPUT_ERROR", "issues": [], "error": str(exc)})
    blocked = any(report["status"] == "BLOCKED" for report in reports)
    status = "INPUT_ERROR" if input_error else "BLOCKED" if blocked else "PASS"
    print(json.dumps({"status": status, "reports": reports}, ensure_ascii=False, indent=2))
    if input_error:
        return 2
    return 1 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
