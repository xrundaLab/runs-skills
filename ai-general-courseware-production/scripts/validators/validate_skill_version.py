#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path


VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)-r(\d+)$")
REGISTRY_RELATIVE_PATH = Path("references/version-registry.json")


def parse_version(value: str) -> tuple[int, int, int, int]:
    match = VERSION_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"invalid Skill version: {value!r}")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def compare_versions(left: str, right: str) -> int:
    left_parts = parse_version(left)
    right_parts = parse_version(right)
    return (left_parts > right_parts) - (left_parts < right_parts)


def load_registry(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("version registry root must be an object")
    return payload


def issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": "BLOCKER", "message": message}


def validate_registry(registry: dict[str, object]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    entries = registry.get("versions", [])
    if not isinstance(entries, list):
        return [issue("SKILL_VERSION_REGISTRY_INVALID", "versions must be a list")]

    seen: set[str] = set()
    occupied: list[str] = []
    for raw_entry in entries:
        if not isinstance(raw_entry, dict):
            issues.append(
                issue("SKILL_VERSION_REGISTRY_INVALID", "version entry must be an object")
            )
            continue
        version = raw_entry.get("version")
        if not isinstance(version, str):
            issues.append(
                issue("SKILL_VERSION_REGISTRY_INVALID", "version entry is missing version")
            )
            continue
        try:
            parse_version(version)
        except ValueError as error:
            issues.append(issue("SKILL_VERSION_FORMAT_INVALID", str(error)))
            continue
        if version in seen:
            issues.append(
                issue("SKILL_VERSION_DUPLICATE", f"version is reused: {version}")
            )
        seen.add(version)
        occupied.append(version)

    ranges = registry.get("reservedRanges", [])
    if isinstance(ranges, list):
        for raw_range in ranges:
            if not isinstance(raw_range, dict) or raw_range.get("reusable") is not False:
                continue
            start = raw_range.get("from")
            end = raw_range.get("to")
            if not isinstance(start, str) or not isinstance(end, str):
                continue
            try:
                start_parts = parse_version(start)
                end_parts = parse_version(end)
            except ValueError:
                continue
            for version in occupied:
                parts = parse_version(version)
                if start_parts <= parts <= end_parts:
                    issues.append(
                        issue(
                            "SKILL_VERSION_LEGACY_RANGE_REUSED",
                            f"version {version} is in reserved range {start}..{end}",
                        )
                    )

    return issues


def validate_versions(current: str, base: str | None) -> list[dict[str, str]]:
    try:
        parse_version(current)
        if base is None:
            return []
        if compare_versions(current, base) <= 0:
            return [
                issue(
                    "SKILL_VERSION_NOT_GREATER_THAN_BASE",
                    f"current version {current} must be greater than base {base}",
                )
            ]
    except ValueError as error:
        return [issue("SKILL_VERSION_FORMAT_INVALID", str(error))]
    return []


if __name__ == "__main__":
    raise SystemExit("CLI is added after payload identity tests define its contract")
