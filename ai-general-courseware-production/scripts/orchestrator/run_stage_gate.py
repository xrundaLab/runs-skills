#!/usr/bin/env python3
"""Run registered R36 stage commands with hash-bound Gate receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


CONTRACT = "RunS_V3.5.0-S1-S6-R36-20260731"
SCRIPT_ROOT = Path(__file__).resolve().parents[1]
VALIDATORS = SCRIPT_ROOT / "validators"
GENERATORS = SCRIPT_ROOT / "generators"
ASSEMBLER = SCRIPT_ROOT / "assembler" / "assemble_whole_course.py"
STATIC_CHECKER = VALIDATORS / "check_whole_course_static.py"
PREVIOUS_STAGE = {"S3": "S2", "S4": "S3", "S5": "S4", "S6": "S5"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact(role: str, path: Path) -> dict[str, str]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"INPUT_FILE_MISSING:{role}:{resolved}")
    return {"role": role, "path": str(resolved), "sha256": sha256(resolved)}


def receipt_path(receipt_dir: Path, stage: str) -> Path:
    return receipt_dir / f"{stage.lower()}_gate_receipt.json"


def attempt_receipt_path(receipt_dir: Path, stage: str) -> tuple[int, Path]:
    """Allocate an immutable receipt for each invocation of one stage."""
    receipt_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{stage.lower()}_gate_receipt_attempt-"
    attempts = []
    for path in receipt_dir.glob(f"{prefix}*.json"):
        suffix = path.stem.removeprefix(prefix)
        if suffix.isdigit():
            attempts.append(int(suffix))
    attempt = max(attempts, default=0) + 1
    return attempt, receipt_dir / f"{prefix}{attempt:03d}.json"


def write_receipt(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def find_input(receipt: dict[str, Any], role: str) -> dict[str, str] | None:
    for item in receipt.get("inputs") or []:
        if isinstance(item, dict) and item.get("role") == role:
            return item
    return None


def verify_prior(
    stage: str,
    lesson_id: str,
    visual_mode: str,
    prior_path: Path | None,
    upstream: Path,
    working_plan: Path | None,
) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    expected_stage = PREVIOUS_STAGE.get(stage)
    if expected_stage is None:
        return None, None
    if prior_path is None:
        raise ValueError("PRIOR_RECEIPT_MISSING")
    resolved = prior_path.resolve()
    if not resolved.is_file():
        raise ValueError("PRIOR_RECEIPT_MISSING")
    try:
        prior = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ValueError("PRIOR_RECEIPT_INVALID")
    if prior.get("contract") != CONTRACT:
        raise ValueError("PRIOR_RECEIPT_CONTRACT_MISMATCH")
    if prior.get("lesson_id") != lesson_id:
        raise ValueError("PRIOR_RECEIPT_LESSON_MISMATCH")
    if prior.get("stage") != expected_stage:
        raise ValueError("PRIOR_RECEIPT_STAGE_MISMATCH")
    prior_visual_mode = prior.get("visualMode")
    legacy_visual_s4 = (
        stage == "S5"
        and visual_mode == "visual_enhanced"
        and "visualMode" not in prior
    )
    if prior_visual_mode != visual_mode and not legacy_visual_s4:
        raise ValueError("VISUAL_MODE_DRIFT")
    if prior.get("status") != "PASS":
        raise ValueError("PRIOR_GATE_NOT_PASS")
    prior_output = prior.get("output")
    if not isinstance(prior_output, dict):
        raise ValueError("PRIOR_OUTPUT_MISSING")
    resolved_upstream = upstream.resolve()
    if prior_output.get("path") != str(resolved_upstream):
        raise ValueError("PRIOR_OUTPUT_PATH_MISMATCH")
    if prior_output.get("sha256") != sha256(resolved_upstream):
        raise ValueError("PRIOR_OUTPUT_HASH_MISMATCH")
    if stage == "S4" and working_plan is not None:
        recorded_working = find_input(prior, "working_plan")
        if not recorded_working:
            raise ValueError("PRIOR_WORKING_PLAN_MISSING")
        resolved_working = working_plan.resolve()
        if recorded_working.get("path") != str(resolved_working):
            raise ValueError("PRIOR_WORKING_PLAN_PATH_MISMATCH")
        if recorded_working.get("sha256") != sha256(resolved_working):
            raise ValueError("PRIOR_WORKING_PLAN_HASH_MISMATCH")
    return prior, {"path": str(resolved), "sha256": sha256(resolved)}


def verify_visual_receipt(
    lesson_id: str,
    visual_manifest: Path,
    visual_receipt: Path,
) -> dict[str, str]:
    resolved_receipt = visual_receipt.resolve()
    if not resolved_receipt.is_file():
        raise ValueError("VISUAL_RECEIPT_MISSING")
    try:
        receipt = json.loads(resolved_receipt.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ValueError("VISUAL_RECEIPT_INVALID")
    if receipt.get("contract") != CONTRACT:
        raise ValueError("VISUAL_RECEIPT_CONTRACT_MISMATCH")
    if (receipt.get("lessonId") or receipt.get("lesson_id")) != lesson_id:
        raise ValueError("VISUAL_RECEIPT_LESSON_MISMATCH")
    if receipt.get("visualMode") != "visual_enhanced":
        raise ValueError("VISUAL_MODE_DRIFT")
    if receipt.get("ownerStage") != "S1" or receipt.get("phase") != "resolved":
        raise ValueError("VISUAL_RECEIPT_PHASE_MISMATCH")
    if receipt.get("status") != "PASS":
        raise ValueError("VISUAL_GATE_NOT_PASS")
    output = receipt.get("output")
    if not isinstance(output, dict):
        raise ValueError("VISUAL_RECEIPT_OUTPUT_MISSING")
    resolved_manifest = visual_manifest.resolve()
    if output.get("path") != str(resolved_manifest):
        raise ValueError("VISUAL_RECEIPT_OUTPUT_PATH_MISMATCH")
    if output.get("sha256") != sha256(resolved_manifest):
        raise ValueError("VISUAL_RECEIPT_OUTPUT_HASH_MISMATCH")
    return {"path": str(resolved_receipt), "sha256": sha256(resolved_receipt)}


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=False)


def execute_commands(commands: list[list[str]]) -> tuple[int, list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    for command in commands:
        completed = run_command(command)
        results.append(
            {
                "command": command,
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )
        if completed.returncode != 0:
            return completed.returncode, results
    return 0, results


def extract_command_issues(result: dict[str, Any]) -> list[dict[str, str]]:
    """Preserve machine-readable blocker codes from a failed stage command."""
    stdout = str(result.get("stdout") or "")
    stderr = str(result.get("stderr") or "")
    extracted: list[dict[str, str]] = []
    seen: set[str] = set()

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        issue_groups = [payload.get("issues") or []]
        issue_groups.extend(
            report.get("issues") or []
            for report in payload.get("reports") or []
            if isinstance(report, dict)
        )
        for group in issue_groups:
            for item in group:
                if not isinstance(item, dict):
                    continue
                code = str(item.get("issue_type") or item.get("code") or "").strip()
                if code and code not in seen:
                    extracted.append(
                        {"issue_type": code, "message": str(item.get("message") or code)}
                    )
                    seen.add(code)

    for code in re.findall(r"\bBLOCKED:([A-Z0-9_:-]+)", f"{stderr}\n{stdout}"):
        if code not in seen:
            extracted.append({"issue_type": code, "message": f"BLOCKED:{code}"})
            seen.add(code)

    if not extracted:
        excerpt = (stderr or stdout).strip().splitlines()
        message = excerpt[-1] if excerpt else "STAGE_COMMAND_BLOCKED"
        extracted.append(
            {"issue_type": "STAGE_COMMAND_BLOCKED", "message": message}
        )
    return extracted


def required_path(value: Path | None, role: str) -> Path:
    if value is None:
        raise ValueError(f"ARGUMENT_MISSING:{role}")
    resolved = value.resolve()
    if not resolved.is_file():
        raise ValueError(f"INPUT_FILE_MISSING:{role}")
    return resolved


def temp_output(final_output: Path) -> Path:
    final_output.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        prefix=f".{final_output.name}.",
        suffix=".tmp",
        dir=final_output.parent,
        delete=False,
    )
    handle.close()
    return Path(handle.name)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="按 R36 Gate 回执串行执行 S2-S6；上一阶段未 PASS 时禁止继续"
    )
    parser.add_argument("--stage", required=True, choices=("S2", "S3", "S4", "S5", "S6"))
    parser.add_argument("--lesson-id", required=True)
    parser.add_argument("--visual-mode")
    parser.add_argument("--receipt-dir", required=True, type=Path)
    parser.add_argument("--prior-receipt", type=Path)
    parser.add_argument("--working-plan", type=Path)
    parser.add_argument("--question-processed", type=Path)
    parser.add_argument("--page-plan", type=Path)
    parser.add_argument("--visual-manifest", type=Path)
    parser.add_argument("--visual-receipt", type=Path)
    parser.add_argument("--effective-content", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    stage = args.stage
    resolved_receipt_dir = args.receipt_dir.resolve()
    receipt_file = receipt_path(resolved_receipt_dir, stage)
    attempt, immutable_receipt_file = attempt_receipt_path(resolved_receipt_dir, stage)
    inputs: list[dict[str, str]] = []
    commands: list[list[str]] = []
    prior_record: dict[str, str] | None = None
    final_output: Path | None = None
    temporary: Path | None = None
    issues: list[dict[str, str]] = []
    command_results: list[dict[str, Any]] = []
    exit_code: int | None = None

    try:
        if args.visual_mode is None:
            raise ValueError("VISUAL_MODE_NOT_SELECTED")
        if args.visual_mode not in {"text_only", "visual_enhanced"}:
            raise ValueError("VISUAL_MODE_INVALID")
        working = required_path(args.working_plan, "working_plan") if stage in {"S2", "S3", "S4"} else None
        question = required_path(args.question_processed, "question_processed") if stage in {"S3", "S4"} else None
        page_plan = required_path(args.page_plan, "page_plan") if stage == "S5" else None
        effective = required_path(args.effective_content, "effective_content") if stage == "S6" else None
        upstream = {
            "S3": working,
            "S4": question,
            "S5": page_plan,
            "S6": effective,
        }.get(stage)
        if upstream is not None:
            _, prior_record = verify_prior(
                stage,
                args.lesson_id,
                args.visual_mode,
                args.prior_receipt,
                upstream,
                working,
            )

        if stage == "S2":
            inputs = [artifact("working_plan", working)]
            commands = [[sys.executable, str(VALIDATORS / "validate_v35_page_plan_question_boundaries.py"), "--working-plan-contract", str(working)]]
            final_output = working
        elif stage == "S3":
            inputs = [artifact("working_plan", working)]
            commands = [[sys.executable, str(VALIDATORS / "validate_question_component_json.py"), "--stage3-contract", str(question)]]
            final_output = question
        elif stage == "S4":
            if args.output is None:
                raise ValueError("ARGUMENT_MISSING:output")
            inputs = [artifact("working_plan", working), artifact("question_processed", question)]
            final_output = args.output.resolve()
            temporary = temp_output(final_output)
            commands = [
                [sys.executable, str(GENERATORS / "build_final_page_plan.py"), "--working-plan", str(working), "--question-processed", str(question), "--output", str(temporary)],
                [sys.executable, str(VALIDATORS / "validate_v35_page_plan_question_boundaries.py"), "--effective-plan-contract", "--working-plan", str(working), "--question-processed", str(question), str(temporary)],
            ]
        elif stage == "S5":
            if args.output is None:
                raise ValueError("ARGUMENT_MISSING:output")
            inputs = [artifact("page_plan", page_plan)]
            visual_manifest: Path | None = None
            visual_receipt_record: dict[str, str] | None = None
            if args.visual_mode == "visual_enhanced":
                visual_manifest = required_path(args.visual_manifest, "visual_manifest")
                visual_receipt = required_path(args.visual_receipt, "visual_receipt")
                visual_receipt_record = verify_visual_receipt(
                    args.lesson_id, visual_manifest, visual_receipt
                )
                inputs.extend(
                    [
                        artifact("visual_manifest", visual_manifest),
                        artifact("visual_receipt", visual_receipt),
                    ]
                )
            elif args.visual_manifest is not None or args.visual_receipt is not None:
                raise ValueError("VISUAL_INPUT_FORBIDDEN_IN_TEXT_ONLY")
            final_output = args.output.resolve()
            temporary = temp_output(final_output)
            generator_command = [
                sys.executable,
                str(GENERATORS / "build_effective_content.py"),
                "--lesson-id",
                args.lesson_id,
                "--visual-mode",
                args.visual_mode,
                "--page-plan",
                str(page_plan),
            ]
            validator_command = [
                sys.executable,
                str(VALIDATORS / "validate_v35_effective_content.py"),
                "--page-plan",
                str(page_plan),
                "--visual-mode",
                args.visual_mode,
            ]
            if visual_manifest is not None:
                generator_command.extend(["--visual-manifest", str(visual_manifest)])
                validator_command.extend(["--visual-manifest", str(visual_manifest)])
            generator_command.extend(["--output", str(temporary)])
            validator_command.append(str(temporary))
            commands = [generator_command, validator_command]
        else:
            if args.output is None:
                raise ValueError("ARGUMENT_MISSING:output")
            inputs = [artifact("effective_content", effective)]
            final_output = args.output.resolve()
            temporary = temp_output(final_output)
            commands = [
                [sys.executable, str(ASSEMBLER), "--lesson-id", args.lesson_id, "--effective-content", str(effective), "--output", str(temporary)],
                [sys.executable, str(STATIC_CHECKER), "--s6-contract", "--formal-stage6", "--lesson-id", args.lesson_id, "--effective-content", str(effective), "--whole-course", str(temporary)],
            ]

        exit_code, command_results = execute_commands(commands)
        if exit_code != 0:
            issues = extract_command_issues(command_results[-1])
        elif temporary is not None and final_output is not None:
            os.replace(temporary, final_output)
            temporary = None
    except (OSError, ValueError) as exc:
        code = str(exc)
        issues = [{"issue_type": code, "message": code}]
        exit_code = 1
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()

    status = "PASS" if not issues and exit_code == 0 else "BLOCKED"
    output_record = (
        artifact(
            {
                "S2": "working_plan",
                "S3": "question_processed",
                "S4": "page_plan",
                "S5": "effective_content",
                "S6": "whole_course",
            }[stage],
            final_output,
        )
        if status == "PASS" and final_output is not None
        else None
    )
    payload = {
        "contract": CONTRACT,
        "lesson_id": args.lesson_id,
        "visualMode": args.visual_mode,
        "stage": stage,
        "attempt": attempt,
        "status": status,
        "commands": commands,
        "exit_code": exit_code,
        "inputs": inputs,
        "output": output_record,
        "issues": issues,
        "prior_receipt": prior_record,
        "command_results": command_results,
        "downstream_authorized": status == "PASS" and stage != "S6",
        "static_result": "IMPORT_READY_STATIC" if status == "PASS" and stage == "S6" else None,
    }
    write_receipt(immutable_receipt_file, payload)
    write_receipt(receipt_file, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
