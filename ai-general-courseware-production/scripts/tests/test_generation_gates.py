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
VISUAL_GATE_RUNNER = SKILL_ROOT / "scripts" / "orchestrator" / "run_visual_manifest_gate.py"
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
            page["content"]["taskTitle"],
            page["sections"],
            "complete",
            {
                "visualAsset": {
                    "assetId": "L001-P10-C01",
                    "url": "https://res.xrunda.com/test/p10.webp",
                    "alt": "",
                    "placement": {
                        "authority": "model_visual_review",
                        "anchorType": "reviewed_semantic_anchor",
                        "rule": "extension_contextual_image",
                        "insertAfter": "story_sequence_or_task_goal",
                        "fallback": "after_first_text_block",
                        "terminalPlacementForbidden": True,
                    },
                },
                "visualPresentation": {
                    "groupLayout": "vertical_stack",
                    "terminalPlacementForbidden": True,
                },
            },
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

    def test_p10_story_sequence_and_composite_paragraph_keep_distinct_semantics(self) -> None:
        generator = self.load_module("courseware_p10_story_projection", S5_GENERATOR_MODULE)
        assembler = self.load_module("courseware_p10_story_assembler", ASSEMBLER)
        checker = self.load_module("courseware_p10_story_checker", STATIC_CHECKER)
        raw = (
            FIXTURES
            / "representative-projections"
            / "p10_story_sequence_source.md"
        ).read_text(encoding="utf-8").strip()
        page = generator.protected_page(
            {
                "page_no": "P10",
                "page_type": "课后任务",
                "capsule": "课后任务",
                "action": "complete",
                "source_block": "fixture-p10-story-sequence",
                "body": raw,
            }
        )

        roles = {section.get("role") for section in page["sections"]}
        for expected_role in ("storySequenceHeading", "storySequence", "composite"):
            self.assertIn(expected_role, roles)
        story_heading = next(
            section for section in page["sections"]
            if section.get("role") == "storySequenceHeading"
        )
        story_sequence = next(
            section for section in page["sections"]
            if section.get("role") == "storySequence"
        )
        composite = next(
            section for section in page["sections"]
            if section.get("role") == "composite"
        )
        self.assertEqual(story_heading["type"], "section_heading")
        self.assertEqual(story_sequence["type"], "facts")
        self.assertNotEqual(story_sequence.get("label"), "任务要点")
        self.assertEqual(composite["type"], "composite")
        self.assertEqual(
            [segment["role"] for segment in composite["segments"]],
            ["action", "completionCheck", "supportNote"],
        )
        self.assertEqual(
            "".join(segment["text"] for segment in composite["segments"]),
            composite["text"],
        )

        self.assertEqual(assembler.task_sections(page), page["sections"])

        document = assembler.task_html(
            page["content"]["taskTitle"],
            page["sections"],
            "complete",
            {
                "visualAsset": {
                    "assetId": "L001-P10-C01",
                    "url": "https://res.xrunda.com/test/p10.webp",
                    "alt": "",
                    "placement": {
                        "authority": "model_visual_review",
                        "anchorType": "reviewed_semantic_anchor",
                        "rule": "extension_contextual_image",
                        "insertAfter": "story_sequence_or_task_goal",
                        "fallback": "after_first_text_block",
                        "terminalPlacementForbidden": True,
                    },
                },
                "visualPresentation": {
                    "groupLayout": "vertical_stack",
                    "terminalPlacementForbidden": True,
                },
            },
        )
        self.assertIn('story-sequence-card"', document)
        story_html = document.split('story-sequence-card"', 1)[1].split(
            "</section>", 1
        )[0]
        self.assertNotIn("任务要点", story_html)
        self.assertIn('class="completion-check"', document)
        self.assertIn('class="support-note"', document)
        action_text = assembler.esc(composite["segments"][0]["text"])
        check_text = assembler.esc(composite["segments"][1]["text"])
        support_text = assembler.esc(composite["segments"][2]["text"])
        action_group = document.split(action_text, 1)[0].rsplit('class="step-group', 1)[-1]
        self.assertNotIn(check_text, action_group)
        self.assertLess(document.index(action_text), document.index(check_text))
        self.assertLess(document.index(check_text), document.index(support_text))
        self.assertEqual(
            [int(value) for value in re.findall(r'data-source-section-index="(\d+)"', document)],
            list(range(len(page["sections"]))),
        )
        self.assertTrue(checker.task_sections_match_static_dom(page["sections"], document))
        self.assertTrue(checker.task_semantic_structure_matches_static_dom(page["sections"], document))
        self.assertLess(document.index('story-sequence-card"'), document.index('class="visual-gallery"'))
        self.assertLess(document.index('class="visual-gallery"'), document.index('class="action-section"'))
        self.assertRegex(
            document,
            r'<button type="button" class="visual-lightbox-close" aria-label="关闭大图"><span aria-hidden="true">×</span></button>',
        )
        self.assertIn("function positionVisualClose()", document)
        self.assertIn("getBoundingClientRect", document)
        self.assertIn("border-radius:50%", document.replace(" ", ""))

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
            "--visual-mode",
            "text_only",
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
            "visualMode": "text_only",
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
                        "visualMode": "text_only",
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
                "--visual-mode",
                "text_only",
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
        for values in (assembler.VISUAL_FIXED["课程开篇"],):
            kind, filename, variable, _, oneshot_hash, demo_hash, nonvar_hash = values
            oneshot = SKILL_ROOT / "templates" / "oneshots" / filename
            demo = SKILL_ROOT / "templates" / "demos" / "visual_enhanced" / "course_intro_demo.html"
            demo_text = demo.read_text(encoding="utf-8")
            visual_start = demo_text.index("    const VISUAL_DATA = Object.freeze(")
            visual_end = demo_text.index("    function renderVisualAssets()", visual_start)
            normalized = demo_text[:visual_start] + "    const VISUAL_DATA = Object.freeze({});\n\n" + demo_text[visual_end:]
            content_start = normalized.index(f"    const {variable} = Object.freeze(")
            marker = "    /* ======================= 变量区结束 ======================= */"
            content_end = normalized.index(marker, content_start)
            normalized = normalized[:content_start] + f"    const {variable} = Object.freeze({{}});\n" + normalized[content_end:]
            self.assertEqual(oneshot_hash, sha256(oneshot), filename)
            self.assertEqual(demo_hash, sha256(demo), demo.name)
            self.assertEqual(
                nonvar_hash,
                hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
                f"{demo.name}: visual non-variable region",
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
        current_version = (SKILL_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        for marker in (
            "validate_skill_version.py",
            current_version,
            "runs-ai-monorepo",
            "runs-skills",
            "禁止直接",
            "公开分发镜像",
            "版本不得倒退或复用",
        ):
            self.assertIn(marker, skill)


class VisualManifestGateTests(unittest.TestCase):
    def write_teacher_inputs(
        self,
        temp: Path,
        *,
        anchor_line: int = 3,
        recorded_sha: str | None = None,
    ) -> tuple[Path, Path]:
        teacher = temp / "final.md"
        teacher.write_text(
            "# 测试课\n导入情境。\n观察这张主图。\n说出图中的线索。\n继续学习。\n",
            encoding="utf-8",
        )
        teacher_sha = recorded_sha or sha256(teacher)
        visual_script = temp / "teacher-visual.md"
        visual_script.write_text(
            "# 阶段一教学必备视觉资产功能与衔接脚本\n\n"
            "## 1. 第1课\n\n"
            "源教案：`lesson001/final.md`  \n"
            f"SHA-256：`{teacher_sha}`\n\n"
            "### `L001-V01` 测试主图\n\n"
            "| 字段 | 内容 |\n|---|---|\n"
            "| 图片用途 | 支持观察主图 |\n"
            f"| 教案位置 | 第{anchor_line}行后单独显示 |\n"
            "| 图片要求 | 展示测试对象 |\n"
            "| 图片地址 | https://res.xrunda.com/test/l001-v01.webp |\n",
            encoding="utf-8",
        )
        return teacher, visual_script

    def write_page_plan(self, temp: Path) -> Path:
        page_plan = temp / "page_plan_full.md"
        page_plan.write_text(
            "## P01\n"
            "- 页面类型：知识讲解\n- 胶囊文案：知识讲解\n- 页面动作：nextPage\n"
            "- 来源块：B01\n- 内容块类型：段落\n- 布局意图：按原文展示。\n"
            "- 过渡句位置：none\n- 过渡句原文：无\n\n### 有效内容\n\n"
            "观察这张主图。\n说出图中的线索。\n\n"
            "## P02\n"
            "- 页面类型：课后任务\n- 胶囊文案：课后任务\n- 页面动作：nextPage\n"
            "- 来源块：B02\n- 内容块类型：段落\n- 布局意图：按原文展示。\n"
            "- 过渡句位置：none\n- 过渡句原文：无\n\n### 有效内容\n\n"
            "完成一个课后作品。\n\n"
            "## P03\n"
            "- 页面类型：互动题目\n- 胶囊文案：试一试\n- 页面动作：complete\n"
            "- 来源块：B03\n- 内容块类型：题目\n- 布局意图：组件展示。\n"
            "- 过渡句位置：none\n- 过渡句原文：无\n- 组件类型：galaxy_select_question\n\n"
            "### 有效内容\n\n```json\n{\"type\":\"galaxy_select_question\",\"componentId\":\"L001-I01\",\"content\":{\"questions\":[{\"question\":\"请选择\",\"options\":[\"A\",\"B\"],\"isMultiple\":false,\"answerIndex\":[0],\"answer\":[\"A\"]}]}}\n```\n",
            encoding="utf-8",
        )
        return page_plan

    def run_initial(
        self,
        temp: Path,
        teacher: Path,
        visual_script: Path,
    ) -> tuple[subprocess.CompletedProcess[str], Path]:
        output = temp / "lesson001__S1__visual_asset_manifest.initial.json"
        result = run(
            VISUAL_GATE_RUNNER,
            "--phase",
            "initial",
            "--lesson-id",
            "lesson001",
            "--visual-mode",
            "visual_enhanced",
            "--teacher-final",
            teacher,
            "--teacher-visual-script",
            visual_script,
            "--receipt-dir",
            temp / "receipts",
            "--output",
            output,
        )
        return result, output

    def run_request(
        self,
        temp: Path,
        initial: Path,
        page_plan: Path,
        *,
        receipt_visual_mode: str | None = "visual_enhanced",
    ) -> tuple[subprocess.CompletedProcess[str], Path]:
        s4_receipt = temp / "s4_gate_receipt.json"
        receipt_payload = {
            "contract": "RunS_V3.5.0-S1-S6-R36-20260731",
            "lesson_id": "lesson001",
            "stage": "S4",
            "status": "PASS",
            "output": {
                "role": "page_plan",
                "path": str(page_plan.resolve()),
                "sha256": sha256(page_plan),
            },
        }
        if receipt_visual_mode is not None:
            receipt_payload["visualMode"] = receipt_visual_mode
        s4_receipt.write_text(
            json.dumps(
                receipt_payload,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        output = temp / "lesson001__S1__visual_asset_manifest.request.json"
        result = run(
            VISUAL_GATE_RUNNER,
            "--phase",
            "request",
            "--lesson-id",
            "lesson001",
            "--visual-mode",
            "visual_enhanced",
            "--initial-manifest",
            initial,
            "--page-plan",
            page_plan,
            "--s4-receipt",
            s4_receipt,
            "--receipt-dir",
            temp / "receipts",
            "--output",
            output,
        )
        return result, output

    def write_task_placement_review(
        self,
        temp: Path,
        request: Path,
        external: Path,
    ) -> Path:
        request_payload = json.loads(request.read_text(encoding="utf-8"))
        asset_id = next(
            item["assetId"]
            for item in request_payload["placements"]
            if item.get("pageNo") == "P02"
        )
        review = temp / "lesson001__S1__visual_placement_review.json"
        review.write_text(
            json.dumps(
                {
                    "schemaVersion": "1.0",
                    "lessonId": "lesson001",
                    "sourceRequestManifest": {"path": str(request.resolve()), "sha256": sha256(request)},
                    "sourceExternalReturn": {"path": str(external.resolve()), "sha256": sha256(external)},
                    "reviews": [
                        {
                            "pageNo": "P02",
                            "assetId": asset_id,
                            "imageReviewed": True,
                            "semanticRelation": "图片支持理解课后作品任务。",
                            "embeddedTextOverlapDetected": False,
                            "fallbackUsed": True,
                            "renderPlacement": {
                                "authority": "model_visual_review",
                                "anchorType": "reviewed_semantic_anchor",
                                "rule": "extension_contextual_image",
                                "insertAfter": "first_text_block",
                                "fallback": "after_first_text_block",
                                "terminalPlacementForbidden": True,
                            },
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        return review

    def test_visual_mode_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            result = run(
                VISUAL_GATE_RUNNER,
                "--phase",
                "initial",
                "--lesson-id",
                "lesson001",
                "--receipt-dir",
                temp / "receipts",
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("VISUAL_MODE_NOT_SELECTED", result.stdout)

    def test_text_only_writes_skip_receipt_without_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            output = temp / "should-not-exist.json"
            result = run(
                VISUAL_GATE_RUNNER,
                "--phase",
                "initial",
                "--lesson-id",
                "lesson001",
                "--visual-mode",
                "text_only",
                "--receipt-dir",
                temp / "receipts",
                "--output",
                output,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(output.exists())
            receipt = json.loads(
                (temp / "receipts" / "visual_manifest_gate_receipt.json").read_text(encoding="utf-8")
            )
            self.assertEqual(receipt["status"], "SKIPPED_BY_VISUAL_MODE")
            self.assertEqual(receipt["visualMode"], "text_only")
            self.assertEqual(receipt["inputs"], [])
            self.assertEqual(receipt["outputs"], [])

    def test_initial_freezes_teacher_assets_and_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            teacher, visual_script = self.write_teacher_inputs(temp)
            result, output = self.run_initial(temp, teacher, visual_script)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["lifecycleState"], "initial")
            self.assertEqual(payload["assets"][0]["imageType"], "lesson_plan_image")
            self.assertEqual(payload["assets"][0]["url"], "https://res.xrunda.com/test/l001-v01.webp")
            self.assertEqual(payload["placements"][0]["sourceAnchor"]["teacherLineAfter"], 3)
            self.assertEqual(payload["placements"][0]["sourceAnchor"]["beforeText"], "观察这张主图。")
            self.assertEqual(payload["placements"][0]["sourceAnchor"]["afterText"], "说出图中的线索。")
            self.assertEqual(payload["placements"][0]["sourceLocationText"], "第3行后单独显示")
            self.assertEqual(payload["placements"][0]["sourceLocationDetail"], "单独显示")
            self.assertEqual(
                payload["placements"][0]["renderPlacement"],
                {
                    "authority": "teacher_visual_script",
                    "anchorType": "teacher_source_anchor",
                    "insertAfterText": "观察这张主图。",
                    "insertBeforeText": "说出图中的线索。",
                    "fallback": "none",
                },
            )

    def test_initial_allows_courseware_only_lesson_when_visual_script_has_no_lesson_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            teacher, _ = self.write_teacher_inputs(temp)
            visual_script = temp / "teacher-visual.md"
            visual_script.write_text(
                "# 阶段一教学必备视觉资产功能与衔接脚本\n\n"
                "## 1. 第9课\n\n"
                "源教案：`lesson009/final.md`  \n"
                f"SHA-256：`{'0' * 64}`\n\n"
                "### `L009-V01` 仅属于第9课的教案图\n\n"
                "| 字段 | 内容 |\n|---|---|\n"
                "| 图片用途 | 第9课示例 |\n"
                "| 教案位置 | 第1行后单独显示 |\n"
                "| 图片地址 | https://res.xrunda.com/test/l009-v01.webp |\n",
                encoding="utf-8",
            )

            initial_result, initial = self.run_initial(temp, teacher, visual_script)

            self.assertEqual(initial_result.returncode, 0, initial_result.stdout + initial_result.stderr)
            initial_payload = json.loads(initial.read_text(encoding="utf-8"))
            self.assertEqual(initial_payload["assets"], [])
            self.assertEqual(initial_payload["placements"], [])
            self.assertFalse(initial_payload["checks"]["teacherVisualScriptLessonPresent"])
            self.assertFalse(initial_payload["checks"]["lessonPlanImagesDeclared"])

            page_plan = self.write_page_plan(temp)
            request_result, request = self.run_request(temp, initial, page_plan)

            self.assertEqual(request_result.returncode, 0, request_result.stdout + request_result.stderr)
            decisions = {
                item["pageNo"]: item["decision"]
                for item in json.loads(request.read_text(encoding="utf-8"))["pageDecisions"]
            }
            self.assertEqual(
                decisions,
                {
                    "P01": "courseware_image",
                    "P02": "courseware_image",
                    "P03": "interaction_no_image",
                },
            )

    def test_initial_stops_before_delivery_check_and_uses_explicit_before_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            teacher = temp / "final.md"
            teacher_lines = [f"第{line_number}行占位文字" for line_number in range(1, 99)]
            teacher_lines[87] = "A只处理背景过密这一处问题，也保留了已经合适的主题和风格方向。"
            teacher_lines[88] = "<!-- 互动规格开始：这不是学生可见文字 -->"
            teacher_lines[97] = "修改后的版本减少了背景小物件。图片缩小后，黄色潜水艇重新变得清楚。"
            teacher.write_text("\n".join(teacher_lines) + "\n", encoding="utf-8")

            visual_script = temp / "teacher-visual.md"
            visual_script.write_text(
                "# 阶段一教学必备视觉资产功能与衔接脚本\n\n"
                "## 7. 第18课\n\n"
                "源教案：`lesson018/final.md`  \n"
                f"SHA-256：`{sha256(teacher)}`\n\n"
                "### `L018-V03` 修改后的潜水艇画面\n\n"
                "| 字段 | 内容 |\n|---|---|\n"
                "| 图片用途 | 支持修改前后对比 |\n"
                "| 教案位置 | 第88行后、下一条学生可见文字第98行前，与L018-V02以相同缩略尺寸并列显示 |\n"
                "| 图片地址 | https://res.xrunda.com/test/l018-v03.webp |\n\n"
                "## 8. 视觉资产交付检查\n\n"
                "| 检查项 | 要求 |\n|---|---|\n"
                "| 教案位置 | 每张图片同时匹配行号和文字锚点 |\n",
                encoding="utf-8",
            )
            output = temp / "lesson018__S1__visual_asset_manifest.initial.json"

            result = run(
                VISUAL_GATE_RUNNER,
                "--phase",
                "initial",
                "--lesson-id",
                "lesson018",
                "--visual-mode",
                "visual_enhanced",
                "--teacher-final",
                teacher,
                "--teacher-visual-script",
                visual_script,
                "--receipt-dir",
                temp / "receipts",
                "--output",
                output,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            placement = payload["placements"][0]
            self.assertEqual(
                placement["sourceLocationText"],
                "第88行后、下一条学生可见文字第98行前，与L018-V02以相同缩略尺寸并列显示",
            )
            self.assertEqual(placement["sourceAnchor"]["teacherLineAfter"], 88)
            self.assertEqual(
                placement["sourceAnchor"]["beforeText"],
                "A只处理背景过密这一处问题，也保留了已经合适的主题和风格方向。",
            )
            self.assertEqual(
                placement["sourceAnchor"]["afterText"],
                "修改后的版本减少了背景小物件。图片缩小后，黄色潜水艇重新变得清楚。",
            )

    def test_initial_blocks_teacher_sha_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            teacher, visual_script = self.write_teacher_inputs(temp, recorded_sha="0" * 64)
            result, output = self.run_initial(temp, teacher, visual_script)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertFalse(output.exists())
            self.assertIn("TEACHER_VISUAL_SCRIPT_TEACHER_SHA_MISMATCH", result.stdout)

    def test_request_binds_pages_and_reuses_canonical_page_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            teacher, visual_script = self.write_teacher_inputs(temp)
            initial_result, initial = self.run_initial(temp, teacher, visual_script)
            self.assertEqual(initial_result.returncode, 0, initial_result.stdout + initial_result.stderr)
            page_plan = self.write_page_plan(temp)
            result, output = self.run_request(temp, initial, page_plan)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            decisions = {item["pageNo"]: item for item in payload["pageDecisions"]}
            self.assertEqual(decisions["P01"]["decision"], "lesson_plan_image")
            self.assertEqual(decisions["P02"]["decision"], "courseware_image")
            self.assertEqual(decisions["P02"]["pageType"], "拓展练习")
            self.assertEqual(decisions["P03"]["decision"], "interaction_no_image")
            p02_placement = next(item for item in payload["placements"] if item["pageNo"] == "P02")
            self.assertEqual(p02_placement["renderPlacement"]["rule"], "extension_contextual_image")
            self.assertEqual(p02_placement["renderPlacement"]["fallback"], "after_first_text_block")

    def test_request_accepts_hash_bound_legacy_s4_receipt_without_visual_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            teacher, visual_script = self.write_teacher_inputs(temp)
            initial_result, initial = self.run_initial(temp, teacher, visual_script)
            self.assertEqual(initial_result.returncode, 0, initial_result.stdout + initial_result.stderr)
            page_plan = self.write_page_plan(temp)

            result, output = self.run_request(
                temp,
                initial,
                page_plan,
                receipt_visual_mode=None,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(output.is_file())

    def test_request_blocks_explicit_s4_visual_mode_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            teacher, visual_script = self.write_teacher_inputs(temp)
            initial_result, initial = self.run_initial(temp, teacher, visual_script)
            self.assertEqual(initial_result.returncode, 0, initial_result.stdout + initial_result.stderr)
            page_plan = self.write_page_plan(temp)

            result, output = self.run_request(
                temp,
                initial,
                page_plan,
                receipt_visual_mode="text_only",
            )

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertFalse(output.exists())
            self.assertIn("VISUAL_MODE_DRIFT", result.stdout)

    def test_request_binds_unique_surviving_anchor_when_transition_side_is_absent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            teacher, visual_script = self.write_teacher_inputs(temp)
            initial_result, initial = self.run_initial(temp, teacher, visual_script)
            self.assertEqual(initial_result.returncode, 0, initial_result.stdout + initial_result.stderr)
            initial_payload = json.loads(initial.read_text(encoding="utf-8"))
            absent_transition = "该过渡引导句未进入S4学生有效内容。"
            initial_payload["placements"][0]["sourceAnchor"]["afterText"] = absent_transition
            initial_payload["placements"][0]["renderPlacement"]["insertBeforeText"] = absent_transition
            initial.write_text(
                json.dumps(initial_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            page_plan = self.write_page_plan(temp)

            result, output = self.run_request(temp, initial, page_plan)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["placements"][0]["pageNo"], "P01")

    def test_request_blocks_when_surviving_anchor_is_not_unique(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            teacher, visual_script = self.write_teacher_inputs(temp)
            initial_result, initial = self.run_initial(temp, teacher, visual_script)
            self.assertEqual(initial_result.returncode, 0, initial_result.stdout + initial_result.stderr)
            initial_payload = json.loads(initial.read_text(encoding="utf-8"))
            absent_transition = "该过渡引导句未进入S4学生有效内容。"
            initial_payload["placements"][0]["sourceAnchor"]["afterText"] = absent_transition
            initial_payload["placements"][0]["renderPlacement"]["insertBeforeText"] = absent_transition
            initial.write_text(
                json.dumps(initial_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            page_plan = self.write_page_plan(temp)
            page_plan.write_text(
                page_plan.read_text(encoding="utf-8").replace(
                    "完成一个课后作品。",
                    "观察这张主图。\n\n完成一个课后作品。",
                ),
                encoding="utf-8",
            )

            result, output = self.run_request(temp, initial, page_plan)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertFalse(output.exists())
            self.assertIn("LESSON_PLAN_IMAGE_ANCHOR_INVALID", result.stdout)

    def test_request_defers_reviewable_courseware_placement_until_image_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            teacher, visual_script = self.write_teacher_inputs(temp)
            initial_result, initial = self.run_initial(temp, teacher, visual_script)
            self.assertEqual(initial_result.returncode, 0, initial_result.stdout + initial_result.stderr)
            page_plan = self.write_page_plan(temp)
            result, output = self.run_request(temp, initial, page_plan)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            placement = next(item for item in payload["placements"] if item["pageNo"] == "P02")
            self.assertEqual(placement["placementStatus"], "pending_visual_review")
            self.assertEqual(placement["renderPlacement"]["decisionStatus"], "candidate_only")
            self.assertTrue(placement["renderPlacement"]["terminalPlacementForbidden"])

    def test_request_suppresses_teacher_image_on_interaction_page(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            teacher, visual_script = self.write_teacher_inputs(temp)
            initial_result, initial = self.run_initial(temp, teacher, visual_script)
            self.assertEqual(initial_result.returncode, 0, initial_result.stdout + initial_result.stderr)
            page_plan = self.write_page_plan(temp)
            text = page_plan.read_text(encoding="utf-8")
            text = text.replace("观察这张主图。\n说出图中的线索。", "没有教案图片。")
            text = text.replace("```json", "观察这张主图。\n说出图中的线索。\n\n```json")
            page_plan.write_text(text, encoding="utf-8")
            result, output = self.run_request(temp, initial, page_plan)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            placement = payload["placements"][0]
            self.assertEqual(placement["pageNo"], "P03")
            self.assertEqual(placement["placementStatus"], "suppressed_on_interaction_page")
            decision = next(item for item in payload["pageDecisions"] if item["pageNo"] == "P03")
            self.assertEqual(decision["decision"], "interaction_no_image")
            self.assertEqual(decision["assetIds"], [])

    def test_request_recognizes_transformed_interaction_anchor_fragment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            teacher, visual_script = self.write_teacher_inputs(temp)
            initial_result, initial = self.run_initial(temp, teacher, visual_script)
            self.assertEqual(initial_result.returncode, 0, initial_result.stdout + initial_result.stderr)
            initial_payload = json.loads(initial.read_text(encoding="utf-8"))
            initial_payload["placements"][0]["sourceAnchor"] = {
                "teacherLineAfter": 82,
                "beforeText": "答案是：A—B—C。",
                "afterText": "小狐狸先画卡，接着卡片被风吹上树枝，最后小鸟把卡送回来。三个事件前后相连，故事才完整。",
            }
            initial_payload["placements"][0]["sourceLocationText"] = "第82行后单独显示"
            initial_payload["placements"][0]["sourceLocationDetail"] = "单独显示"
            initial_payload["placements"][0]["renderPlacement"] = {
                "authority": "teacher_visual_script",
                "anchorType": "teacher_source_anchor",
                "insertAfterText": "答案是：A—B—C。",
                "insertBeforeText": "小狐狸先画卡，接着卡片被风吹上树枝，最后小鸟把卡送回来。三个事件前后相连，故事才完整。",
                "fallback": "none",
            }
            initial.write_text(json.dumps(initial_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            page_plan = self.write_page_plan(temp)
            text = page_plan.read_text(encoding="utf-8")
            text = text.replace("观察这张主图。\n说出图中的线索。", "没有教案图片。")
            text = text.replace(
                '"answer":["A"]',
                '"answer":["A"],"explanation":"正确顺序是A—B—C：小狐狸先画卡，接着卡片被风吹上树枝，最后小鸟把卡送回来。"',
            )
            page_plan.write_text(text, encoding="utf-8")
            result, output = self.run_request(temp, initial, page_plan)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["placements"][0]["pageNo"], "P03")
            self.assertEqual(payload["placements"][0]["placementStatus"], "suppressed_on_interaction_page")

    def test_resolved_accepts_only_requested_courseware_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            teacher, visual_script = self.write_teacher_inputs(temp)
            initial_result, initial = self.run_initial(temp, teacher, visual_script)
            self.assertEqual(initial_result.returncode, 0, initial_result.stdout + initial_result.stderr)
            page_plan = self.write_page_plan(temp)
            request_result, request = self.run_request(temp, initial, page_plan)
            self.assertEqual(request_result.returncode, 0, request_result.stdout + request_result.stderr)
            external = temp / "lesson001__external__page_plan_visual_return.md"
            external.write_text(
                page_plan.read_text(encoding="utf-8").replace(
                    "完成一个课后作品。",
                    "完成一个课后作品。\n\n- 课件配图地址：https://res.xrunda.com/test/l001-p02.webp\n"
                    "- 课件配图宽度：1200\n- 课件配图高度：800\n- 课件配图 alt：课后作品示意图",
                ),
                encoding="utf-8",
            )
            output = temp / "lesson001__S1__visual_asset_manifest.resolved.json"
            review = self.write_task_placement_review(temp, request, external)
            result = run(
                VISUAL_GATE_RUNNER,
                "--phase",
                "resolved",
                "--lesson-id",
                "lesson001",
                "--visual-mode",
                "visual_enhanced",
                "--request-manifest",
                request,
                "--page-plan",
                page_plan,
                "--external-return",
                external,
                "--placement-review",
                review,
                "--receipt-dir",
                temp / "receipts",
                "--output",
                output,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            courseware = next(item for item in payload["assets"] if item["imageType"] == "courseware_image")
            self.assertEqual(courseware["url"], "https://res.xrunda.com/test/l001-p02.webp")
            self.assertEqual(courseware["width"], 1200)
            self.assertEqual(courseware["height"], 800)
            self.assertEqual(payload["externalReturn"]["sha256"], sha256(external))

    def test_resolved_freezes_model_reviewed_task_fallback_before_s5(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            teacher, visual_script = self.write_teacher_inputs(temp)
            initial_result, initial = self.run_initial(temp, teacher, visual_script)
            self.assertEqual(initial_result.returncode, 0, initial_result.stdout + initial_result.stderr)
            page_plan = self.write_page_plan(temp)
            request_result, request = self.run_request(temp, initial, page_plan)
            self.assertEqual(request_result.returncode, 0, request_result.stdout + request_result.stderr)
            external = temp / "lesson001__external__page_plan_visual_return.md"
            external.write_text(
                page_plan.read_text(encoding="utf-8").replace(
                    "完成一个课后作品。",
                    "完成一个课后作品。\n\n- 课件配图地址：https://res.xrunda.com/test/l001-p02.webp",
                ),
                encoding="utf-8",
            )
            output = temp / "lesson001__S1__visual_asset_manifest.resolved.json"
            review = self.write_task_placement_review(temp, request, external)
            result = run(
                VISUAL_GATE_RUNNER,
                "--phase", "resolved",
                "--lesson-id", "lesson001",
                "--visual-mode", "visual_enhanced",
                "--request-manifest", request,
                "--page-plan", page_plan,
                "--external-return", external,
                "--placement-review", review,
                "--receipt-dir", temp / "receipts",
                "--output", output,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            placement = next(item for item in payload["placements"] if item["pageNo"] == "P02")
            self.assertEqual(placement["placementStatus"], "reviewed")
            self.assertTrue(placement["visualReview"]["imageReviewed"])
            self.assertTrue(placement["visualReview"]["fallbackUsed"])
            self.assertEqual(placement["renderPlacement"]["insertAfter"], "first_text_block")
            self.assertTrue(placement["renderPlacement"]["terminalPlacementForbidden"])

    def test_resolved_allows_image_text_overlap_and_records_it_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            teacher, visual_script = self.write_teacher_inputs(temp)
            initial_result, initial = self.run_initial(temp, teacher, visual_script)
            self.assertEqual(initial_result.returncode, 0, initial_result.stdout + initial_result.stderr)
            page_plan = self.write_page_plan(temp)
            request_result, request = self.run_request(temp, initial, page_plan)
            self.assertEqual(request_result.returncode, 0, request_result.stdout + request_result.stderr)
            external = temp / "lesson001__external__page_plan_visual_return.md"
            external.write_text(
                page_plan.read_text(encoding="utf-8").replace(
                    "完成一个课后作品。",
                    "完成一个课后作品。\n\n- 课件配图地址：https://res.xrunda.com/test/l001-p02.webp",
                ),
                encoding="utf-8",
            )
            review = self.write_task_placement_review(temp, request, external)
            review_payload = json.loads(review.read_text(encoding="utf-8"))
            review_payload["reviews"][0].pop("embeddedTextOverlapDetected")
            review_payload["reviews"][0]["embeddedTextConflict"] = True
            review.write_text(
                json.dumps(review_payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            output = temp / "lesson001__S1__visual_asset_manifest.resolved.json"
            result = run(
                VISUAL_GATE_RUNNER,
                "--phase", "resolved",
                "--lesson-id", "lesson001",
                "--visual-mode", "visual_enhanced",
                "--request-manifest", request,
                "--page-plan", page_plan,
                "--external-return", external,
                "--placement-review", review,
                "--receipt-dir", temp / "receipts",
                "--output", output,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            placement = next(item for item in payload["placements"] if item["pageNo"] == "P02")
            self.assertTrue(placement["visualReview"]["embeddedTextOverlapDetected"])
            self.assertNotIn("embeddedTextConflict", placement["visualReview"])

    def test_resolved_ignores_courseware_candidate_on_lesson_plan_image_page(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            teacher, visual_script = self.write_teacher_inputs(temp)
            initial_result, initial = self.run_initial(temp, teacher, visual_script)
            self.assertEqual(initial_result.returncode, 0, initial_result.stdout + initial_result.stderr)
            page_plan = self.write_page_plan(temp)
            request_result, request = self.run_request(temp, initial, page_plan)
            self.assertEqual(request_result.returncode, 0, request_result.stdout + request_result.stderr)
            external = temp / "lesson001__external__page_plan_visual_return.md"
            external_text = page_plan.read_text(encoding="utf-8")
            external_text = external_text.replace(
                "说出图中的线索。",
                "说出图中的线索。\n\n- 课件配图地址：https://res.xrunda.com/test/ignored-p01.webp",
            )
            external_text = external_text.replace(
                "完成一个课后作品。",
                "完成一个课后作品。\n\n- 课件配图地址：https://res.xrunda.com/test/l001-p02.webp",
            )
            external.write_text(external_text, encoding="utf-8")
            output = temp / "lesson001__S1__visual_asset_manifest.resolved.json"
            review = self.write_task_placement_review(temp, request, external)
            result = run(
                VISUAL_GATE_RUNNER,
                "--phase", "resolved",
                "--lesson-id", "lesson001",
                "--visual-mode", "visual_enhanced",
                "--request-manifest", request,
                "--page-plan", page_plan,
                "--external-return", external,
                "--placement-review", review,
                "--receipt-dir", temp / "receipts",
                "--output", output,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            lesson_plan = next(item for item in payload["assets"] if item["imageType"] == "lesson_plan_image")
            courseware = next(item for item in payload["assets"] if item["imageType"] == "courseware_image")
            self.assertEqual(lesson_plan["url"], "https://res.xrunda.com/test/l001-v01.webp")
            self.assertEqual(courseware["url"], "https://res.xrunda.com/test/l001-p02.webp")
            self.assertEqual(payload["externalReturn"]["ignoredCoursewarePages"], ["P01"])
            self.assertTrue(payload["checks"]["lessonPlanImagePriorityApplied"])

    def test_resolved_accepts_cross_chain_body_drift_with_matching_page_types(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            teacher, visual_script = self.write_teacher_inputs(temp)
            initial_result, initial = self.run_initial(temp, teacher, visual_script)
            self.assertEqual(initial_result.returncode, 0, initial_result.stdout + initial_result.stderr)
            page_plan = self.write_page_plan(temp)
            request_result, request = self.run_request(temp, initial, page_plan)
            self.assertEqual(request_result.returncode, 0, request_result.stdout + request_result.stderr)
            external = temp / "drift.md"
            external.write_text(
                page_plan.read_text(encoding="utf-8").replace(
                    "完成一个课后作品。",
                    "旧链中经过局部调整的课后作品说明。\n\n"
                    "- 课件配图地址：https://res.xrunda.com/test/l001-p02.webp",
                ),
                encoding="utf-8",
            )
            output = temp / "resolved.json"
            review = self.write_task_placement_review(temp, request, external)
            result = run(
                VISUAL_GATE_RUNNER,
                "--phase", "resolved",
                "--lesson-id", "lesson001",
                "--visual-mode", "visual_enhanced",
                "--request-manifest", request,
                "--page-plan", page_plan,
                "--external-return", external,
                "--placement-review", review,
                "--receipt-dir", temp / "receipts",
                "--output", output,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["externalReturn"]["bindingMode"], "cross_chain_page_metadata")
            self.assertFalse(payload["checks"]["externalReturnPagePlanExactAfterMetadataRemoval"])
            self.assertTrue(payload["checks"]["externalReturnPageSetAndTypesMatch"])

    def test_resolved_blocks_cross_chain_page_type_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            teacher, visual_script = self.write_teacher_inputs(temp)
            initial_result, initial = self.run_initial(temp, teacher, visual_script)
            self.assertEqual(initial_result.returncode, 0, initial_result.stdout + initial_result.stderr)
            page_plan = self.write_page_plan(temp)
            request_result, request = self.run_request(temp, initial, page_plan)
            self.assertEqual(request_result.returncode, 0, request_result.stdout + request_result.stderr)
            external = temp / "wrong-page-type.md"
            external.write_text(
                page_plan.read_text(encoding="utf-8")
                .replace("- 页面类型：课后任务", "- 页面类型：课程小结")
                .replace(
                    "完成一个课后作品。",
                    "完成一个课后作品。\n\n"
                    "- 课件配图地址：https://res.xrunda.com/test/l001-p02.webp",
                ),
                encoding="utf-8",
            )
            review = self.write_task_placement_review(temp, request, external)

            result = run(
                VISUAL_GATE_RUNNER,
                "--phase", "resolved",
                "--lesson-id", "lesson001",
                "--visual-mode", "visual_enhanced",
                "--request-manifest", request,
                "--page-plan", page_plan,
                "--external-return", external,
                "--placement-review", review,
                "--receipt-dir", temp / "receipts",
                "--output", temp / "resolved.json",
            )

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("EXTERNAL_RETURN_PAGE_TYPE_MISMATCH", result.stdout)

    def test_stage_gate_blocks_visual_mode_drift(self) -> None:
        fixture = FIXTURES / "transition-boundary"
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            working = fixture / "page_plan_working_full.md"
            question = fixture / "question_processed_full.md"
            prior = temp / "s3.json"
            prior.write_text(
                json.dumps(
                    {
                        "contract": "RunS_V3.5.0-S1-S6-R36-20260731",
                        "lesson_id": "lesson001",
                        "stage": "S3",
                        "visualMode": "text_only",
                        "status": "PASS",
                        "inputs": [{"role": "working_plan", "path": str(working.resolve()), "sha256": sha256(working)}],
                        "output": {"role": "question_processed", "path": str(question.resolve()), "sha256": sha256(question)},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            result = run(
                GATE_RUNNER,
                "--stage", "S4",
                "--lesson-id", "lesson001",
                "--visual-mode", "visual_enhanced",
                "--receipt-dir", temp / "receipts",
                "--prior-receipt", prior,
                "--working-plan", working,
                "--question-processed", question,
                "--output", temp / "page_plan_full.md",
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("VISUAL_MODE_DRIFT", result.stdout)


class VisualS5ProjectionTests(unittest.TestCase):
    def write_s5_inputs(self, temp: Path) -> tuple[Path, Path]:
        page_plan = temp / "page_plan_full.md"
        page_plan.write_text(
            "## P01\n- 页面类型：课程开篇\n- 胶囊文案：课程开篇\n- 页面动作：nextPage\n"
            "- 来源块：course_info_header\n- 内容块类型：课程信息头\n- 布局意图：六项课程信息按原顺序展示。\n"
            "- 过渡句位置：none\n- 过渡句原文：无\n\n### 有效内容\n\n"
            "课包名称：测试课包\n单元名称：测试单元\n课程编号：第1课\n课程标题：视觉测试\n课程目标：理解配图规则\n知识点：教案图；课件图\n\n"
            "## P02\n- 页面类型：知识讲解\n- 胶囊文案：知识讲解\n- 页面动作：nextPage\n"
            "- 来源块：B02\n- 内容块类型：段落\n- 布局意图：按原文展示。\n"
            "- 过渡句位置：none\n- 过渡句原文：无\n\n### 有效内容\n\n"
            "图片呈现可见信息。\n\n"
            "- 画面A：小狐狸在窗边画生日卡。\n"
            "- 画面B：生日卡被风吹到树枝上。\n\n"
            "文字补充画面外的信息。\n\n"
            "## P03\n- 页面类型：互动题目\n- 胶囊文案：试一试\n- 页面动作：nextPage\n"
            "- 来源块：B03\n- 内容块类型：题目\n- 布局意图：组件展示。\n"
            "- 过渡句位置：none\n- 过渡句原文：无\n- 组件类型：galaxy_select_question\n\n### 有效内容\n\n"
            "```json\n{\"type\":\"galaxy_select_question\",\"componentId\":\"L001-I01\",\"content\":{\"questions\":[{\"question\":\"请选择\",\"options\":[\"A\",\"B\"],\"isMultiple\":false,\"answerIndex\":[0],\"answer\":[\"A\"]}]}}\n```\n\n"
            "## P04\n- 页面类型：拓展练习\n- 胶囊文案：拓展练习\n- 页面动作：complete\n"
            "- 来源块：B04\n- 内容块类型：任务\n- 布局意图：按原文展示。\n"
            "- 过渡句位置：none\n- 过渡句原文：无\n\n### 有效内容\n\n"
            "## 完成图文作品\n\n按顺序组合图片和文字。\n\n"
            "**固定材料：**课程配图；课程文字。\n\n"
            "```text\n请按顺序组合课程配图和课程文字。\n```\n",
            encoding="utf-8",
        )
        external = temp / "already-consumed-and-removed.md"
        resolved = temp / "lesson001__S1__visual_asset_manifest.resolved.json"
        resolved.write_text(
            json.dumps(
                {
                    "schemaVersion": "1.1",
                    "lessonId": "lesson001",
                    "visualMode": "visual_enhanced",
                    "ownerStage": "S1",
                    "lifecycleState": "resolved",
                    "sourceTeacherFinal": {"path": "/frozen/final.md", "sha256": "1" * 64},
                    "sourceTeacherVisualScript": {"path": "/frozen/visual.md", "sha256": "2" * 64},
                    "sourcePagePlan": {"path": str(page_plan.resolve()), "sha256": sha256(page_plan)},
                    "externalReturn": {"path": str(external.resolve()), "sha256": "3" * 64},
                    "policy": {
                        "lessonPlanImagePriority": True,
                        "coursewareImageOnlyWithoutLessonPlanImage": True,
                        "coursewareImageOnInteractionPage": False,
                        "maximumCoursewareImagesPerPage": 1,
                        "missingUrlFallbackAllowed": False,
                    },
                    "assets": [
                        {"assetId": "L001-P01-C01", "imageType": "courseware_image", "url": "https://res.xrunda.com/test/p01.webp", "width": 1200, "height": 800, "alt": "课程开篇图", "teachingPurpose": None, "sourceAuthority": "external_courseware_return", "assetStatus": "ready"},
                        {"assetId": "L001-V01", "imageType": "lesson_plan_image", "url": "https://res.xrunda.com/test/v01.webp", "width": None, "height": None, "alt": "画面一", "teachingPurpose": "比较画面", "sourceAuthority": "teacher_visual_script", "assetStatus": "ready"},
                        {"assetId": "L001-V02", "imageType": "lesson_plan_image", "url": "https://res.xrunda.com/test/v02.webp", "width": 900, "height": 1200, "alt": "画面二", "teachingPurpose": "比较画面", "sourceAuthority": "teacher_visual_script", "assetStatus": "ready"},
                        {"assetId": "L001-P04-C01", "imageType": "courseware_image", "url": "https://res.xrunda.com/test/p04.webp", "width": None, "height": None, "alt": None, "teachingPurpose": None, "sourceAuthority": "external_courseware_return", "assetStatus": "ready"},
                    ],
                    "placements": [
                        {"placementId": "P01-C", "assetId": "L001-P01-C01", "sourceAnchor": None, "sourceLocationText": None, "sourceLocationDetail": None, "renderPlacement": {"authority": "page_type_contract", "anchorType": "page_type_rule", "rule": "course_intro_primary_image", "inside": "course_overview", "insertBefore": "lesson_chip", "replaces": "existing_intro_decorative_image_slot", "fallback": "before_course_title", "decisionStatus": "final_fixed", "terminalPlacementForbidden": True}, "pageNo": "P01", "displayMode": "single", "groupId": None, "order": None, "displayLabel": None, "placementStatus": "active", "visualReview": {"imageReviewed": False, "reviewNotRequiredReason": "fixed_page_type_placement", "fallbackUsed": False}},
                        {"placementId": "P02-V1", "assetId": "L001-V01", "sourceAnchor": {"teacherLineAfter": 1, "beforeText": "图片呈现可见信息。", "afterText": "- 画面A：小狐狸在窗边画生日卡。"}, "sourceLocationText": "第1行后与下一张图并列", "sourceLocationDetail": "与下一张图并列", "renderPlacement": {"authority": "teacher_visual_script", "anchorType": "teacher_source_anchor", "insertAfterText": "图片呈现可见信息。", "insertBeforeText": "- 画面A：小狐狸在窗边画生日卡。", "fallback": "none"}, "pageNo": "P02", "displayMode": "group_item", "groupId": "L001-G1", "order": 1, "displayLabel": "画面 A", "placementStatus": "active"},
                        {"placementId": "P02-V2", "assetId": "L001-V02", "sourceAnchor": {"teacherLineAfter": 1, "beforeText": "图片呈现可见信息。", "afterText": "- 画面A：小狐狸在窗边画生日卡。"}, "sourceLocationText": "第1行后与上一张图并列", "sourceLocationDetail": "与上一张图并列", "renderPlacement": {"authority": "teacher_visual_script", "anchorType": "teacher_source_anchor", "insertAfterText": "图片呈现可见信息。", "insertBeforeText": "- 画面A：小狐狸在窗边画生日卡。", "fallback": "none"}, "pageNo": "P02", "displayMode": "group_item", "groupId": "L001-G1", "order": 2, "displayLabel": "画面 B", "placementStatus": "active"},
                        {"placementId": "P03-V1-SUPPRESSED", "assetId": "L001-V01", "sourceAnchor": {"teacherLineAfter": 2, "beforeText": "请选择。", "afterText": "查看答案。"}, "sourceLocationText": "第2行后复用", "sourceLocationDetail": "复用", "renderPlacement": {"authority": "teacher_visual_script", "anchorType": "teacher_source_anchor", "insertAfterText": "请选择。", "insertBeforeText": "查看答案。", "fallback": "none"}, "pageNo": "P03", "displayMode": "reuse", "groupId": None, "order": None, "displayLabel": None, "placementStatus": "suppressed_on_interaction_page", "suppressionReason": "interaction_component_contract_forbids_course_images"},
                        {"placementId": "P04-C", "assetId": "L001-P04-C01", "sourceAnchor": None, "sourceLocationText": None, "sourceLocationDetail": None, "renderPlacement": {"authority": "model_visual_review", "anchorType": "reviewed_semantic_anchor", "rule": "extension_contextual_image", "insertAfter": "first_text_block", "fallback": "after_first_text_block", "terminalPlacementForbidden": True}, "pageNo": "P04", "displayMode": "single", "groupId": None, "order": None, "displayLabel": None, "placementStatus": "reviewed", "visualReview": {"imageReviewed": True, "semanticRelation": "图片支持理解任务目标。", "embeddedTextOverlapDetected": False, "fallbackUsed": True}},
                    ],
                    "pageDecisions": [
                        {"pageNo": "P01", "pageType": "课程开篇", "decision": "courseware_image", "reason": "non_interactive_without_lesson_plan_image", "requiredAssetCount": 1, "assetIds": ["L001-P01-C01"], "status": "resolved"},
                        {"pageNo": "P02", "pageType": "知识讲解", "decision": "lesson_plan_image", "reason": "teacher_visual_script_anchor_bound_to_page", "requiredAssetCount": 2, "assetIds": ["L001-V01", "L001-V02"], "status": "ready"},
                        {"pageNo": "P03", "pageType": "互动题目", "decision": "interaction_no_image", "reason": "interaction_component_contract_forbids_course_images", "requiredAssetCount": 0, "assetIds": [], "status": "not_applicable"},
                        {"pageNo": "P04", "pageType": "拓展练习", "decision": "courseware_image", "reason": "non_interactive_without_lesson_plan_image", "requiredAssetCount": 1, "assetIds": ["L001-P04-C01"], "status": "resolved"},
                    ],
                    "checks": {},
                    "blockingPoints": [],
                },
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        return page_plan, resolved

    def test_text_only_explicit_mode_keeps_s5_bytes_unchanged(self) -> None:
        fixture = FIXTURES / "summary-status-preview" / "page_plan_full.md"
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            legacy = temp / "legacy.json"
            explicit = temp / "explicit.json"
            legacy_result = run(S5_GENERATOR, "--lesson-id", "lesson001", "--page-plan", fixture, "--output", legacy)
            explicit_result = run(S5_GENERATOR, "--lesson-id", "lesson001", "--visual-mode", "text_only", "--page-plan", fixture, "--output", explicit)
            self.assertEqual(legacy_result.returncode, 0, legacy_result.stdout + legacy_result.stderr)
            self.assertEqual(explicit_result.returncode, 0, explicit_result.stdout + explicit_result.stderr)
            self.assertEqual(legacy.read_bytes(), explicit.read_bytes())
            self.assertNotIn("visual", explicit.read_text(encoding="utf-8"))

    def test_visual_enhanced_projects_resolved_manifest_without_external_read(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            page_plan, resolved = self.write_s5_inputs(temp)
            output = temp / "effective_content_full.json"
            result = run(S5_GENERATOR, "--lesson-id", "lesson001", "--visual-mode", "visual_enhanced", "--page-plan", page_plan, "--visual-manifest", resolved, "--output", output)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["visualMode"], "visual_enhanced")
            self.assertEqual(payload["sourceVisualManifest"], str(resolved.resolve()))
            self.assertEqual(payload["sourceVisualManifestSha256"], sha256(resolved))
            self.assertEqual(payload["pages"][0]["visual"]["imageType"], "courseware_image")
            self.assertEqual(payload["pages"][1]["visual"]["displayMode"], "group")
            self.assertEqual([asset["displayLabel"] for asset in payload["pages"][1]["visual"]["assets"]], ["画面 A", "画面 B"])
            self.assertEqual(
                [asset["pairedStudentText"] for asset in payload["pages"][1]["visual"]["assets"]],
                ["画面A：小狐狸在窗边画生日卡。", "画面B：生日卡被风吹到树枝上。"],
            )
            self.assertEqual(
                [asset["pairedSource"] for asset in payload["pages"][1]["visual"]["assets"]],
                [
                    {"blockIndex": 1, "itemIndex": 0, "blockType": "unordered_list"},
                    {"blockIndex": 1, "itemIndex": 1, "blockType": "unordered_list"},
                ],
            )
            self.assertEqual(
                payload["pages"][0]["visual"]["assets"][0]["placement"],
                {
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
            )
            self.assertEqual(
                payload["pages"][1]["visual"]["assets"][0]["placement"]["insertAfterText"],
                "图片呈现可见信息。",
            )
            self.assertEqual(
                payload["pages"][1]["visual"]["assets"][0]["placement"]["insertBeforeText"],
                "- 画面A：小狐狸在窗边画生日卡。",
            )
            self.assertEqual(
                payload["pages"][0]["visual"]["presentation"],
                {
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
                },
            )
            self.assertNotIn("visual", payload["pages"][2])
            validation = run(VALIDATOR, "--page-plan", page_plan, "--visual-mode", "visual_enhanced", "--visual-manifest", resolved, output)
            self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)

    def test_visual_s5_blocks_manifest_bound_to_stale_s4(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            page_plan, resolved = self.write_s5_inputs(temp)
            payload = json.loads(resolved.read_text(encoding="utf-8"))
            payload["sourcePagePlan"]["sha256"] = "0" * 64
            resolved.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            result = run(S5_GENERATOR, "--lesson-id", "lesson001", "--visual-mode", "visual_enhanced", "--page-plan", page_plan, "--visual-manifest", resolved, "--output", temp / "effective.json")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("VISUAL_MANIFEST_PAGE_PLAN_HASH_MISMATCH", result.stderr)

    def test_visual_s5_gate_verifies_visual_receipt_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            page_plan, resolved = self.write_s5_inputs(temp)
            s4_receipt = temp / "s4.json"
            s4_receipt.write_text(json.dumps({"contract": "RunS_V3.5.0-S1-S6-R36-20260731", "lesson_id": "lesson001", "stage": "S4", "visualMode": "visual_enhanced", "status": "PASS", "output": {"role": "page_plan", "path": str(page_plan.resolve()), "sha256": sha256(page_plan)}}), encoding="utf-8")
            visual_receipt = temp / "visual.json"
            visual_receipt.write_text(json.dumps({"contract": "RunS_V3.5.0-S1-S6-R36-20260731", "lessonId": "lesson001", "lesson_id": "lesson001", "visualMode": "visual_enhanced", "ownerStage": "S1", "phase": "resolved", "status": "PASS", "output": {"role": "visual_manifest_resolved", "path": str(resolved.resolve()), "sha256": "0" * 64}}), encoding="utf-8")
            result = run(GATE_RUNNER, "--stage", "S5", "--lesson-id", "lesson001", "--visual-mode", "visual_enhanced", "--receipt-dir", temp / "receipts", "--prior-receipt", s4_receipt, "--page-plan", page_plan, "--visual-manifest", resolved, "--visual-receipt", visual_receipt, "--output", temp / "effective.json")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("VISUAL_RECEIPT_OUTPUT_HASH_MISMATCH", result.stdout)

    def test_visual_s5_gate_accepts_hash_bound_legacy_s4_receipt_without_visual_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            page_plan, resolved = self.write_s5_inputs(temp)
            s4_receipt = temp / "s4.json"
            s4_receipt.write_text(
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
                    }
                ),
                encoding="utf-8",
            )
            visual_receipt = temp / "visual.json"
            visual_receipt.write_text(
                json.dumps(
                    {
                        "contract": "RunS_V3.5.0-S1-S6-R36-20260731",
                        "lessonId": "lesson001",
                        "lesson_id": "lesson001",
                        "visualMode": "visual_enhanced",
                        "ownerStage": "S1",
                        "phase": "resolved",
                        "status": "PASS",
                        "output": {
                            "role": "visual_manifest_resolved",
                            "path": str(resolved.resolve()),
                            "sha256": sha256(resolved),
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = run(
                GATE_RUNNER,
                "--stage", "S5",
                "--lesson-id", "lesson001",
                "--visual-mode", "visual_enhanced",
                "--receipt-dir", temp / "receipts",
                "--prior-receipt", s4_receipt,
                "--page-plan", page_plan,
                "--visual-manifest", resolved,
                "--visual-receipt", visual_receipt,
                "--output", temp / "effective.json",
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_visual_s5_gate_blocks_explicit_legacy_s4_visual_mode_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            page_plan, resolved = self.write_s5_inputs(temp)
            s4_receipt = temp / "s4.json"
            s4_receipt.write_text(
                json.dumps(
                    {
                        "contract": "RunS_V3.5.0-S1-S6-R36-20260731",
                        "lesson_id": "lesson001",
                        "stage": "S4",
                        "visualMode": "text_only",
                        "status": "PASS",
                        "output": {
                            "role": "page_plan",
                            "path": str(page_plan.resolve()),
                            "sha256": sha256(page_plan),
                        },
                    }
                ),
                encoding="utf-8",
            )
            visual_receipt = temp / "visual.json"
            visual_receipt.write_text(
                json.dumps(
                    {
                        "contract": "RunS_V3.5.0-S1-S6-R36-20260731",
                        "lessonId": "lesson001",
                        "lesson_id": "lesson001",
                        "visualMode": "visual_enhanced",
                        "ownerStage": "S1",
                        "phase": "resolved",
                        "status": "PASS",
                        "output": {
                            "role": "visual_manifest_resolved",
                            "path": str(resolved.resolve()),
                            "sha256": sha256(resolved),
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = run(
                GATE_RUNNER,
                "--stage", "S5",
                "--lesson-id", "lesson001",
                "--visual-mode", "visual_enhanced",
                "--receipt-dir", temp / "receipts",
                "--prior-receipt", s4_receipt,
                "--page-plan", page_plan,
                "--visual-manifest", resolved,
                "--visual-receipt", visual_receipt,
                "--output", temp / "effective.json",
            )

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("VISUAL_MODE_DRIFT", result.stdout)

    def test_visual_validator_blocks_any_interaction_image_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            page_plan, resolved = self.write_s5_inputs(temp)
            output = temp / "effective.json"
            result = run(S5_GENERATOR, "--lesson-id", "lesson001", "--visual-mode", "visual_enhanced", "--page-plan", page_plan, "--visual-manifest", resolved, "--output", output)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            payload["pages"][2]["visual"] = {"imageType": "courseware_image", "displayMode": "single", "assets": []}
            output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            validation = run(VALIDATOR, "--page-plan", page_plan, "--visual-mode", "visual_enhanced", "--visual-manifest", resolved, output)
            self.assertEqual(validation.returncode, 1, validation.stdout + validation.stderr)
            self.assertIn("V35_S5_INTERACTION_IMAGE_FORBIDDEN", validation.stdout)

    def test_visual_pair_bindings_are_optional_but_cannot_be_partial(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            page_plan, resolved = self.write_s5_inputs(temp)
            output = temp / "effective.json"
            generated = run(S5_GENERATOR, "--lesson-id", "lesson001", "--visual-mode", "visual_enhanced", "--page-plan", page_plan, "--visual-manifest", resolved, "--output", output)
            self.assertEqual(generated.returncode, 0, generated.stdout + generated.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            assets = payload["pages"][1]["visual"]["assets"]
            frozen_pair = {
                "pairedStudentText": assets[0]["pairedStudentText"],
                "pairedSource": assets[0]["pairedSource"],
            }
            for asset in assets:
                asset.pop("pairedStudentText", None)
                asset.pop("pairedSource", None)
            output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            compatible = run(VALIDATOR, "--page-plan", page_plan, "--visual-mode", "visual_enhanced", "--visual-manifest", resolved, output)
            self.assertEqual(compatible.returncode, 0, compatible.stdout + compatible.stderr)
            assets[0].update(frozen_pair)
            output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            partial = run(VALIDATOR, "--page-plan", page_plan, "--visual-mode", "visual_enhanced", "--visual-manifest", resolved, output)
            self.assertEqual(partial.returncode, 1, partial.stdout + partial.stderr)
            self.assertIn("V35_S5_VISUAL_TEXT_PAIRING_INVALID", partial.stdout)


class VisualS6ProjectionTests(VisualS5ProjectionTests):
    def build_visual_s5(self, temp: Path) -> Path:
        page_plan, resolved = self.write_s5_inputs(temp)
        effective = temp / "effective_content_full.json"
        result = run(
            S5_GENERATOR,
            "--lesson-id", "lesson001",
            "--visual-mode", "visual_enhanced",
            "--page-plan", page_plan,
            "--visual-manifest", resolved,
            "--output", effective,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        page_plan.unlink()
        resolved.unlink()
        return effective

    def test_s6_visual_enhanced_consumes_only_s5_and_projects_page_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            effective = self.build_visual_s5(temp)
            output = temp / "whole_course.json"
            result = run(
                ASSEMBLER,
                "--lesson-id", "lesson001",
                "--effective-content", effective,
                "--output", output,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["visualMode"], "visual_enhanced")
            self.assertEqual(payload["pages"][0]["page_data"]["visualAsset"]["url"], "https://res.xrunda.com/test/p01.webp")
            self.assertEqual(
                payload["pages"][0]["page_data"]["visualAsset"]["placement"]["rule"],
                "course_intro_primary_image",
            )
            self.assertEqual(
                payload["pages"][0]["page_data"]["introDensityContract"]["minimumUnlockRowHeightPx"],
                44,
            )
            self.assertTrue(payload["pages"][0]["page_data"]["visualPresentation"]["thumbnailForbidden"])
            self.assertEqual(
                [asset["displayLabel"] for asset in payload["pages"][1]["page_data"]["planVisualAssets"]],
                ["画面 A", "画面 B"],
            )
            self.assertEqual(
                [asset["pairedStudentText"] for asset in payload["pages"][1]["page_data"]["planVisualAssets"]],
                ["画面A：小狐狸在窗边画生日卡。", "画面B：生日卡被风吹到树枝上。"],
            )
            self.assertEqual(
                [asset["pairedSource"] for asset in payload["pages"][1]["page_data"]["planVisualAssets"]],
                [
                    {"blockIndex": 1, "itemIndex": 0, "blockType": "unordered_list"},
                    {"blockIndex": 1, "itemIndex": 1, "blockType": "unordered_list"},
                ],
            )
            self.assertEqual(payload["pages"][3]["page_data"]["visualAsset"]["alt"], "")
            self.assertNotIn("visualAsset", payload["pages"][2]["page_data"])
            self.assertNotIn("planVisualAssets", payload["pages"][2]["page_data"])
            for page in (payload["pages"][0], payload["pages"][1], payload["pages"][3]):
                prompt = page["prompt"]
                expected_trigger = "hero-image-button" if page["page_no"] == "P01" else "image-zoom-trigger"
                self.assertIn(expected_trigger, prompt)
                self.assertIn("visual-lightbox", prompt)
                self.assertIn("Escape", prompt)
                self.assertIn("object-fit: contain", prompt)
                self.assertIn("正文主配图", prompt)
                self.assertIn("禁止缩略图", prompt)
                self.assertNotIn("window.open", prompt)
                self.assertNotIn('target="_blank"', prompt)
            for marker in (
                "pairedStudentText",
                "visual-paired-list",
                "visual-paired-item",
                "visual-paired-copy",
            ):
                self.assertIn(marker, payload["pages"][1]["prompt"])

            check = run(
                STATIC_CHECKER,
                "--s6-contract",
                "--lesson-id", "lesson001",
                "--effective-content", effective,
                "--whole-course", output,
            )
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            self.assertIn("IMPORT_READY_STATIC", check.stdout)

    def test_s6_prompt_version_changes_with_visual_url_alt_and_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            effective = self.build_visual_s5(temp)
            first = temp / "first.json"
            result = run(ASSEMBLER, "--lesson-id", "lesson001", "--effective-content", effective, "--output", first)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(effective.read_text(encoding="utf-8"))
            assets = payload["pages"][1]["visual"]["assets"]
            assets[0]["url"] = "https://res.xrunda.com/test/v01-revised.webp"
            assets[0]["alt"] = "更新后的画面一"
            payload["pages"][1]["visual"]["assets"] = list(reversed(assets))
            effective.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            second = temp / "second.json"
            result = run(ASSEMBLER, "--lesson-id", "lesson001", "--effective-content", effective, "--output", second)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            first_page = json.loads(first.read_text(encoding="utf-8"))["pages"][1]
            second_page = json.loads(second.read_text(encoding="utf-8"))["pages"][1]
            self.assertNotEqual(first_page["page_data"]["prompt_version"], second_page["page_data"]["prompt_version"])
            self.assertNotEqual(first_page["page_data"]["prompt_instance_sha256"], second_page["page_data"]["prompt_instance_sha256"])

    def test_dynamic_html_visual_contract_accepts_exact_assets_and_blocks_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            effective = self.build_visual_s5(temp)
            payload = json.loads(effective.read_text(encoding="utf-8"))
            blocks = payload["pages"][1]["effective_content"]["blocks"]
            source_before = blocks[0]["text"]
            source_after = blocks[-1]["text"]
            html = temp / "page.html"
            html.write_text(
                '<!doctype html><html><head><style>.visual-image{width:100%;max-width:920px;height:auto;object-fit: contain;}.visual-gallery{display:block}.visual-lightbox-stage{display:flex;align-items:center;justify-content:center}.visual-lightbox-close{position:fixed;left:50%;border-radius:50%;}</style></head><body>'
                f'<article class="knowledge-content"><p>{source_before}</p>'
                '<section class="visual-gallery" data-visual-group-layout="vertical_stack" data-visual-placement-terminal="forbidden">'
                '<ul class="visual-paired-list">'
                '<li class="visual-paired-item" data-visual-pair-asset-id="L001-V01"><button type="button" class="image-zoom-trigger"><img class="visual-image" src="https://res.xrunda.com/test/v01.webp" alt="画面一"></button><span>画面 A</span><p class="visual-paired-copy">画面A：小狐狸在窗边画生日卡。</p></li>'
                '<li class="visual-paired-item" data-visual-pair-asset-id="L001-V02"><button type="button" class="image-zoom-trigger"><img class="visual-image" src="https://res.xrunda.com/test/v02.webp" alt="画面二"></button><span>画面 B</span><p class="visual-paired-copy">画面B：生日卡被风吹到树枝上。</p></li>'
                f'</ul></section><p>{source_after}</p></article>'
                '<div class="visual-lightbox" hidden><div class="visual-lightbox-dialog"><div class="visual-lightbox-stage"><img class="visual-lightbox-image" alt=""></div><button type="button" class="visual-lightbox-close" aria-label="关闭大图"><span aria-hidden="true">×</span></button></div></div>'
                '<script>function resetVisualTransform(){};function positionVisualClose(){var imageRect=document.querySelector(".visual-lightbox-image").getBoundingClientRect();return imageRect.bottom;}var stage=document.querySelector(".visual-lightbox-stage");stage.addEventListener("touchstart",function(){});stage.addEventListener("touchmove",function(){var scale=Math.max(1,Math.min(4,2));});document.addEventListener("keydown",function(event){if(event.key==="Escape"){};});</script>'
                '</body></html>',
                encoding="utf-8",
            )
            valid = run(DYNAMIC_HTML_VALIDATOR, "--effective-content", effective, "--page-no", "P02", "--html", html)
            self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)
            html.write_text(html.read_text(encoding="utf-8").replace("</section>", '<img src="https://res.xrunda.com/test/v01.webp" alt="画面一"></section>', 1), encoding="utf-8")
            invalid = run(DYNAMIC_HTML_VALIDATOR, "--effective-content", effective, "--page-no", "P02", "--html", html)
            self.assertEqual(invalid.returncode, 1, invalid.stdout + invalid.stderr)
            self.assertIn("DYNAMIC_HTML_VISUAL_URL_CARDINALITY", invalid.stdout)

    def test_dynamic_html_visual_contract_blocks_detached_group_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            effective = self.build_visual_s5(temp)
            payload = json.loads(effective.read_text(encoding="utf-8"))
            blocks = payload["pages"][1]["effective_content"]["blocks"]
            html = temp / "page.html"
            html.write_text(
                '<!doctype html><html><head><style>.visual-image{width:100%;height:auto;object-fit: contain;}.visual-gallery{display:block}.visual-lightbox-stage{display:flex;align-items:center;justify-content:center}.visual-lightbox-close{position:fixed;left:50%;border-radius:50%;}</style></head><body>'
                f'<article class="knowledge-content"><p>{blocks[0]["text"]}</p>'
                '<section class="visual-gallery" data-visual-group-layout="vertical_stack" data-visual-placement-terminal="forbidden">'
                '<button type="button" class="image-zoom-trigger"><img class="visual-image" src="https://res.xrunda.com/test/v01.webp" alt="画面一"></button><span>画面 A</span>'
                '<button type="button" class="image-zoom-trigger"><img class="visual-image" src="https://res.xrunda.com/test/v02.webp" alt="画面二"></button><span>画面 B</span></section>'
                '<ul><li>画面A：小狐狸在窗边画生日卡。</li><li>画面B：生日卡被风吹到树枝上。</li></ul>'
                f'<p>{blocks[-1]["text"]}</p></article>'
                '<div class="visual-lightbox" hidden><div class="visual-lightbox-dialog"><div class="visual-lightbox-stage"><img class="visual-lightbox-image" alt=""></div><button type="button" class="visual-lightbox-close" aria-label="关闭大图"><span aria-hidden="true">×</span></button></div></div>'
                '<script>function resetVisualTransform(){};function positionVisualClose(){var imageRect=document.querySelector(".visual-lightbox-image").getBoundingClientRect();return imageRect.bottom;}var stage=document.querySelector(".visual-lightbox-stage");stage.addEventListener("touchstart",function(){});stage.addEventListener("touchmove",function(){var scale=Math.max(1,Math.min(4,2));});document.addEventListener("keydown",function(event){if(event.key==="Escape"){};});</script>'
                '</body></html>',
                encoding="utf-8",
            )
            invalid = run(DYNAMIC_HTML_VALIDATOR, "--effective-content", effective, "--page-no", "P02", "--html", html)
            self.assertEqual(invalid.returncode, 1, invalid.stdout + invalid.stderr)
            self.assertIn("DYNAMIC_HTML_VISUAL_TEXT_PAIRING_INVALID", invalid.stdout)

    def test_dynamic_html_visual_contract_blocks_horizontal_terminal_gallery_and_old_close_button(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            effective = self.build_visual_s5(temp)
            payload = json.loads(effective.read_text(encoding="utf-8"))
            source = "".join(
                str(block.get("text") or "")
                for block in payload["pages"][1]["effective_content"]["blocks"]
                if isinstance(block, dict)
            )
            html = temp / "page.html"
            html.write_text(
                '<!doctype html><html><head><style>.visual-image{width:33%;height:auto;object-fit: contain;}.visual-gallery{display:flex}.visual-lightbox-close{position:absolute;top:82%;right:10px}</style></head><body>'
                f'<article class="knowledge-content"><p>{source}</p>'
                '<section class="visual-gallery"><button type="button" class="image-zoom-trigger"><img class="visual-image" src="https://res.xrunda.com/test/v01.webp" alt="画面一"></button><span>画面 A</span><button type="button" class="image-zoom-trigger"><img class="visual-image" src="https://res.xrunda.com/test/v02.webp" alt="画面二"></button><span>画面 B</span></section></article>'
                '<div class="visual-lightbox" hidden><div class="visual-lightbox-dialog"><div class="visual-lightbox-stage"><img class="visual-lightbox-image" alt=""></div><button type="button" class="visual-lightbox-close">关闭</button></div></div>'
                '<script>function resetVisualTransform(){};var stage=document.querySelector(".visual-lightbox-stage");stage.addEventListener("touchstart",function(){});stage.addEventListener("touchmove",function(){var scale=Math.max(1,Math.min(4,2));});document.addEventListener("keydown",function(event){if(event.key==="Escape"){};});</script>'
                '</body></html>',
                encoding="utf-8",
            )
            invalid = run(
                DYNAMIC_HTML_VALIDATOR,
                "--effective-content", effective,
                "--page-no", "P02",
                "--html", html,
            )
            self.assertEqual(invalid.returncode, 1, invalid.stdout + invalid.stderr)
            issue_codes = {item["code"] for item in json.loads(invalid.stdout)["issues"]}
            self.assertIn("DYNAMIC_HTML_VISUAL_GROUP_LAYOUT_INVALID", issue_codes)
            self.assertIn("DYNAMIC_HTML_VISUAL_TERMINAL_PLACEMENT", issue_codes)
            self.assertIn("DYNAMIC_HTML_VISUAL_LIGHTBOX_CONTRACT", issue_codes)

    def test_dynamic_html_visual_contract_rejects_modal_caption_and_missing_touch_zoom(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            effective = self.build_visual_s5(temp)
            payload = json.loads(effective.read_text(encoding="utf-8"))
            source = "".join(
                str(block.get("text") or "")
                for block in payload["pages"][1]["effective_content"]["blocks"]
                if isinstance(block, dict)
            )
            html = temp / "page.html"
            html.write_text(
                '<!doctype html><html><head><style>.visual-image{width:100%;height:auto;object-fit: contain;}</style></head><body>'
                '<section class="visual-gallery">'
                '<button type="button" class="image-zoom-trigger"><img class="visual-image" src="https://res.xrunda.com/test/v01.webp" alt="画面一"></button>'
                '<span class="visual-caption">画面 A</span>'
                '<button type="button" class="image-zoom-trigger"><img class="visual-image" src="https://res.xrunda.com/test/v02.webp" alt="画面二"></button>'
                '<span class="visual-caption">画面 B</span></section>'
                '<div class="visual-lightbox" hidden><div class="visual-lightbox-dialog">'
                '<div class="visual-lightbox-stage"><img class="visual-lightbox-image" alt=""><span class="visual-caption">重复说明</span></div>'
                '<button type="button" class="visual-lightbox-close">关闭</button></div></div>'
                f'<article class="knowledge-content"><p>{source}</p></article>'
                '<script>document.addEventListener("keydown",function(event){if(event.key==="Escape"){};});</script>'
                '</body></html>',
                encoding="utf-8",
            )
            invalid = run(
                DYNAMIC_HTML_VALIDATOR,
                "--effective-content", effective,
                "--page-no", "P02",
                "--html", html,
            )
            self.assertEqual(invalid.returncode, 1, invalid.stdout + invalid.stderr)
            self.assertIn("DYNAMIC_HTML_VISUAL_LIGHTBOX_CONTRACT", invalid.stdout)

    def test_visual_oneshots_and_demos_are_chrome68_compatible(self) -> None:
        static_spec = importlib.util.spec_from_file_location("visual_static_checker", STATIC_CHECKER)
        dynamic_spec = importlib.util.spec_from_file_location("visual_dynamic_checker", DYNAMIC_HTML_VALIDATOR)
        self.assertIsNotNone(static_spec)
        self.assertIsNotNone(dynamic_spec)
        static_module = importlib.util.module_from_spec(static_spec)
        dynamic_module = importlib.util.module_from_spec(dynamic_spec)
        assert static_spec.loader is not None
        assert dynamic_spec.loader is not None
        static_spec.loader.exec_module(static_module)
        dynamic_spec.loader.exec_module(dynamic_module)
        visual_oneshots = [
            path
            for number in range(9, 15)
            for path in (SKILL_ROOT / "templates" / "oneshots").glob(f"{number:02d}_*.md")
        ]
        visual_demos = sorted((SKILL_ROOT / "templates" / "demos" / "visual_enhanced").glob("*.html"))
        self.assertEqual(len(visual_oneshots), 6)
        self.assertEqual(len(visual_demos), 6)
        for path in visual_oneshots:
            self.assertEqual(static_module.chrome68_prompt_incompatibilities(path.read_text(encoding="utf-8")), [], path.name)
        for path in visual_demos:
            self.assertEqual(dynamic_module.chrome68_incompatibilities(path.read_text(encoding="utf-8")), [], path.name)

    def test_non_intro_visual_templates_use_full_width_shared_type_and_touch_lightbox(self) -> None:
        oneshots = [
            path
            for number in range(10, 15)
            for path in (SKILL_ROOT / "templates" / "oneshots").glob(f"{number:02d}_*.md")
        ]
        demos = [
            path
            for path in sorted((SKILL_ROOT / "templates" / "demos" / "visual_enhanced").glob("*.html"))
            if path.name != "course_intro_demo.html"
        ]
        self.assertEqual(len(oneshots), 5)
        self.assertEqual(len(demos), 5)
        required_markers = (
            "--runs-type-h1-size",
            "--runs-type-h2-size",
            "--runs-type-body-size",
            "--runs-type-list-size",
            "--runs-type-caption-size",
            "visual-lightbox-dialog",
            "visual-lightbox-stage",
            "touchstart",
            "touchmove",
            "resetVisualTransform",
        )
        for path in oneshots + demos:
            text = path.read_text(encoding="utf-8")
            for marker in required_markers:
                self.assertIn(marker, text, f"{path.name}: missing {marker}")
            self.assertNotRegex(text, r">\s*查看大图\s*<", path.name)
            self.assertNotRegex(
                text,
                r"visual-lightbox[^\n]{0,400}visual-caption",
                f"{path.name}: modal must not repeat captions",
            )
            self.assertIn("圆形", text, f"{path.name}: missing round icon-only close contract")
            self.assertIn("纵向中点", text, f"{path.name}: missing close-control midpoint contract")
            self.assertIn("positionVisualClose", text, f"{path.name}: missing calculated close-control placement")
            self.assertIn("getBoundingClientRect", text, f"{path.name}: missing actual-image placement measurement")
            if path.suffix == ".html" or path.name.startswith(("10_", "13_")):
                self.assertIn("width: 46px", text, f"{path.name}: close control must use the compact icon size")
                self.assertIn("height: 46px", text, f"{path.name}: close control must use the compact icon size")
                self.assertIn("top: 82%", text, f"{path.name}: close control must sit between the image stage and page bottom")
                self.assertRegex(
                    text,
                    r'<button type="button" class="visual-lightbox-close"(?: id="visualLightboxClose")? aria-label="关闭大图"><span aria-hidden="true">×</span></button>',
                    f"{path.name}: close control must be the icon-only reference button",
                )
                self.assertNotRegex(text, r">\s*关闭\s*<", f"{path.name}: close control must not show a text label")
        for number in (10, 13):
            path = next(
                (SKILL_ROOT / "templates" / "oneshots").glob(f"{number:02d}_*.md")
            )
            self.assertNotIn("width: calc(100% - 48px)", path.read_text(encoding="utf-8"))
        for name in ("scene_intro_demo.html", "course_summary_demo.html"):
            self.assertNotIn(
                "width: calc(100% - 48px)",
                (SKILL_ROOT / "templates" / "demos" / "visual_enhanced" / name).read_text(encoding="utf-8"),
            )

    def test_knowledge_visual_template_requires_frozen_order_adjacent_image_copy_pairs(self) -> None:
        oneshot = next((SKILL_ROOT / "templates" / "oneshots").glob("11_*.md"))
        demo = SKILL_ROOT / "templates" / "demos" / "visual_enhanced" / "knowledge_demo.html"
        for path in (oneshot, demo):
            text = path.read_text(encoding="utf-8")
            self.assertIn("visual-paired-list", text, f"{path.name}: missing paired group list")
            self.assertIn("visual-paired-item", text, f"{path.name}: missing image-copy pair item")
            self.assertIn("visual-paired-copy", text, f"{path.name}: missing adjacent source copy")
            self.assertIn("冻结顺序", text, f"{path.name}: group must follow frozen S5 order")
            self.assertNotIn("B、C、A", text, f"{path.name}: hidden storyboard reordering is forbidden")
            self.assertIn("纵向", text, f"{path.name}: group images must be vertical")
            self.assertNotIn("width: 33.333%", text, f"{path.name}: group thumbnails are forbidden")

    def test_course_intro_visual_templates_use_top_hero_reference_style(self) -> None:
        oneshot = next((SKILL_ROOT / "templates" / "oneshots").glob("09_*.md"))
        demo = SKILL_ROOT / "templates" / "demos" / "visual_enhanced" / "course_intro_demo.html"
        text_only_demo = SKILL_ROOT / "templates" / "demos" / "course_intro_demo.html"
        prompt_match = re.search(r"```text\n(.*?)\n```", oneshot.read_text(encoding="utf-8"), re.S)
        self.assertIsNotNone(prompt_match)
        assert prompt_match is not None
        html_match = re.search(r"<!doctype html>\n<html.*?</html>", prompt_match.group(1), re.S)
        self.assertIsNotNone(html_match)
        assert html_match is not None
        text_only_html = text_only_demo.read_text(encoding="utf-8")

        def css_rule_body(html_text: str, selector: str) -> str:
            match = re.search(re.escape(selector) + r"\s*\{(.*?)\}", html_text, re.S)
            self.assertIsNotNone(match, f"missing CSS rule: {selector}")
            assert match is not None
            return re.sub(r"\s+", " ", match.group(1)).strip()

        shared_intro_selectors = (
            ".content-card h3",
            ".core-question-panel h3",
            "#knowledgeList li",
            ".knowledge-index",
        )
        for name, html_text in (("oneshot", html_match.group(0)), ("demo", demo.read_text(encoding="utf-8"))):
            for marker in (
                'class="course-overview"',
                'id="visualHero"',
                'class="hero-image-button"',
                'class="hero-image"',
                'class="visual-lightbox-stage"',
                'class="visual-lightbox-image-wrap"',
                "touchstart",
                "touchmove",
                "resetVisualTransform",
            ):
                self.assertIn(marker, html_text, f"{name}: missing {marker}")
            self.assertLess(html_text.index('id="visualHero"'), html_text.index('id="lessonChip"'))
            self.assertLess(html_text.index('id="lessonChip"'), html_text.index('id="courseTitle"'))
            self.assertLess(html_text.index('id="courseTitle"'), html_text.index('id="learningGoal"'))
            self.assertLess(html_text.index('id="learningGoal"'), html_text.index('id="knowledgeList"'))
            self.assertLess(html_text.index('class="visual-lightbox-stage"'), html_text.index('class="visual-lightbox-close"'))
            self.assertNotIn('id="visualGallery"', html_text)
            self.assertNotIn("intro-illustration", html_text)
            self.assertNotIn('class="course-path"', html_text)
            self.assertNotIn('id="packageName"', html_text)
            self.assertNotIn('id="unitName"', html_text)
            self.assertNotIn('getElementById("packageName")', html_text)
            self.assertNotIn('getElementById("unitName")', html_text)
            self.assertNotRegex(html_text, r">\s*查看大图\s*<")
            self.assertRegex(
                html_text,
                r'class="learning-goal-heading"[^>]*>\s*<img class="core-question-icon"[\s\S]*?<h3 id="learningGoalTitle">学习目标</h3>',
            )
            heading_rule = css_rule_body(html_text, ".learning-goal-heading")
            self.assertIn("display: flex", heading_rule)
            self.assertIn("justify-content: center", heading_rule)
            icon_rule = css_rule_body(html_text, ".core-question-icon")
            self.assertIn("position: static", icon_rule)
            self.assertIn("width: 28px", icon_rule)
            goal_rule = css_rule_body(html_text, "#learningGoal")
            self.assertIn("text-align: left", goal_rule)
            self.assertIn("font-size: 14px", goal_rule)
            self.assertIn("line-height: 23px", goal_rule)
            for selector in shared_intro_selectors:
                self.assertEqual(
                    css_rule_body(html_text, selector),
                    css_rule_body(text_only_html, selector),
                    f"{name}: {selector} must reuse the text-only intro style",
                )

    def test_course_intro_visual_placement_targets_first_visible_identity(self) -> None:
        scripts_dir = str(SKILL_ROOT / "scripts")
        sys.path.insert(0, scripts_dir)
        try:
            spec = importlib.util.spec_from_file_location(
                "course_intro_visual_placement_contract",
                SKILL_ROOT / "scripts" / "visual_placement_contract.py",
            )
            self.assertIsNotNone(spec)
            assert spec is not None and spec.loader is not None
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            sys.path.remove(scripts_dir)
        placement = module.courseware_render_placement("课程开篇")
        self.assertEqual(placement["inside"], "course_overview")
        self.assertEqual(placement["insertBefore"], "lesson_chip")
        self.assertNotIn("course_identity", placement.values())

    def test_course_intro_visual_demo_uses_reviewable_sample_image(self) -> None:
        demo = SKILL_ROOT / "templates" / "demos" / "visual_enhanced" / "course_intro_demo.html"
        html_text = demo.read_text(encoding="utf-8")
        self.assertIn(
            "https://res.xrunda.com/ai-test/Galaxy/knowledge/20260804/72/1785848574637-62cf93816f772a4e.webp",
            html_text,
        )
        self.assertNotIn("https://res.xrunda.com/test/baseline/p01.webp", html_text)

    def test_visual_template_integrity_checks_reject_diff_markers_and_clipped_gallery(self) -> None:
        static_spec = importlib.util.spec_from_file_location("visual_integrity_static_checker", STATIC_CHECKER)
        dynamic_spec = importlib.util.spec_from_file_location("visual_integrity_dynamic_checker", DYNAMIC_HTML_VALIDATOR)
        self.assertIsNotNone(static_spec)
        self.assertIsNotNone(dynamic_spec)
        static_module = importlib.util.module_from_spec(static_spec)
        dynamic_module = importlib.util.module_from_spec(dynamic_spec)
        assert static_spec.loader is not None
        assert dynamic_spec.loader is not None
        static_spec.loader.exec_module(static_module)
        dynamic_spec.loader.exec_module(dynamic_module)

        diff_marked = (
            "<style>\n+    .visual-gallery { width: 100%; }\n</style>"
            "<script>\n+    const VISUAL_DATA = Object.freeze({});\n</script>"
        )
        clipped_gallery = (
            '<main class="runs-intro-page">'
            '<div class="intro-scroll"><div class="intro-inner"></div></div>'
            '<section class="visual-gallery" id="visualGallery"></section>'
            '</main>'
        )

        self.assertIn("diff marker", static_module.chrome68_prompt_incompatibilities(diff_marked))
        self.assertIn("diff marker", dynamic_module.chrome68_incompatibilities(diff_marked))
        self.assertIn(
            "visual gallery outside intro-scroll",
            static_module.chrome68_prompt_incompatibilities(clipped_gallery),
        )


if __name__ == "__main__":
    unittest.main()
