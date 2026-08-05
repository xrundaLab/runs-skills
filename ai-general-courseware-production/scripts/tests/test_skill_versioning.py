#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]
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


if __name__ == "__main__":
    unittest.main()
