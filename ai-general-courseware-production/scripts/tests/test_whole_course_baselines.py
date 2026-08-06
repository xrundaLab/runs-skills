#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = SKILL_ROOT / "references" / "whole-course-baseline-registry.json"
ASSEMBLER = SKILL_ROOT / "scripts" / "assembler" / "assemble_whole_course.py"
STATIC_CHECKER = SKILL_ROOT / "scripts" / "validators" / "check_whole_course_static.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, *map(str, args)], text=True, capture_output=True, check=False)


def normalize_source_paths(payload: dict[str, object]) -> dict[str, object]:
    source = payload.get("source")
    if isinstance(source, dict):
        source["effective_content"] = "__FIXTURE_EFFECTIVE_PATH__"
        source["whole_course_oneshot"] = "__SKILL_ROOT__/templates/oneshots/02_整课JSON_完整外层OneShot.md"
    return payload


class WholeCourseBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))

    def test_registry_and_receipts_pin_every_baseline_and_asset_sha(self) -> None:
        baselines = self.registry.get("baselines")
        self.assertIsInstance(baselines, list)
        self.assertEqual({item["visualMode"] for item in baselines}, {"text_only", "visual_enhanced"})
        demo_names = {
            "course_intro": "course_intro_demo.html",
            "scene_intro": "scene_intro_demo.html",
            "knowledge": "knowledge_demo.html",
            "case_analysis": "case_analysis_demo.html",
            "post_class_task": "post_class_task_demo.html",
            "course_summary": "course_summary_demo.html",
        }
        for baseline in baselines:
            effective = SKILL_ROOT / baseline["effectiveContent"]["path"]
            expected = SKILL_ROOT / baseline["expectedWholeCourse"]["path"]
            receipt = json.loads((SKILL_ROOT / baseline["receipt"]).read_text(encoding="utf-8"))
            self.assertEqual(sha256(effective), baseline["effectiveContent"]["sha256"])
            self.assertEqual(sha256(expected), baseline["expectedWholeCourse"]["sha256"])
            self.assertEqual(receipt["baselineId"], baseline["baselineId"])
            self.assertEqual(receipt["visualMode"], baseline["visualMode"])
            self.assertEqual(receipt["effectiveContentSha256"], sha256(effective))
            self.assertEqual(receipt["expectedWholeCourseSha256"], sha256(expected))
            self.assertTrue(baseline["replaceable"])
            self.assertIsNone(baseline["supersededBy"])
            for number, digest in baseline["oneshotAssets"].items():
                matches = list((SKILL_ROOT / "templates" / "oneshots").glob(f"{number}_*.md"))
                self.assertEqual(len(matches), 1, number)
                self.assertEqual(sha256(matches[0]), digest, matches[0].name)
            for name, digest in baseline["demoAssets"].items():
                path = SKILL_ROOT / "templates" / "demos" / "visual_enhanced" / demo_names[name]
                self.assertEqual(sha256(path), digest, path.name)

    def test_both_modes_reassemble_to_registered_expected_json_and_static_pass(self) -> None:
        for baseline in self.registry["baselines"]:
            with self.subTest(baseline=baseline["baselineId"]), tempfile.TemporaryDirectory() as temp_dir:
                effective = SKILL_ROOT / baseline["effectiveContent"]["path"]
                expected = json.loads((SKILL_ROOT / baseline["expectedWholeCourse"]["path"]).read_text(encoding="utf-8"))
                output = Path(temp_dir) / "whole_course.json"
                assembled = run(
                    ASSEMBLER,
                    "--lesson-id", "lesson022",
                    "--effective-content", effective,
                    "--output", output,
                )
                self.assertEqual(assembled.returncode, 0, assembled.stdout + assembled.stderr)
                actual = normalize_source_paths(json.loads(output.read_text(encoding="utf-8")))
                self.assertEqual(actual, expected)
                checked = run(
                    STATIC_CHECKER,
                    "--s6-contract",
                    "--lesson-id", "lesson022",
                    "--effective-content", effective,
                    "--whole-course", output,
                )
                self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
                self.assertIn("IMPORT_READY_STATIC", checked.stdout)

    def test_manual_reference_is_not_a_registered_baseline(self) -> None:
        registered = {item["baselineId"] for item in self.registry["baselines"]}
        references = self.registry.get("manualReferences")
        self.assertIsInstance(references, list)
        self.assertNotIn("lesson012-user-supplied-json", registered)
        self.assertEqual(references[0]["status"], "manual_reference")
        self.assertFalse(references[0]["registeredAsBaseline"])


if __name__ == "__main__":
    unittest.main()
