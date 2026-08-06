#!/usr/bin/env python3
"""Run the S1-owned visual manifest lifecycle with immutable Gate receipts."""

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
GENERATORS = SCRIPT_ROOT / "generators"
VALIDATOR = SCRIPT_ROOT / "validators" / "validate_visual_asset_manifest.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact(role: str, path: Path) -> dict[str, str]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ValueError(f"INPUT_FILE_MISSING:{role}")
    return {"role": role, "path": str(resolved), "sha256": sha256(resolved)}


def attempt_receipt_path(receipt_dir: Path) -> tuple[int, Path]:
    receipt_dir.mkdir(parents=True, exist_ok=True)
    prefix = "visual_manifest_gate_receipt_attempt-"
    attempts: list[int] = []
    for path in receipt_dir.glob(f"{prefix}*.json"):
        suffix = path.stem.removeprefix(prefix)
        if suffix.isdigit():
            attempts.append(int(suffix))
    attempt = max(attempts, default=0) + 1
    return attempt, receipt_dir / f"{prefix}{attempt:03d}.json"


def write_receipt(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def required_file(value: Path | None, role: str) -> Path:
    if value is None:
        raise ValueError(f"ARGUMENT_MISSING:{role}")
    resolved = value.resolve()
    if not resolved.is_file():
        raise ValueError(f"INPUT_FILE_MISSING:{role}")
    return resolved


def extract_issues(stdout: str, stderr: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    seen: set[str] = set()
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        for item in payload.get("issues") or []:
            if isinstance(item, dict):
                code = str(item.get("issue_type") or item.get("code") or "")
                if code and code not in seen:
                    issues.append({"issue_type": code, "message": str(item.get("message") or code)})
                    seen.add(code)
    for code in re.findall(r"\bBLOCKED:([A-Z0-9_:-]+)", f"{stderr}\n{stdout}"):
        if code not in seen:
            issues.append({"issue_type": code, "message": f"BLOCKED:{code}"})
            seen.add(code)
    if not issues:
        message = (stderr or stdout).strip().splitlines()
        issues.append({"issue_type": "VISUAL_MANIFEST_COMMAND_BLOCKED", "message": message[-1] if message else "VISUAL_MANIFEST_COMMAND_BLOCKED"})
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Run initial/request/resolved visual manifest Gates")
    parser.add_argument("--phase", required=True, choices=("initial", "request", "resolved"))
    parser.add_argument("--lesson-id", required=True)
    parser.add_argument("--visual-mode")
    parser.add_argument("--teacher-final", type=Path)
    parser.add_argument("--teacher-visual-script", type=Path)
    parser.add_argument("--initial-manifest", type=Path)
    parser.add_argument("--request-manifest", type=Path)
    parser.add_argument("--page-plan", type=Path)
    parser.add_argument("--s4-receipt", type=Path)
    parser.add_argument("--external-return", type=Path)
    parser.add_argument("--placement-review", type=Path)
    parser.add_argument("--receipt-dir", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    receipt_dir = args.receipt_dir.resolve()
    attempt, immutable_receipt = attempt_receipt_path(receipt_dir)
    latest_receipt = receipt_dir / "visual_manifest_gate_receipt.json"
    inputs: list[dict[str, str]] = []
    outputs: list[dict[str, str]] = []
    commands: list[list[str]] = []
    command_results: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    exit_code = 1
    temporary: Path | None = None
    status = "BLOCKED"

    try:
        if args.visual_mode is None:
            raise ValueError("VISUAL_MODE_NOT_SELECTED")
        if args.visual_mode not in {"text_only", "visual_enhanced"}:
            raise ValueError("VISUAL_MODE_INVALID")
        if args.visual_mode == "text_only":
            if args.phase != "initial":
                raise ValueError("VISUAL_MODE_DRIFT")
            status = "SKIPPED_BY_VISUAL_MODE"
            exit_code = 0
        else:
            if args.output is None:
                raise ValueError("ARGUMENT_MISSING:output")
            final_output = args.output.resolve()
            if final_output.exists():
                raise ValueError("VISUAL_MANIFEST_SNAPSHOT_EXISTS")
            final_output.parent.mkdir(parents=True, exist_ok=True)
            handle = tempfile.NamedTemporaryFile(prefix=f".{final_output.name}.", suffix=".tmp", dir=final_output.parent, delete=False)
            handle.close()
            temporary = Path(handle.name)
            if args.phase == "initial":
                teacher = required_file(args.teacher_final, "teacher_final")
                script = required_file(args.teacher_visual_script, "teacher_visual_script")
                inputs = [artifact("teacher_final", teacher), artifact("teacher_visual_script", script)]
                generator = [sys.executable, str(GENERATORS / "build_visual_asset_manifest.py"), "--lesson-id", args.lesson_id, "--teacher-final", str(teacher), "--teacher-visual-script", str(script), "--output", str(temporary)]
            elif args.phase == "request":
                initial = required_file(args.initial_manifest, "initial_manifest")
                page_plan = required_file(args.page_plan, "page_plan")
                s4_receipt = required_file(args.s4_receipt, "s4_receipt")
                inputs = [artifact("initial_manifest", initial), artifact("page_plan", page_plan), artifact("s4_receipt", s4_receipt)]
                generator = [sys.executable, str(GENERATORS / "bind_visual_asset_manifest.py"), "--lesson-id", args.lesson_id, "--initial-manifest", str(initial), "--page-plan", str(page_plan), "--s4-receipt", str(s4_receipt), "--output", str(temporary)]
            else:
                request = required_file(args.request_manifest, "request_manifest")
                page_plan = required_file(args.page_plan, "page_plan")
                external = required_file(args.external_return, "external_return")
                inputs = [artifact("request_manifest", request), artifact("page_plan", page_plan), artifact("external_return", external)]
                generator = [sys.executable, str(GENERATORS / "finalize_visual_asset_manifest.py"), "--lesson-id", args.lesson_id, "--request-manifest", str(request), "--page-plan", str(page_plan), "--external-return", str(external), "--output", str(temporary)]
                if args.placement_review is not None:
                    placement_review = required_file(args.placement_review, "placement_review")
                    inputs.append(artifact("placement_review", placement_review))
                    generator.extend(["--placement-review", str(placement_review)])
            commands = [generator, [sys.executable, str(VALIDATOR), "--phase", args.phase, "--manifest", str(temporary)]]
            for command in commands:
                completed = subprocess.run(command, text=True, capture_output=True, check=False)
                result = {"command": command, "exit_code": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}
                command_results.append(result)
                if completed.returncode != 0:
                    issues = extract_issues(completed.stdout, completed.stderr)
                    exit_code = completed.returncode
                    break
            else:
                os.replace(temporary, final_output)
                temporary = None
                outputs = [artifact(f"visual_manifest_{args.phase}", final_output)]
                status = "PASS"
                exit_code = 0
    except (OSError, ValueError) as exc:
        code = str(exc)
        issues = [{"issue_type": code, "message": code}]
        exit_code = 1
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()

    payload = {
        "contract": CONTRACT,
        "lessonId": args.lesson_id,
        "lesson_id": args.lesson_id,
        "visualMode": args.visual_mode,
        "ownerStage": "S1",
        "phase": args.phase,
        "attempt": attempt,
        "status": status,
        "inputs": inputs,
        "outputs": outputs,
        "output": outputs[0] if outputs else None,
        "commands": commands,
        "commandResults": command_results,
        "exitCode": exit_code,
        "issues": issues,
        "downstreamAuthorized": status == "PASS",
    }
    write_receipt(immutable_receipt, payload)
    write_receipt(latest_receipt, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if exit_code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
