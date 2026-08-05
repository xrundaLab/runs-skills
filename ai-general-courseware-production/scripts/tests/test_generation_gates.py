#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
VALIDATOR = SKILL_ROOT / "scripts" / "validators" / "validate_v35_effective_content.py"
S4_GENERATOR = SKILL_ROOT / "scripts" / "generators" / "build_final_page_plan.py"
S5_GENERATOR = SKILL_ROOT / "scripts" / "generators" / "build_effective_content.py"
BOUNDARY_VALIDATOR = SKILL_ROOT / "scripts" / "validators" / "validate_v35_page_plan_question_boundaries.py"
QUESTION_VALIDATOR = SKILL_ROOT / "scripts" / "validators" / "validate_question_component_json.py"
GATE_RUNNER = SKILL_ROOT / "scripts" / "orchestrator" / "run_stage_gate.py"
ASSEMBLER = SKILL_ROOT / "scripts" / "assembler" / "assemble_whole_course.py"
STATIC_CHECKER = SKILL_ROOT / "scripts" / "validators" / "check_whole_course_static.py"
DYNAMIC_HTML_VALIDATOR = SKILL_ROOT / "scripts" / "validators" / "validate_dynamic_html.py"
S5_GENERATOR_MODULE = SKILL_ROOT / "scripts" / "generators" / "build_effective_content.py"


def run(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *map(str, args)],
        text=True,
        capture_output=True,
        check=False,
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class GenerationGateTests(unittest.TestCase):
    @staticmethod
    def load_module(name: str, path: Path):
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise AssertionError(f"cannot load module: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_s5_blocks_course_summary_without_heading(self) -> None:
        fixture = FIXTURES / "summary-missing-heading"
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            page_plan = temp / "page_plan_full.md"
            page_plan.write_text(
                (fixture / "page_plan_full.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            payload = json.loads(
                (fixture / "effective_content_full.json").read_text(encoding="utf-8")
            )
            payload["source_page_plan"] = str(page_plan.resolve())
            effective = temp / "effective_content_full.json"
            effective.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            result = run(VALIDATOR, "--page-plan", page_plan, effective)
            report = json.loads(result.stdout)
            issue_types = {
                issue["issue_type"]
                for lesson in report["reports"]
                for issue in lesson["issues"]
            }

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("COURSE_SUMMARY_TITLE_MISSING", issue_types)

    def test_s4_generator_preserves_s2_none_transition(self) -> None:
        fixture = FIXTURES / "transition-boundary"
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "page_plan_full.md"
            result = run(
                S4_GENERATOR,
                "--working-plan",
                fixture / "page_plan_working_full.md",
                "--question-processed",
                fixture / "question_processed_full.md",
                "--output",
                output,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            text = output.read_text(encoding="utf-8")
            p02 = text.split("## P02", 1)[1].split("## P03", 1)[0]
            p03 = text.split("## P03", 1)[1]
            self.assertIn("- 过渡句位置：none", p02)
            self.assertIn("- 过渡句原文：无", p02)
            self.assertNotIn("试一试：再连一次", p02)
            self.assertIn("- 胶囊文案：试一试：再连一次", p03)

    def test_s2_owns_interaction_boundary_semantics_and_s4_does_not_repeat_them(self) -> None:
        validator = self.load_module("courseware_boundary_validator", BOUNDARY_VALIDATOR)
        working = (FIXTURES / "transition-boundary" / "page_plan_working_full.md").read_text(encoding="utf-8")
        working = working.replace(
            "ChatBot、LLM、GenAI 和 AIGC 处在不同位置。",
            "ChatBot、LLM、GenAI 和 AIGC 处在不同位置。\n\n现在来选一条更容易执行的修改要求。",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "page_plan_working_full.md"
            path.write_text(working, encoding="utf-8")
            s2_issue_types = {
                issue["issue_type"]
                for issue in validator.validate_working_plan_contract(path)["issues"]
            }
            s4_issue_types = {
                issue["issue_type"]
                for issue in validator.validate_effective_plan_contract(path)["issues"]
            }

        self.assertIn("V35_INTERACTION_STEM_SPLIT_ACROSS_PAGES", s2_issue_types)
        self.assertNotIn("V35_INTERACTION_STEM_SPLIT_ACROSS_PAGES", s4_issue_types)

    def test_stage_freeze_contracts_use_path_and_sha_without_redundant_byte_count(self) -> None:
        s2_validator = self.load_module("courseware_s2_sha_freeze", BOUNDARY_VALIDATOR)
        s3_validator = self.load_module("courseware_s3_sha_freeze", QUESTION_VALIDATOR)
        digest = "a" * 64
        s2_header = (
            "<!-- S2_INPUT_FREEZE\n"
            "source_manifest: /tmp/source_manifest.json\n"
            "final_preprocessed: /tmp/final_preprocessed.md\n"
            f"sha256: {digest}\n-->"
        )
        s3_header = (
            "<!-- S3_INPUT_FREEZE\n"
            "page_plan_working_full: /tmp/page_plan_working_full.md\n"
            f"sha256: {digest}\n-->"
        )

        self.assertIsNotNone(s2_validator.S2_INPUT_FREEZE_RE.search(s2_header))
        self.assertIsNotNone(s3_validator.S3_INPUT_FREEZE_RE.search(s3_header))
        self.assertNotIn("bytes", s2_validator.S2_INPUT_FREEZE_RE.pattern)
        self.assertNotIn("bytes", s3_validator.S3_INPUT_FREEZE_RE.pattern)

    def test_gate_receipt_attempt_paths_are_immutable_and_incrementing(self) -> None:
        runner = self.load_module("courseware_gate_attempt_receipts", GATE_RUNNER)
        with tempfile.TemporaryDirectory() as temp_dir:
            receipts = Path(temp_dir) / "receipts"
            first_attempt, first_path = runner.attempt_receipt_path(receipts, "S3")
            first_path.write_text("{}\n", encoding="utf-8")
            second_attempt, second_path = runner.attempt_receipt_path(receipts, "S3")

            self.assertEqual(first_attempt, 1)
            self.assertEqual(first_path.name, "s3_gate_receipt_attempt-001.json")
            self.assertEqual(second_attempt, 2)
            self.assertEqual(second_path.name, "s3_gate_receipt_attempt-002.json")

    def test_s5_generator_filters_only_status_sentence(self) -> None:
        fixture = FIXTURES / "summary-status-preview"
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "effective_content_full.json"
            result = run(
                S5_GENERATOR,
                "--lesson-id",
                "lesson001",
                "--page-plan",
                fixture / "page_plan_full.md",
                "--output",
                output,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            page = json.loads(output.read_text(encoding="utf-8"))["pages"][0]
            raw = page["source"]["rawMarkdown"]
            blocks = page["effective_content"]["blocks"]
            visible = "\n".join(
                block.get("text", "") for block in blocks if isinstance(block, dict)
            )
            self.assertIn("本课没有课后练习。", raw)
            self.assertNotIn("本课没有课后练习。", visible)
            self.assertIn("下一课，我们继续学习如何核查 AI 输出。", visible)
            self.assertEqual(blocks[0]["type"], "heading")
            self.assertEqual(blocks[0]["text"], "这一课记住一件事")

    def test_s5_projects_complete_post_class_task_from_frozen_source(self) -> None:
        generator = self.load_module("courseware_post_class_projection", S5_GENERATOR_MODULE)
        assembler = self.load_module("courseware_post_class_assembler", ASSEMBLER)
        raw = (
            "## 课后练习：完成太空猫语音责任卡\n\n"
            "请完成一次固定的合成语音实践。\n\n"
            "**固定材料：**课程原创太空猫；不模仿真人。\n\n"
            "```text\n请把这段文字转换为通用合成语音。\n```\n\n"
            "完整听一遍，再填写责任卡。"
        )
        page = generator.protected_page(
            {
                "page_no": "P10",
                "page_type": "课后任务",
                "capsule": "课后任务",
                "action": "complete",
                "source_block": "S1U2-L014-B06",
                "body": raw,
            },
        )

        self.assertEqual(page["content"]["taskTitle"], "课后练习：完成太空猫语音责任卡")
        self.assertEqual(
            [section["type"] for section in page["sections"]],
            ["task", "facts", "prompt", "paragraph"],
        )
        self.assertEqual(
            [section["role"] for section in page["sections"]],
            ["lead", "preflight", "prompt", "review"],
        )
        self.assertEqual(
            "\n\n".join(section["sourceMarkdown"] for section in page["sections"]),
            "\n\n".join(raw.split("\n\n")[1:]),
        )

        html = assembler.task_html(
            page["content"]["taskTitle"], page["sections"], "complete"
        )
        for expected in (
            "请完成一次固定的合成语音实践。",
            "课程原创太空猫；不模仿真人。",
            "请把这段文字转换为通用合成语音。",
            "完整听一遍，再填写责任卡。",
        ):
            self.assertIn(expected, html)

    def test_s5_blocks_post_class_task_that_only_projects_first_section(self) -> None:
        sys.path.insert(0, str(VALIDATOR.parent))
        try:
            validator = self.load_module("courseware_post_class_validator", VALIDATOR)
        finally:
            sys.path.pop(0)
        raw = "## 课后练习\n\n第一段。\n\n第二段。"
        issues: list[dict[str, str]] = []
        validator.validate_template_preflight(
            {
                "page_no": "P10",
                "page_type": "课后任务",
                "content": {"taskTitle": "课后练习"},
                "sections": [
                    {
                        "type": "task",
                        "text": "第一段。",
                        "sourceMarkdown": "第一段。",
                    }
                ],
                "display_hints": {"layout": "task"},
                "source": {"rawMarkdown": raw},
            },
            issues,
        )
        self.assertIn(
            "V35_S2E_POST_CLASS_TASK_SOURCE_PROJECTION_INVALID",
            {issue["issue_type"] for issue in issues},
        )

    def test_s5_does_not_require_dynamic_design_seed(self) -> None:
        generator = self.load_module("courseware_s5_preflight_generator", S5_GENERATOR_MODULE)
        blocks = generator.parse_dynamic_source_blocks("## 标题\n\n第一段。")
        brief = generator.normalize_dynamic_design_brief(blocks)
        self.assertTrue(brief["teachingAction"].strip())
        self.assertTrue(brief["readingFlow"])

    def test_p01_projects_delimited_knowledge_points_to_ordered_list(self) -> None:
        generator = self.load_module("courseware_p01_projection", S5_GENERATOR_MODULE)
        validator = self.load_module("courseware_p01_validator", VALIDATOR)
        assembler = self.load_module("courseware_p01_assembler", ASSEMBLER)
        raw = (
            FIXTURES / "representative-projections" / "p01_source.md"
        ).read_text(encoding="utf-8").strip()
        page = generator.protected_page(
            {
                "page_no": "P01",
                "page_type": "课程开篇",
                "capsule": "课程开篇",
                "action": "nextPage",
                "source_block": "course_info_header",
                "body": raw,
            }
        )

        self.assertIn("；", page["effective_content"]["知识点"])
        self.assertIn("\n", page["effective_content"]["知识点"])
        self.assertEqual(
            page["content"]["knowledgePoints"],
            ["识别输入", "比较输出", "记录判断"],
        )
        self.assertEqual(
            page["sections"][-1]["items"],
            page["content"]["knowledgePoints"],
        )
        self.assertEqual(
            assembler.intro_values(page, "nextpage")["knowledgePoints"],
            ["识别输入", "比较输出", "记录判断"],
        )
        issues: list[dict[str, str]] = []
        validator.validate_p01(page, raw, issues)
        self.assertFalse(issues)

        page["content"]["knowledgePoints"] = [page["effective_content"]["知识点"]]
        validator.validate_p01(page, raw, issues)
        self.assertIn(
            "V35_S2E_P01_KNOWLEDGE_POINTS_PROJECTION_INVALID",
            {item["issue_type"] for item in issues},
        )

    def test_p05_exact_blocks_and_visual_recipe_are_source_derived(self) -> None:
        generator = self.load_module("courseware_p05_projection", S5_GENERATOR_MODULE)
        assembler = self.load_module("courseware_p05_assembler", ASSEMBLER)
        raw = (
            FIXTURES / "representative-projections" / "p05_source.md"
        ).read_text(encoding="utf-8").strip()
        page = generator.protected_page(
            {
                "page_no": "P05",
                "page_type": "知识讲解",
                "capsule": "知识讲解",
                "action": "nextPage",
                "source_block": "fixture-p05",
                "body": raw,
            }
        )
        expected_blocks = generator.parse_dynamic_source_blocks(raw)
        self.assertEqual(page["effective_content"]["blocks"], expected_blocks)
        self.assertEqual(page["content"]["blocks"], expected_blocks)
        self.assertEqual(page["sections"], expected_blocks)

        page_data = assembler.dynamic_page_data(
            page, "lesson999", 5, 10, "knowledge_explanation", "next"
        )
        self.assertEqual(page_data["contentBlocks"], expected_blocks)
        recipes = {row["recipe"] for row in page_data["visualRecipePlan"]["recipes"]}
        self.assertTrue(
            {"process_steps", "list_or_option_compact", "role_distribution_inline"}.issubset(recipes)
        )
        execution = page_data["visualRecipePlan"]["designExecutionContract"]
        for key in (
            "layoutArchetype",
            "groupPresentation",
            "sourceProjectionPlan",
            "emphasisTargets",
            "surfacePolicy",
            "colorRoles",
            "spaceBalance",
            "alignmentPolicy",
            "comparisonLayoutPolicy",
            "highlightPolicy",
        ):
            self.assertEqual(execution[key], page["design_brief"][key])
        self.assertTrue(
            page_data["visualRecipePlan"]["sourceTextProjectionContract"]["required"]
        )

    def test_p10_task_dom_follows_s5_section_order(self) -> None:
        generator = self.load_module("courseware_p10_projection", S5_GENERATOR_MODULE)
        assembler = self.load_module("courseware_p10_assembler", ASSEMBLER)
        checker = self.load_module("courseware_p10_checker", STATIC_CHECKER)
        raw = (
            FIXTURES / "representative-projections" / "p10_source.md"
        ).read_text(encoding="utf-8").strip()
        page = generator.protected_page(
            {
                "page_no": "P10",
                "page_type": "课后任务",
                "capsule": "课后任务",
                "action": "complete",
                "source_block": "fixture-p10",
                "body": raw,
            }
        )
        self.assertEqual(
            [section["type"] for section in page["sections"]],
            ["task", "facts", "step", "prompt", "decision", "fallback"],
        )
        self.assertEqual(
            [section["role"] for section in page["sections"]],
            ["lead", "preflight", "action", "prompt", "decision", "fallback"],
        )
        document = assembler.task_html(
            page["content"]["taskTitle"], page["sections"], "complete"
        )
        self.assertEqual(
            [int(value) for value in re.findall(r'data-source-section-index="(\d+)"', document)],
            list(range(len(page["sections"]))),
        )
        self.assertTrue(checker.task_sections_match_static_dom(page["sections"], document))
        self.assertFalse(
            checker.task_sections_match_static_dom(
                list(reversed(page["sections"])), document
            )
        )
        visible = [
            section.get("text") or "".join(section.get("items", []))
            for section in page["sections"]
        ]
        positions = [document.index(assembler.esc(value)) for value in visible]
        self.assertEqual(positions, sorted(positions))

    def test_p10_semantic_steps_compile_into_one_ordered_timeline(self) -> None:
        generator = self.load_module("courseware_p10_semantic_projection", S5_GENERATOR_MODULE)
        assembler = self.load_module("courseware_p10_semantic_assembler", ASSEMBLER)
        checker = self.load_module("courseware_p10_semantic_checker", STATIC_CHECKER)
        raw = (
            FIXTURES
            / "representative-projections"
            / "p10_semantic_steps_source.md"
        ).read_text(encoding="utf-8").strip()
        page = generator.protected_page(
            {
                "page_no": "P10",
                "page_type": "课后任务",
                "capsule": "课后任务",
                "action": "complete",
                "source_block": "fixture-p10-semantic-steps",
                "body": raw,
            }
        )

        self.assertEqual(
            [section.get("role") for section in page["sections"]],
            [
                "lead",
                "preflight",
                "action",
                "prompt",
                "review",
                "checklist",
                "note",
                "condition",
                "correctivePrompt",
                "safetyFallback",
            ],
        )
        document = assembler.task_html(
            page["content"]["taskTitle"], page["sections"], "complete"
        )
        self.assertEqual(document.count("<h2>操作步骤</h2>"), 1)
        self.assertNotIn("开始行动", document)
        for pair in (
            "action-prompt",
            "review-checklist",
            "condition-correctivePrompt",
        ):
            self.assertEqual(document.count(f'data-task-group-pair="{pair}"'), 1)
        self.assertIn('class="checklist-block"', document)
        checklist_html = document.split('class="checklist-block"', 1)[1].split(
            "</section>", 1
        )[0]
        self.assertNotIn('class="prompt-label"', checklist_html)
        lead_html = document.split('data-section-role="lead"', 1)[0]
        self.assertNotIn('class="glass-card task-card"', lead_html)
        self.assertTrue(checker.task_sections_match_static_dom(page["sections"], document))
        self.assertFalse(
            checker.task_sections_match_static_dom(
                page["sections"], document.replace("仍需核验：", "待补充：", 1)
            )
        )
        self.assertTrue(checker.task_semantic_structure_matches_static_dom(page["sections"], document))
        self.assertFalse(
            checker.task_semantic_structure_matches_static_dom(
                page["sections"], document.replace("操作步骤", "开始行动")
            )
        )

    def test_s2_requires_extension_practice_for_post_class_metadata(self) -> None:
        validator = self.load_module(
            "courseware_post_class_page_type_validator", BOUNDARY_VALIDATOR
        )
        working = (
            '<mark>页面块 P01｜页面类型：课后任务｜胶囊文案：课后练习</mark>\n'
            "## 课后练习\n\n完成一次练习。\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "page_plan_working_full.md"
            path.write_text(working, encoding="utf-8")
            report = validator.validate(path, legacy_boundary_heuristic=False)

        self.assertIn(
            "POST_CLASS_PAGE_LABEL_NOT_CANONICAL",
            {issue["issue_type"] for issue in report["issues"]},
        )

    def test_s5_s6_canonicalize_post_class_input_aliases(self) -> None:
        generator = self.load_module(
            "courseware_post_class_alias_projection", S5_GENERATOR_MODULE
        )
        assembler = self.load_module(
            "courseware_post_class_alias_assembler", ASSEMBLER
        )
        checker = self.load_module(
            "courseware_post_class_alias_checker", STATIC_CHECKER
        )
        raw = "## 课后练习\n\n完成一次练习。"

        for alias in ("课后任务", "课后练习", "拓展练习"):
            with self.subTest(alias=alias):
                self.assertEqual(
                    checker.expected_page_envelope_metadata(
                        {"page_type": alias, "capsule": alias}
                    ),
                    {
                        "page_kind": "post_class_task",
                        "title": "拓展练习",
                        "tag": "拓展练习",
                    },
                )
                page = generator.protected_page(
                    {
                        "page_no": "P10",
                        "page_type": alias,
                        "capsule": alias,
                        "action": "complete",
                        "source_block": "fixture-post-class-alias",
                        "body": raw,
                    }
                )
                self.assertEqual(page["page_type"], "拓展练习")
                self.assertEqual(page["capsule"], "拓展练习")
                self.assertEqual(page["effective_content"]["text"], "拓展练习")

                prompt, _, _ = assembler.task_prompt(
                    page, "lesson012", "complete", 10, 10
                )
                self.assertIn(
                    "适用页面：lesson012｜P10｜第 10/10 页｜拓展练习页。",
                    prompt,
                )
                issues: list[dict[str, str]] = []
                checker.check_current_prompt_context(
                    {
                        "page_no": "P10",
                        "page_kind": "post_class_task",
                        "title": "拓展练习",
                        "tag": "拓展练习",
                        "prompt": prompt,
                    },
                    9,
                    10,
                    "lesson012",
                    Path("whole_course.json"),
                    issues,
                )
                self.assertEqual(issues, [])

    def test_s5_help_and_runner_expose_no_candidate_input(self) -> None:
        generator_help = run(S5_GENERATOR, "--help")
        runner_help = run(GATE_RUNNER, "--help")
        self.assertEqual(generator_help.returncode, 0, generator_help.stderr)
        self.assertEqual(runner_help.returncode, 0, runner_help.stderr)
        self.assertNotIn("--draft", generator_help.stdout)
        self.assertNotIn("--draft", runner_help.stdout)

    def test_s6_summary_projection_uses_heading_only_as_title(self) -> None:
        fixture = FIXTURES / "summary-status-preview"
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "effective_content_full.json"
            result = run(
                S5_GENERATOR,
                "--lesson-id",
                "lesson001",
                "--page-plan",
                fixture / "page_plan_full.md",
                "--output",
                output,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            page = json.loads(output.read_text(encoding="utf-8"))["pages"][0]

            module = self.load_module("courseware_assembler", ASSEMBLER)
            values = module.summary_values(page, "complete")

            self.assertEqual(values["summaryTitle"], "这一课记住一件事")
            self.assertFalse(
                any(block.get("type") == "heading" for block in values["contentBlocks"])
            )

    def test_s6_summary_prompt_precompiles_static_cta_from_page_action(self) -> None:
        module = self.load_module("courseware_summary_static_cta", ASSEMBLER)
        context = {
            "lesson_id": "lesson015",
            "page_no": "P08",
            "page_index": 8,
            "page_count": 9,
            "page_label": "课程小结",
        }
        base_values = {
            "completionTitle": "本课重点回顾",
            "summaryTitle": "课程小结",
            "contentBlocks": [{"type": "paragraph", "text": "本课重点。"}],
            "nextLessonPreview": "",
        }

        next_prompt = module.prompt_from_asset(
            "04_课程小结页_固定模板OneShot.md",
            "COURSE_SUMMARY_VARIABLES",
            {**base_values, "pageAction": "next"},
            context,
        )
        complete_prompt = module.prompt_from_asset(
            "04_课程小结页_固定模板OneShot.md",
            "COURSE_SUMMARY_VARIABLES",
            {**base_values, "pageAction": "complete"},
            context,
        )

        self.assertRegex(
            next_prompt,
            r'<button[^>]+id="completeButton"[^>]*>继续学习</button>',
        )
        self.assertRegex(
            complete_prompt,
            r'<button[^>]+id="completeButton"[^>]*>完成学习</button>',
        )

    def run_s4_gate(
        self,
        temp: Path,
        prior_receipt: Path | None,
    ) -> tuple[subprocess.CompletedProcess[str], Path]:
        fixture = FIXTURES / "transition-boundary"
        output = temp / "S4" / "page_plan_full.md"
        args: list[object] = [
            GATE_RUNNER,
            "--stage",
            "S4",
            "--lesson-id",
            "lesson001",
            "--receipt-dir",
            temp / "receipts",
            "--working-plan",
            fixture / "page_plan_working_full.md",
            "--question-processed",
            fixture / "question_processed_full.md",
            "--output",
            output,
        ]
        if prior_receipt is not None:
            args.extend(["--prior-receipt", prior_receipt])
        return run(*args), output

    def write_s3_receipt(
        self,
        path: Path,
        *,
        status: str = "PASS",
        question_sha: str | None = None,
    ) -> Path:
        fixture = FIXTURES / "transition-boundary"
        working = fixture / "page_plan_working_full.md"
        question = fixture / "question_processed_full.md"
        payload = {
            "contract": "RunS_V3.5.0-S1-S6-R36-20260731",
            "lesson_id": "lesson001",
            "stage": "S3",
            "status": status,
            "command": ["fixture"],
            "exit_code": 0 if status == "PASS" else 1,
            "inputs": [
                {"role": "working_plan", "path": str(working.resolve()), "sha256": sha256(working)}
            ],
            "output": {
                "role": "question_processed",
                "path": str(question.resolve()),
                "sha256": question_sha or sha256(question),
            },
            "issues": [],
            "prior_receipt": None,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def test_gate_runner_blocks_s4_without_prior_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result, output = self.run_s4_gate(Path(temp_dir), None)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertFalse(output.exists())
            self.assertIn("PRIOR_RECEIPT_MISSING", result.stdout)

    def test_gate_runner_blocks_s4_after_blocked_s3(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            prior = self.write_s3_receipt(temp / "s3.json", status="BLOCKED")
            result, output = self.run_s4_gate(temp, prior)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertFalse(output.exists())
            self.assertIn("PRIOR_GATE_NOT_PASS", result.stdout)

    def test_gate_runner_blocks_s4_when_s3_hash_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            prior = self.write_s3_receipt(temp / "s3.json", question_sha="0" * 64)
            result, output = self.run_s4_gate(temp, prior)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertFalse(output.exists())
            self.assertIn("PRIOR_OUTPUT_HASH_MISMATCH", result.stdout)

    def test_gate_runner_allows_s4_after_matching_s3_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            prior = self.write_s3_receipt(temp / "s3.json")
            result, output = self.run_s4_gate(temp, prior)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(output.is_file())
            receipt = json.loads(
                (temp / "receipts" / "s4_gate_receipt.json").read_text(encoding="utf-8")
            )
            self.assertEqual(receipt["status"], "PASS")
            self.assertEqual(receipt["output"]["sha256"], sha256(output))

    def test_gate_runner_preserves_generator_blocker_code(self) -> None:
        fixture = FIXTURES / "summary-missing-heading"
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            page_plan = fixture / "page_plan_full.md"
            prior = temp / "s4.json"
            prior.write_text(
                json.dumps(
                    {
                        "contract": "RunS_V3.5.0-S1-S6-R36-20260731",
                        "lesson_id": "lesson001",
                        "stage": "S4",
                        "status": "PASS",
                        "output": {
                            "role": "page_plan",
                            "path": str(page_plan.resolve()),
                            "sha256": sha256(page_plan),
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            result = run(
                GATE_RUNNER,
                "--stage",
                "S5",
                "--lesson-id",
                "lesson001",
                "--receipt-dir",
                temp / "receipts",
                "--prior-receipt",
                prior,
                "--page-plan",
                page_plan,
                "--output",
                temp / "effective_content_full.json",
            )

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            receipt = json.loads(
                (temp / "receipts" / "s5_gate_receipt.json").read_text(encoding="utf-8")
            )
            self.assertEqual(receipt["status"], "BLOCKED")
            self.assertEqual(
                receipt["issues"][0]["issue_type"],
                "COURSE_SUMMARY_TITLE_MISSING",
            )

    def test_static_checker_accepts_cta_button_with_extra_attributes(self) -> None:
        checker = self.load_module("courseware_static_checker", STATIC_CHECKER)
        recipes = {
            "nonRenderable": True,
            "recipeContract": "R36_REUSABLE_DYNAMIC_VISUAL_RECIPES",
            "recipes": [
                {"recipe": "intro_observation_band"},
                {"recipe": "analysis_conclusion_emphasis"},
            ],
            "mediumReadingAreaBalance": {
                "required": False,
                "target": "60_to_75_percent_of_available_reading_area",
                "method": "distributed_real_groups_card_density_and_spacing",
                "forbidFillers": True,
            },
            "orderedListOrdinalContract": {
                "required": False,
                "source": "items[]",
                "startAt": 1,
                "displayExpression": "itemIndex + 1",
                "forbid": ["contentBlockIndex", "globalCounter", "doubleNumbering"],
            },
            "unorderedListPresentationContract": {
                "required": False,
                "source": "items[]",
                "preserveExistingLabels": True,
                "forbid": ["numericBadge", "autoOrdinal", "doubleNumbering"],
            },
            "visibleRecipeDifferenceContract": {
                "required": True,
                "minimumDistinctTreatments": 2,
                "forbid": ["sameWhiteCardStack", "positionOnlyDifferentiation"],
            },
        }
        footer = {
            "required": True,
            "footerClass": "case-footer",
            "buttonClass": "case-primary-button",
            "buttonText": "继续学习",
        }
        prompt_data = {
            "contentBlocks": [
                {"type": "heading", "text": "案例"},
                {"type": "paragraph", "text": "材料"},
                {"type": "paragraph", "text": "分析"},
            ],
            "visualRecipePlan": recipes,
            "footerContract": footer,
        }
        prompt = "\n".join(
            [
                "<PAGE_DATA>",
                json.dumps(prompt_data, ensure_ascii=False),
                "</PAGE_DATA>",
                "禁止装饰性左侧彩色竖线、轨道、连接点或箭头 border-left",
                "content-module--intro-band content-module--list-compact",
                "content-module--sequence-compact content-module--emphasis",
                "sameWhiteCardStack positionOnlyDifferentiation 至少两种选中的配方",
                '<footer class="case-footer">',
                '<button class="case-primary-button" type="button">继续学习</button>',
                "不得条件省略 display:none visibility:hidden opacity:0",
            ]
        )
        page = {
            "page_kind": "case_analysis",
            "sdk_action": "nextpage",
            "prompt": prompt,
            "page_data": {
                "oneshot_contract_version": "RunS-CaseAnalysis-Dynamic-OneShot-v1.13",
                "visualRecipePlan": recipes,
                "design_brief": {"density": "medium"},
                "footerContract": footer,
            },
        }
        issues: list[dict[str, str]] = []

        checker.check_r34_visual_prompt_contract(page, 4, Path("whole_course.json"), issues)

        self.assertNotIn(
            "V35_DYNAMIC_VISIBLE_CTA_CONTRACT_MISSING",
            {item["code"] for item in issues},
        )

    def test_case_oneshot_embeds_visible_cta_prohibition_contract(self) -> None:
        assembler = self.load_module("courseware_case_assembler", ASSEMBLER)
        prompt = assembler.text_block("08_案例分析页_动态生成OneShot.md")

        for marker in (
            "不得条件省略",
            "display:none",
            "visibility:hidden",
            "opacity:0",
            "整块原文 + 派生子项",
            "拼接后的 textContent 必须逐字等于该来源块原文",
            "uniformRoundedCardStack",
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
        ):
            self.assertIn(marker, prompt)

    def test_s5_derives_knowledge_groups_from_content_relationships(self) -> None:
        generator = self.load_module("courseware_s5_generator", S5_GENERATOR_MODULE)
        comparison_blocks = [
            {"type": "heading", "text": "每一种媒介都要对共同目标有用"},
            {"type": "paragraph", "text": "活动的可靠信息已经确定。"},
            {"type": "paragraph", "text": "小组做了两个方案。"},
            {"type": "paragraph", "text": "方案A中，文字、图片和声音各自承担任务。"},
            {"type": "paragraph", "text": "方案B中，三种媒介重复同一段通知。"},
            {"type": "paragraph", "text": "关键是每一种媒介都承担有用的任务。"},
        ]
        brief = generator.normalize_dynamic_design_brief(comparison_blocks)

        self.assertEqual(brief["density"], "medium")
        self.assertEqual(brief["contentShape"], "parallel_comparison")
        self.assertIn("comparison", [group["id"] for group in brief["semanticGroups"]])
        self.assertNotIn("frozen_segment_01", brief["hierarchyFocus"])

    def test_s5_freezes_executable_visual_strategy_for_process_page(self) -> None:
        generator = self.load_module("courseware_s5_design_generator", S5_GENERATOR_MODULE)
        blocks = [
            {"type": "heading", "text": "组合之前先写清目标、受众和分工"},
            {"type": "paragraph", "text": "制作多媒介内容时，可以先完成一个简单计划。"},
            {
                "type": "paragraph",
                "text": "先写受众是谁、希望他们知道或做到什么。再选择至少两种真正有用的媒介，说明每一种媒介负责哪部分信息。完成初版后，检查事实、来源、个人信息和各部分是否一致。",
            },
            {
                "type": "paragraph",
                "text": "在这个观星提醒里，受众是第一次参加的家庭，目标是迅速获得完整、准确的准备信息。文字负责精确信息，图片帮助看懂活动场景，声音提醒内容开始。",
            },
            {
                "type": "paragraph",
                "text": "工具可以帮助整理或生成其中一部分，但哪些信息可靠、哪些素材能用、最终是否采用，仍要由人判断。",
            },
        ]
        brief = generator.normalize_dynamic_design_brief(blocks)

        self.assertEqual(
            brief["layoutArchetype"], "guided_process_with_role_distribution"
        )
        self.assertEqual(
            [row["groupId"] for row in brief["groupPresentation"]],
            [row["id"] for row in brief["semanticGroups"]],
        )
        self.assertTrue(brief["surfacePolicy"]["lightDominant"])
        self.assertFalse(brief["surfacePolicy"]["allowLargeDarkSurface"])
        self.assertEqual(
            brief["surfacePolicy"]["nonCodeDarkSurfaceAreaPercentMax"], 0
        )
        self.assertGreaterEqual(brief["surfacePolicy"]["minimumOpenRegions"], 1)
        self.assertEqual(brief["surfacePolicy"]["maximumTopLevelVisualRegions"], 4)
        self.assertEqual(brief["surfacePolicy"]["nestedItemStyle"], "flat_subregion")
        self.assertFalse(brief["surfacePolicy"]["nestedItemsUseIndependentShadow"])
        self.assertEqual(brief["surfacePolicy"]["maximumDecorativeGroups"], 2)
        self.assertEqual(brief["spaceBalance"]["maximumUnusedLowerAreaPercent"], 12)
        self.assertEqual(
            brief["alignmentPolicy"],
            {
                "priority": ["shared_left_edge", "shared_top_edge", "consistent_width", "semantic_asymmetry"],
                "sameSemanticLevelSharedLeftEdge": True,
                "comparisonPeersTopAligned": True,
                "comparisonPeersEqualWidth": True,
                "sequenceItemsSharedLeftEdge": True,
                "asymmetryOnlyForExplicitPrimarySupporting": True,
                "forbid": ["randomIndent", "randomWidth", "staggerForVariety"],
            },
        )
        self.assertEqual(
            brief["comparisonLayoutPolicy"],
            {
                "sideBySideAllowed": True,
                "sideBySideMaxCharsPerPeer": 80,
                "sideBySideMaxCombinedChars": 150,
                "withinLimitLayout": "aligned_equal_width_columns",
                "overLimitLayout": "vertical_full_width_stack",
                "verticalStackSharedLeftEdge": True,
            },
        )
        self.assertEqual(
            brief["highlightPolicy"],
            {
                "maximumSegmentsPerPage": 3,
                "sameSemanticCategoryUsesSameStyle": True,
                "shortHighlightNoWrapMaxChars": 12,
                "shortHighlightMoveWholeToNextLine": True,
                "forbidOrphanTailCharsMax": 2,
                "forbid": ["multicolorSameCategory", "oneOrTwoCharacterHighlightedTail"],
            },
        )
        relation_highlights = sum(
            len(row.get("highlightTargets", []))
            for row in brief["sourceProjectionPlan"]
        )
        self.assertLessEqual(relation_highlights + len(brief["emphasisTargets"]), 3)
        self.assertEqual(
            [row["blockIndex"] for row in brief["sourceProjectionPlan"]],
            [1, 2, 3, 4],
        )
        self.assertLessEqual(len(brief["emphasisTargets"]), 3)
        reading = blocks[1:]
        for target in brief["emphasisTargets"]:
            self.assertIn(
                target["exactText"], reading[target["blockIndex"] - 1]["text"]
            )
        process = next(
            row for row in brief["sourceProjectionPlan"] if row["blockIndex"] == 2
        )
        self.assertEqual(process["mode"], "sentence_sequence")
        self.assertEqual(process["renderMode"], "single_section_flat_steps")
        self.assertEqual(len(process["fragments"]), 3)
        self.assertEqual(
            "".join(fragment["text"] for fragment in process["fragments"]),
            reading[1]["text"],
        )
        roles = next(
            row for row in brief["sourceProjectionPlan"] if row["blockIndex"] == 3
        )
        self.assertEqual(roles["mode"], "role_distribution_inline")
        self.assertEqual(roles["renderMode"], "continuous_inline_highlights")
        self.assertTrue(roles["preserveSourceAsSingleTextFlow"])
        self.assertEqual(
            [target["exactText"] for target in roles["highlightTargets"]],
            ["文字负责精确信息", "图片帮助看懂活动场景", "声音提醒内容开始"],
        )
        example_presentation = next(
            row for row in brief["groupPresentation"] if row["groupId"] == "example"
        )
        self.assertEqual(example_presentation["geometry"], "inline_role_distribution")
        self.assertEqual(example_presentation["surfaceRole"], "open_with_inline_highlights")

    def test_s5_splits_conflicting_evidence_without_duplicate_source(self) -> None:
        generator = self.load_module("courseware_s5_conflict_generator", S5_GENERATOR_MODULE)
        evidence = "文字卡写着“周六20:00开始”，图片仍是屋顶花园和望远镜，语音却说“周六21:00见”。"
        blocks = [
            {"type": "heading", "text": "各部分的信息还要保持一致"},
            {"type": "paragraph", "text": "小组根据方案A制作了初版，随后发现一个新问题。"},
            {"type": "paragraph", "text": evidence},
            {"type": "paragraph", "text": "同一件事在不同媒介里出现了两个时间。"},
            {"type": "paragraph", "text": "发现冲突时，先改最妨碍目标的一处，再重新检查其他部分。"},
        ]
        brief = generator.normalize_dynamic_design_brief(blocks)

        comparison = next(
            row for row in brief["semanticGroups"] if row["role"] == "comparison"
        )
        self.assertEqual(comparison["blockIndexes"], [2])
        self.assertEqual(brief["layoutArchetype"], "inline_evidence_then_resolution")
        comparison_presentation = next(
            row for row in brief["groupPresentation"] if row["groupId"] == comparison["id"]
        )
        self.assertEqual(
            comparison_presentation["geometry"], "inline_evidence_comparison"
        )
        projection = next(
            row for row in brief["sourceProjectionPlan"] if row["blockIndex"] == 2
        )
        self.assertEqual(projection["mode"], "inline_conflict_evidence")
        self.assertEqual(projection["renderMode"], "continuous_inline_flow")
        self.assertEqual(
            "".join(fragment["text"] for fragment in projection["fragments"]),
            evidence,
        )
        self.assertEqual(
            projection["fragments"],
            [
                {
                    "text": "文字卡写着“周六20:00开始”",
                    "region": "inline_evidence_a",
                },
                {
                    "text": "，图片仍是屋顶花园和望远镜，",
                    "region": "inline_shared_context",
                },
                {
                    "text": "语音却说“周六21:00见”。",
                    "region": "inline_evidence_b",
                },
            ],
        )
        self.assertEqual(
            [target["exactText"] for target in brief["emphasisTargets"][:2]],
            ["周六20:00开始", "周六21:00见"],
        )

    def test_s5_validator_blocks_linguistically_broken_exact_fragments(self) -> None:
        generator = self.load_module("courseware_s5_linguistic_generator", S5_GENERATOR_MODULE)
        validator = self.load_module("courseware_s5_linguistic_validator", VALIDATOR)
        evidence = "文字卡写着“周六20:00开始”，图片仍是屋顶花园和望远镜，语音却说“周六21:00见”。"
        blocks = [
            {"type": "heading", "text": "各部分的信息还要保持一致"},
            {"type": "paragraph", "text": "小组发现一个新问题。"},
            {"type": "paragraph", "text": evidence},
            {"type": "paragraph", "text": "同一件事出现两个时间。"},
            {"type": "paragraph", "text": "发现冲突时，先改最妨碍目标的一处，再检查其他部分。"},
        ]
        brief = generator.normalize_dynamic_design_brief(blocks)
        projection = next(
            row for row in brief["sourceProjectionPlan"] if row["blockIndex"] == 2
        )
        projection["fragments"] = [
            {"text": "文字卡写着", "region": "inline_shared_context"},
            {"text": "“周六20:00开始”", "region": "inline_evidence_a"},
            {"text": "，图片仍是屋顶花园和望远镜，语音却说", "region": "inline_shared_context"},
            {"text": "“周六21:00见”", "region": "inline_evidence_b"},
            {"text": "。", "region": "inline_shared_context"},
        ]
        page = {
            "page_no": "P05",
            "page_type": "案例分析",
            "effective_content": {"blocks": blocks},
            "design_brief": brief,
        }
        issues: list[dict[str, str]] = []

        validator.validate_dynamic_design_brief(page, issues, required=True)

        self.assertIn(
            "V35_DYNAMIC_PROJECTION_LINGUISTIC_UNIT_INVALID",
            {item["issue_type"] for item in issues},
        )

    def test_s5_validator_blocks_incomplete_executable_design(self) -> None:
        generator = self.load_module("courseware_s5_valid_design_generator", S5_GENERATOR_MODULE)
        validator = self.load_module("courseware_s5_design_validator", VALIDATOR)
        blocks = [
            {"type": "heading", "text": "标题"},
            {"type": "paragraph", "text": "先确认目标，再选择媒介，最后完成检查。"},
            {"type": "paragraph", "text": "文字负责信息，图片负责场景，声音负责提醒。"},
            {"type": "paragraph", "text": "最终是否采用，仍要由人判断。"},
        ]
        brief = generator.normalize_dynamic_design_brief(blocks)
        page = {
            "page_no": "P03",
            "page_type": "知识讲解",
            "effective_content": {"blocks": blocks},
            "design_brief": brief,
        }
        valid_issues: list[dict[str, str]] = []
        validator.validate_dynamic_design_brief(page, valid_issues, required=True)
        self.assertNotIn(
            "V35_DYNAMIC_EXECUTABLE_DESIGN_MISSING",
            {item["issue_type"] for item in valid_issues},
        )

        del brief["surfacePolicy"]
        invalid_issues: list[dict[str, str]] = []
        validator.validate_dynamic_design_brief(page, invalid_issues, required=True)
        self.assertIn(
            "V35_DYNAMIC_EXECUTABLE_DESIGN_MISSING",
            {item["issue_type"] for item in invalid_issues},
        )

    def test_s5_validator_blocks_punctuated_role_clauses_as_block_fragments(self) -> None:
        generator = self.load_module("courseware_role_inline_generator", S5_GENERATOR_MODULE)
        validator = self.load_module("courseware_role_inline_validator", VALIDATOR)
        blocks = [
            {"type": "heading", "text": "组合之前先写清目标、受众和分工"},
            {"type": "paragraph", "text": "制作多媒介内容时，可以先完成一个简单计划。"},
            {"type": "paragraph", "text": "文字负责精确信息，图片帮助看懂活动场景，声音提醒内容开始。"},
            {"type": "paragraph", "text": "最终是否采用，仍要由人判断。"},
        ]
        brief = generator.normalize_dynamic_design_brief(blocks)
        role_projection = next(
            row for row in brief["sourceProjectionPlan"] if row["blockIndex"] == 2
        )
        role_projection.clear()
        role_projection.update(
            {
                "blockIndex": 2,
                "mode": "role_distribution_flow",
                "renderMode": "single_section_with_flat_subitems",
                "fragments": [
                    {"text": "文字负责精确信息，", "region": "role_item_1"},
                    {"text": "图片帮助看懂活动场景，", "region": "role_item_2"},
                    {"text": "声音提醒内容开始。", "region": "role_item_3"},
                ],
                "concatenatedTextMustEqualSource": True,
            }
        )
        page = {
            "page_no": "P07",
            "page_type": "知识讲解",
            "effective_content": {"blocks": blocks},
            "design_brief": brief,
        }
        issues: list[dict[str, str]] = []

        validator.validate_dynamic_design_brief(page, issues, required=True)

        self.assertIn(
            "V35_DYNAMIC_PUNCTUATED_CLAUSE_BLOCK_SPLIT",
            {item["issue_type"] for item in issues},
        )

    def test_s6_emits_executable_relationship_layout_recipes(self) -> None:
        assembler = self.load_module("courseware_relation_assembler", ASSEMBLER)
        generator = self.load_module("courseware_relation_s5_generator", S5_GENERATOR_MODULE)
        blocks = [
            {"type": "heading", "text": "组合之前先写清目标、受众和分工"},
            {"type": "paragraph", "text": "制作多媒介内容时，可以先完成一个简单计划。"},
            {"type": "paragraph", "text": "先写受众是谁、希望他们知道或做到什么。再选择至少两种真正有用的媒介，说明每一种媒介负责哪部分信息。完成初版后，检查事实、来源、个人信息和各部分是否一致。"},
            {"type": "paragraph", "text": "在这个观星提醒里，受众是第一次参加的家庭，目标是迅速获得完整、准确的准备信息。文字负责精确信息，图片帮助看懂活动场景，声音提醒内容开始。"},
            {"type": "paragraph", "text": "工具可以帮助整理或生成其中一部分，但哪些信息可靠、哪些素材能用、最终是否采用，仍要由人判断。"},
        ]
        brief = generator.normalize_dynamic_design_brief(blocks)

        plan = assembler.dynamic_visual_recipe_plan(blocks, brief, "knowledge_explanation")

        self.assertNotIn("visibleRecipeDifferenceContract", plan)
        self.assertNotIn("compositionDiversityContract", plan)
        self.assertEqual(
            plan["semanticCompositionContract"],
            {
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
        )
        self.assertEqual(plan["alignmentContract"], brief["alignmentPolicy"])
        self.assertEqual(plan["comparisonLayoutContract"], brief["comparisonLayoutPolicy"])
        self.assertEqual(plan["highlightContract"], brief["highlightPolicy"])
        self.assertEqual(
            plan["webViewCompatibilityContract"]["baseline"],
            "Android System WebView Chrome 68",
        )
        names = [row["recipe"] for row in plan["recipes"]]

        self.assertIn("process_steps", names)
        self.assertIn("role_distribution_inline", names)
        self.assertTrue(plan["mediumReadingAreaBalance"]["required"])
        self.assertEqual(
            plan["sourceTextProjectionContract"],
            {
                "required": True,
                "visibleOccurrencesPerBlock": 1,
                "allowContiguousDomFragments": True,
                "concatenatedTextMustEqualSource": True,
                "forbidFullBlockPlusDerivedFragments": True,
                "forbidParaphrasedLabels": True,
            },
        )
        self.assertEqual(
            plan["visualHierarchyContract"],
            {
                "required": True,
                "semanticHierarchyFirst": True,
                "priorityOrder": [
                    "source_fidelity",
                    "semantic_relationship",
                    "reading_clarity",
                    "typographic_elegance",
                    "decoration",
                ],
                "minimumReadingAreaCoveragePercent": 60,
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
        )
        execution = plan["designExecutionContract"]
        self.assertTrue(execution["required"])
        self.assertEqual(execution["source"], "S5.design_brief")
        self.assertFalse(execution["surfacePolicy"]["allowLargeDarkSurface"])
        self.assertEqual(
            execution["surfacePolicy"]["nonCodeDarkSurfaceAreaPercentMax"], 0
        )

    def test_knowledge_oneshot_requires_relationship_layout_classes(self) -> None:
        assembler = self.load_module("courseware_knowledge_assembler", ASSEMBLER)
        prompt = assembler.text_block("07_知识讲解页_动态生成OneShot.md")

        for marker in (
            "content-module--comparison",
            "content-module--process-steps",
            "content-module--role-inline",
            "整块原文 + 派生子项",
            "拼接后的 textContent 必须逐字等于该来源块原文",
            "uniformRoundedCardStack",
            "排版优雅优先",
            "装饰不是必选项",
            "不得为了丰富度增加表面",
            "禁止自动生成 Emoji",
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
        ):
            self.assertIn(marker, prompt)

    def test_generated_html_gate_blocks_duplicate_copy_orphan_punctuation_and_surface_overflow(self) -> None:
        self.assertTrue(DYNAMIC_HTML_VALIDATOR.is_file())
        payload = {
            "lesson_id": "lesson015",
            "pages": [
                {
                    "page_no": "P03",
                    "page_type": "知识讲解",
                    "effective_content": {
                        "blocks": [
                            {"type": "heading", "text": "标题"},
                            {"type": "paragraph", "text": "第一段。"},
                            {"type": "paragraph", "text": "第二段。"},
                        ]
                    },
                }
            ],
        }
        valid_html = """<!doctype html><html><body><article class="knowledge-content"><h1 data-visual-region="top">标题</h1><section data-visual-region="top"><p>第一段。</p></section><section data-visual-region="top"><p>第二段。</p></section></article></body></html>"""
        invalid_html = """<!doctype html><html><body><article class="knowledge-content"><h1 data-visual-region="top">标题</h1><section data-visual-region="top"><p>第一段。</p></section><section data-visual-region="top"><p>第一段。</p></section><section data-visual-region="top"><p>，第二段。</p></section><section data-visual-region="top"></section></article></body></html>"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            effective = temp / "effective.json"
            effective.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            valid = temp / "valid.html"
            valid.write_text(valid_html, encoding="utf-8")
            invalid = temp / "invalid.html"
            invalid.write_text(invalid_html, encoding="utf-8")

            valid_result = run(
                DYNAMIC_HTML_VALIDATOR,
                "--effective-content",
                effective,
                "--page-no",
                "P03",
                "--html",
                valid,
            )
            invalid_result = run(
                DYNAMIC_HTML_VALIDATOR,
                "--effective-content",
                effective,
                "--page-no",
                "P03",
                "--html",
                invalid,
            )

        self.assertEqual(valid_result.returncode, 0, valid_result.stdout + valid_result.stderr)
        self.assertEqual(invalid_result.returncode, 1, invalid_result.stdout + invalid_result.stderr)
        issue_codes = {item["code"] for item in json.loads(invalid_result.stdout)["issues"]}
        self.assertIn("DYNAMIC_HTML_SOURCE_PROJECTION_MISMATCH", issue_codes)
        self.assertIn("DYNAMIC_HTML_ORPHAN_PUNCTUATION", issue_codes)
        self.assertIn("DYNAMIC_HTML_TOP_LEVEL_REGION_OVERFLOW", issue_codes)

    def test_generated_html_gate_blocks_punctuated_role_clauses_in_separate_blocks(self) -> None:
        payload = {
            "lesson_id": "lesson015",
            "pages": [
                {
                    "page_no": "P07",
                    "page_type": "知识讲解",
                    "effective_content": {
                        "blocks": [
                            {"type": "heading", "text": "标题"},
                            {"type": "paragraph", "text": "文字负责精确信息，图片帮助看懂活动场景，声音提醒内容开始。"},
                        ]
                    },
                }
            ],
        }
        valid_html = """<!doctype html><html><body><article class="knowledge-content"><h1>标题</h1><p><span>文字负责精确信息</span>，<span>图片帮助看懂活动场景</span>，<span>声音提醒内容开始</span>。</p></article></body></html>"""
        invalid_html = """<!doctype html><html><body><article class="knowledge-content"><h1>标题</h1><div><p>文字负责精确信息，</p><p>图片帮助看懂活动场景，</p><p>声音提醒内容开始。</p></div></article></body></html>"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            effective = temp / "effective.json"
            effective.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            valid = temp / "valid.html"
            valid.write_text(valid_html, encoding="utf-8")
            invalid = temp / "invalid.html"
            invalid.write_text(invalid_html, encoding="utf-8")
            valid_result = run(DYNAMIC_HTML_VALIDATOR, "--effective-content", effective, "--page-no", "P07", "--html", valid)
            invalid_result = run(DYNAMIC_HTML_VALIDATOR, "--effective-content", effective, "--page-no", "P07", "--html", invalid)

        self.assertEqual(valid_result.returncode, 0, valid_result.stdout + valid_result.stderr)
        self.assertEqual(invalid_result.returncode, 1, invalid_result.stdout + invalid_result.stderr)
        issue_codes = {item["code"] for item in json.loads(invalid_result.stdout)["issues"]}
        self.assertIn("DYNAMIC_HTML_PUNCTUATED_CLAUSE_BLOCK_SPLIT", issue_codes)

    def test_dynamic_oneshots_use_chrome68_compatible_shell(self) -> None:
        assembler = self.load_module("courseware_chrome68_assembler", ASSEMBLER)
        banned = (
            "100dvh",
            "clamp(",
            "width: min(",
            "env(safe-area",
            "text-wrap:",
            "?.",
            "??",
            "replaceChildren(",
        )
        for filename in (
            "07_知识讲解页_动态生成OneShot.md",
            "08_案例分析页_动态生成OneShot.md",
        ):
            prompt = assembler.text_block(filename)
            for marker in banned:
                self.assertNotIn(marker, prompt, f"{filename}: {marker}")
            self.assertIn("Android System WebView Chrome 68", prompt)
            self.assertIn("短高亮词组整体换行", prompt)
            self.assertIn("全页最多 3 个高亮片段", prompt)
            self.assertIn("任一对比项超过 80 个字符", prompt)

    def test_registered_oneshots_and_demos_are_chrome68_compatible(self) -> None:
        validator = self.load_module(
            "courseware_chrome68_asset_gate", DYNAMIC_HTML_VALIDATOR
        )
        assets = list((SKILL_ROOT / "templates" / "oneshots").glob("*.md"))
        assets.extend((SKILL_ROOT / "templates" / "demos").glob("*.html"))
        incompatible = {
            str(path.relative_to(SKILL_ROOT)): validator.chrome68_incompatibilities(
                path.read_text(encoding="utf-8")
            )
            for path in assets
        }
        self.assertEqual(
            {path: issues for path, issues in incompatible.items() if issues},
            {},
        )
        outer = (
            SKILL_ROOT / "templates" / "oneshots" / "02_整课JSON_完整外层OneShot.md"
        ).read_text(encoding="utf-8")
        for obsolete in ("锁定 `100dvh`", "width:min(100%,680px)"):
            self.assertNotIn(obsolete, outer)
        self.assertIn("Android System WebView Chrome 68", outer)

    def test_registered_asset_hashes_match_current_files(self) -> None:
        assembler = self.load_module("courseware_asset_hashes", ASSEMBLER)
        demo_by_kind = {
            "course_intro": "course_intro_demo.html",
            "scene_intro": "scene_intro_demo.html",
            "course_summary": "course_summary_demo.html",
        }
        for values in assembler.FIXED.values():
            kind, filename, variable, _, oneshot_hash, demo_hash, nonvar_hash = values
            oneshot = SKILL_ROOT / "templates" / "oneshots" / filename
            demo = SKILL_ROOT / "templates" / "demos" / demo_by_kind[kind]
            normalized = re.sub(
                rf"const\s+{variable}\s*=\s*Object\.freeze\(\{{.*?\}}\);",
                f"const {variable} = Object.freeze({{}});",
                demo.read_text(encoding="utf-8"),
                count=1,
                flags=re.S,
            )
            self.assertEqual(oneshot_hash, sha256(oneshot), filename)
            self.assertEqual(demo_hash, sha256(demo), demo.name)
            self.assertEqual(
                nonvar_hash,
                hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
                f"{demo.name}: non-variable region",
            )
        for _, filename, _, expected_hash in assembler.DYNAMIC.values():
            self.assertEqual(
                expected_hash,
                sha256(SKILL_ROOT / "templates" / "oneshots" / filename),
                filename,
            )

    def test_prompt_instance_version_contains_contract_asset_and_prompt_fingerprints(self) -> None:
        assembler = self.load_module("courseware_prompt_version", ASSEMBLER)
        version = assembler.prompt_version(
            "RunS-Knowledge-Dynamic-OneShot-v1.19",
            "71ec5e5f3aefeb37c03102eb86a04f13e7177a21fb69b27006966fe0c4576fc1",
            "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
            "lesson015",
            "P03",
        )
        self.assertEqual(
            version,
            "RunS-Knowledge-Dynamic-OneShot-v1.19-asset-71ec5e5f3aef-prompt-abcdef012345-lesson015-P03-R36-20260731",
        )

    def test_same_oneshot_produces_new_version_when_prompt_content_changes(self) -> None:
        assembler = self.load_module("courseware_prompt_instance_hash", ASSEMBLER)
        base = "提示词版本号：__PROMPT_VERSION__\n适用页面：lesson015｜P03\n正文：{text}"
        prompt_a, version_a, digest_a = assembler.finalize_prompt_version(
            base.format(text="第一版"),
            "RunS-Knowledge-Dynamic-OneShot-v1.19",
            "71ec5e5f3aefeb37c03102eb86a04f13e7177a21fb69b27006966fe0c4576fc1",
            "lesson015",
            "P03",
        )
        prompt_b, version_b, digest_b = assembler.finalize_prompt_version(
            base.format(text="第二版"),
            "RunS-Knowledge-Dynamic-OneShot-v1.19",
            "71ec5e5f3aefeb37c03102eb86a04f13e7177a21fb69b27006966fe0c4576fc1",
            "lesson015",
            "P03",
        )
        self.assertNotEqual(version_a, version_b)
        self.assertNotEqual(digest_a, digest_b)
        self.assertIn(version_a, prompt_a.splitlines()[0])
        self.assertIn(version_b, prompt_b.splitlines()[0])

    def test_static_checker_requires_asset_bound_prompt_version(self) -> None:
        checker = self.load_module("courseware_prompt_version_gate", STATIC_CHECKER)
        expected = checker.expected_prompt_version(
            "RunS-Knowledge-Dynamic-OneShot-v1.19",
            "71ec5e5f3aefeb37c03102eb86a04f13e7177a21fb69b27006966fe0c4576fc1",
            "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
            "lesson015",
            "P03",
        )
        self.assertEqual(
            expected,
            "RunS-Knowledge-Dynamic-OneShot-v1.19-asset-71ec5e5f3aef-prompt-abcdef012345-lesson015-P03-R36-20260731",
        )
        self.assertNotEqual(
            expected,
            "RunS-Knowledgeexplanation-lesson015-P03-OneShot-R36-20260731",
        )

    def test_generated_html_gate_blocks_chrome68_incompatible_features(self) -> None:
        payload = {
            "page_no": "P03",
            "effective_content": {
                "blocks": [
                    {"type": "heading", "text": "标题"},
                    {"type": "paragraph", "text": "正文"},
                ]
            },
        }
        html = """<!doctype html><html><head><style>.x{width:clamp(10px,20vw,30px);height:100dvh}</style></head><body><article class=\"knowledge-content\"><h1>标题</h1><p>正文</p></article><script>var x = window.foo?.bar;</script></body></html>"""
        issues = self.load_module(
            "courseware_chrome68_dom_gate", DYNAMIC_HTML_VALIDATOR
        ).validate_html(html, payload)
        self.assertIn(
            "DYNAMIC_HTML_CHROME68_INCOMPATIBLE",
            {issue["code"] for issue in issues},
        )

    def test_static_checker_detects_chrome68_incompatible_prompt_code(self) -> None:
        checker = self.load_module("courseware_chrome68_static_gate", STATIC_CHECKER)
        incompatible = """<style>.x{display:flex;gap:8px;width:clamp(10px,20vw,30px)}</style><script>var x=window.foo?.bar;</script>"""
        compatible = """<style>.x{display:flex;width:100%;max-width:30px;margin-right:8px}</style><script>var x=window.foo && window.foo.bar;</script>"""
        self.assertIn("flex gap", checker.chrome68_prompt_incompatibilities(incompatible))
        self.assertIn("clamp()", checker.chrome68_prompt_incompatibilities(incompatible))
        self.assertIn("optional chaining", checker.chrome68_prompt_incompatibilities(incompatible))
        self.assertEqual(checker.chrome68_prompt_incompatibilities(compatible), [])

    def test_s6_adds_evidence_quote_visual_recipe(self) -> None:
        assembler = self.load_module("courseware_evidence_assembler", ASSEMBLER)
        blocks = [
            {"type": "heading", "text": "AI能给结果，人负责判断"},
            {"type": "paragraph", "text": "完整不等于正确。"},
            {"type": "paragraph", "text": "比如，聊天应用回答："},
            {"type": "blockquote", "text": "法国的首都是北京。"},
            {"type": "paragraph", "text": "这句话读起来很顺，事实却是错的。"},
        ]
        brief = {
            "density": "medium",
            "semanticGroups": [
                {"id": "claim", "blockIndexes": [1]},
                {"id": "evidence", "blockIndexes": [2, 3]},
                {"id": "judgment", "blockIndexes": [4]},
            ],
        }

        plan = assembler.dynamic_visual_recipe_plan(
            blocks, brief, "knowledge_explanation"
        )
        evidence = next(
            row for row in plan["recipes"]
            if row["recipe"] == "evidence_quote_focus"
        )

        self.assertEqual(evidence["geometry"], "warm_evidence_quote_surface")
        self.assertEqual(evidence["visualTreatment"], "warm_alert_contrast")

    def test_static_checker_blocks_missing_source_text_once_contract(self) -> None:
        checker = self.load_module("courseware_projection_checker", STATIC_CHECKER)
        recipes = {
            "nonRenderable": True,
            "recipeContract": "R36_REUSABLE_DYNAMIC_VISUAL_RECIPES",
            "recipes": [
                {"recipe": "intro_observation_band"},
                {"recipe": "analysis_conclusion_emphasis"},
            ],
            "mediumReadingAreaBalance": {
                "required": False,
                "target": "60_to_75_percent_of_available_reading_area",
                "method": "distributed_real_groups_card_density_and_spacing",
                "forbidFillers": True,
            },
            "orderedListOrdinalContract": {"required": False},
            "unorderedListPresentationContract": {"required": False},
            "visibleRecipeDifferenceContract": {
                "required": True,
                "minimumDistinctTreatments": 2,
                "forbid": ["sameWhiteCardStack", "positionOnlyDifferentiation"],
            },
        }
        page_data = {
            "contentBlocks": [
                {"type": "heading", "text": "标题"},
                {"type": "paragraph", "text": "原文一"},
                {"type": "paragraph", "text": "原文二"},
            ],
            "visualRecipePlan": recipes,
            "footerContract": {
                "required": True,
                "footerClass": "knowledge-footer",
                "buttonClass": "knowledge-primary-button",
                "buttonText": "继续学习",
            },
        }
        prompt = "\n".join(
            [
                "<PAGE_DATA>",
                json.dumps(page_data, ensure_ascii=False),
                "</PAGE_DATA>",
                "禁止装饰性左侧彩色竖线、轨道、连接点或箭头 border-left",
                "content-module--intro-band content-module--list-compact content-module--sequence-compact content-module--emphasis",
                "content-module--comparison content-module--process-steps content-module--role-inline",
                "sameWhiteCardStack positionOnlyDifferentiation 至少两种选中的配方",
                '<footer class="knowledge-footer">',
                '<button class="knowledge-primary-button">继续学习</button>',
                "不得条件省略 display:none visibility:hidden opacity:0",
            ]
        )
        page = {
            "page_kind": "knowledge_explanation",
            "sdk_action": "nextpage",
            "prompt": prompt,
            "page_data": {
                "oneshot_contract_version": "RunS-Knowledge-Dynamic-OneShot-v1.19",
                "visualRecipePlan": recipes,
                "design_brief": {"density": "light"},
                "footerContract": page_data["footerContract"],
            },
        }
        issues: list[dict[str, str]] = []

        checker.check_r34_visual_prompt_contract(
            page, 7, Path("whole_course.json"), issues
        )

        self.assertIn(
            "V35_DYNAMIC_SOURCE_TEXT_ONCE_CONTRACT_MISSING",
            {item["code"] for item in issues},
        )
        self.assertIn(
            "V35_DYNAMIC_VISUAL_HIERARCHY_CONTRACT_MISSING",
            {item["code"] for item in issues},
        )
        self.assertIn(
            "V35_DYNAMIC_S5_DESIGN_EXECUTION_CONTRACT_MISSING",
            {item["code"] for item in issues},
        )

    def test_gate_runner_extracts_top_level_checker_issue_code(self) -> None:
        runner = self.load_module("courseware_gate_runner", GATE_RUNNER)
        issues = runner.extract_command_issues(
            {
                "stdout": json.dumps(
                    {
                        "status": "BLOCKED",
                        "issues": [
                            {
                                "code": "V35_DYNAMIC_VISIBLE_CTA_CONTRACT_MISSING",
                                "message": "案例页 CTA 合同不一致",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                "stderr": "",
            }
        )

        self.assertEqual(
            issues,
            [
                {
                    "issue_type": "V35_DYNAMIC_VISIBLE_CTA_CONTRACT_MISSING",
                    "message": "案例页 CTA 合同不一致",
                }
            ],
        )

    def test_skill_declares_independent_version_gate(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        for marker in (
            "validate_skill_version.py",
            "0.2.20-r36",
            "runs-ai-monorepo",
            "runs-skills",
            "禁止直接",
            "公开分发镜像",
            "版本不得倒退或复用",
        ):
            self.assertIn(marker, skill)


if __name__ == "__main__":
    unittest.main()
