#!/usr/bin/env python3
from __future__ import annotations

import json
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


def run(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *map(str, args)],
        text=True,
        capture_output=True,
        check=False,
    )


class GenerationGateTests(unittest.TestCase):
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
            p01 = text.split("## P02", 1)[0]
            p02 = text.split("## P02", 1)[1]
            self.assertIn("- 过渡句位置：none", p01)
            self.assertIn("- 过渡句原文：无", p01)
            self.assertNotIn("试一试：再连一次", p01)
            self.assertIn("- 胶囊文案：试一试：再连一次", p02)

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
                "--draft",
                fixture / "draft_effective_content.json",
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


if __name__ == "__main__":
    unittest.main()
