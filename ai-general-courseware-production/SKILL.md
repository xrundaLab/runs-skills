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
| S5 | Frozen S4 final page plan and a constrained candidate draft | `effective_content_full.json` |
| S6 | Passed S5 effective-content JSON | whole-course JSON and static result |

Run only the requested and unlocked stage. For S2-S6 serial execution, use the bundled Gate runner so the previous `PASS` receipt, artifact path, and SHA-256 are verified before the next command starts. At any `BLOCKED`, stop that lesson; for a batch, stop the entire batch and wait. Do not repair, skip, or advance another lesson without a new instruction.

## Use bundled deterministic tools

From this skill directory, use only these registered tools:

```bash
# Official serial Gate entry; repeat per authorized stage and pass the prior receipt.
python3 scripts/orchestrator/run_stage_gate.py --help

# S2
python3 scripts/validators/validate_v35_page_plan_question_boundaries.py \
  --working-plan-contract <S2/page_plan_working_full.md>

# S3
python3 scripts/validators/validate_question_component_json.py \
  --stage3-contract <S3/question_processed_full.md>

# S4
python3 scripts/generators/build_final_page_plan.py \
  --working-plan <S2/page_plan_working_full.md> \
  --question-processed <S3/question_processed_full.md> \
  --output <S4/page_plan_full.md>
python3 scripts/validators/validate_v35_page_plan_question_boundaries.py \
  --effective-plan-contract --working-plan <S2/page_plan_working_full.md> \
  --question-processed <S3/question_processed_full.md> <S4/page_plan_full.md>

# S5
python3 scripts/generators/build_effective_content.py \
  --lesson-id <lesson_id> --page-plan <S4/page_plan_full.md> \
  --draft <S5/effective_content_candidate.json> \
  --output <S5/effective_content_full.json>
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

# Post-generation DOM Gate; run only against an explicitly supplied generated HTML artifact.
python3 scripts/validators/validate_dynamic_html.py \
  --effective-content <S5/effective_content_full.json> \
  --page-no <PXX> --html <generated_page.html>
```

Standalone generators and validators are audit/debug tools. They do not create a stage receipt and do not authorize a downstream stage. The official sequence is one `run_stage_gate.py` call per stage, using the prior stage's receipt for S3-S6; see [references/generation-gate-design.md](references/generation-gate-design.md).

For knowledge and case pages, S5 replaces mechanical draft groups with deterministic content relationships only when the frozen text actually exposes comparison, process, list, example/role distribution, or judgment structure. S5 must freeze the executable design, including `alignmentPolicy`: left alignment and top alignment take priority; same-level content shares a left edge; peer comparisons share a top edge and width; asymmetry is allowed only for an explicit primary/supporting relationship. Same-block conflicting evidence and comma/semicolon-linked role clauses stay in one continuous linguistic flow; the latter use `role_distribution_inline` / `continuous_inline_highlights`, with exact-source emphasis applied in place. S6 copies the design into `designExecutionContract` and injects `visualHierarchyContract` plus `alignmentContract`; it must not infer a replacement layout. Source fidelity, semantic relationship, reading clarity, and typographic elegance take priority over decoration. Real comparisons, steps, and lists visibly express those relationships; decoration is optional, with no minimum quota. Random indentation, random widths, stagger-for-variety, generic card stacks, decorative clutter, and large near-black panels are invalid. The post-generation DOM Gate checks exact visible projection and punctuation-linked clause splitting; it does not authorize generation, import, rendering, or publication.

Comparison cards may remain side by side only when every peer is at most 80 Chinese characters and the combined peer copy is at most 150 characters; otherwise use a full-width vertical stack with one shared left edge. The page-wide highlight budget is at most three exact-source segments. The same semantic category uses one highlight style; a short highlight of at most 12 characters moves as a whole and must not leave a one- or two-character highlighted tail on a separate line.

Every bundled prompt, fixed Demo, and generated HTML uses **Android System WebView Chrome 68** as the untranspiled baseline, following the [H5 low-version WebView compatibility specification](https://github.com/xrundaLab/.github-private/wiki/H5%E4%BD%8E%E7%89%88%E6%9C%ACWebView%E5%85%BC%E5%AE%B9%E5%BC%80%E5%8F%91%E8%A7%84%E8%8C%83). Do not emit optional chaining, nullish coalescing, logical assignment, class fields/static blocks, numeric separators, unsupported DOM APIs, dynamic viewport units, CSS `min()` / `max()` / `clamp()`, Flex `gap`, logical spacing, `env()`, `backdrop-filter`, `text-wrap`, or modern color functions. Prefer `height:100%`, physical spacing properties, `width` plus `max-width`, guarded Observer APIs, and a visible static first screen when enhancements or external resources fail. The DOM Gate treats violations as blockers.

Every non-interactive prompt version is content-addressed. Its first line and `page_data.prompt_version` must contain the registered OneShot contract, the first 12 characters of the OneShot asset SHA-256, the first 12 characters of the normalized complete prompt SHA-256, lesson ID, page number, and R36 suffix. `page_data.prompt_instance_sha256` stores the full normalized prompt digest. Normalization replaces only the version line with `__PROMPT_VERSION__`; therefore the same OneShot used again with changed variables, `PAGE_DATA`, `DESIGN_BRIEF`, page context, instructions, HTML, CSS, or JavaScript produces a different prompt version. Duplicate-only checks are insufficient.

Use only the bundled OneShots and Demos. Do not hand-build whole-course JSON, replace a bundled template with a local historical file, or downgrade non-interactive prompts to bare HTML.

## Authorization boundary

This skill creates only local, auditable artifacts. `IMPORT_READY_STATIC` is not import, render, interaction testing, acceptance, release, or publication. Use a separately authorized RunS client skill for any live operation.

## Finish with a receipt

Report the release version, status, frozen inputs, artifact paths, SHA-256 values where required, commands, blockers, and unexecuted downstream authorization boundaries.
