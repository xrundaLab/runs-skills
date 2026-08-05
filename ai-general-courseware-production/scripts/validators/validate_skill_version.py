#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import hashlib
import re
import subprocess
import sys
from pathlib import Path


VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)-r(\d+)$")
REGISTRY_RELATIVE_PATH = Path("references/version-registry.json")
SKILL_NAME = "ai-general-courseware-production"
PAYLOAD_EXCLUDES = {REGISTRY_RELATIVE_PATH}


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


def payload_sha256(skill_root: Path) -> str:
    digest = hashlib.sha256()
    files = sorted(path for path in skill_root.rglob("*") if path.is_file())
    for path in files:
        relative = path.relative_to(skill_root)
        if (
            relative in PAYLOAD_EXCLUDES
            or "__pycache__" in relative.parts
            or path.suffix == ".pyc"
        ):
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def git_context(skill_root: Path) -> tuple[Path, Path]:
    result = subprocess.run(
        ["git", "-C", str(skill_root), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or "Skill root is not in a Git repository")
    repository = Path(result.stdout.strip()).resolve()
    try:
        relative = skill_root.resolve().relative_to(repository)
    except ValueError as error:
        raise ValueError("Skill root is outside its Git repository") from error
    return repository, relative


def git_text(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or "Git ref cannot be resolved")
    return result.stdout


def read_version_at_ref(skill_root: Path, ref: str) -> str:
    repository, relative = git_context(skill_root)
    path = (relative / "VERSION").as_posix()
    return git_text(repository, "show", f"{ref}:{path}").strip()


def payload_sha256_at_ref(skill_root: Path, ref: str) -> str:
    repository, skill_relative = git_context(skill_root)
    listing = git_text(
        repository,
        "ls-tree",
        "-r",
        "--name-only",
        ref,
        "--",
        skill_relative.as_posix(),
    )
    files = sorted(line for line in listing.splitlines() if line)
    if not files:
        raise ValueError(f"Skill payload is missing at ref {ref}")

    digest = hashlib.sha256()
    for repository_path in files:
        relative = Path(repository_path).relative_to(skill_relative)
        if (
            relative in PAYLOAD_EXCLUDES
            or "__pycache__" in relative.parts
            or relative.suffix == ".pyc"
        ):
            continue
        result = subprocess.run(
            ["git", "-C", str(repository), "show", f"{ref}:{repository_path}"],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise ValueError(
                result.stderr.decode("utf-8", errors="replace").strip()
                or f"cannot read {repository_path} at {ref}"
            )
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(result.stdout)
        digest.update(b"\0")
    return digest.hexdigest()


def issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "severity": "BLOCKER", "message": message}


def validate_registry(registry: dict[str, object]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    entries = registry.get("versions", [])
    if not isinstance(entries, list):
        return [issue("SKILL_VERSION_REGISTRY_INVALID", "versions must be a list")]

    seen: set[str] = set()
    occupied: list[str] = []
    prior_version: str | None = None
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

        if prior_version is not None and compare_versions(version, prior_version) <= 0:
            issues.append(
                issue(
                    "SKILL_VERSION_ORDER_INVALID",
                    f"version {version} must follow {prior_version} in ascending order",
                )
            )
        prior_version = version

        if raw_entry.get("traceabilityLevel") == "source_exact":
            expected_ref = f"skill-{SKILL_NAME}-v{version}"
            if raw_entry.get("sourceRef") != expected_ref:
                issues.append(
                    issue(
                        "SKILL_VERSION_SOURCE_REF_MISSING",
                        f"source_exact version {version} requires {expected_ref}",
                    )
                )
            payload = raw_entry.get("payloadSha256")
            if not isinstance(payload, str) or re.fullmatch(r"[0-9a-f]{64}", payload) is None:
                issues.append(
                    issue(
                        "SKILL_VERSION_PAYLOAD_MISSING",
                        f"source_exact version {version} requires a lowercase SHA-256",
                    )
                )
            evidence = raw_entry.get("validationEvidence")
            if not isinstance(evidence, list) or not evidence:
                issues.append(
                    issue(
                        "SKILL_VERSION_EVIDENCE_MISSING",
                        f"source_exact version {version} requires validation evidence",
                    )
                )

    ranges = registry.get("reservedLegacyRanges", [])
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


def validate_current(
    current: str,
    *,
    registry_current: str,
) -> list[dict[str, str]]:
    if current != registry_current:
        return [
            issue(
                "SKILL_VERSION_REGISTRY_MISMATCH",
                f"VERSION {current} does not match registry {registry_current}",
            )
        ]
    return []


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


def validate_skill_root(skill_root: Path) -> tuple[str | None, str, list[dict[str, str]]]:
    payload = payload_sha256(skill_root)
    version_path = skill_root / "VERSION"
    registry_path = skill_root / REGISTRY_RELATIVE_PATH
    issues: list[dict[str, str]] = []

    if not version_path.is_file():
        return None, payload, [issue("SKILL_VERSION_FILE_MISSING", str(version_path))]
    current = version_path.read_text(encoding="utf-8").strip()
    try:
        parse_version(current)
    except ValueError as error:
        issues.append(issue("SKILL_VERSION_FORMAT_INVALID", str(error)))

    if not registry_path.is_file():
        issues.append(issue("SKILL_VERSION_REGISTRY_MISSING", str(registry_path)))
        return current, payload, issues

    try:
        registry = load_registry(registry_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        issues.append(issue("SKILL_VERSION_REGISTRY_INVALID", str(error)))
        return current, payload, issues

    issues.extend(validate_registry(registry))
    registry_current = registry.get("currentVersion")
    if not isinstance(registry_current, str):
        issues.append(
            issue("SKILL_VERSION_REGISTRY_INVALID", "currentVersion must be a string")
        )
    else:
        issues.extend(validate_current(current, registry_current=registry_current))

    entries = registry.get("versions", [])
    current_entry = next(
        (
            entry
            for entry in entries
            if isinstance(entry, dict) and entry.get("version") == current
        ),
        None,
    ) if isinstance(entries, list) else None
    if current_entry is None:
        issues.append(
            issue("SKILL_VERSION_CURRENT_ENTRY_MISSING", f"no registry entry for {current}")
        )
    elif current_entry.get("payloadSha256") != payload:
        issues.append(
            issue(
                "SKILL_VERSION_PAYLOAD_MISMATCH",
                f"registry payload does not match Skill payload for {current}",
            )
        )

    return current, payload, issues


def validate_source_refs(
    skill_root: Path,
    registry: dict[str, object],
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    entries = registry.get("versions", [])
    if not isinstance(entries, list):
        return issues
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("traceabilityLevel") != "source_exact":
            continue
        version = entry.get("version")
        source_ref = entry.get("sourceRef")
        expected_payload = entry.get("payloadSha256")
        if not isinstance(version, str) or not isinstance(source_ref, str):
            continue
        try:
            actual_payload = payload_sha256_at_ref(skill_root, source_ref)
        except ValueError as error:
            issues.append(
                issue(
                    "SKILL_VERSION_SOURCE_REF_UNRESOLVED",
                    f"cannot resolve {source_ref} for {version}: {error}",
                )
            )
            continue
        if actual_payload != expected_payload:
            issues.append(
                issue(
                    "SKILL_VERSION_SOURCE_REF_MISMATCH",
                    f"payload at {source_ref} does not match registry for {version}",
                )
            )
    return issues


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate independent Skill versions")
    parser.add_argument("--skill-root", type=Path, required=True)
    parser.add_argument("--base-ref")
    parser.add_argument("--mode", choices=("local", "pr", "release"), default="local")
    parser.add_argument("--print-payload-sha", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    skill_root = args.skill_root.resolve()
    if args.print_payload_sha:
        print(payload_sha256(skill_root))
        return 0

    current, payload, issues = validate_skill_root(skill_root)
    base_version: str | None = None
    if args.mode == "pr":
        if not args.base_ref:
            issues.append(
                issue("SKILL_VERSION_BASE_REF_MISSING", "pr mode requires --base-ref")
            )
        elif current is not None:
            try:
                base_version = read_version_at_ref(skill_root, args.base_ref)
            except ValueError as error:
                issues.append(issue("SKILL_VERSION_BASE_REF_INVALID", str(error)))
            else:
                issues.extend(validate_versions(current, base_version))

    if args.mode == "release":
        registry_path = skill_root / REGISTRY_RELATIVE_PATH
        if registry_path.is_file():
            try:
                registry = load_registry(registry_path)
            except (OSError, ValueError, json.JSONDecodeError):
                pass
            else:
                issues.extend(validate_source_refs(skill_root, registry))
    if issues:
        for current_issue in issues:
            print(
                f"{current_issue['severity']} {current_issue['code']}: "
                f"{current_issue['message']}"
            )
        print("SKILL_VERSION_CHECK=BLOCKED")
        return 1

    details = (
        "SKILL_VERSION_CHECK=PASS "
        f"version={current} payloadSha256={payload} mode={args.mode}"
    )
    if base_version is not None:
        details += f" baseVersion={base_version}"
    print(details)
    return 0


if __name__ == "__main__":
    sys.exit(main())
