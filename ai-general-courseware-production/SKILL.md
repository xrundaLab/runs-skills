---
name: ai-general-courseware-production
description: 将 AI 通识课教师版教案按冻结输入处理为 RunS 网页课件整课 JSON，或独立执行和审计 S1-S6 任一阶段。适用于需要页面规划、题目组件 JSON、有效内容 JSON、整课 JSON 静态装配与 Gate 核验的课程生产；支持本地或固定 GitHub commit 输入，不自动导入、创建、渲染或发布。
---

# AI 通识课网页课件生成

Use this release bundle as a self-contained R36 contract. It supports a read-only preflight, one unlocked stage, a complete S1-S6 local run, an existing-artifact audit, and batch-manifest preparation.

## Collect and freeze inputs

Read [references/input-manifest.md](references/input-manifest.md) before S1. Require one `runs_batch_manifest.yaml`, a fresh local output directory, one teacher `final.md` and six verbatim course-info fields for every lesson.

- Use `source_mode: local` for absolute local source paths.
- Use `source_mode: github` only with a user-authorized `repo`, immutable full commit SHA, manifest path, and repository-relative source paths.
- Freeze all resolved GitHub files locally before S1. Never use a branch, tag, moving URL, or refetch GitHub after S1.
- Use a student file only for the S2 structural cross-check.

Report `BLOCKED_INPUT` as one grouped missing-input list. Do not guess a source file, course-info row, output directory, page type, or component type.

## Run the six-stage chain

Read [references/s1-s6-contract.md](references/s1-s6-contract.md) before generating or validating a stage. It is the sole R36 production contract in this bundle. Use [references/schemas/stage-artifact-map.json](references/schemas/stage-artifact-map.json) only as a quick field map, never as a weaker replacement.

| Stage | Sole input | Sole output |
| --- | --- | --- |
| S1 | Teacher `final.md` and six course-info fields | source manifest, preprocessed Markdown, comparison |
| S2 | Frozen S1 preprocessed Markdown | working plan, student structural check |
| S3 | Frozen S2 working plan | question-processed plan |
| S4 | Frozen S2 working plan and approved S3 plan | final page plan |
| S5 | Frozen S4 final page plan | `effective_content_full.json` |
| S6 | Passed S5 effective-content JSON | whole-course JSON and static result |

Run only the requested and unlocked stage. At any `BLOCKED`, stop that lesson; for a batch, stop the entire batch and wait. Do not repair, skip, or advance another lesson without a new instruction.

## Use bundled deterministic tools

From this skill directory, use only these registered tools:

```bash
# S2
python3 scripts/validators/validate_v35_page_plan_question_boundaries.py \
  --working-plan-contract <S2/page_plan_working_full.md>

# S3
python3 scripts/validators/validate_question_component_json.py \
  --stage3-contract <S3/question_processed_full.md>

# S4
python3 scripts/validators/validate_v35_page_plan_question_boundaries.py \
  --effective-plan-contract --working-plan <S2/page_plan_working_full.md> \
  --question-processed <S3/question_processed_full.md> <S4/page_plan_full.md>

# S5
python3 scripts/validators/validate_v35_effective_content.py \
  --page-plan <S4/page_plan_full.md> <S5/effective_content_full.json>

# S6
python3 scripts/assembler/assemble_whole_course.py \
  --lesson-id <lesson_id> --effective-content <S5/effective_content_full.json> \
  --output <S6/whole_course.json>
python3 scripts/validators/check_whole_course_static.py \
  --s6-contract --formal-stage6 --lesson-id <lesson_id> \
  --effective-content <S5/effective_content_full.json> \
  --whole-course <S6/whole_course.json>
```

Use only the bundled OneShots and Demos. Do not hand-build whole-course JSON, replace a bundled template with a local historical file, or downgrade non-interactive prompts to bare HTML.

## Authorization boundary

This skill creates only local, auditable artifacts. `IMPORT_READY_STATIC` is not import, render, interaction testing, acceptance, release, or publication. Use a separately authorized RunS client skill for any live operation.

## Finish with a receipt

Report the release version, status, frozen inputs, artifact paths, SHA-256 values where required, commands, blockers, and unexecuted downstream authorization boundaries.
