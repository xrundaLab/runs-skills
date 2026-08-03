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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ONESHOTS = ROOT / "templates" / "oneshots"
TASK_DEMO = ROOT / "templates" / "demos" / "post_class_task_demo.html"
OUTER_ONESHOT = ONESHOTS / "02_整课JSON_完整外层OneShot.md"
TASK_CONTRACT = "RunS-PostClassTask-Compact-Direct-OneShot-Contract-v1.8-20260727"
SOP_CONTRACT_VERSION = "RunS_V3.5.0-S1-S6-R36-20260731"

FIXED = {
    "课程开篇": ("course_intro", "05_课程开篇页_固定模板OneShot.md", "COURSE_INTRO_VARIABLES", "RunS-CourseIntro-FixedTemplate-OneShot-v1.8", "c7f141cceb38443b086d6e2d47b309bc67ab2ff3f97b401c62b07beee96c55c6", "ba53ef84a86f7286839c8027460714906c1048849fd1d9c1403fe4bc555dfb89", "070cf9823d34755856019e88d0cd24c64d1c17e6f0535776a08b1a4945cca8e3"),
    "场景引入": ("scene_intro", "06_场景引入页_固定模板OneShot.md", "SCENE_INTRO_VARIABLES", "RunS-SceneIntro-FixedTemplate-OneShot-v1.5", "01283ebc5662402ed4553d65aba1c633107c63e9dd907802ba13bd4e4097f095", "0b746794a30a826b376ce6992b9fd896d3ead1a76d93b4d93540ee6eff13973a", "edd32ece1d155f5b727a5c8e0c7f1cd91228d5e9bded49b2ebf0d72364c0d94c"),
    "课程小结": ("course_summary", "04_课程小结页_固定模板OneShot.md", "COURSE_SUMMARY_VARIABLES", "RunS-CourseSummary-FixedTemplate-OneShot-v1.10", "247a1e348a80994746ba42be467d86e85072c2106ad48e293e9ca1d6df2e55c1", "4fe01113b7712686f01406dde73b98b22ec9bc10776330166f72209d6f4cdec3", "da54febaa5b03f21a1e0c5dfefa375c2a88465ce82cc87d5ddb3ffeddd487f9a"),
}
DYNAMIC = {
    "知识讲解": ("knowledge_explanation", "07_知识讲解页_动态生成OneShot.md", "RunS-Knowledge-Dynamic-OneShot-v1.13", "9c20c5b6dff48fbe2a13d53aaa52c0946e8815b3bf61a097cf0b299d9d6f0233"),
    "案例分析": ("case_analysis", "08_案例分析页_动态生成OneShot.md", "RunS-CaseAnalysis-Dynamic-OneShot-v1.12", "20452514917bbc1bbe7eed1460e66177cdffec2188e16892af800c92108f7d53"),
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

def prompt_version(kind, lesson_id, page_no):
    return f"RunS-{kind}-{lesson_id}-{page_no}-OneShot-R36-20260731"

def rebind_page_context(prompt, context):
    line = (
        f"适用页面：{context['lesson_id']}｜{context['page_no']}｜"
        f"第 {context['page_index']}/{context['page_count']} 页｜{context['page_label']}页。"
    )
    prompt, count = re.subn(r"适用页面：[^\n]+", line, prompt, count=1)
    if count != 1:
        raise ValueError("PROMPT_PAGE_CONTEXT_NOT_FOUND")
    return prompt

def prompt_from_asset(filename, variable, values, version, context):
    prompt = text_block(filename)
    prompt = re.sub(r"提示词版本号：[^\n]+", f"提示词版本号：{version}", prompt, count=1)
    prompt = rebind_page_context(prompt, context)
    replacement = f"const {variable} = Object.freeze({canonical(values)});"
    prompt, count = re.subn(rf"const\s+{variable}\s*=\s*Object\.freeze\(\{{.*?\}}\);", lambda _: replacement, prompt, count=1, flags=re.S)
    if count != 1:
        raise ValueError(f"VARIABLE_REGION_NOT_FOUND:{variable}")
    return prompt

def intro_values(page, action):
    content = page.get("content")
    if not isinstance(content, dict):
        raise ValueError("COURSE_INTRO_CONTENT_MISSING")
    points = content.get("knowledgePoints")
    if isinstance(points, str):
        points = [re.sub(r"^\s*\d+[.、]\s*", "", line).strip() for line in points.splitlines() if line.strip()]
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
    recipes = []
    if non_heading:
        recipes.append({
            "recipe": "intro_observation_band",
            "groupId": group_ids[0] if group_ids else None,
            "source": "first_real_reading_group",
        })
    if ordered_list_indexes or unordered_list_indexes:
        recipes.append({
            "recipe": "list_or_option_compact",
            "blockIndexes": ordered_list_indexes + unordered_list_indexes,
            "source": "frozen_list_blocks",
        })
    elif brief.get("contentShape") == "process_or_sequence" and len(non_heading) >= 3:
        recipes.append({
            "recipe": "sequence_compact",
            "groupId": group_ids[1] if len(group_ids) > 1 else None,
            "source": "frozen_process_relationship",
        })
    if len(non_heading) >= 2:
        recipes.append({
            "recipe": "analysis_conclusion_emphasis",
            "groupId": group_ids[-1] if group_ids else None,
            "source": "last_real_reading_group",
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
        "visibleRecipeDifferenceContract": {
            "required": len(recipes) >= 2,
            "minimumDistinctTreatments": 2,
            "forbid": ["sameWhiteCardStack", "positionOnlyDifferentiation"],
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
    return data

def dynamic_prompt_from_asset(filename, page_data, design_brief, version, context):
    prompt = text_block(filename)
    prompt = re.sub(r"提示词版本号：[^\n]+", f"提示词版本号：{version}", prompt, count=1)
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
    allowed = {"paragraph", "task", "facts", "step", "prompt", "decision", "safety", "fallback"}
    if any(not isinstance(x, dict) or x.get("type") not in allowed for x in sections):
        raise ValueError("POST_CLASS_TASK_SECTIONS_INVALID")
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

def task_html(title, sections, action):
    demo = TASK_DEMO.read_text(encoding="utf-8")
    prefix = demo.split("  <script>", 1)[0]
    prefix = prefix.replace('<h1 id="taskTitle"></h1>', f'<h1 id="taskTitle">{esc(title)}</h1>')
    prefix = prefix.replace('>完成任务</button>', f'>{"完成学习" if action == "complete" else "继续学习"}</button>')
    chunks, support, action_chunks = [], [], []
    for index, block in enumerate(sections):
        typ, text = block["type"], block.get("text", "")
        if typ == "paragraph": chunks.append(f'<p class="task-intro">{esc(text)}</p>')
        elif typ == "task": chunks.append(f'<section class="glass-card task-card"><div class="card-heading"><span class="card-symbol">✓</span><h2>{esc(block.get("label", "任务"))}</h2></div><p>{esc(text)}</p></section>')
        elif typ == "facts":
            items = block.get("items")
            # S5 has two governed facts shapes: an explicit item list or one
            # frozen fact paragraph.  Both are source-preserving; the latter
            # is a single list item, not a reason to invent a new split.
            if not isinstance(items, list) or not items:
                items = [text] if isinstance(text, str) and text.strip() else []
            if not all(isinstance(item, str) and item.strip() for item in items):
                raise ValueError("POST_CLASS_TASK_FACTS_INVALID")
            chunks.append(f'<section class="glass-card facts-card"><div class="card-heading"><span class="card-symbol">•</span><h2>{esc(block.get("label", "可靠信息"))}</h2></div><ul class="facts-grid">' + "".join(f"<li>{esc(item)}</li>" for item in items) + "</ul></section>")
        elif typ == "step":
            next_block = sections[index + 1] if index + 1 < len(sections) else None
            prompt = next_block if isinstance(next_block, dict) and next_block.get("type") == "prompt" else None
            inner = f'<p class="step-lead">{esc(text)}</p>'
            if prompt: inner += f'<div class="prompt-block"><div class="prompt-label">{esc(prompt.get("label") or prompt.get("promptLabel") or "PROMPT")}</div><pre><code>{esc(prompt.get("text", ""))}</code></pre></div>'
            action_chunks.append(f'<article class="step-group"><span class="step-index">{esc(block.get("stepNumber") or str(len(action_chunks)+1).zfill(2))}</span><section class="glass-card step-card">{inner}</section></article>')
        elif typ == "prompt":
            previous = sections[index - 1] if index else None
            if not isinstance(previous, dict) or previous.get("type") != "step":
                action_chunks.append(f'<article class="step-group"><span class="step-index">{str(len(action_chunks)+1).zfill(2)}</span><section class="glass-card step-card"><div class="prompt-block"><div class="prompt-label">{esc(block.get("label") or block.get("promptLabel") or "PROMPT")}</div><pre><code>{esc(text)}</code></pre></div></section></article>')
        elif typ == "decision": chunks.append(f'<section class="glass-card decision-card"><div class="card-heading"><span class="card-symbol">?</span><h2>检查与决定</h2></div><p>{esc(text)}</p></section>')
        else: support.append(f'<div class="support-row" data-support-type="{typ}"><span class="support-mark">{"!" if typ == "safety" else "↗"}</span><p class="support-copy">{esc(text)}</p></div>')
    if action_chunks: chunks.append('<section class="action-section"><div class="action-title"><h2>开始行动</h2></div>' + "".join(action_chunks) + '</section>')
    if support: chunks.append('<section class="support-stack">' + "".join(support) + '</section>')
    content = "".join(chunks)
    prefix = prefix.replace('<section class="task-content" id="taskContent" aria-label="课后任务内容"></section>', f'<section class="task-content" id="taskContent" aria-label="课后任务内容">{content}</section>')
    handler = "safeComplete" if action == "complete" else "safeNextPage"
    return prefix + f'''  <script>
function safeNextPage() {{ if (window.CreatorReviewSDK && (!CreatorReviewSDK.isAvailable || CreatorReviewSDK.isAvailable()) && typeof CreatorReviewSDK.nextPage === "function") CreatorReviewSDK.nextPage(); }}
function safeComplete() {{ if (window.CreatorReviewSDK && (!CreatorReviewSDK.isAvailable || CreatorReviewSDK.isAvailable()) && typeof CreatorReviewSDK.complete === "function") CreatorReviewSDK.complete(); }}
function syncFooterReserve() {{ const footer=document.querySelector(".task-footer"); if (footer) document.documentElement.style.setProperty("--footer-h", Math.ceil(footer.getBoundingClientRect().height || 92) + "px"); }}
syncFooterReserve(); if ("ResizeObserver" in window) new ResizeObserver(syncFooterReserve).observe(document.querySelector(".task-footer")); window.addEventListener("resize", syncFooterReserve, {{passive:true}}); document.getElementById("taskButton").addEventListener("click", {handler});
  </script>\n</body>\n</html>'''

def task_prompt(page, lesson_id, action, page_index, page_count):
    sections = task_sections(page)
    content = page.get("content")
    title = content.get("taskTitle") if isinstance(content, dict) else None
    if not isinstance(title, str) or not title.strip():
        raise ValueError("POST_CLASS_TASK_TITLE_MISSING")
    version = prompt_version("PostClassTask", lesson_id, page["page_no"])
    document = task_html(title, sections, action)
    return f'''提示词版本号：{version}

适用页面：{lesson_id}｜{page["page_no"]}｜第 {page_index}/{page_count} 页｜课后任务页。

这是一次性完整 Compact-OneShot，没有任何外部上下文。当前合同：{TASK_CONTRACT}。学生正文已按冻结 sections 预编译为静态富卡片 DOM；不得改写、删减、调序或用 JavaScript 重建正文。

最终回复必须且只能包含下方从 <!doctype html> 到 </html> 的完整 HTML，不得输出解释、Markdown 围栏、版本说明、提示词正文、PAGE_DATA 或字段名。

请原样输出下方完整代码：

{document}''', version

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
    result = []
    try:
        for i, page in enumerate(pages):
            typ, no = page.get("page_type"), page.get("page_no"); action = "complete" if i == len(pages) - 1 else "nextpage"
            base = {"page_no": no, "tag": page.get("capsule"), "title": typ, "summary": "S5 frozen effective-content projection", "sdk_action": action, "is_last_page": i == len(pages)-1, "page_data": {"source_block_ids": page.get("source_block_ids"), "effective_content_sha256": digest(page.get("effective_content")), "assembly_mode": "model_oneshot_prompt_control", "expected_model_output": "pure_complete_html", "model_output_status": "NOT_GENERATED", "whole_course_oneshot": OUTER_ONESHOT.name}}
            if typ == "互动题目": base.update(page_kind="question_component_page", runtime_type="component", prompt="", components=[page.get("effective_content")]); result.append(base); continue
            if typ == "课后任务":
                prompt, version = task_prompt(page, args.lesson_id, "complete" if action == "complete" else "next", i + 1, len(pages))
                base["page_data"].update(route="compact_direct_oneshot", oneshot_contract_version=TASK_CONTRACT, prompt_version=version)
                base.update(page_kind="post_class_task", runtime_type="html", components=[], prompt=prompt); result.append(base); continue
            if typ in DYNAMIC:
                kind, filename, contract, sha = DYNAMIC[typ]; brief = page.get("design_brief")
                if not isinstance(brief, dict) or brief.get("nonRenderable") is not True: raise ValueError(f"DYNAMIC_DESIGN_BRIEF_INVALID:{no}")
                pdata = dynamic_page_data(page, args.lesson_id, i+1, len(pages), kind, "complete" if action == "complete" else "next")
                if kind == "case_analysis" and i+1 < len(pages): pdata["linkedQuestionPageId"] = pages[i+1].get("page_no")
                version = prompt_version(kind.replace("_", "").title(), args.lesson_id, no)
                base["page_data"].update(route="dynamic_oneshot", oneshot_contract_version=contract, oneshot_asset_sha256=sha, design_brief=brief, visualRecipePlan=pdata["visualRecipePlan"], footerContract=pdata["footerContract"], prompt_version=version)
                context = {"lesson_id": args.lesson_id, "page_no": no, "page_index": i + 1, "page_count": len(pages), "page_label": typ}
                base.update(page_kind=kind, runtime_type="html", components=[], prompt=dynamic_prompt_from_asset(filename, pdata, brief, version, context)); result.append(base); continue
            if typ not in FIXED: raise ValueError(f"UNSUPPORTED_PAGE_TYPE:{typ}")
            kind, filename, variable, contract, sha, template_sha, nonvar_sha = FIXED[typ]
            if typ == "课程开篇": values = intro_values(page, action)
            elif typ == "场景引入":
                lines = [x for x in str(page.get("source", {}).get("rawMarkdown", "")).split("\n\n") if x and not x.startswith("#")]; values = {"sceneParagraphs": lines[:-1], "lessonLead": lines[-1] if lines else "", "pageAction": "next" if action == "nextpage" else "complete"}
            else:
                values = summary_values(page, "next" if action == "nextpage" else "complete")
            version = prompt_version(kind.replace("_", "").title(), args.lesson_id, no)
            base["page_data"].update(route="fixed_template", template=variable, oneshot_contract_version=contract, oneshot_asset_sha256=sha, template_sha256=template_sha, non_variable_sha256=nonvar_sha, template_outside_variable_region_unchanged=True, prompt_version=version)
            context = {"lesson_id": args.lesson_id, "page_no": no, "page_index": i + 1, "page_count": len(pages), "page_label": typ}
            base.update(page_kind=kind, runtime_type="html", components=[], prompt=prompt_from_asset(filename, variable, values, version, context)); result.append(base)
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
    args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

if __name__ == "__main__": main()
