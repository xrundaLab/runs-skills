#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = SKILL_ROOT.parents[1]
VALIDATORS = SKILL_ROOT / "scripts" / "validators"
VALIDATOR = VALIDATORS / "validate_skill_version.py"
sys.path.insert(0, str(VALIDATORS))

from validate_skill_version import (  # noqa: E402
    parse_version,
    payload_sha256,
    validate_current,
    validate_registry,
    validate_versions,
)


def issue_codes(report: list[dict[str, str]]) -> set[str]:
    return {issue["code"] for issue in report}


def registry_with_versions(*versions: str) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "skill": "ai-general-courseware-production",
        "currentVersion": versions[-1],
        "reservedLegacyRanges": [],
        "versions": [
            {
                "version": version,
                "status": "candidate",
                "traceabilityLevel": "source_exact",
                "sourceRef": (
                    "skill-ai-general-courseware-production-v" + version
                ),
            }
            for version in versions
        ],
    }


def registry_with_current(version: str) -> dict[str, object]:
    registry = registry_with_versions(version)
    registry["reservedLegacyRanges"] = [
        {
            "from": "0.2.1-r36",
            "to": "0.2.7-r36",
            "status": "legacy_audit_only",
            "reusable": False,
        }
    ]
    return registry


def source_exact_without_ref() -> dict[str, object]:
    registry = registry_with_versions("0.2.9-r36")
    entry = registry["versions"][0]  # type: ignore[index]
    del entry["sourceRef"]  # type: ignore[index]
    return registry


def run_cli(*args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), *map(str, args)],
        text=True,
        capture_output=True,
        check=False,
    )


def write_valid_skill_root(skill_root: Path) -> None:
    (skill_root / "references").mkdir(parents=True)
    (skill_root / "VERSION").write_text("0.2.9-r36\n", encoding="utf-8")
    (skill_root / "SKILL.md").write_text("# Test Skill\n", encoding="utf-8")
    payload = payload_sha256(skill_root)
    registry = registry_with_versions("0.2.9-r36")
    entry = registry["versions"][0]  # type: ignore[index]
    entry["payloadSha256"] = payload  # type: ignore[index]
    entry["validationEvidence"] = ["unit:test"]  # type: ignore[index]
    registry_path = skill_root / "references" / "version-registry.json"
    registry_path.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        text=True,
        capture_output=True,
        check=False,
    )


def initialize_repository(repo: Path, base_version: str) -> Path:
    skill_root = repo / "skills" / "ai-general-courseware-production"
    skill_root.mkdir(parents=True)
    (skill_root / "VERSION").write_text(base_version + "\n", encoding="utf-8")
    (skill_root / "SKILL.md").write_text("# Test Skill\n", encoding="utf-8")
    for args in (
        ("init", "-q"),
        ("config", "user.name", "Skill Version Test"),
        ("config", "user.email", "skill-version-test@example.invalid"),
        ("add", "."),
        ("commit", "-qm", "base"),
    ):
        result = git(repo, *args)
        if result.returncode != 0:
            raise AssertionError(result.stdout + result.stderr)
    return skill_root


class SkillVersionTests(unittest.TestCase):
    def test_startup_preflight_selects_mode_before_output_confirmation(self) -> None:
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        input_contract = (
            SKILL_ROOT / "references" / "input-manifest.md"
        ).read_text(encoding="utf-8")
        combined = skill_text + "\n" + input_contract

        self.assertIn("STARTUP_MODE_SELECTION_NEEDED", combined)
        self.assertIn("1. 配图增强模式（推荐）", combined)
        self.assertIn("2. 纯文字模式", combined)
        self.assertIn("回复数字 `1` 或 `2`", combined)
        self.assertIn("STARTUP_OUTPUT_CONFIRMATION_NEEDED", combined)
        self.assertIn("recommendedOutputRoot", combined)
        self.assertIn(
            "Do not recommend or confirm an output root in the same message as the mode selection",
            combined,
        )
        self.assertIn("must not report `BLOCKED_INPUT`", combined)
        self.assertIn("does not contain a section for the target lesson", combined)
        self.assertIn("recommend excluding it from that lesson", combined)
        self.assertIn("纯文字模式", combined)
        self.assertIn("配图增强模式", combined)
        self.assertIn(
            "Do not present `text_only` or `visual_enhanced` as user-facing choice labels",
            combined,
        )

    def test_canonical_registry_compacts_unpublished_local_iterations(self) -> None:
        registry_path = SKILL_ROOT / "references" / "version-registry.json"
        registry = json.loads(registry_path.read_text(encoding="utf-8"))

        formal_entries = {
            entry["version"]: entry
            for entry in registry["versions"]
        }
        local_versions = {
            f"0.2.{patch}-r36"
            for patch in range(13, 20)
        }
        self.assertTrue(local_versions.isdisjoint(formal_entries))
        self.assertTrue(
            local_versions.issubset(set(registry["localReservedVersions"]))
        )

        compact_range = next(
            item
            for item in registry["reservedLegacyRanges"]
            if item["from"] == "0.2.13-r36"
        )
        self.assertEqual(compact_range["to"], "0.2.19-r36")
        self.assertFalse(compact_range["reusable"])
        self.assertEqual(compact_range["rolledIntoVersion"], "0.2.20-r36")

        merged_candidate = formal_entries["0.2.20-r36"]
        self.assertEqual(
            merged_candidate["traceabilityLevel"],
            "merged_candidate",
        )
        self.assertNotIn("sourceRef", merged_candidate)
        self.assertNotIn("tag", merged_candidate)

        current = formal_entries[registry["currentVersion"]]
        self.assertEqual(registry["currentVersion"], "0.2.24-r36")
        self.assertEqual(current["traceabilityLevel"], "source_exact")

    def test_parse_version_accepts_current_contract(self) -> None:
        self.assertEqual(parse_version("0.2.9-r36"), (0, 2, 9, 36))

    def test_parse_version_rejects_missing_runs_track(self) -> None:
        with self.assertRaises(ValueError):
            parse_version("0.2.9")

    def test_registry_rejects_duplicate_version(self) -> None:
        report = validate_registry(
            registry_with_versions("0.2.9-r36", "0.2.9-r36")
        )
        self.assertIn("SKILL_VERSION_DUPLICATE", issue_codes(report))

    def test_registry_rejects_reserved_legacy_reuse(self) -> None:
        report = validate_registry(registry_with_current("0.2.7-r36"))
        self.assertIn("SKILL_VERSION_LEGACY_RANGE_REUSED", issue_codes(report))

    def test_current_must_be_greater_than_base(self) -> None:
        report = validate_versions("0.2.8-r36", "0.2.8-r36")
        self.assertIn("SKILL_VERSION_NOT_GREATER_THAN_BASE", issue_codes(report))

    def test_payload_hash_ignores_registry_but_includes_skill_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_root = Path(temp_dir)
            registry_path = skill_root / "references" / "version-registry.json"
            registry_path.parent.mkdir(parents=True)
            registry_path.write_text('{"currentVersion":"0.2.9-r36"}\n', encoding="utf-8")
            skill_file = skill_root / "SKILL.md"
            skill_file.write_text("first\n", encoding="utf-8")

            before = payload_sha256(skill_root)
            registry_path.write_text('{"currentVersion":"9.9.9-r99"}\n', encoding="utf-8")
            self.assertEqual(payload_sha256(skill_root), before)

            skill_file.write_text("second\n", encoding="utf-8")
            self.assertNotEqual(payload_sha256(skill_root), before)

    def test_source_exact_requires_namespaced_tag(self) -> None:
        report = validate_registry(source_exact_without_ref())
        self.assertIn("SKILL_VERSION_SOURCE_REF_MISSING", issue_codes(report))

    def test_current_version_matches_version_file(self) -> None:
        report = validate_current(
            "0.2.9-r36",
            registry_current="0.2.8-r36",
        )
        self.assertIn("SKILL_VERSION_REGISTRY_MISMATCH", issue_codes(report))

    def test_registry_rejects_descending_entries(self) -> None:
        report = validate_registry(
            registry_with_versions("0.2.9-r36", "0.2.8-r36")
        )
        self.assertIn("SKILL_VERSION_ORDER_INVALID", issue_codes(report))

    def test_source_exact_requires_payload_hash(self) -> None:
        report = validate_registry(registry_with_versions("0.2.9-r36"))
        self.assertIn("SKILL_VERSION_PAYLOAD_MISSING", issue_codes(report))

    def test_source_exact_requires_validation_evidence(self) -> None:
        registry = registry_with_versions("0.2.9-r36")
        entry = registry["versions"][0]  # type: ignore[index]
        entry["payloadSha256"] = "a" * 64  # type: ignore[index]
        report = validate_registry(registry)
        self.assertIn("SKILL_VERSION_EVIDENCE_MISSING", issue_codes(report))

    def test_merged_candidate_requires_merge_evidence_without_release_tag(self) -> None:
        registry = registry_with_versions("0.2.20-r36")
        entry = registry["versions"][0]  # type: ignore[index]
        entry["traceabilityLevel"] = "merged_candidate"  # type: ignore[index]
        entry["payloadSha256"] = "a" * 64  # type: ignore[index]
        entry["sourceRef"] = "skill-ai-general-courseware-production-v0.2.20-r36"  # type: ignore[index]
        report = validate_registry(registry)
        codes = issue_codes(report)
        self.assertIn("SKILL_VERSION_MERGE_COMMIT_MISSING", codes)
        self.assertIn("SKILL_VERSION_UNPUBLISHED_TAG_INVALID", codes)

    def test_cli_local_accepts_matching_registry_and_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_root = Path(temp_dir)
            write_valid_skill_root(skill_root)
            result = run_cli("--skill-root", skill_root, "--mode", "local")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SKILL_VERSION_CHECK=PASS", result.stdout)
        self.assertIn("version=0.2.9-r36", result.stdout)

    def test_cli_prints_payload_without_requiring_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_root = Path(temp_dir)
            (skill_root / "SKILL.md").write_text("# Test Skill\n", encoding="utf-8")
            expected = payload_sha256(skill_root)
            result = run_cli(
                "--skill-root",
                skill_root,
                "--print-payload-sha",
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), expected)

    def test_cli_pr_requires_current_version_greater_than_base_ref(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            skill_root = initialize_repository(repo, "0.2.9-r36")
            write_valid_skill_root(skill_root)
            result = run_cli(
                "--skill-root",
                skill_root,
                "--base-ref",
                "HEAD",
                "--mode",
                "pr",
            )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("SKILL_VERSION_NOT_GREATER_THAN_BASE", result.stdout)

    def test_cli_pr_accepts_version_greater_than_base_ref(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            skill_root = initialize_repository(repo, "0.2.8-r36")
            write_valid_skill_root(skill_root)
            result = run_cli(
                "--skill-root",
                skill_root,
                "--base-ref",
                "HEAD",
                "--mode",
                "pr",
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("baseVersion=0.2.8-r36", result.stdout)

    def test_cli_release_requires_resolvable_source_tag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            skill_root = initialize_repository(repo, "0.2.8-r36")
            write_valid_skill_root(skill_root)
            result = run_cli("--skill-root", skill_root, "--mode", "release")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("SKILL_VERSION_SOURCE_REF_UNRESOLVED", result.stdout)

    def test_cli_release_verifies_tag_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            skill_root = initialize_repository(repo, "0.2.8-r36")
            unicode_asset = skill_root / "templates" / "中文模板.md"
            unicode_asset.parent.mkdir(parents=True)
            unicode_asset.write_text("模板内容\n", encoding="utf-8")
            write_valid_skill_root(skill_root)
            for args in (
                ("add", "."),
                ("commit", "-qm", "candidate"),
                (
                    "tag",
                    "-a",
                    "skill-ai-general-courseware-production-v0.2.9-r36",
                    "-m",
                    "0.2.9-r36",
                ),
            ):
                git_result = git(repo, *args)
                self.assertEqual(
                    git_result.returncode,
                    0,
                    git_result.stdout + git_result.stderr,
                )
            result = run_cli("--skill-root", skill_root, "--mode", "release")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SKILL_VERSION_CHECK=PASS", result.stdout)

    def test_pr_workflow_runs_version_gate_for_skill_paths(self) -> None:
        workflow_path = (
            REPOSITORY_ROOT / ".github" / "workflows" /
            "validate-ai-courseware-skill.yml"
        )
        workflow = workflow_path.read_text(encoding="utf-8")
        for marker in (
            "skills/ai-general-courseware-production/**",
            "fetch-depth: 0",
            "validate_skill_version.py",
            "--base-ref origin/${{ github.base_ref }}",
            "--mode pr",
            "test_skill_versioning.py",
            "test_generation_gates.py",
        ):
            self.assertIn(marker, workflow)

    def test_sync_workflow_verifies_latest_public_skill_mirror(self) -> None:
        workflow_path = REPOSITORY_ROOT / ".github" / "workflows" / "sync-subtrees.yml"
        workflow = workflow_path.read_text(encoding="utf-8")
        self.assertEqual(workflow.count("git push target HEAD:main --force"), 1)
        for marker in (
            "git clone --depth 1 https://github.com/xrundaLab/runs-skills.git /tmp/runs-skills-verify",
            "/tmp/skills-work/ai-general-courseware-production/VERSION",
            "/tmp/runs-skills-verify/ai-general-courseware-production/VERSION",
            "/tmp/runs-skills-verify/ai-general-courseware-production/scripts/validators/validate_skill_version.py",
            "canonical_payload=",
            "public_payload=",
            'test "$canonical_payload" = "$public_payload"',
            "--mode local",
        ):
            self.assertIn(marker, workflow)
        self.assertNotIn("git push target --tags", workflow)


if __name__ == "__main__":
    unittest.main()
