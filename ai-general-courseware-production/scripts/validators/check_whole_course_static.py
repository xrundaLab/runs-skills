#!/usr/bin/env python3
"""Read-only checker for V3.5 Stage 6 / formal-P3 whole-course assembly.

The historical filename is retained for indexed-asset compatibility.  Default
mode preserves the historical candidate report.  ``--formal-stage6`` reports
an assembly-only ``IMPORT_READY_STATIC`` result when there are no static
BLOCKERs.  Neither mode edits artifacts, creates a RunS task, nor declares
real-render or batch acceptance; QA, final_import, create, rendering, and
release remain later gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


EXIT_PASS = 0
EXIT_BLOCKED = 1
EXIT_INPUT_ERROR = 2
EXIT_REVIEW_REQUIRED = 3
DYNAMIC_PAGE_KINDS = {"knowledge_explanation", "case_analysis"}
OLD_FOOTER_CONTRACT = "SHORT_PAGE_BOTTOM_ALIGNED_LONG_PAGE_FLOW_END"
ONESHOT_VERSION_PREFIX = "提示词版本号："
PROMPT_VERSION_PLACEHOLDER = "__PROMPT_VERSION__"
PROMPT_VERSION_SUFFIX = "R36-20260731"
CHECKER_VERSION = "0.10.20"
POST_CLASS_TASK_ONESHOT_CONTRACT = (
    "RunS-PostClassTask-Compact-Direct-OneShot-Contract-v1.9-20260805"
)
POST_CLASS_TASK_ASSET_SHA256 = "2811205ae6b0b037f0b8160ec4dd1d9485e90e36cfe010bcf59dba55e0b616bf"
DESIGN_BRIEF_TAG_RE = re.compile(
    r"<DESIGN_BRIEF>\s*(?P<json>\{.*?\})\s*</DESIGN_BRIEF>",
    re.S,
)
PAGE_DATA_TAG_RE = re.compile(
    r"<PAGE_DATA>\s*(?P<json>\{.*?\})\s*</PAGE_DATA>",
    re.S,
)
FIXED_TEMPLATE_CONTRACTS = {
    "course_intro": {
        "variable": "COURSE_INTRO_VARIABLES",
        "contract": "RunS-CourseIntro-FixedTemplate-OneShot-v1.9",
        "oneshot_sha256": "9cf6b757e7bc635189c89d585ea65b54efbc6605c57d061726d0aac45ca6b1b8",
        "template_sha256": "48b56b0fcb700da149078b7ef95b412081bb14937334a31ef24d375d79045090",
        "non_variable_sha256": "2ad388fffc2fea884354b32429cf648ffc189cd39402c5c849b190636f463012",
    },
    "scene_intro": {
        "variable": "SCENE_INTRO_VARIABLES",
        "contract": "RunS-SceneIntro-FixedTemplate-OneShot-v1.6",
        "oneshot_sha256": "e4c2ce909288b84c2fa3ab72a273e5b0f2979c0b149a0eed233a9d6c86fa67e9",
        "template_sha256": "a5134a0e4dd526eca584009e0430372015a8fe9c0200bbbcbdc7b9772dd2876d",
        "non_variable_sha256": "8315cf8d264b68a93e58a8d5f07c639f2a698dbfe626953e8033dddb7b9578fc",
    },
    "course_summary": {
        "variable": "COURSE_SUMMARY_VARIABLES",
        "contract": "RunS-CourseSummary-FixedTemplate-OneShot-v1.11",
        "oneshot_sha256": "95f033f32583035fb846732e9092d868ede638a8aa837c9fd41bf20d1aaee142",
        "template_sha256": "52310103bf4db235c39b94f1393b6a1f8436a32794b4b42aee1580d44ee51d8c",
        "non_variable_sha256": "80570336e03205383a7a296d07b00e57d15e745b7f53f90ac6660d9221efa356",
    },
}
DYNAMIC_ONESHOT_CONTRACTS = {
    "knowledge_explanation": (
        "RunS-Knowledge-Dynamic-OneShot-v1.19",
        "71ec5e5f3aefeb37c03102eb86a04f13e7177a21fb69b27006966fe0c4576fc1",
        ("knowledge-page", "knowledge-scroll", "knowledge-footer"),
    ),
    "case_analysis": (
        "RunS-CaseAnalysis-Dynamic-OneShot-v1.18",
        "35ee30c45d3b7757b771c785039c6888584b12e3fa66fd7ed9a9c1184305f433",
        ("case-page", "case-scroll", "case-footer"),
    ),
}

# 已生成的 R10 课件保持历史可读；新课件必须走上方 R11 合同。
DYNAMIC_ONESHOT_LEGACY_CONTRACTS = {
    "knowledge_explanation": {
        ("RunS-Knowledge-Dynamic-OneShot-v1.18", "93f6ff5857c2460a6c5e2f7d99f4e017f5ecb0307b53123f06ab7a53a00afaea"),
        ("RunS-Knowledge-Dynamic-OneShot-v1.17", "8275dd65992a8e9cbcb163855468d573e2b4c08c332a164bd7d3e593b8ccc29f"),
        ("RunS-Knowledge-Dynamic-OneShot-v1.16", "987e4c7445f39ad44bff82264c8577ef5d66bf2eadf631c39628a899373c7545"),
        ("RunS-Knowledge-Dynamic-OneShot-v1.15", "d97501da9f3a4b9b91d3a67bdf8d7883dfe6ee16f7b7168a8e127424bad8aa5a"),
        ("RunS-Knowledge-Dynamic-OneShot-v1.14", "c564a5bec17ee8bdf4dc0b9d25be1f4c3f4b50f75398db7741bcdc6783573f95"),
        ("RunS-Knowledge-Dynamic-OneShot-v1.13", "9c20c5b6dff48fbe2a13d53aaa52c0946e8815b3bf61a097cf0b299d9d6f0233"),
        ("RunS-Knowledge-Dynamic-OneShot-v1.6", "8b45852a7a50081caf3aeddbce15e3f7e703139340081af81bf610ae1b2575e6"),
    },
    "case_analysis": {
        ("RunS-CaseAnalysis-Dynamic-OneShot-v1.17", "405debf25f1d0b4a695d863782faa5896692afbd1b2f1a667a0e490c7d54b11e"),
        ("RunS-CaseAnalysis-Dynamic-OneShot-v1.16", "a99dc0833a25b64aa700ec70be6ee6117c8a2e1e745bf3b9c3808a1b1067ef61"),
        ("RunS-CaseAnalysis-Dynamic-OneShot-v1.15", "2f6cb159a32110bcc7b53662334c55272bca07da84584d904826decc5385f6c7"),
        ("RunS-CaseAnalysis-Dynamic-OneShot-v1.14", "c7c69986b18dc687d702a32b66ee90680613bee318e2f7f7eb39fc170873fb72"),
        ("RunS-CaseAnalysis-Dynamic-OneShot-v1.13", "4aaf49c5baffe6260c20ca7fa7562112301f8f4e830693204e43aa5240c2b4c0"),
        ("RunS-CaseAnalysis-Dynamic-OneShot-v1.12", "20452514917bbc1bbe7eed1460e66177cdffec2188e16892af800c92108f7d53"),
        ("RunS-CaseAnalysis-Dynamic-OneShot-v1.7", "c5af21a739f1801dbc5e66148c2b90f905fc9c0436fa728abdda9ce15391cc27"),
        ("RunS-CaseAnalysis-Dynamic-OneShot-v1.6", "a4b2dcf01f6dc16e6c8be7d1628688d21fcbf56655e5ce55bce25a0c966ff1e9"),
        ("RunS-CaseAnalysis-Dynamic-OneShot-v1.5", "1f5419101f08e95a20fa00a2c5d7c21741527e20f424977ec28f8e1fb6fe502c"),
    },
}

CHROME68_PROMPT_CSS_PATTERNS = {
    "clamp()": re.compile(r"\bclamp\s*\(", re.I),
    "min()/max()": re.compile(r"\b(?:min|max)\s*\(", re.I),
    "dynamic viewport unit": re.compile(r"\d(?:dvh|svh|lvh)\b", re.I),
    "env()": re.compile(r"\benv\s*\(", re.I),
    "backdrop-filter": re.compile(r"backdrop-filter\s*:", re.I),
    "text-wrap": re.compile(r"\btext-wrap\s*:", re.I),
    "overflow-wrap:anywhere": re.compile(r"\boverflow-wrap\s*:\s*anywhere\b", re.I),
    "aspect-ratio": re.compile(r"\baspect-ratio\s*:", re.I),
    "inset shorthand": re.compile(r"(?:^|[;{])\s*inset\s*:", re.I),
    "logical spacing": re.compile(r"\b(?:margin|padding|inset)-(?:inline|block)(?:-start|-end)?\s*:", re.I),
    "modern color": re.compile(r"\b(?:oklab|oklch|color-mix)\s*\(", re.I),
}
CHROME68_PROMPT_JS_PATTERNS = {
    "optional chaining": re.compile(r"\?\."),
    "nullish coalescing": re.compile(r"\?\?"),
    "logical assignment": re.compile(r"(?:\|\||&&|\?\?)="),
    "numeric separator": re.compile(r"\b\d[\d_]*_\d[\d_]*\b"),
    "unsupported DOM API": re.compile(r"\.(?:replaceChildren|toggleAttribute|getAnimations)\s*\(|\b(?:queueMicrotask|structuredClone)\s*\(|crypto\.randomUUID\s*\("),
    "unsupported builtin": re.compile(r"\.(?:flat|flatMap|at|matchAll|replaceAll)\s*\(|Object\.(?:fromEntries|hasOwn)\s*\(|Promise\.(?:allSettled|any)\s*\(|\bglobalThis\b"),
}


def chrome68_prompt_incompatibilities(prompt: str) -> list[str]:
    styles = "\n".join(re.findall(r"<style\b[^>]*>(.*?)</style>", prompt, re.I | re.S))
    scripts = "\n".join(re.findall(r"<script\b[^>]*>(.*?)</script>", prompt, re.I | re.S))
    found = [name for name, pattern in CHROME68_PROMPT_CSS_PATTERNS.items() if pattern.search(styles)]
    for block in re.findall(r"\{([^{}]*)\}", styles, re.S):
        if re.search(r"display\s*:\s*(?:inline-)?flex\b", block, re.I) and re.search(r"(?:^|;)\s*gap\s*:", block, re.I):
            found.append("flex gap")
            break
    found.extend(name for name, pattern in CHROME68_PROMPT_JS_PATTERNS.items() if pattern.search(scripts))
    return sorted(set(found))


def normalize_prompt_version(prompt: str) -> str | None:
    normalized, count = re.subn(
        r"提示词版本号：[^\n]+",
        f"提示词版本号：{PROMPT_VERSION_PLACEHOLDER}",
        prompt,
        count=1,
    )
    return normalized if count == 1 else None


def expected_prompt_version(
    contract: str,
    asset_sha256: str,
    prompt_sha256: str,
    lesson_id: str,
    page_no: str,
) -> str:
    return (
        f"{contract}-asset-{asset_sha256[:12]}-prompt-{prompt_sha256[:12]}-"
        f"{lesson_id}-{page_no}-{PROMPT_VERSION_SUFFIX}"
    )


def check_asset_bound_prompt_version(
    page: dict[str, Any],
    index: int,
    lesson_id: str,
    path: Path,
    issues: list[dict[str, str]],
) -> None:
    kind = str(page.get("page_kind") or "")
    page_data = page.get("page_data") if isinstance(page.get("page_data"), dict) else {}
    prompt = page.get("prompt") if isinstance(page.get("prompt"), str) else ""
    page_no = str(page.get("page_no") or "")
    contract = ""
    asset_sha256 = ""
    if kind in FIXED_TEMPLATE_CONTRACTS:
        registered = FIXED_TEMPLATE_CONTRACTS[kind]
        contract = registered["contract"]
        asset_sha256 = registered["oneshot_sha256"]
    elif kind in DYNAMIC_ONESHOT_CONTRACTS:
        contract, asset_sha256, _ = DYNAMIC_ONESHOT_CONTRACTS[kind]
    elif kind == "post_class_task":
        contract = POST_CLASS_TASK_ONESHOT_CONTRACT
        asset_sha256 = POST_CLASS_TASK_ASSET_SHA256
    else:
        return

    normalized = normalize_prompt_version(prompt)
    prompt_sha256 = (
        hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        if normalized is not None
        else ""
    )
    expected = expected_prompt_version(
        contract, asset_sha256, prompt_sha256, lesson_id, page_no
    )
    first_line = next((line.strip() for line in prompt.splitlines() if line.strip()), "")
    actual_first_line = (
        first_line[len(ONESHOT_VERSION_PREFIX):].strip()
        if first_line.startswith(ONESHOT_VERSION_PREFIX)
        else ""
    )
    mismatches = []
    for key, actual, wanted in (
        ("oneshot_contract_version", page_data.get("oneshot_contract_version"), contract),
        ("oneshot_asset_sha256", page_data.get("oneshot_asset_sha256"), asset_sha256),
        ("prompt_instance_sha256", page_data.get("prompt_instance_sha256"), prompt_sha256),
        ("prompt_version", page_data.get("prompt_version"), expected),
        ("prompt_first_line", actual_first_line, expected),
    ):
        if actual != wanted:
            mismatches.append(key)
    if mismatches:
        issues.append(
            issue(
                "V35_STAGE6_PROMPT_VERSION_ASSET_MISMATCH",
                "BLOCKER",
                f"pages[{index}] 提示词版本未绑定当前 OneShot、完整提示词实例或页上下文：{'、'.join(mismatches)}",
                str(path),
            )
        )


def tag_has_class(value: str, tag: str, class_name: str) -> bool:
    """Match a required HTML class without rejecting unrelated attributes."""
    for opening_tag in re.findall(rf"<{re.escape(tag)}\b[^>]*>", value, re.I):
        class_match = re.search(r"\bclass\s*=\s*([\"'])(.*?)\1", opening_tag, re.I | re.S)
        if class_match and class_name in class_match.group(2).split():
            return True
    return False


def uses_current_dynamic_contract(page: dict[str, Any]) -> bool:
    page_kind = str(page.get("page_kind"))
    current = DYNAMIC_ONESHOT_CONTRACTS.get(page_kind)
    page_data = page.get("page_data") if isinstance(page.get("page_data"), dict) else {}
    return bool(current) and page_data.get("oneshot_contract_version") == current[0]


def uses_historical_r10_dynamic_contract(page: dict[str, Any]) -> bool:
    """Recognize the frozen R10 dynamic prompt shape without backfilling metadata."""
    page_kind = str(page.get("page_kind"))
    page_data = page.get("page_data") if isinstance(page.get("page_data"), dict) else {}
    prompt = page.get("prompt") if isinstance(page.get("prompt"), str) else ""
    first_line = next((line.strip() for line in prompt.splitlines() if line.strip()), "")
    type_token = {
        "knowledge_explanation": "Knowledge",
        "case_analysis": "CaseAnalysis",
    }.get(page_kind)
    if not type_token:
        return False
    version_pattern = re.compile(
        rf"^{re.escape(ONESHOT_VERSION_PREFIX)}RunS-{type_token}-"
        r"lesson\d{3}-P\d{2}-OneShot-R10-\S+$"
    )
    scroll_marker = (
        'class="knowledge-scroll'
        if page_kind == "knowledge_explanation"
        else 'class="case-scroll'
    )
    required_markers = (
        "<DESIGN_BRIEF>",
        "<PAGE_DATA>",
        "<!doctype html>",
        scroll_marker,
        "https://res.xrunda.com/runs/plugin/creator/creator-review-sdk.js",
        "syncFooterReserve",
    )
    return (
        page_data.get("route") == "dynamic_oneshot"
        and bool(version_pattern.match(first_line))
        and all(marker.lower() in prompt.lower() for marker in required_markers)
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def tagged_json(prompt: str, pattern: re.Pattern[str]) -> Any:
    match = pattern.search(prompt)
    if not match:
        return None
    try:
        return json.loads(match.group("json"))
    except json.JSONDecodeError:
        return None


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def issue(code: str, severity: str, message: str, artifact: str | None = None) -> dict[str, str]:
    item = {"code": code, "severity": severity, "message": message}
    if artifact:
        item["artifact"] = artifact
    return item


def load_manifest(manifest_path: Path, lesson_id: str, lesson_root: Path, p3_import_root: Path | None = None) -> tuple[dict[str, Any] | None, list[dict[str, str]]]:
    problems: list[dict[str, str]] = []
    if not manifest_path.is_file() or manifest_path.is_symlink():
        return None, [issue("INPUT_OR_CONFIG_ERROR", "BLOCKER", "manifest 不存在或是符号链接", str(manifest_path))]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [issue("INPUT_OR_CONFIG_ERROR", "BLOCKER", f"manifest 无法解析：{exc}", str(manifest_path))]
    if not isinstance(manifest, dict) or manifest.get("lesson_id") != lesson_id:
        problems.append(issue("INPUT_OR_CONFIG_ERROR", "BLOCKER", "manifest.lesson_id 与命令行不一致"))
    if manifest.get("schema_version") != "v1":
        problems.append(issue("INPUT_OR_CONFIG_ERROR", "BLOCKER", "只接受 schema_version=v1 的受控 manifest"))
    for section in ("p1", "p2", "s2e", "p3"):
        data = manifest.get(section)
        if not isinstance(data, dict) or not data.get("path") or not data.get("sha256"):
            problems.append(issue("INPUT_OR_CONFIG_ERROR", "BLOCKER", f"manifest 缺少 {section}.path 或 {section}.sha256"))
            continue
        candidate = Path(str(data["path"])).expanduser()
        if not candidate.is_absolute():
            candidate = lesson_root / candidate
        allowed_root = p3_import_root if section == "p3" and p3_import_root else lesson_root
        if candidate.is_symlink() or not inside(candidate, allowed_root):
            problems.append(issue("INPUT_OR_CONFIG_ERROR", "BLOCKER", f"{section}.path 必须位于受控根目录内且不能是符号链接", str(candidate)))
    return manifest, problems


def verify_artifact(section: str, data: dict[str, Any], issues: list[dict[str, str]], lesson_root: Path) -> Path | None:
    path = Path(str(data["path"])).expanduser()
    if not path.is_absolute():
        path = lesson_root / path
    if not path.is_file():
        issues.append(issue("ARTIFACT_MISSING", "BLOCKER", f"{section} 主产物不存在", str(path)))
        return None
    actual = sha256_file(path)
    if actual != data.get("sha256"):
        issues.append(issue("ARTIFACT_HASH_MISMATCH", "BLOCKER", f"{section} SHA-256 不匹配", str(path)))
    return path


def check_p1(path: Path, issues: list[dict[str, str]]) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if "<!-- 教师正文开始 -->" in text:
        required_course_info = (
            "课包名称",
            "单元名称",
            "课程编号",
            "课程标题",
            "课程目标",
            "知识点",
        )
        missing = [label for label in required_course_info if label not in text]
        if missing:
            issues.append(
                issue(
                    "S1_PREPROCESS_CONTRACT_MISSING",
                    "BLOCKER",
                    f"S1 预处理文件缺少课程信息字段：{','.join(missing)}",
                    str(path),
                )
            )
        return {
            "status": "PASS" if not missing else "BLOCKED",
            "sha256": sha256_file(path),
            "bytes": len(text.encode("utf-8")),
        }
    # V3.5 clean P1 uses a machine-readable header.  Keep the old text
    # fallback solely for controlled legacy fixtures; do not require a
    # student-visible literal "课程" / "题目" when the header proves both.
    header = re.search(r"<!-- V3\.5 P1 (?:PREPROCESS HEADER|PROCESSED CONTENT)\s*(\{.*?\})\s*-->", text, re.S)
    missing: list[str] = []
    if header:
        try:
            data = json.loads(header.group(1))
        except json.JSONDecodeError:
            data = None
            missing = ["P1 header JSON"]
        if isinstance(data, dict):
            info = data.get("course_info") or data.get("content_info")
            questions = data.get("question_components")
            required_info = ("package_name", "unit_name", "lesson_number", "course_name", "course_introduction", "knowledge_points")
            if not isinstance(info, dict) or any(not info.get(key) for key in required_info):
                missing.append("course_info")
            if not isinstance(questions, list) or not questions:
                missing.append("question_components")
    else:
        missing = []
        if "课程" not in text:
            missing.append("课程")
        if "题目" not in text and "互动规格开始" not in text:
            missing.append("题目或互动规格")
    if missing:
        issues.append(issue("P1_PREPROCESS_CONTRACT_MISSING", "BLOCKER", f"预处理文件缺少可识别字段：{','.join(missing)}", str(path)))
    return {"status": "PASS" if not missing else "BLOCKED", "sha256": sha256_file(path), "bytes": len(text.encode("utf-8"))}


def check_p2(path: Path, issues: list[dict[str, str]]) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    page_types = [
        "课程开篇",
        "场景引入",
        "知识讲解",
        "案例分析",
        "互动题目",
        "课后任务",
        "课程小结",
    ]
    found = [page_type for page_type in page_types if page_type in text]
    if not found:
        issues.append(issue("P2_PAGE_PLAN_UNREADABLE", "BLOCKER", "页面规划未发现受控页面类型", str(path)))
    if "complete" not in text:
        issues.append(issue("P2_COMPLETE_ACTION_MISSING", "BLOCKER", "页面规划未发现最后一页 complete 动作", str(path)))
    return {"status": "PASS" if found and "complete" in text else "BLOCKED", "page_types_found": found, "sha256": sha256_file(path)}


def nested_key_exists(value: Any, target: str) -> bool:
    if isinstance(value, dict):
        return target in value or any(nested_key_exists(item, target) for item in value.values())
    if isinstance(value, list):
        return any(nested_key_exists(item, target) for item in value)
    return False


def compare_stage6_to_effective_content(
    effective_payload: dict[str, Any],
    stage6_payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Return deterministic per-page diffs between S2E and Stage 6."""
    page_kind_map = {
        "课程开篇": "course_intro",
        "场景引入": "scene_intro",
        "知识讲解": "knowledge_explanation",
        "案例分析": "case_analysis",
        "互动题目": "question_component_page",
        "课后任务": "post_class_task",
        "课程小结": "course_summary",
    }
    effective_pages = effective_payload.get("pages")
    stage6_pages = stage6_payload.get("pages")
    rows: list[dict[str, Any]] = []
    problems: list[dict[str, str]] = []
    if not isinstance(effective_pages, list) or not isinstance(stage6_pages, list):
        return rows, [
            issue(
                "V35_STAGE6_EFFECTIVE_CONTENT_DIFF_UNRESOLVED",
                "BLOCKER",
                "S2E 或阶段6缺少 pages[]，无法执行逐页无损投影检查",
            )
        ]

    page_total = max(len(effective_pages), len(stage6_pages))
    for index in range(page_total):
        differences: list[str] = []
        effective_page = effective_pages[index] if index < len(effective_pages) else None
        stage6_page = stage6_pages[index] if index < len(stage6_pages) else None
        page_no = (
            effective_page.get("page_no")
            if isinstance(effective_page, dict)
            else stage6_page.get("page_no")
            if isinstance(stage6_page, dict)
            else f"INDEX_{index}"
        )
        if not isinstance(effective_page, dict):
            differences.append("S2E 页面缺失或不是对象")
        if not isinstance(stage6_page, dict):
            differences.append("阶段6页面缺失或不是对象")
        if isinstance(effective_page, dict) and isinstance(stage6_page, dict):
            expected_kind = page_kind_map.get(effective_page.get("page_type"))
            expected_action = "complete" if effective_page.get("page_action") == "complete" else "nextpage"
            expected_is_last = index == len(effective_pages) - 1
            source_content = effective_page.get("effective_content")
            page_data = stage6_page.get("page_data")
            actual_components = stage6_page.get("components")
            expected_components = [source_content] if effective_page.get("page_type") == "互动题目" else []
            comparisons = (
                ("page_no", effective_page.get("page_no"), stage6_page.get("page_no")),
                ("page_kind", expected_kind, stage6_page.get("page_kind")),
                ("tag", effective_page.get("capsule"), stage6_page.get("tag")),
                ("sdk_action", expected_action, stage6_page.get("sdk_action")),
                ("is_last_page", expected_is_last, stage6_page.get("is_last_page")),
                (
                    "source_block_ids",
                    effective_page.get("source_block_ids"),
                    page_data.get("source_block_ids") if isinstance(page_data, dict) else None,
                ),
                (
                    "effective_content_sha256",
                    sha256_bytes(canonical_json(source_content).encode("utf-8")),
                    page_data.get("effective_content_sha256") if isinstance(page_data, dict) else None,
                ),
            )
            for field, expected, actual in comparisons:
                if expected != actual:
                    differences.append(f"{field} 不一致")
            if json.dumps(expected_components, ensure_ascii=False, separators=(",", ":")) != json.dumps(
                actual_components, ensure_ascii=False, separators=(",", ":")
            ):
                differences.append("components 未原样投影 effective_content")
            if effective_page.get("page_type") == "互动题目" and stage6_page.get("prompt") != "":
                differences.append("互动页 prompt 不是空字符串")
            if effective_page.get("page_type") in {"知识讲解", "案例分析"}:
                expected_brief = effective_page.get("design_brief")
                actual_brief = page_data.get("design_brief") if isinstance(page_data, dict) else None
                if expected_brief != actual_brief:
                    differences.append("design_brief 未原样投影")
                expected_blocks = (
                    source_content.get("blocks")
                    if isinstance(source_content, dict)
                    else None
                )
                prompt_data = tagged_json(
                    stage6_page.get("prompt") if isinstance(stage6_page.get("prompt"), str) else "",
                    PAGE_DATA_TAG_RE,
                )
                actual_blocks = (
                    prompt_data.get("contentBlocks")
                    if isinstance(prompt_data, dict)
                    else None
                )
                if (
                    not isinstance(expected_blocks, list)
                    or actual_blocks != expected_blocks
                    or any(
                        isinstance(block, dict) and block.get("type") == "markdown"
                        for block in actual_blocks or []
                    )
                ):
                    differences.append("动态 PAGE_DATA.contentBlocks 未原样投影结构化 S5 blocks")

        status = "DIFF" if differences else "PASS"
        rows.append(
            {
                "page_no": page_no,
                "status": status,
                "differences": differences,
            }
        )
        if differences:
            problems.append(
                issue(
                    "V35_STAGE6_EFFECTIVE_CONTENT_DIFF_UNRESOLVED",
                    "BLOCKER",
                    f"{page_no}：{'；'.join(differences)}",
                )
            )
    return rows, problems


def check_dynamic_design_brief(
    page: dict[str, Any],
    index: int,
    path: Path,
    issues: list[dict[str, str]],
) -> None:
    page_data = page.get("page_data")
    brief = page_data.get("design_brief") if isinstance(page_data, dict) else None
    prompt = page.get("prompt") if isinstance(page.get("prompt"), str) else ""
    tagged = DESIGN_BRIEF_TAG_RE.search(prompt)
    prompt_brief: Any = None
    if tagged:
        try:
            prompt_brief = json.loads(tagged.group("json"))
        except json.JSONDecodeError:
            prompt_brief = None
    if (
        not isinstance(brief, dict)
        or brief.get("nonRenderable") is not True
        or not tagged
        or prompt_brief != brief
    ):
        issues.append(
            issue(
                "V35_DYNAMIC_DESIGN_BRIEF_INVALID",
                "BLOCKER",
                f"pages[{index}] 必须把 S2E design_brief 原样写入 page_data 与完整 OneShot 的 DESIGN_BRIEF 区块",
                str(path),
            )
        )


def check_dynamic_page_prompt(page: dict[str, Any], index: int, path: Path, issues: list[dict[str, str]]) -> None:
    prompt = page.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        issues.append(issue("DYNAMIC_PAGE_PROMPT_MISSING", "BLOCKER", f"pages[{index}] 动态页缺少完整 HTML prompt", str(path)))
        return
    compact = re.sub(r"\s+", "", prompt).lower()
    required = {
        "height:100%": "Chrome 68 基础高度",
        "overflow:hidden": "外层不滚动",
        "overflow-y:auto": "唯一内部纵向滚动容器",
        "position:absolute": "footer 绝对定位",
        "left:0": "footer left=0",
        "right:0": "footer right=0",
        "bottom:0": "footer bottom=0",
        "position:static": "按钮自身 static",
        "calc(var(--footer-h)+24px)": "footer 实测高度 +24px 预留",
        "padding:8px": "顶部 8px 呼吸空间",
        "syncfooterreserve": "底栏高度同步函数",
        "resizeobserver": "底栏高度变化监听",
    }
    if uses_current_dynamic_contract(page):
        required.update(
            {
                "66.667%": "顶部三分之二渐变终点",
                "background:var(--page-bottom-bg)": "footer 同色实底",
                "text-align:center": "原文标题居中",
            }
        )
    missing = [label for marker, label in required.items() if marker not in compact]
    h1_blocks = re.findall(r"[^{}]*h1[^{}]*\{([^{}]*)\}", compact)
    title_forced_nowrap = any("white-space:nowrap" in block for block in h1_blocks)
    old_contract_present = OLD_FOOTER_CONTRACT.lower() in prompt.lower() or (
        "margin-top:auto" in compact and "position:static" in compact
    )
    responsive_content_width = (
        "box-sizing:border-box" in compact
        and "width:100%" in compact
        and "max-width:680px" in compact
    )
    scroll_box_sizing_present = bool(
        re.search(
            r"\.(?:knowledge|case)-scroll\{[^{}]*box-sizing:border-box",
            compact,
        )
    )
    locked_content_width = (
        "width:min(100%,360px)" in compact
        or "--content-max:360px" in compact
        or "max-width:360px" in compact
    )
    if missing or title_forced_nowrap or old_contract_present:
        details = []
        if missing:
            details.append("缺少：" + "、".join(missing))
        if title_forced_nowrap:
            details.append("标题被整体 nowrap")
        if old_contract_present:
            details.append("仍含旧流内底栏合同")
        issues.append(
            issue(
                "DYNAMIC_PAGE_PERSISTENT_FOOTER_CONTRACT_MISSING",
                "BLOCKER",
                f"pages[{index}] 未满足 UNIFIED_PERSISTENT_BOTTOM_ACTION_BAR（{'；'.join(details)}）",
                str(path),
            )
        )
    if (
        page.get("page_kind") == "case_analysis"
        and uses_current_dynamic_contract(page)
        and "禁止装饰性左侧彩色竖线" not in prompt
    ):
        issues.append(
            issue(
                "CASE_ANALYSIS_DECORATIVE_RAIL_CONTRACT_MISSING",
                "BLOCKER",
                f"pages[{index}] 案例分析 OneShot 缺少禁止卡片装饰性左竖线的当前合同",
                str(path),
            )
        )
    if locked_content_width or not responsive_content_width:
        issues.append(
            issue(
                "V35_DYNAMIC_CONTENT_WIDTH_INVALID",
                "BLOCKER",
                f"pages[{index}] 动态内容区必须使用 box-sizing:border-box、width:100% 与 max-width:680px，"
                "不得锁死 360px",
                str(path),
            )
        )
    if not scroll_box_sizing_present:
        issues.append(
            issue(
                "V35_DYNAMIC_SCROLL_BOX_INVALID",
                "BLOCKER",
                f"pages[{index}] 唯一内部滚动容器必须显式使用 box-sizing:border-box，"
                "避免 height:100% 与 padding 叠加后超出 iframe",
                str(path),
            )
        )


def check_r34_visual_prompt_contract(
    page: dict[str, Any],
    index: int,
    path: Path,
    issues: list[dict[str, str]],
) -> None:
    """Verify R36 recipe, CTA, medium-density, and local-list contracts in model input.

    Rendering remains a later acceptance surface.  This gate makes the
    controlled layout plan and visible-footer obligation machine-checkable in
    the actual OneShot rather than leaving them as an unstructured reminder.
    """
    page_data = page.get("page_data") if isinstance(page.get("page_data"), dict) else {}
    contract = str(page_data.get("oneshot_contract_version") or "")
    prompt = page.get("prompt") if isinstance(page.get("prompt"), str) else ""
    kind = str(page.get("page_kind") or "")
    prompt_data = tagged_json(prompt, PAGE_DATA_TAG_RE)

    expected_dynamic_contract = DYNAMIC_ONESHOT_CONTRACTS.get(kind, ("",))[0]
    if kind in DYNAMIC_PAGE_KINDS and contract == expected_dynamic_contract:
        if "禁止装饰性左侧彩色竖线、轨道、连接点或箭头" not in prompt or "border-left" not in prompt:
            issues.append(
                issue(
                    "V35_DYNAMIC_DECORATIVE_RAIL_CONTRACT_MISSING",
                    "BLOCKER",
                    f"pages[{index}] R36 动态页 OneShot 缺少全页内容卡禁用装饰性左侧彩轨/连接轨规则",
                    str(path),
                )
            )
        recipes = page_data.get("visualRecipePlan")
        prompt_recipes = prompt_data.get("visualRecipePlan") if isinstance(prompt_data, dict) else None
        blocks = prompt_data.get("contentBlocks") if isinstance(prompt_data, dict) else []
        non_heading_count = sum(
            1 for block in blocks
            if isinstance(block, dict) and block.get("type") != "heading"
        )
        brief = page_data.get("design_brief") if isinstance(page_data.get("design_brief"), dict) else {}
        expected_medium = (
            kind == "knowledge_explanation"
            and brief.get("density") == "medium"
            and non_heading_count >= 3
            and brief.get("shortPageComposition") != "two_layer_reading"
        )
        valid_recipe_names = {
            "intro_observation_band",
            "list_or_option_compact",
            "sequence_compact",
            "analysis_conclusion_emphasis",
            "comparison_split",
            "process_steps",
            "role_distribution_grid",
            "role_distribution_inline",
            "evidence_quote_focus",
            "open_body_flow",
            "inline_conflict_evidence",
        }
        recipe_rows = recipes.get("recipes") if isinstance(recipes, dict) else None
        recipe_names = [row.get("recipe") for row in recipe_rows if isinstance(row, dict)] if isinstance(recipe_rows, list) else []
        balance = recipes.get("mediumReadingAreaBalance") if isinstance(recipes, dict) else None
        if (
            not isinstance(recipes, dict)
            or recipes.get("nonRenderable") is not True
            or recipes.get("recipeContract") != "R36_REUSABLE_DYNAMIC_VISUAL_RECIPES"
            or prompt_recipes != recipes
            or len(recipe_names) < 1
            or len(recipe_names) != len(set(recipe_names))
            or any(name not in valid_recipe_names for name in recipe_names)
            or not isinstance(balance, dict)
            or balance.get("required") is not expected_medium
            or balance.get("target") != "60_to_75_percent_of_available_reading_area"
            or balance.get("forbidFillers") is not True
        ):
            issues.append(
                issue(
                    "V35_DYNAMIC_VISUAL_RECIPE_PLAN_INVALID",
                    "BLOCKER",
                    f"pages[{index}] R36 动态页缺少与 PAGE_DATA 一致的可复用视觉配方计划或中篇幅目标",
                    str(path),
                )
            )
        required_recipe_markers = (
            "content-module--intro-band",
            "content-module--open-flow",
            "content-module--inline-conflict",
            "content-module--list-compact",
            "content-module--sequence-compact",
            "content-module--emphasis",
        )
        if kind == "knowledge_explanation":
            required_recipe_markers += (
                "content-module--comparison",
                "content-module--process-steps",
                "content-module--role-inline",
                "content-module--evidence-quote",
            )
        if any(marker not in prompt for marker in required_recipe_markers):
            issues.append(
                issue(
                    "V35_DYNAMIC_VISUAL_RECIPE_PROMPT_MISSING",
                    "BLOCKER",
                    f"pages[{index}] R36 动态页 OneShot 缺少可执行的三类视觉配方 class 合同",
                    str(path),
                )
            )
        expected_semantic_composition = {
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
        }
        semantic_composition = recipes.get("semanticCompositionContract") if isinstance(recipes, dict) else None
        semantic_composition_markers = (
            "语义关系决定构图",
            "真实列表必须保持列表形态",
            "连续说明不得为了丰富而拆块",
            "sameWhiteCardStack",
            "positionOnlyDifferentiation",
        )
        if (
            semantic_composition != expected_semantic_composition
            or not isinstance(prompt_data, dict)
            or prompt_data.get("visualRecipePlan", {}).get("semanticCompositionContract") != expected_semantic_composition
            or any(marker not in prompt for marker in semantic_composition_markers)
        ):
            issues.append(
                issue(
                    "V35_DYNAMIC_SEMANTIC_COMPOSITION_CONTRACT_MISSING",
                    "BLOCKER",
                    f"pages[{index}] R36 动态页缺少关系驱动、连续句流或列表保真的构图合同",
                    str(path),
                )
            )
        expected_alignment = {
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
        alignment = recipes.get("alignmentContract") if isinstance(recipes, dict) else None
        alignment_markers = (
            "左对齐优先",
            "顶部对齐优先",
            "同级内容共享左边界",
            "同级对比项顶边对齐且等宽",
            "只有明确主次关系才允许非对称",
        )
        if (
            alignment != expected_alignment
            or not isinstance(prompt_data, dict)
            or prompt_data.get("visualRecipePlan", {}).get("alignmentContract") != expected_alignment
            or any(marker not in prompt for marker in alignment_markers)
        ):
            issues.append(
                issue(
                    "V35_DYNAMIC_ALIGNMENT_CONTRACT_MISSING",
                    "BLOCKER",
                    f"pages[{index}] R36 动态页缺少左对齐、顶部对齐或同级内容一致栅格合同",
                    str(path),
                )
            )
        expected_comparison_layout = {
            "sideBySideAllowed": True,
            "sideBySideMaxCharsPerPeer": 80,
            "sideBySideMaxCombinedChars": 150,
            "withinLimitLayout": "aligned_equal_width_columns",
            "overLimitLayout": "vertical_full_width_stack",
            "verticalStackSharedLeftEdge": True,
        }
        expected_highlight = {
            "maximumSegmentsPerPage": 3,
            "sameSemanticCategoryUsesSameStyle": True,
            "shortHighlightNoWrapMaxChars": 12,
            "shortHighlightMoveWholeToNextLine": True,
            "forbidOrphanTailCharsMax": 2,
            "forbid": ["multicolorSameCategory", "oneOrTwoCharacterHighlightedTail"],
        }
        expected_webview = {
            "baseline": "Android System WebView Chrome 68",
            "untranspiledSource": True,
            "modernFeaturesEnhancementOnly": True,
            "forbidJavaScriptSyntax": ["nullishCoalescing", "optionalChaining", "logicalAssignment", "classFields", "topLevelAwait"],
            "forbidDomApis": ["replaceChildren", "toggleAttribute", "queueMicrotask", "structuredClone", "crypto.randomUUID"],
            "forbidCssFeatures": ["minFunction", "maxFunction", "clampFunction", "dynamicViewportUnits", "aspectRatio", "insetShorthand", "flexGap", "textWrap", "backdropFilter", "logicalProperties", "modernColorFunctions"],
            "requiredFallbacks": ["height100Percent", "physicalSpacingProperties", "widthPlusMaxWidth", "guardedObservers", "visibleStaticFirstScreen"],
        }
        contract_checks = (
            ("comparisonLayoutContract", expected_comparison_layout, ("任一对比项超过 80 个字符", "上下同宽"), "V35_DYNAMIC_COMPARISON_LAYOUT_CONTRACT_MISSING"),
            ("highlightContract", expected_highlight, ("全页最多 3 个高亮片段", "短高亮词组整体换行", "孤立高亮尾巴"), "V35_DYNAMIC_HIGHLIGHT_CONTRACT_MISSING"),
            ("webViewCompatibilityContract", expected_webview, ("Android System WebView Chrome 68", "观察器必须先检测再使用"), "V35_DYNAMIC_CHROME68_CONTRACT_MISSING"),
        )
        for key, expected, markers, code in contract_checks:
            if (
                recipes.get(key) != expected
                or not isinstance(prompt_data, dict)
                or prompt_data.get("visualRecipePlan", {}).get(key) != expected
                or any(marker not in prompt for marker in markers)
            ):
                issues.append(
                    issue(
                        code,
                        "BLOCKER",
                        f"pages[{index}] R36 动态页缺少 {key} 当前合同",
                        str(path),
                    )
                )
        expected_source_projection = {
            "required": True,
            "visibleOccurrencesPerBlock": 1,
            "allowContiguousDomFragments": True,
            "concatenatedTextMustEqualSource": True,
            "forbidFullBlockPlusDerivedFragments": True,
            "forbidParaphrasedLabels": True,
        }
        source_projection = recipes.get("sourceTextProjectionContract") if isinstance(recipes, dict) else None
        if source_projection != expected_source_projection or any(
            marker not in prompt
            for marker in (
                "整块原文 + 派生子项",
                "拼接后的 textContent 必须逐字等于该来源块原文",
            )
        ):
            issues.append(
                issue(
                    "V35_DYNAMIC_SOURCE_TEXT_ONCE_CONTRACT_MISSING",
                    "BLOCKER",
                    f"pages[{index}] R36 动态页缺少来源文字逐块单次投影合同",
                    str(path),
                )
            )

        expected_hierarchy = {
            "required": non_heading_count >= 3 and brief.get("shortPageComposition") != "two_layer_reading",
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
        }
        hierarchy = recipes.get("visualHierarchyContract") if isinstance(recipes, dict) else None
        hierarchy_markers = (
            "semanticHierarchyFirst",
            "排版优雅优先",
            "装饰不是必选项",
            "不得为了丰富度增加表面",
            "禁止自动生成 Emoji",
        )
        if (
            hierarchy != expected_hierarchy
            or not isinstance(prompt_data, dict)
            or prompt_data.get("visualRecipePlan", {}).get("visualHierarchyContract") != expected_hierarchy
            or any(marker not in prompt for marker in hierarchy_markers)
        ):
            issues.append(
                issue(
                    "V35_DYNAMIC_VISUAL_HIERARCHY_CONTRACT_MISSING",
                    "BLOCKER",
                    f"pages[{index}] R36 动态页缺少语义层级、排版优雅、关系表达或可选装饰合同",
                    str(path),
                )
            )
        expected_execution = {
            "required": True,
            "source": "S5.design_brief",
            "layoutArchetype": brief.get("layoutArchetype"),
            "groupPresentation": brief.get("groupPresentation"),
            "sourceProjectionPlan": brief.get("sourceProjectionPlan"),
            "emphasisTargets": brief.get("emphasisTargets"),
            "surfacePolicy": brief.get("surfacePolicy"),
            "colorRoles": brief.get("colorRoles"),
            "spaceBalance": brief.get("spaceBalance"),
            "alignmentPolicy": brief.get("alignmentPolicy"),
            "comparisonLayoutPolicy": brief.get("comparisonLayoutPolicy"),
            "highlightPolicy": brief.get("highlightPolicy"),
        }
        execution = recipes.get("designExecutionContract") if isinstance(recipes, dict) else None
        execution_markers = (
            "designExecutionContract",
            "sourceProjectionPlan",
            "emphasisTargets",
            "nonCodeDarkSurfaceAreaPercentMax",
            "非代码内容禁止大面积近黑背景",
            "inline_conflict_evidence",
            "continuous_inline_flow",
            "single_section_flat_steps",
            "continuous_inline_highlights",
            "punctuated clauses 不得拆成独立块",
            "semanticHierarchyFirst",
            "maximumTopLevelVisualRegions",
            "maximumDecorativeGroups",
        )
        if (
            execution != expected_execution
            or not isinstance(prompt_data, dict)
            or prompt_data.get("visualRecipePlan", {}).get("designExecutionContract")
            != expected_execution
            or any(marker not in prompt for marker in execution_markers)
        ):
            issues.append(
                issue(
                    "V35_DYNAMIC_S5_DESIGN_EXECUTION_CONTRACT_MISSING",
                    "BLOCKER",
                    f"pages[{index}] R36 动态页未逐字执行 S5 构图、唯一投影、原句强调、浅色表面或空间平衡合同",
                    str(path),
                )
            )
        footer = page_data.get("footerContract")
        prompt_footer = prompt_data.get("footerContract") if isinstance(prompt_data, dict) else None
        expected_footer = {
            "required": True,
            "footerClass": "knowledge-footer" if kind == "knowledge_explanation" else "case-footer",
            "buttonClass": "knowledge-primary-button" if kind == "knowledge_explanation" else "case-primary-button",
            "buttonText": "完成学习" if page.get("sdk_action") == "complete" else "继续学习",
        }
        footer_markers = (
            "不得条件省略",
            "display:none",
            "visibility:hidden",
            "opacity:0",
        )
        if (
            footer != expected_footer
            or prompt_footer != footer
            or not tag_has_class(prompt, "footer", expected_footer["footerClass"])
            or not tag_has_class(prompt, "button", expected_footer["buttonClass"])
            or any(marker not in prompt for marker in footer_markers)
        ):
            issues.append(
                issue(
                    "V35_DYNAMIC_VISIBLE_CTA_CONTRACT_MISSING",
                    "BLOCKER",
                    f"pages[{index}] R36 动态页缺少与页面动作一致的可见固定 CTA 合同",
                    str(path),
                )
            )
        if expected_medium and (
            "60%—75%" not in prompt
            or "knowledge-content--medium-structured" not in prompt
            or "align-content:space-between" not in prompt
        ):
            issues.append(
                issue(
                    "V35_DYNAMIC_MEDIUM_DENSITY_BALANCE_CONTRACT_MISSING",
                    "BLOCKER",
                    f"pages[{index}] R36 知识讲解 OneShot 缺少中篇幅分布式阅读区构图合同",
                    str(path),
                )
            )

        ordered_list_count = sum(
            1
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "ordered_list"
        )
        ordinal_contract = recipes.get("orderedListOrdinalContract") if isinstance(recipes, dict) else None
        expected_ordinal_contract = {
            "required": bool(ordered_list_count),
            "source": "items[]",
            "startAt": 1,
            "displayExpression": "itemIndex + 1",
            "forbid": ["contentBlockIndex", "globalCounter", "doubleNumbering"],
        }
        ordinal_markers = (
            "itemIndex + 1",
            "contentBlockIndex",
            "globalCounter",
            "doubleNumbering",
        )
        has_local_items_marker = (
            "items[] 内 itemIndex" in prompt
            or "items[]` 内 `itemIndex" in prompt
        )
        if ordered_list_count and (
            ordinal_contract != expected_ordinal_contract
            or not isinstance(prompt_data, dict)
            or prompt_data.get("visualRecipePlan", {}).get("orderedListOrdinalContract") != expected_ordinal_contract
            or not has_local_items_marker
            or any(marker not in prompt for marker in ordinal_markers)
        ):
            issues.append(
                issue(
                    "V35_DYNAMIC_ORDERED_LIST_ORDINAL_CONTRACT_MISSING",
                    "BLOCKER",
                    f"pages[{index}] 有序列表缺少按本列表 items[] 从 1 连续编号、禁止双重编号的 R36 合同",
                    str(path),
                )
            )

        unordered_list_count = sum(
            1
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "unordered_list"
        )
        unordered_contract = recipes.get("unorderedListPresentationContract") if isinstance(recipes, dict) else None
        expected_unordered_contract = {
            "required": bool(unordered_list_count),
            "source": "items[]",
            "preserveExistingLabels": True,
            "forbid": ["numericBadge", "autoOrdinal", "doubleNumbering"],
        }
        if unordered_list_count and (
            unordered_contract != expected_unordered_contract
            or not isinstance(prompt_data, dict)
            or prompt_data.get("visualRecipePlan", {}).get("unorderedListPresentationContract") != expected_unordered_contract
            or any(marker not in prompt for marker in ("无序列表", "numericBadge", "autoOrdinal", "doubleNumbering"))
        ):
            issues.append(
                issue(
                    "V35_DYNAMIC_UNORDERED_LIST_NUMERIC_BADGE_CONTRACT_MISSING",
                    "BLOCKER",
                    f"pages[{index}] 无序列表缺少保留既有标签、禁止数字徽标或自动编号的 R36 合同",
                    str(path),
                )
            )

    if kind == "course_summary" and contract.endswith("-v1.11") and (
        "单一总结块时使用单块小结构图分支" not in prompt
        or "不得补写、拆改或重复学生原文" not in prompt
    ):
        issues.append(
            issue(
                "V35_SUMMARY_SINGLE_BLOCK_COMPOSITION_CONTRACT_MISSING",
                "BLOCKER",
                f"pages[{index}] R33 课程小结 OneShot 缺少单块小结构图分支或原文保真规则",
                str(path),
            )
        )
    elif kind == "course_summary" and contract.endswith("-v1.11") and (
        "summary-card--single-block" not in prompt
        or "classList.toggle(\"summary-card--single-block\"" not in prompt
    ):
        issues.append(
            issue(
                "V35_SUMMARY_SINGLE_BLOCK_COMPOSITION_HOOK_MISSING",
                "BLOCKER",
                f"pages[{index}] R33 课程小结单块分支缺少可执行 CSS/JS 构图钩子",
                str(path),
            )
        )


def check_non_interactive_footer_seam_contract(
    page: dict[str, Any],
    index: int,
    path: Path,
    issues: list[dict[str, str]],
) -> None:
    prompt = page.get("prompt") if isinstance(page.get("prompt"), str) else ""
    compact = re.sub(r"\s+", "", prompt).lower()
    is_dynamic_page = uses_current_dynamic_contract(page)
    transparent_footer = re.search(
        r"\.[a-z0-9_-]*footer\{[^{}]*background:transparent(?:[;}])[^{}]*\}",
        compact,
    )
    missing_bottom_token = is_dynamic_page and "background:var(--page-bottom-bg)" not in compact
    missing_top_two_thirds_stop = is_dynamic_page and "66.667%" not in compact
    footer_feather = re.search(
        r"\.[a-z0-9_-]*footer::before\{[^{}]*(?:height:18px|bottom:100%)[^{}]*\}",
        compact,
    )
    if (is_dynamic_page and transparent_footer) or missing_bottom_token or missing_top_two_thirds_stop or footer_feather:
        details = []
        if is_dynamic_page and transparent_footer:
            details.append("footer 仍为透明背景")
        if missing_bottom_token:
            details.append("footer 未使用页面底色令牌")
        if missing_top_two_thirds_stop:
            details.append("主渐变未在 66.667% 收口")
        if footer_feather:
            details.append("footer 仍含 ::before 18px / bottom:100% 羽化层")
        issues.append(
            issue(
                "V35_STAGE6_FOOTER_SEAM_CONTRACT_INVALID",
                "BLOCKER",
                f"pages[{index}] 未满足 R11 顶部三分之二渐变与同色底栏合同（{'；'.join(details)}）",
                str(path),
            )
        )


def check_non_interactive_oneshot_prompt(
    page: dict[str, Any],
    index: int,
    path: Path,
    issues: list[dict[str, str]],
) -> None:
    prompt = page.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        issues.append(
            issue(
                "V35_STAGE6_PROMPT_DELIVERY_MODE_INVALID",
                "BLOCKER",
                f"pages[{index}] 非互动页缺少完整 OneShot 实际模型输入",
                str(path),
            )
        )
        return
    stripped = prompt.lstrip()
    if (
        stripped.lower().startswith("<!doctype html")
        or not stripped.startswith(ONESHOT_VERSION_PREFIX)
        or "<!doctype html" not in prompt.lower()
    ):
        issues.append(
            issue(
                "V35_STAGE6_PROMPT_DELIVERY_MODE_INVALID",
                "BLOCKER",
                f"pages[{index}] prompt 必须以唯一提示词版本号开头并内嵌完整 HTML，禁止裸 HTML",
                str(path),
            )
        )


def final_html_payload(prompt: str) -> str:
    """Return the final HTML supplied by a full OneShot, never its instructions."""
    start = prompt.lower().rfind("<!doctype html")
    if start < 0:
        return ""
    html = prompt[start:].strip()
    return html if html.lower().endswith("</html>") else ""


def check_governed_oneshot_asset_contract(
    page: dict[str, Any],
    index: int,
    path: Path,
    issues: list[dict[str, str]],
) -> None:
    """Reject generic substitute HTML that only mimics a few CSS markers."""
    page_kind = page.get("page_kind")
    page_data = page.get("page_data")
    prompt = page.get("prompt") if isinstance(page.get("prompt"), str) else ""
    if not isinstance(page_data, dict):
        return
    if uses_historical_r10_dynamic_contract(page):
        return

    common_expected = {
        "assembly_mode": "model_oneshot_prompt_control",
        "expected_model_output": "pure_complete_html",
        "model_output_status": "NOT_GENERATED",
    }
    mismatches = [
        key for key, expected in common_expected.items()
        if page_data.get(key) != expected
    ]

    fixed = FIXED_TEMPLATE_CONTRACTS.get(str(page_kind))
    if fixed:
        fixed_expected = {
            "route": "fixed_template",
            "template": fixed["variable"],
            "oneshot_contract_version": fixed["contract"],
            "oneshot_asset_sha256": fixed["oneshot_sha256"],
            "template_sha256": fixed["template_sha256"],
            "non_variable_sha256": fixed["non_variable_sha256"],
            "template_outside_variable_region_unchanged": True,
        }
        mismatches.extend(
            key for key, expected in fixed_expected.items()
            if page_data.get(key) != expected
        )
        required_prompt_markers = (
            fixed["variable"],
            "FIXED_LAYOUT_CONTRACT",
            "https://res.xrunda.com/runs/plugin/creator/creator-review-sdk.js",
        )
        missing_markers = [
            marker for marker in required_prompt_markers if marker not in prompt
        ]
        if mismatches or missing_markers:
            details = []
            if mismatches:
                details.append("元数据不匹配：" + "、".join(sorted(set(mismatches))))
            if missing_markers:
                details.append("提示词缺少：" + "、".join(missing_markers))
            issues.append(
                issue(
                    "V35_STAGE6_REGISTERED_ONESHOT_ASSET_INVALID",
                    "BLOCKER",
                    f"pages[{index}] 固定模板未使用当前登记 Demo / OneShot（{'；'.join(details)}）",
                    str(path),
                )
            )
        return

    dynamic = DYNAMIC_ONESHOT_CONTRACTS.get(str(page_kind))
    if dynamic:
        contract, oneshot_sha256, class_markers = dynamic
        is_legacy_dynamic = (
            page_data.get("oneshot_contract_version"),
            page_data.get("oneshot_asset_sha256"),
        ) in DYNAMIC_ONESHOT_LEGACY_CONTRACTS.get(str(page_kind), set())
        if page_data.get("route") != "dynamic_oneshot":
            mismatches.append("route")
        if not is_legacy_dynamic:
            dynamic_expected = {
                "oneshot_contract_version": contract,
                "oneshot_asset_sha256": oneshot_sha256,
            }
            mismatches.extend(
                key for key, expected in dynamic_expected.items()
                if page_data.get(key) != expected
            )
        required_prompt_markers = (
            "<PAGE_DATA>",
            "<DESIGN_BRIEF>",
            "<REQUIRED_CSS>",
            "<REQUIRED_JS>",
            *class_markers,
        )
        missing_markers = [
            marker for marker in required_prompt_markers
            if marker.lower() not in prompt.lower()
        ]
        forbidden_markers = [
            marker for marker in (
                "sourceContent",
                "输出只能是下方完整 HTML",
                ".course-action",
            )
            if marker.lower() in prompt.lower()
        ]
        if mismatches or missing_markers or forbidden_markers:
            details = []
            if mismatches:
                details.append("元数据不匹配：" + "、".join(sorted(set(mismatches))))
            if missing_markers:
                details.append("提示词缺少：" + "、".join(missing_markers))
            if forbidden_markers:
                details.append("命中错误通用分支：" + "、".join(forbidden_markers))
            issues.append(
                issue(
                    "V35_STAGE6_REGISTERED_ONESHOT_ASSET_INVALID",
                    "BLOCKER",
                    f"pages[{index}] 动态页未使用当前登记 OneShot（{'；'.join(details)}）",
                    str(path),
                )
            )


def check_course_intro_image_contract(
    page: dict[str, Any],
    index: int,
    path: Path,
    issues: list[dict[str, str]],
) -> None:
    prompt = page.get("prompt") if isinstance(page.get("prompt"), str) else ""
    image_url = "https://res.xrunda.com/xruns/static/image/20270724/1.png"
    actual_data_image = re.search(
        r"""(?ix)
        (?:
            (?:src|href)\s*=\s*["']\s*
          | url\(\s*["']?\s*
          | (?:image(?:url|_url)?|src)\s*[:=]\s*["']\s*
        )
        data:image/
        """,
        prompt,
    )
    if image_url not in prompt or actual_data_image:
        issues.append(
            issue(
                "COURSE_INTRO_IMAGE_ASSET_INVALID",
                "BLOCKER",
                f"pages[{index}] 开篇插画必须使用当前登记 HTTPS 资产，禁止 data:image / Base64",
                str(path),
            )
        )


def check_course_intro_variable_schema(
    page: dict[str, Any],
    index: int,
    path: Path,
    issues: list[dict[str, str]],
) -> None:
    """Require the v1.8 template's real camelCase variables.

    A prompt can contain the correct intro Demo and image while still inject
    S5's Chinese audit keys.  The page then renders as a visually correct but
    empty template, so this is an assembly blocker rather than visual QA.
    """
    prompt = page.get("prompt") if isinstance(page.get("prompt"), str) else ""
    if "courseintro-fixedtemplate-oneshot" not in prompt.lower():
        return
    html_payload = final_html_payload(prompt)
    match = re.search(
        r"const\s+COURSE_INTRO_VARIABLES\s*=\s*(?:Object\.freeze\(\s*)?(\{.*?\})\s*\)?;",
        html_payload,
        flags=re.DOTALL,
    )
    values: dict[str, Any] = {}
    try:
        values = json.loads(match.group(1)) if match else {}
    except json.JSONDecodeError:
        pass
    required_text = ("packageName", "unitName", "courseName", "courseIntroduction")
    missing = [key for key in required_text if not isinstance(values.get(key), str) or not values[key].strip()]
    if not isinstance(values.get("lessonNumber"), int) or values["lessonNumber"] < 1:
        missing.append("lessonNumber")
    points = values.get("knowledgePoints")
    if not isinstance(points, list) or not points or not all(isinstance(point, str) and point.strip() for point in points):
        missing.append("knowledgePoints")
    if not match or missing:
        detail = "未找到 COURSE_INTRO_VARIABLES 变量区" if not match else "缺少或类型错误：" + "、".join(missing)
        issues.append(
            issue(
                "COURSE_INTRO_VARIABLE_SCHEMA_INVALID",
                "BLOCKER",
                f"pages[{index}] 课程开篇 v1.9 变量合同不匹配（{detail}）",
                str(path),
            )
        )


def check_scene_intro_header_visual(
    page: dict[str, Any],
    index: int,
    path: Path,
    issues: list[dict[str, str]],
) -> None:
    """Require the registered scene-header image rather than an emoji glyph."""
    prompt = page.get("prompt") if isinstance(page.get("prompt"), str) else ""
    compact = re.sub(r"\s+", "", prompt).lower()
    is_fixed_scene_contract = "runs-sceneintro-fixedtemplate-oneshot" in compact
    has_scene_visual = (
        'class="scene-emoji"' in compact
        and "https://res.xrunda.com/xruns/static/image/20270724/2.png" in prompt
    )
    if is_fixed_scene_contract and not has_scene_visual:
        issues.append(
            issue(
                "SCENE_INTRO_HEADER_VISUAL_INVALID",
                "BLOCKER",
                f"pages[{index}] 场景引入固定头图必须使用登记的 HTTPS 图片，不能只依赖 emoji 字体",
                str(path),
            )
        )


def check_course_summary_ordered_list_style(
    page: dict[str, Any],
    index: int,
    path: Path,
    issues: list[dict[str, str]],
) -> None:
    prompt = page.get("prompt") if isinstance(page.get("prompt"), str) else ""
    prompt = final_html_payload(prompt)
    compact = re.sub(r"\s+", "", prompt).lower()
    has_source_numbered_data = (
        "sourcenumbered:true" in compact
        or '"sourcenumbered":true' in compact
    )
    if not has_source_numbered_data:
        return
    required_markers = {
        'listitem.classname="summary-item"': "统一有样式列表项",
        'number.classname="summary-index"': "紫色数字徽标",
        'number.textcontent=string(index+1).padstart(2,"0")': "01/02/03 序号",
        "listitem.appendchild(number)": "序号写入每个列表项",
    }
    missing = [label for marker, label in required_markers.items() if marker not in compact]
    hides_badge = "if(!block.sourcenumbered)" in compact
    if missing or hides_badge:
        details = []
        if missing:
            details.append("缺少：" + "、".join(missing))
        if hides_badge:
            details.append("sourceNumbered 分支仍隐藏模板数字徽标")
        issues.append(
            issue(
                "COURSE_SUMMARY_ORDERED_LIST_STYLE_INVALID",
                "BLOCKER",
                f"pages[{index}] 课程小结未按 R5 显示有样式数字列表（{'；'.join(details)}）",
                str(path),
            )
        )


def check_course_summary_page_action_contract(
    page: dict[str, Any],
    index: int,
    path: Path,
    issues: list[dict[str, str]],
) -> None:
    prompt = page.get("prompt") if isinstance(page.get("prompt"), str) else ""
    action_match = re.search(
        r"""(?:["']?pageAction["']?)\s*:\s*["'](next|complete)["']""",
        prompt,
        flags=re.IGNORECASE,
    )
    expected_action = "complete" if page.get("sdk_action") == "complete" else "next"
    expected_label = "完成学习" if expected_action == "complete" else "继续学习"
    variable_action = action_match.group(1).lower() if action_match else None
    conflicting_literal = re.search(
        rf"""pageAction\s*=\s*["'](?!{re.escape(expected_action)}["'])(next|complete)["']""",
        prompt,
        flags=re.IGNORECASE,
    )
    if variable_action != expected_action or conflicting_literal:
        details = []
        if variable_action != expected_action:
            details.append(
                f"COURSE_SUMMARY_VARIABLES.pageAction={variable_action!r}，应为 {expected_action!r}"
            )
        if conflicting_literal:
            details.append(
                f"提示词仍硬编码冲突动作 {conflicting_literal.group(1)!r}"
            )
        issues.append(
            issue(
                "COURSE_SUMMARY_PAGE_ACTION_CONTRACT_INVALID",
                "BLOCKER",
                f"pages[{index}] 课程小结动作合同不一致（{'；'.join(details)}）",
                str(path),
            )
        )

    # The platform can show the precompiled static DOM before inline enhancement
    # runs, so the visible footer label must already match the page action.
    body_match = re.search(
        r"<body\b[^>]*>(.*?)(?:<script\b|</body>)",
        prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    html_part = body_match.group(1) if body_match else ""
    button_match = re.search(
        r'''<button[^>]*\bid=["']completeButton["'][^>]*>\s*([^<]+?)\s*</button>''',
        html_part,
        flags=re.IGNORECASE,
    )
    static_label = button_match.group(1).strip() if button_match else None
    is_fixed_summary_contract = "coursesummary-fixedtemplate-oneshot" in prompt.lower()
    if is_fixed_summary_contract and static_label != expected_label:
        issues.append(
            issue(
                "COURSE_SUMMARY_STATIC_ACTION_FALLBACK_INVALID",
                "BLOCKER",
                f"pages[{index}] 课程小结静态底栏动作兜底为 {static_label!r}，应为 {expected_label!r}",
                str(path),
            )
        )


def javascript_has_raw_linebreak_in_quoted_string(script: str) -> bool:
    state = "normal"
    escaped = False
    index = 0
    while index < len(script):
        char = script[index]
        next_char = script[index + 1] if index + 1 < len(script) else ""
        if state in {"single", "double"}:
            if char in "\r\n":
                return True
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif (state == "single" and char == "'") or (
                state == "double" and char == '"'
            ):
                state = "normal"
        elif state == "template":
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "`":
                state = "normal"
        elif state == "line_comment":
            if char in "\r\n":
                state = "normal"
        elif state == "block_comment":
            if char == "*" and next_char == "/":
                state = "normal"
                index += 1
        else:
            if char == "/" and next_char == "/":
                state = "line_comment"
                index += 1
            elif char == "/" and next_char == "*":
                state = "block_comment"
                index += 1
            elif char == "'":
                state = "single"
            elif char == '"':
                state = "double"
            elif char == "`":
                state = "template"
        index += 1
    return state in {"single", "double"}


def check_course_summary_embedded_script(
    page: dict[str, Any],
    index: int,
    path: Path,
    issues: list[dict[str, str]],
) -> None:
    prompt = page.get("prompt") if isinstance(page.get("prompt"), str) else ""
    prompt = final_html_payload(prompt)
    inline_scripts = re.findall(
        r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>",
        prompt,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not inline_scripts or any(
        javascript_has_raw_linebreak_in_quoted_string(script)
        for script in inline_scripts
    ):
        issues.append(
            issue(
                "COURSE_SUMMARY_EMBEDDED_SCRIPT_INVALID",
                "BLOCKER",
                f"pages[{index}] 课程小结内嵌脚本缺失，或字符串含未转义换行 / 引号漂移",
                str(path),
            )
        )


def check_course_summary_static_content_fallback(
    page: dict[str, Any],
    index: int,
    path: Path,
    issues: list[dict[str, str]],
) -> None:
    """The visible summary must survive a platform-side inline-script failure."""
    full_prompt = page.get("prompt") if isinstance(page.get("prompt"), str) else ""
    prompt = final_html_payload(full_prompt)
    compact = re.sub(r"\s+", "", prompt).lower()
    is_fixed_summary_contract = "coursesummary-fixedtemplate-oneshot" in full_prompt.lower()
    has_static_fallback = (
        'id="summarytitle">' in compact
        and 'id="summarycontent"data-summary-static="true"' in compact
        and 'data-summary-static="true"><' in compact
    )
    if is_fixed_summary_contract and not has_static_fallback:
        issues.append(
            issue(
                "COURSE_SUMMARY_STATIC_CONTENT_FALLBACK_MISSING",
                "BLOCKER",
                f"pages[{index}] 课程小结缺少预编译静态正文兜底，平台脚本注入失败会显示空页",
                str(path),
            )
        )


def check_course_summary_variable_schema(
    page: dict[str, Any],
    index: int,
    path: Path,
    issues: list[dict[str, str]],
) -> None:
    """Reject upstream `blocks` leakage into the v1.8 summary template."""
    full_prompt = page.get("prompt") if isinstance(page.get("prompt"), str) else ""
    if "coursesummary-fixedtemplate-oneshot" not in full_prompt.lower():
        return
    prompt = final_html_payload(full_prompt)
    match = re.search(
        r"const\s+COURSE_SUMMARY_VARIABLES\s*=\s*(?:Object\.freeze\(\s*)?(\{.*?\})\s*\)?;",
        prompt,
        flags=re.DOTALL,
    )
    variable_block = match.group(1) if match else ""
    has_raw_blocks = bool(re.search(r"(?:[\"']?blocks[\"']?)\s*:", variable_block))
    required_fields = ("completionTitle", "summaryTitle", "contentBlocks", "nextLessonPreview", "pageAction")
    missing_fields = [
        field
        for field in required_fields
        if not re.search(rf"(?:[\"']{field}[\"']|\b{field}\b)\s*:", variable_block)
    ]
    if not match or has_raw_blocks or missing_fields:
        details = []
        if not match:
            details.append("未找到 COURSE_SUMMARY_VARIABLES 变量区")
        if has_raw_blocks:
            details.append("误注入上游 blocks，必须投影为 contentBlocks")
        if missing_fields:
            details.append("缺少 v1.8 必填字段：" + "、".join(missing_fields))
        issues.append(
            issue(
                "COURSE_SUMMARY_VARIABLE_SCHEMA_INVALID",
                "BLOCKER",
                f"pages[{index}] 课程小结 v1.8 变量合同不匹配（{'；'.join(details)}）",
                str(path),
            )
        )


def check_current_prompt_context(
    page: dict[str, Any],
    index: int,
    page_count: int,
    course_id: str,
    path: Path,
    issues: list[dict[str, str]],
) -> None:
    """Current prompts must never retain a copied lesson/page applicability line."""
    prompt = page.get("prompt") if isinstance(page.get("prompt"), str) else ""
    first_line = next((line.strip() for line in prompt.splitlines() if line.strip()), "")
    if "-R33-" not in first_line or page.get("page_kind") == "question_component_page":
        return
    label = str(page.get("tag") or page.get("title") or "")
    expected = (
        f"适用页面：{course_id}｜{page.get('page_no')}｜"
        f"第 {index + 1}/{page_count} 页｜{label}页。"
    )
    if expected not in prompt:
        issues.append(
            issue(
                "V35_STAGE6_PROMPT_CONTEXT_INVALID",
                "BLOCKER",
                f"pages[{index}] OneShot 适用页面必须为当前课次/页号/页数，期望：{expected}",
                str(path),
            )
        )


def check_post_class_task_compact_oneshot(
    page: dict[str, Any],
    index: int,
    path: Path,
    issues: list[dict[str, str]],
) -> None:
    prompt = page.get("prompt") if isinstance(page.get("prompt"), str) else ""
    compact = re.sub(r"\s+", "", prompt).lower()
    expected_action = "complete" if page.get("sdk_action") == "complete" else "next"
    required_markers = {
        "runs-postclasstask-": "Compact 课后任务提示词版本",
        "compact-oneshot": "登记的 Compact OneShot 路线",
        POST_CLASS_TASK_ONESHOT_CONTRACT.lower(): "当前 v1.9 正式合同",
        "https://res.xrunda.com/runs/plugin/creator/creator-review-sdk.js": "正式 CreatorReview SDK",
        'class="post-task-page"': "正式课后任务页面外层",
        'class="task-hero"': "正式课后任务头部",
        'class="notebook-badge"': "固定笔记本头图",
        "https://res.xrunda.com/xruns/static/image/20270724/3.png": "登记课后任务头图",
        'class="task-content"': "阶段 6 预编译的静态任务正文",
        "syncfooterreserve": "footer 高度同步",
    }
    forbidden_markers = {
        "fixedtemplate-oneshot": "旧 FixedTemplate 分支",
        "```": "Markdown 代码围栏",
        '"markdown"': "markdown 字段",
        "rawmarkdown": "rawMarkdown 字段",
        "constpage_data=": "运行时 PAGE_DATA",
        "page_data.blocks.foreach": "运行时 blocks 渲染",
        "promptlines": "运行时 promptLines",
        "document.createelement": "运行时创建学生正文节点",
        "li.textcontent=item": "对象直接写入 textContent",
        "https://r.xrunda.com/sdk/creatorreviewsdk.js": "旧 SDK 地址",
        "📒": "已替代的书本 emoji 头图",
    }
    missing = [label for marker, label in required_markers.items() if marker not in compact]
    forbidden = [label for marker, label in forbidden_markers.items() if marker in compact]
    expected_handler = "safecomplete" if expected_action == "complete" else "safenextpage"
    if f'function{expected_handler}' not in compact or f'click",{expected_handler}' not in compact:
        missing.append(f"{expected_action} 对应的安全 SDK 按钮绑定")
    if missing or forbidden:
        details = []
        if missing:
            details.append("缺少：" + "、".join(missing))
        if forbidden:
            details.append("禁止：" + "、".join(forbidden))
        issues.append(
            issue(
                "POST_CLASS_TASK_COMPACT_ONESHOT_INVALID",
                "BLOCKER",
                f"pages[{index}] 课后任务未使用登记的 Compact OneShot 合同（{'；'.join(details)}）",
                str(path),
            )
        )


def check_post_class_task_rich_static_dom(
    page: dict[str, Any],
    index: int,
    path: Path,
    issues: list[dict[str, str]],
) -> None:
    """Reject the Stage 6 flattening failure before import/create.

    The Compact contract permits source-absent optional modules, but a task page
    may not collapse its complete body into only task-intro paragraphs and bare
    pre blocks.  Rich semantic wrappers are the fixed Demo's rendering hooks.
    """
    prompt = page.get("prompt") if isinstance(page.get("prompt"), str) else ""
    html = final_html_payload(prompt)
    compact = re.sub(r"\s+", "", html).lower()
    if "runs-postclasstask-" not in prompt.lower():
        return

    has_semantic_wrapper = any(
        marker in compact
        for marker in (
            'class="glass-cardtask-card"',
            'class="glass-cardfacts-card"',
            'class="action-section"',
            'class="support-stack"',
            'class="glass-carddecision-card"',
        )
    )
    has_bare_prompt = "<pre" in compact and 'class="prompt-block"' not in compact
    has_rich_prompt = "<pre" not in compact or (
        'class="prompt-block"' in compact
        and 'class="prompt-label"' in compact
        and 'class="step-group"' in compact
        and 'class="glass-cardstep-card"' in compact
    )
    raw_markdown = "**" in html
    leaked_placeholder = any(marker in compact for marker in (">undefined<", ">null<"))
    if has_semantic_wrapper and has_rich_prompt and not raw_markdown and not leaked_placeholder:
        return

    details = []
    if not has_semantic_wrapper:
        details.append("正文缺少来源块对应的富语义容器，疑似被压平成段落")
    if has_bare_prompt or not has_rich_prompt:
        details.append("Prompt 未嵌入 step-group / step-card / prompt-block 富结构")
    if raw_markdown:
        details.append("学生 DOM 泄漏 Markdown 标记")
    if leaked_placeholder:
        details.append("学生 DOM 泄漏 undefined/null 占位")
    issues.append(
        issue(
            "POST_CLASS_TASK_RICH_STATIC_DOM_INVALID",
            "BLOCKER",
            f"pages[{index}] 课后任务静态 DOM 不符合富卡片投影合同（{'；'.join(details)}）",
            str(path),
        )
    )


def check_knowledge_transition_contract(
    page: dict[str, Any],
    index: int,
    path: Path,
    issues: list[dict[str, str]],
) -> None:
    page_data = page.get("page_data")
    if not isinstance(page_data, dict):
        return
    transition_text = page_data.get("transition_text")
    transition_placement = page_data.get("transition_placement")
    if not transition_text and transition_placement in {None, "", "none"}:
        return
    prompt = page.get("prompt") if isinstance(page.get("prompt"), str) else ""
    compact = re.sub(r"\s+", "", prompt).lower()
    required_markers = {
        ".knowledge-transition{": "固定类名",
        "font-size:14px": "14px 字号",
        "font-weight:400": "400 字重",
        "line-height:1.65": "1.65 行高",
        "background:transparent": "透明背景",
        "border:0": "无边框",
        "border-radius:0": "无圆角",
        "box-shadow:none": "无阴影",
        ".knowledge-transition::before,.knowledge-transition::after{content:none": "无伪元素",
    }
    if transition_placement == "after_content":
        required_markers[
            ".knowledge-content>.knowledge-transition:last-child{margin:16px00"
        ] = "末尾过渡句上间距"
    missing = [label for marker, label in required_markers.items() if marker not in compact]
    if (
        not isinstance(transition_text, str)
        or not transition_text.strip()
        or transition_placement not in {"before_title", "after_content"}
        or transition_text not in prompt
        or missing
    ):
        issues.append(
            issue(
                "KNOWLEDGE_TRANSITION_STYLE_DRIFT",
                "BLOCKER",
                f"pages[{index}] 过渡句未逐字携带或缺少固定弱化样式"
                + (f"（缺少：{'、'.join(missing)}）" if missing else ""),
                str(path),
            )
        )


def check_p3(path: Path, issues: list[dict[str, str]]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        issues.append(issue("P3_JSON_PARSE_FAIL", "BLOCKER", f"整课 JSON 无法解析：{exc}", str(path)))
        return {"status": "BLOCKED", "sha256": sha256_file(path)}
    pages = payload.get("pages") if isinstance(payload, dict) else None
    if not isinstance(pages, list) or not pages:
        issues.append(issue("P3_PAGES_MISSING", "BLOCKER", "整课 JSON 缺少非空 pages[]", str(path)))
        return {"status": "BLOCKED", "sha256": sha256_file(path)}
    require_governed_envelope = str(payload.get("version", "")).startswith(
        (
            "V3.5.0-R6",
            "V3.5.0-R7",
            "V3.5.0-R8",
            "V3.5.0-R9",
            "V3.5.0-R10",
            "V3.5.0-R11",
            "V3.5.0-R12",
            "V3.5.0-R28",
            "V3.5.0-R29",
            "V3.5.0-R30",
            "V3.5.0-R31",
            "V3.5.0-R32",
            "V3.5.0-R33",
            "V3.5.0-P3",
        )
    )
    prompt_versions: dict[str, list[int]] = {}
    if require_governed_envelope:
        required_root_fields = ("course_id", "title", "description", "source", "workflow")
        missing_root = [field for field in required_root_fields if field not in payload]
        if missing_root:
            issues.append(
                issue(
                    "V35_STAGE6_PAGE_ENVELOPE_INVALID",
                    "BLOCKER",
                    f"R6/R7 整课包络缺少根字段：{','.join(missing_root)}",
                    str(path),
                )
            )
        if str(payload.get("version")) in {"V3.5.0-R28", "V3.5.0-R29", "V3.5.0-R30", "V3.5.0-R31", "V3.5.0-R32", "V3.5.0-R33"}:
            expected_contract = (
                "R33-20260731"
                if str(payload.get("version")) == "V3.5.0-R33"
                else "R32-20260731"
                if str(payload.get("version")) == "V3.5.0-R32"
                else "R31-20260731"
                if str(payload.get("version")) == "V3.5.0-R31"
                else
                "R30-20260731"
                if str(payload.get("version")) == "V3.5.0-R30"
                else "R29-20260731"
                if str(payload.get("version")) == "V3.5.0-R29"
                else "R28-20260730"
            )
            task_title = payload.get("title")
            if not isinstance(task_title, str) or not re.fullmatch(
                rf"第[1-9]\d*课｜.+｜RunS_V3\.5\.0-S1-S6-{expected_contract}", task_title
            ):
                issues.append(
                    issue(
                        "WHOLE_COURSE_TASK_TITLE_INVALID",
                        "BLOCKER",
                        f"导入课件任务名必须来自顶层 title，格式为“第N课｜课程名称｜RunS_V3.5.0-S1-S6-{expected_contract}”；不得使用 pages[].title 或课程任务页标题。",
                        str(path),
                    )
                )
    for index, page in enumerate(pages):
        if not isinstance(page, dict):
            issues.append(issue("P3_PAGE_NOT_OBJECT", "BLOCKER", f"pages[{index}] 不是对象", str(path)))
            continue
        page_kind = page.get("page_kind")
        if require_governed_envelope:
            required_page_fields = (
                "tag",
                "title",
                "summary",
                "page_no",
                "page_kind",
                "runtime_type",
                "sdk_action",
                "is_last_page",
                "prompt",
                "components",
                "page_data",
            )
            missing_page = [field for field in required_page_fields if field not in page]
            expected_runtime = "component" if page_kind == "question_component_page" else "html"
            if (
                missing_page
                or not isinstance(page.get("summary"), str)
                or not page.get("summary", "").strip()
                or page.get("runtime_type") != expected_runtime
            ):
                issues.append(
                    issue(
                        "V35_STAGE6_PAGE_ENVELOPE_INVALID",
                        "BLOCKER",
                        f"pages[{index}] R6/R7 包络字段缺失或 runtime_type 不匹配"
                        + (f"（缺少：{','.join(missing_page)}）" if missing_page else ""),
                        str(path),
                    )
                )
        if nested_key_exists(page, "background"):
            issues.append(issue("QUESTION_BACKGROUND_FIELD_FORBIDDEN", "BLOCKER", f"pages[{index}] 含禁止的独立 background 字段", str(path)))
        components = page.get("components")
        if isinstance(components, list):
            for component in components:
                if (
                    isinstance(component, dict)
                    and component.get("type") == "categorization_question"
                    and (
                        not isinstance(component.get("content"), dict)
                        or component["content"].get("instruction") != ""
                    )
                ):
                    issues.append(
                        issue(
                            "CATEGORIZATION_INSTRUCTION_NOT_EMPTY",
                            "BLOCKER",
                            f"pages[{index}] categorization_question.content.instruction 必须为空字符串",
                            str(path),
                        )
                    )
        if not components:
            check_non_interactive_oneshot_prompt(page, index, path, issues)
            check_non_interactive_footer_seam_contract(page, index, path, issues)
            if require_governed_envelope:
                check_governed_oneshot_asset_contract(page, index, path, issues)
            prompt = page.get("prompt") if isinstance(page.get("prompt"), str) else ""
            incompatible = chrome68_prompt_incompatibilities(prompt)
            if incompatible:
                issues.append(
                    issue(
                        "V35_STAGE6_CHROME68_INCOMPATIBLE",
                        "BLOCKER",
                        f"pages[{index}] OneShot 使用 Chrome 68 不兼容特性：{'、'.join(incompatible)}",
                        str(path),
                    )
                )
            check_asset_bound_prompt_version(
                page,
                index,
                str(payload.get("course_id", "")),
                path,
                issues,
            )
            first_line = next((line.strip() for line in prompt.splitlines() if line.strip()), "")
            if first_line.startswith(ONESHOT_VERSION_PREFIX):
                version = first_line[len(ONESHOT_VERSION_PREFIX):].strip()
                prompt_versions.setdefault(version, []).append(index)
            check_current_prompt_context(page, index, len(pages), str(payload.get("course_id", "")), path, issues)
        if page_kind in DYNAMIC_PAGE_KINDS:
            check_dynamic_page_prompt(page, index, path, issues)
            check_dynamic_design_brief(page, index, path, issues)
            check_r34_visual_prompt_contract(page, index, path, issues)
        if page_kind == "course_summary":
            check_course_summary_ordered_list_style(page, index, path, issues)
            check_course_summary_page_action_contract(page, index, path, issues)
            check_course_summary_embedded_script(page, index, path, issues)
            check_course_summary_static_content_fallback(page, index, path, issues)
            check_course_summary_variable_schema(page, index, path, issues)
            check_r34_visual_prompt_contract(page, index, path, issues)
        if page_kind == "post_class_task":
            check_post_class_task_compact_oneshot(page, index, path, issues)
            check_post_class_task_rich_static_dom(page, index, path, issues)
        if page_kind == "course_intro":
            check_course_intro_image_contract(page, index, path, issues)
            check_course_intro_variable_schema(page, index, path, issues)
        if page_kind == "scene_intro":
            check_scene_intro_header_visual(page, index, path, issues)
        if page_kind == "knowledge_explanation":
            check_knowledge_transition_contract(page, index, path, issues)
        if components:
            if page.get("prompt") != "":
                issues.append(issue("INTERACTION_PROMPT_NOT_EMPTY", "BLOCKER", f"pages[{index}] 互动页 prompt 必须为空字符串", str(path)))
        elif page_kind not in DYNAMIC_PAGE_KINDS and page.get("prompt") is None:
            issues.append(issue("P3_PAGE_PROMPT_MISSING", "BLOCKER", f"pages[{index}] 非互动页缺少 prompt", str(path)))
        expected_action = "complete" if index == len(pages) - 1 else "nextpage"
        if page.get("sdk_action") != expected_action:
            issues.append(issue("P3_PAGE_ACTION_INVALID", "BLOCKER", f"pages[{index}].sdk_action 应为 {expected_action}", str(path)))
    for version, indexes in prompt_versions.items():
        if version and len(indexes) > 1:
            issues.append(
                issue(
                    "V35_STAGE6_PROMPT_VERSION_DUPLICATE",
                    "BLOCKER",
                    f"非互动页实际提示词版本号重复：{version}，pages={indexes}",
                    str(path),
                )
            )
    stage6_codes = {
        "DYNAMIC_PAGE_PROMPT_MISSING",
        "DYNAMIC_PAGE_PERSISTENT_FOOTER_CONTRACT_MISSING",
        "V35_DYNAMIC_CONTENT_WIDTH_INVALID",
        "V35_DYNAMIC_SCROLL_BOX_INVALID",
        "CASE_ANALYSIS_DECORATIVE_RAIL_CONTRACT_MISSING",
        "V35_DYNAMIC_DECORATIVE_RAIL_CONTRACT_MISSING",
        "V35_DYNAMIC_MEDIUM_DENSITY_BALANCE_CONTRACT_MISSING",
        "V35_SUMMARY_SINGLE_BLOCK_COMPOSITION_CONTRACT_MISSING",
        "V35_SUMMARY_SINGLE_BLOCK_COMPOSITION_HOOK_MISSING",
        "V35_STAGE6_FOOTER_SEAM_CONTRACT_INVALID",
        "QUESTION_BACKGROUND_FIELD_FORBIDDEN",
        "INTERACTION_PROMPT_NOT_EMPTY",
        "V35_STAGE6_PROMPT_DELIVERY_MODE_INVALID",
        "V35_STAGE6_PROMPT_VERSION_DUPLICATE",
        "COURSE_INTRO_IMAGE_ASSET_INVALID",
        "COURSE_INTRO_VARIABLE_SCHEMA_INVALID",
        "COURSE_SUMMARY_ORDERED_LIST_STYLE_INVALID",
        "COURSE_SUMMARY_PAGE_ACTION_CONTRACT_INVALID",
        "COURSE_SUMMARY_STATIC_ACTION_FALLBACK_INVALID",
        "COURSE_SUMMARY_EMBEDDED_SCRIPT_INVALID",
        "COURSE_SUMMARY_STATIC_CONTENT_FALLBACK_MISSING",
        "COURSE_SUMMARY_VARIABLE_SCHEMA_INVALID",
        "POST_CLASS_TASK_COMPACT_ONESHOT_INVALID",
        "POST_CLASS_TASK_RICH_STATIC_DOM_INVALID",
        "SCENE_INTRO_HEADER_VISUAL_INVALID",
        "KNOWLEDGE_TRANSITION_STYLE_DRIFT",
        "V35_DYNAMIC_DESIGN_BRIEF_INVALID",
        "V35_STAGE6_PAGE_ENVELOPE_INVALID",
        "V35_STAGE6_REGISTERED_ONESHOT_ASSET_INVALID",
        "V35_STAGE6_PROMPT_CONTEXT_INVALID",
        "V35_STAGE6_CHROME68_INCOMPATIBLE",
        "V35_STAGE6_PROMPT_VERSION_ASSET_MISMATCH",
        "CATEGORIZATION_INSTRUCTION_NOT_EMPTY",
    }
    blocked = any(item["code"].startswith("P3_") or item["code"] in stage6_codes for item in issues)
    return {"status": "BLOCKED" if blocked else "PASS", "page_count": len(pages), "sha256": sha256_file(path)}


def check_resource_branch(manifest: dict[str, Any], issues: list[dict[str, str]]) -> dict[str, Any]:
    branch = manifest.get("resource_branch") or {"status": "NOT_APPLICABLE"}
    status = branch.get("status") if isinstance(branch, dict) else None
    if status not in {"NOT_APPLICABLE", "APPLICABLE"}:
        issues.append(issue("RESOURCE_BRANCH_STATUS_INVALID", "BLOCKER", "resource_branch.status 必须是 NOT_APPLICABLE 或 APPLICABLE"))
        return {"status": "BLOCKED"}
    if status == "APPLICABLE" and not branch.get("final_import_path"):
        issues.append(issue("FINAL_IMPORT_PATH_MISSING", "BLOCKER", "资源分支已启用但缺少 final_import_path"))
        return {"status": "BLOCKED"}
    return {"status": status, "note": "P4 仅为条件性备用分支"}


def write_report(report_root: Path, report: dict[str, Any]) -> tuple[Path, Path]:
    canonical = dict(report)
    canonical.pop("generated_at", None)
    report_digest = sha256_bytes(canonical_json(canonical).encode("utf-8"))
    report["report_digest"] = report_digest
    target = report_root / "four_stage_check.json"
    markdown = report_root / "four_stage_check.md"
    if target.exists() or markdown.exists():
        raise FileExistsError(f"拒绝覆盖既有报告目录：{report_root}")
    report_root.mkdir(parents=True, exist_ok=False)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [f"# {report['lesson_id']} 六阶段 / Stage 6 候选检查", "", f"状态：`{report['status']}`", f"报告摘要：`{report_digest}`", "", "## 阶段结果", ""]
    for name, data in report["stages"].items():
        lines.append(f"- `{name}`：`{data['status']}`")
    lines.extend(["", "## 问题", ""])
    if report["issues"]:
        lines.extend(f"- `{item['severity']}` `{item['code']}`：{item['message']}" for item in report["issues"])
    else:
        lines.append("- 无静态阻断")
    lines.extend(["", "## S2E → 阶段6逐页差异", ""])
    if report.get("page_diffs"):
        lines.append("| 页面 | 结果 | 差异 |")
        lines.append("|---|---|---|")
        for row in report["page_diffs"]:
            differences = "；".join(row["differences"]) if row["differences"] else "无"
            lines.append(f"| `{row['page_no']}` | `{row['status']}` | {differences} |")
    else:
        lines.append("- 未进入逐页差异检查")
    lines.extend(["", "> 本报告不代表 S5.5 真机验收或 S5.6 BATCH_GO。"])
    markdown.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target, markdown


def run_s6_contract(lesson_id: str, effective_path: Path, whole_path: Path) -> int:
    """Validate S6 from its sole frozen S5 input, without legacy manifests."""
    issues: list[dict[str, str]] = []
    try:
        effective = json.loads(effective_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        issues.append(issue("S6_EFFECTIVE_CONTENT_UNAVAILABLE", "BLOCKER", f"S5 effective_content_full.json 无法解析：{exc}", str(effective_path)))
        effective = {}
    stage = check_p3(whole_path, issues) if whole_path.is_file() else {"status": "BLOCKED"}
    if not whole_path.is_file():
        issues.append(issue("S6_WHOLE_COURSE_JSON_MISSING", "BLOCKER", "S6 整课 JSON 不存在", str(whole_path)))
    effective_pages = effective.get("pages") if isinstance(effective, dict) else None
    whole_pages = []
    if whole_path.is_file():
        try:
            whole_payload = json.loads(whole_path.read_text(encoding="utf-8"))
            whole_pages = whole_payload.get("pages", []) if isinstance(whole_payload, dict) else []
        except (OSError, json.JSONDecodeError):
            pass
    page_diffs, diff_issues = compare_stage6_to_effective_content(
        effective if isinstance(effective_pages, list) else {"pages": []},
        {"pages": whole_pages} if isinstance(whole_pages, list) else {"pages": []},
    )
    issues.extend(diff_issues)
    blocked = any(item["severity"] == "BLOCKER" for item in issues)
    print(json.dumps({"checker": "check_four_stage_candidate", "checker_version": CHECKER_VERSION, "lesson_id": lesson_id, "status": "BLOCKED" if blocked else "IMPORT_READY_STATIC", "stages": {"S6": stage}, "page_diffs": page_diffs, "issues": issues}, ensure_ascii=False, indent=2))
    return EXIT_BLOCKED if blocked else EXIT_PASS


def main() -> int:
    parser = argparse.ArgumentParser(description="V3.5 六阶段链 Stage 6 / 正式 P3 整课装配检查器（只读）")
    parser.add_argument("--lesson-id", required=True)
    parser.add_argument("--lesson-root", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--report-dir", type=Path)
    parser.add_argument("--s6-contract", action="store_true", help="只以 S5 effective_content_full.json 与 S6 整课 JSON 校验静态装配。")
    parser.add_argument("--effective-content", type=Path)
    parser.add_argument("--whole-course", type=Path)
    parser.add_argument("--p3-import-root", type=Path, help="仅配合 --formal-stage6：允许 p3 指向原位集中导入目录，避免复制第二套 JSON")
    parser.add_argument(
        "--formal-stage6",
        action="store_true",
        help="无静态 BLOCKER 时输出 IMPORT_READY_STATIC；不替代 S5.x、create 或真实渲染验收",
    )
    args = parser.parse_args()
    if args.s6_contract:
        if not args.effective_content or not args.whole_course:
            parser.error("--s6-contract 必须同时提供 --effective-content 与 --whole-course")
        return run_s6_contract(args.lesson_id, args.effective_content.resolve(), args.whole_course.resolve())
    if not args.lesson_root or not args.manifest or not args.report_dir:
        parser.error("默认历史模式必须提供 --lesson-root、--manifest 与 --report-dir")
    lesson_root = args.lesson_root.expanduser().resolve()
    manifest_path = args.manifest.expanduser().resolve()
    p3_import_root = args.p3_import_root.expanduser().resolve() if args.p3_import_root else None
    if not lesson_root.is_dir() or lesson_root.is_symlink():
        print("INPUT_OR_CONFIG_ERROR: lesson-root 不存在或是符号链接", file=sys.stderr)
        return EXIT_INPUT_ERROR
    if p3_import_root and (not args.formal_stage6 or not p3_import_root.is_dir() or p3_import_root.is_symlink()):
        print("INPUT_OR_CONFIG_ERROR: --p3-import-root 仅可在 --formal-stage6 下指定为真实目录", file=sys.stderr)
        return EXIT_INPUT_ERROR
    manifest, issues = load_manifest(manifest_path, args.lesson_id, lesson_root, p3_import_root)
    if manifest is None:
        print(json.dumps({"status": "INPUT_OR_CONFIG_ERROR", "issues": issues}, ensure_ascii=False, indent=2))
        return EXIT_INPUT_ERROR
    stages: dict[str, Any] = {}
    if issues:
        stages["P1"] = {"status": "NOT_ENTERED"}
        stages["P2"] = {"status": "NOT_ENTERED"}
        stages["S2E"] = {"status": "NOT_ENTERED"}
        stages["P3"] = {"status": "NOT_ENTERED"}
        stages["STAGE4"] = {"status": "NOT_ENTERED"}
        page_diffs: list[dict[str, Any]] = []
    else:
        p1 = verify_artifact("p1", manifest["p1"], issues, lesson_root)
        stages["P1"] = check_p1(p1, issues) if p1 else {"status": "BLOCKED"}
        if stages["P1"]["status"] != "PASS":
            stages["P2"] = {"status": "NOT_ENTERED"}
            stages["S2E"] = {"status": "NOT_ENTERED"}
            stages["P3"] = {"status": "NOT_ENTERED"}
            stages["STAGE4"] = {"status": "NOT_ENTERED"}
            page_diffs = []
        else:
            p2 = verify_artifact("p2", manifest["p2"], issues, lesson_root)
            stages["P2"] = check_p2(p2, issues) if p2 else {"status": "BLOCKED"}
            if stages["P2"]["status"] != "PASS":
                stages["S2E"] = {"status": "NOT_ENTERED"}
                stages["P3"] = {"status": "NOT_ENTERED"}
                stages["STAGE4"] = {"status": "NOT_ENTERED"}
                page_diffs = []
            else:
                s2e = verify_artifact("s2e", manifest["s2e"], issues, lesson_root)
                stages["S2E"] = {
                    "status": "PASS" if s2e else "BLOCKED",
                    "sha256": sha256_file(s2e) if s2e else None,
                }
                if stages["S2E"]["status"] != "PASS":
                    stages["P3"] = {"status": "NOT_ENTERED"}
                    stages["STAGE4"] = {"status": "NOT_ENTERED"}
                    page_diffs = []
                else:
                    p3 = verify_artifact("p3", manifest["p3"], issues, lesson_root)
                    stages["P3"] = check_p3(p3, issues) if p3 else {"status": "BLOCKED"}
                    page_diffs = []
                    if p3:
                        try:
                            effective_payload = json.loads(s2e.read_text(encoding="utf-8"))
                            stage6_payload = json.loads(p3.read_text(encoding="utf-8"))
                            page_diffs, diff_issues = compare_stage6_to_effective_content(
                                effective_payload,
                                stage6_payload,
                            )
                            issues.extend(diff_issues)
                            if diff_issues:
                                stages["P3"]["status"] = "BLOCKED"
                        except (OSError, json.JSONDecodeError) as exc:
                            issues.append(
                                issue(
                                    "V35_STAGE6_EFFECTIVE_CONTENT_DIFF_UNRESOLVED",
                                    "BLOCKER",
                                    f"S2E→阶段6差异检查无法解析输入：{exc}",
                                )
                            )
                            stages["P3"]["status"] = "BLOCKED"
                    if stages["P3"]["status"] != "PASS":
                        stages["STAGE4"] = {"status": "NOT_ENTERED"}
                    else:
                        stages["RESOURCE_BRANCH"] = check_resource_branch(manifest, issues)
                        stages["STAGE4"] = {"status": "REVIEW_REQUIRED", "next_gate": "S5.1 -> S5.5", "note": "候选检查器不代替真实任务、DOM、交互和真机截图"}
    blocked = any(item["severity"] == "BLOCKER" for item in issues)
    status = "BLOCKED" if blocked else ("IMPORT_READY_STATIC" if args.formal_stage6 else "REVIEW_REQUIRED")
    next_gate = (
        "资源分支（如适用）→ S5.1 → S5.2（如工具支持）→ 经授权 S5.3 create → S5.4 → S5.5 → S5.6；本结果不授权这些 Gate"
        if args.formal_stage6 and not blocked
        else "修复 BLOCKER 并冻结 Golden Baseline 后，才可评估 Stage 6 正式吸收"
    )
    report = {"checker": "check_four_stage_candidate", "checker_version": CHECKER_VERSION, "lesson_id": args.lesson_id, "formal_stage6": args.formal_stage6, "status": status, "stages": stages, "page_diffs": page_diffs, "issues": issues, "manual_review": ["六阶段后真实 DOM / computed style / 视觉 / 交互 / SDK / 真机截图", "S5.6 BATCH_GO"], "next_gate": next_gate, "input_fingerprints": {"manifest_sha256": sha256_file(manifest_path)}}
    try:
        json_path, md_path = write_report(args.report_dir.expanduser().resolve() / args.lesson_id, report)
    except (OSError, FileExistsError) as exc:
        print(f"INPUT_OR_CONFIG_ERROR: 报告写入失败：{exc}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    print(json.dumps({"status": status, "json_report": str(json_path), "markdown_report": str(md_path), "report_digest": report["report_digest"]}, ensure_ascii=False, indent=2))
    if blocked:
        return EXIT_BLOCKED
    return EXIT_PASS if args.formal_stage6 else EXIT_REVIEW_REQUIRED


if __name__ == "__main__":
    raise SystemExit(main())
