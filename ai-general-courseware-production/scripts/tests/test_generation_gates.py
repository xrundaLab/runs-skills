#!/usr/bin/env python3
from __future__ import annotations

import json
import hashlib
import importlib.util
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
GATE_RUNNER = SKILL_ROOT / "scripts" / "orchestrator" / "run_stage_gate.py"
ASSEMBLER = SKILL_ROOT / "scripts" / "assembler" / "assemble_whole_course.py"


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
                "--draft",
                fixture / "draft_effective_content.json",
                "--output",
                output,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            page = json.loads(output.read_text(encoding="utf-8"))["pages"][0]

            spec = importlib.util.spec_from_file_location("courseware_assembler", ASSEMBLER)
            self.assertIsNotNone(spec)
            self.assertIsNotNone(spec.loader)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            values = module.summary_values(page, "complete")

            self.assertEqual(values["summaryTitle"], "这一课记住一件事")
            self.assertFalse(
                any(block.get("type") == "heading" for block in values["contentBlocks"])
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
            draft = fixture / "effective_content_full.json"
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
                "--draft",
                draft,
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


if __name__ == "__main__":
    unittest.main()
