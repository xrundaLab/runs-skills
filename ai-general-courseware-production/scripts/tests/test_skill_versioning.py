#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[2]
VALIDATORS = SKILL_ROOT / "scripts" / "validators"
sys.path.insert(0, str(VALIDATORS))

from validate_skill_version import (  # noqa: E402
    parse_version,
    validate_registry,
    validate_versions,
)


def issue_codes(report: list[dict[str, str]]) -> set[str]:
    return {issue["code"] for issue in report}


def registry_with_versions(*versions: str) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "currentVersion": versions[-1],
        "reservedRanges": [],
        "versions": [
            {
                "version": version,
                "status": "candidate",
                "traceability": "source_exact",
                "sourceRef": (
                    "skill-ai-general-courseware-production-v" + version
                ),
            }
            for version in versions
        ],
    }


def registry_with_current(version: str) -> dict[str, object]:
    registry = registry_with_versions(version)
    registry["reservedRanges"] = [
        {
            "from": "0.2.1-r36",
            "to": "0.2.7-r36",
            "status": "legacy_audit_only",
            "reusable": False,
        }
    ]
    return registry


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


if __name__ == "__main__":
    unittest.main()
