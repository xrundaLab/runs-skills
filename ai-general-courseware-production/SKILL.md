---
name: ai-general-courseware-production
description: 将 AI 通识课教师版教案按冻结输入处理为 RunS 网页课件整课 JSON，或独立执行和审计 S1-S6 任一阶段。适用于需要页面规划、题目组件 JSON、有效内容 JSON、整课 JSON 静态装配与 Gate 核验的课程生产；支持本地或固定 GitHub commit 输入，不自动导入、创建、渲染或发布。
---

# AI 通识课网页课件生成

Use this release bundle as a self-contained R36 contract. It supports a read-only preflight, one unlocked stage, a complete S1-S6 local run, an existing-artifact audit, and batch-manifest preparation.

## Run an isolated Skill-only verification

For a pure Skill self-test, black-box installation acceptance, or a course verification explicitly limited to three supplied inputs, read only this `SKILL.md`, the contract references it routes to, bundled scripts, and those specified inputs. Do not read or use any workspace SOP, `CURRENT_SOP_ENTRY.md`, SOP inventory, historical `outputs`, prior course artifacts, historical pages, or another course as input, baseline, or supplemental context. Do not infer a production request merely because the inputs mention RunS or a lesson plan.

If the request also includes production governance, batch production, SOP modification, or RunS create / import / render / publish (including preparation, audit, or approval for those actions), stop the isolated mode and use the production SOP path under separately authorized scope.

## Collect and freeze inputs

Read [references/input-manifest.md](references/input-manifest.md) before S1. In three-input mode, accept exactly one course-information table, one teacher `final.md`, and one student `student-playback.md`; resolve the named lesson row into six verbatim course-info fields and freeze a local `runs_batch_manifest.yaml` as derived evidence, not as a fourth source input. A teacher visual script is a conditional visual input, not a fourth semantic source. Also require a fresh local output directory.

Require an explicit `visualMode: text_only | visual_enhanced` before S1. A Gate or manifest freeze attempted without that confirmed value is `BLOCKED:VISUAL_MODE_NOT_SELECTED`; every newly written S2-S6 receipt must preserve the same mode or stop with `BLOCKED:VISUAL_MODE_DRIFT`. A legacy S4 PASS receipt that predates the `visualMode` field remains valid for an enhanced-mode request only when its contract, lesson, stage, output path, and output SHA-256 all match and the frozen S1 initial manifest explicitly records `visual_enhanced`. The same legacy S4 receipt may enter S5 only with a resolved manifest and PASS receipt strictly bound to that exact S4 path and SHA-256; an explicitly present mismatched mode still blocks. Never rewrite or backfill the legacy receipt. `text_only` never reads a teacher visual script and writes a visual Gate receipt with `SKIPPED_BY_VISUAL_MODE`. `visual_enhanced` additionally requires an explicitly supplied teacher visual script whose path and SHA-256 are frozen; the script may be a shared batch source. When that readable source has no section for the target lesson, initial freezes an explicit zero-lesson-plan-image state instead of blocking, and request classifies every non-interactive page as `courseware_image`. A present lesson section remains strict: its teacher SHA, assets, URLs, anchors, and placements must validate. The mode uses the S1-owned `initial → request → resolved` image-management lifecycle in [references/visual-return-contract.md](references/visual-return-contract.md).

Natural-language startup is a collaboration step before any Gate. If an otherwise actionable request omits `visualMode`, report `STARTUP_MODE_SELECTION_NEEDED`, not a Gate failure, and present exactly these numbered user choices in this order:

1. 配图增强模式（推荐）
2. 纯文字模式

Ask the user to 回复数字 `1` 或 `2`. Do not choose on the user's behalf. Do not recommend or confirm an output root in the same message as the mode selection. After the user selects a mode, map `1` to internal `visual_enhanced` and `2` to internal `text_only`.

Only after the mode is selected, if the fresh output root is missing, report `STARTUP_OUTPUT_CONFIRMATION_NEEDED`, provide one collision-free absolute `recommendedOutputRoot`, and ask one concise confirmation question. Do not create the directory or any artifact until confirmed. A supplied visual-script file is not an illegal fourth semantic input: after mode selection, use it only for 配图增强模式; in 纯文字模式 explain that it will be excluded. If the script does not contain a section for the target lesson, state that it will not be used for that lesson and recommend excluding it from that lesson. Do not reopen product design or present multiple alternative output paths.

All user-facing mode choices use Chinese labels: **纯文字模式** maps to internal `text_only`, and **配图增强模式** maps to internal `visual_enhanced`. Recommendations and confirmation questions must say the Chinese label. Do not present `text_only` or `visual_enhanced` as user-facing choice labels; retain those exact enum values only in manifests, CLI arguments, receipts, hashes, and technical audit details.

- Use `source_mode: local` for absolute local source paths.
- Use `source_mode: github` only with a user-authorized `repo`, immutable full commit SHA, manifest path, and repository-relative source paths.
- Freeze all resolved GitHub files locally before S1. Never use a branch, tag, moving URL, or refetch GitHub after S1.
- Use a student file only for the S2 structural cross-check.

After startup choices are confirmed, report `BLOCKED_INPUT` as one grouped list only for a missing, unreadable, conflicting, or ambiguous required source. Before confirmation, missing operational choices must not report `BLOCKED_INPUT` or a Gate blocker. Never silently choose a source file, course-info row, output directory, page type, or component type; recommend safe operational values where this contract explicitly permits it.

## Run the six-stage chain

Read [references/s1-s6-contract.md](references/s1-s6-contract.md) before generating or validating a stage. It is the sole R36 production contract in this bundle. Use [references/schemas/stage-artifact-map.json](references/schemas/stage-artifact-map.json) only as a quick field map, never as a weaker replacement.

| Stage | Sole input | Sole output |
| --- | --- | --- |
| S1 | Teacher `final.md`, six course-info fields; teacher visual script only in `visual_enhanced` | existing three S1 outputs; visual lifecycle snapshots are separate |
| S2 | Frozen S1 preprocessed Markdown | working plan, student structural check |
| S3 | Frozen S2 working plan | question-processed plan |
| S4 | Frozen S2 working plan and approved S3 plan | final page plan |
| S5 | `text_only`: frozen S4 only; `visual_enhanced`: frozen S4 + resolved visual manifest + matching visual PASS receipt | `effective_content_full.json` |
| S6 | Passed S5 effective-content JSON | whole-course JSON and static result |

Run only the requested and unlocked stage. For S2-S6 serial execution, use the bundled Gate runner so the previous `PASS` receipt, artifact path, and SHA-256 are verified before the next command starts. Every call preserves `*_gate_receipt_attempt-XXX.json` and updates the latest receipt. A fixed-format error limited to the current stage may be repaired and re-run only after its `BLOCKED` attempt receipt is retained; input authority, source SHA drift, semantic, page-boundary, or student-visible-content blockers stop that lesson (and a batch) for confirmation. Never skip a Gate or advance another stage before the current stage passes.

An independently executed stage may consume an explicitly selected, passed upstream artifact and receipt from another output root or an older compatible Skill run. The selected S4 remains the complete student-content authority; do not replace it merely because a newer directory exists, and do not require S1-S4 regeneration when current validators can consume it. Regenerate only the downstream snapshot whose current contract changed. The visual manifest is the cross-chain adapter: an external return contributes allowlisted image metadata only. Resolved may bind that metadata to a different current request/S4 when ordered page numbers and canonical page types match; it records `bindingMode: cross_chain_page_metadata`, keeps the selected S4 body authoritative, and never projects external-return body text into S5. Page-set/type mismatch, current request decision mismatch, or invalid current placement review still blocks.

## Use bundled deterministic tools

From this skill directory, use only these registered tools:

```bash
# Official serial Gate entry; repeat per authorized stage and pass the prior receipt.
python3 scripts/orchestrator/run_stage_gate.py --help

# S1-owned visual branch. text_only writes only SKIPPED_BY_VISUAL_MODE;
# visual_enhanced freezes initial, then request after S4 PASS, then resolved.
python3 scripts/orchestrator/run_visual_manifest_gate.py --help

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

The S1 `initial` snapshot freezes every lesson-plan image URL plus the exact teacher `教案位置` text, the before/after source anchor, and a teacher-authoritative render placement. After S4 PASS, `request` preserves that placement while binding its page number. When S4 legitimately omits one transition-side anchor, request may bind by the other side only if the omitted side appears nowhere and the surviving side identifies exactly one page; it never rewrites the teacher placement, and missing or ambiguous surviving evidence still blocks. Intro, scene, and summary courseware images receive final fixed page-type placement; knowledge, case, and task receive only a candidate with `placementStatus: pending_visual_review`. After the external return exists, visually inspect each returned image for those three page types and write the hash-bound `lessonNNN__S1__visual_placement_review.json`: record semantic relation, non-blocking embedded-text overlap audit, and either exact S4 neighboring text anchors or the allowed fallback. Only then may resolved freeze `model_visual_review` placement and enter S5. S5 projects that placement unchanged and never collapses it to generic content-bottom insertion. The separately frozen P01 course-intro image is the top hero inside the rounded course-overview container, before the lesson chip and title; because that image carries the course-package and unit copy, the visual-enhanced P01 does not repeat those two fields as visible text. It is never appended after the knowledge-point list. The learning-goal and unlock title/body type scale stays identical to the bundled text-only P01 Demo; the learning-goal title is centered with the small horn inline beside it, while the goal copy is left aligned.

S6 always consumes only the passed S5 JSON. In `visual_enhanced`, it projects a single S5 image to `page_data.visualAsset` and an ordered image group to `page_data.planVisualAssets[]`, including each asset's frozen `placement`, `visualReview`, optional exact-source `pairedStudentText` / `pairedSource`, and shared `visualPresentation`; it switches the six non-interactive routes to bundled visual OneShots `09`–`14` and emits `visualMode: visual_enhanced`. Interaction pages remain image-free. URL, alt, placement, optional source label, group order, and any frozen pairing are content-addressed in each prompt version. Images are primary content illustrations, never thumbnails, tiny decorative strips, or icon-sized replacements: use the content width, natural ratio, `object-fit: contain`, 16px radius and 16px vertical spacing, without a default standalone card. Every placement forbids terminal insertion: no image may be the final content block, follow the last paragraph, or sit next to CTA/footer. Every group of two or more images is a full-width `vertical_stack` in frozen order; square images are not an exception. When S5 can uniquely match every group label to one labelled unordered-list item, it freezes that exact item per asset; S6 must render one `visual-paired-item` per asset in the order image → caption → corresponding copy, before the next image, and must not separately repeat the consumed source item. Missing or ambiguous matching stays backward-compatible: S5 omits the optional pairing fields and does not block, while S6 keeps the legacy vertical gallery and source list. Every image also has a same-page lightbox opened by a real button and closed by its round × button, backdrop, or Escape; the enlarged image is horizontally and vertically centered, and `positionVisualClose` uses its actual rectangle to keep the button horizontally centered at the vertical midpoint between image bottom and viewport bottom. Zoom never calls the course SDK or opens an external preview. `text_only` keeps the 0.2.21 S6 bytes and registered `03`–`08` assets unchanged.

For `visual_enhanced`, run S5 through the official Gate with explicit
`--visual-manifest <resolved.json>` and `--visual-receipt <visual PASS receipt>`.
S5 verifies both hashes, reads only the original S4 plus resolved manifest,
and projects one ordered `visual.assets[]` array on non-interactive pages.
It never opens `externalReturn.path`. Interactive pages remain byte-faithful
component projections and contain no visual field or image URL.

Standalone generators and validators are audit/debug tools. They do not create a stage receipt and do not authorize a downstream stage. The official sequence is one `run_stage_gate.py` call per stage, using the prior stage's receipt for S3-S6; see [references/generation-gate-design.md](references/generation-gate-design.md).

For knowledge and case pages, S5 derives deterministic content relationships only when the frozen text actually exposes comparison, process, list, example/role distribution, or judgment structure. It never accepts a candidate or initializer. S5 must freeze the executable design, including `alignmentPolicy`: left alignment and top alignment take priority; same-level content shares a left edge; peer comparisons share a top edge and width; asymmetry is allowed only for an explicit primary/supporting relationship. Same-block conflicting evidence and comma/semicolon-linked role clauses stay in one continuous linguistic flow; the latter use `role_distribution_inline` / `continuous_inline_highlights`, with exact-source emphasis applied in place. S6 copies the design into `designExecutionContract` and injects `visualHierarchyContract` plus `alignmentContract`; it must not infer a replacement layout. Source fidelity, semantic relationship, reading clarity, and typographic elegance take priority over decoration. Real comparisons, steps, and lists visibly express those relationships; decoration is optional, with no minimum quota. Random indentation, random widths, stagger-for-variety, generic card stacks, decorative clutter, and large near-black panels are invalid. The post-generation DOM Gate checks exact visible projection and punctuation-linked clause splitting; it does not authorize generation, import, rendering, or publication.

P01 keeps the verbatim `知识点` audit field and deterministically splits `;`、`；`、or newline-delimited values into an ordered non-empty `content.knowledgePoints[]`; S6 must consume that list without re-splitting or merging it. Treat teacher-source headings “课后任务”、 “课后练习”、and “拓展练习” only as input aliases; S2 is the sole semantic pagination decision point and must freeze both the page type and capsule as the canonical value `拓展练习`. S5 and S6 also normalize legacy upstream aliases to `拓展练习`, so `page_type`、`capsule`、S6 `title`、`tag`、fixed UI labels, and OneShot page context never diverge. P10 must render every S5 `sections[]` entry in its original order. S5 assigns only deterministic display roles derived from the frozen blocks; S6 may combine adjacent `action → prompt`、`review → checklist`、or `condition → correctivePrompt` pairs at that exact position, inside one “操作步骤” timeline. A source heading “故事顺序” followed by a list becomes one independent story region, never “任务要点”. A single source paragraph that contains actual action, completion check, and support conditions remains one source section with three exact contiguous `segments[]`; only its action enters the numbered timeline, while check and support render outside the numbered step, and concatenating the segments must reproduce the source paragraph byte-for-byte. S6 must not globally collect Prompt blocks, render a checklist as Prompt, repeat the lead as an extra task card, or invent steps. The S6 Gate verifies P01 cardinality, P05 exact block/design projection, and P10 source-section order plus semantic grouping. These remain static contracts, not visual acceptance; `validate_dynamic_html.py` runs only when generated HTML is explicitly supplied.

For visual-enhanced non-interactive pages other than the separately frozen P01 course-intro asset, image edges share the same left and right boundaries as their owning text region; nested `calc(100% - 48px)` image insets are forbidden. The page image itself remains the only visible lightbox trigger; do not add a visible “查看大图” control or button styling. The dark same-page lightbox contains no caption, vertically and horizontally centers the enlarged image, and places one stable round × close button horizontally centered at the midpoint between image bottom and viewport bottom. It supports backdrop and `Escape` close plus Chrome-68-compatible two-finger 1–4× zoom and one-finger pan when enlarged. Closing resets scale and translation and restores background scrolling. The non-intro visual OneShots and Demos share frozen heading/body/list/caption typography tokens. P10 keeps only its main title centered; all other task copy is left aligned. The DOM Gate rejects horizontal image groups, missing terminal-placement markers, a gallery with no later student content, visible close text, or a close button without actual-rectangle midpoint positioning. Exact student-source projection forbids the HTML itself from rendering a student sentence more than once. Text embedded in a returned image may overlap with page text; the review records that overlap only as audit evidence and never blocks resolved, S5, or S6. These rules are static/DOM contracts; real-device gesture validation remains required before visual acceptance and never authorizes import, render, or publish.

Comparison cards may remain side by side only when every peer is at most 80 Chinese characters and the combined peer copy is at most 150 characters; otherwise use a full-width vertical stack with one shared left edge. The page-wide highlight budget is at most three exact-source segments. The same semantic category uses one highlight style; a short highlight of at most 12 characters moves as a whole and must not leave a one- or two-character highlighted tail on a separate line.

Every bundled prompt, fixed Demo, and generated HTML uses **Android System WebView Chrome 68** as the untranspiled baseline, following the [H5 low-version WebView compatibility specification](https://github.com/xrundaLab/.github-private/wiki/H5%E4%BD%8E%E7%89%88%E6%9C%ACWebView%E5%85%BC%E5%AE%B9%E5%BC%80%E5%8F%91%E8%A7%84%E8%8C%83). Do not emit optional chaining, nullish coalescing, logical assignment, class fields/static blocks, numeric separators, unsupported DOM APIs, dynamic viewport units, CSS `min()` / `max()` / `clamp()`, Flex `gap`, logical spacing, `env()`, `backdrop-filter`, `text-wrap`, or modern color functions. Prefer `height:100%`, physical spacing properties, `width` plus `max-width`, guarded Observer APIs, and a visible static first screen when enhancements or external resources fail. The DOM Gate treats violations as blockers.

Every non-interactive prompt version is content-addressed. Its first line and `page_data.prompt_version` must contain the registered OneShot contract, the first 12 characters of the OneShot asset SHA-256, the first 12 characters of the normalized complete prompt SHA-256, lesson ID, page number, and R36 suffix. `page_data.prompt_instance_sha256` stores the full normalized prompt digest. Normalization replaces only the version line with `__PROMPT_VERSION__`; therefore the same OneShot used again with changed variables, `PAGE_DATA`, `DESIGN_BRIEF`, page context, instructions, HTML, CSS, or JavaScript produces a different prompt version. Duplicate-only checks are insufficient.

Use only the bundled OneShots and Demos. Do not hand-build whole-course JSON, replace a bundled template with a local historical file, or downgrade non-interactive prompts to bare HTML.

## Govern independent Skill versions

Treat `0.2.24-r36` as the current visual-mode release candidate. Local working iterations may reserve version numbers for audit, but only a remotely published exact source snapshot receives an immutable Tag. Before claiming any local iteration valid, run:

```bash
python3 scripts/validators/validate_skill_version.py \
  --skill-root . --mode local
```

Advance the core PATCH only after all applicable tests, static Gates, and governance checks pass. Once a version appears in a commit, formal receipt, Issue, PR, or Tag, 版本不得倒退或复用. A rollback restores an immutable historical source ref into a higher new version and repeats the current validation contract.

The canonical source is `xrundaLab/runs-ai-monorepo/skills/ai-general-courseware-production/`. `xrundaLab/runs-skills` is the automated latest-stable 公开分发镜像; 禁止直接向该镜像人工提交 Skill 变更或版本 Tag. Development and installed use are strictly separated: change and test only the canonical Git worktree; install only from an immutable GitHub full commit SHA into the Codex Skill directory; never edit or link the installed directory back to the worktree. A release is not complete until a clean, SHA-pinned installation is verified against the published files and completes the required black-box S1-S6 canaries. Read [references/generation-gate-design.md](references/generation-gate-design.md) for registry, PR, release, Tag, installation verification, and rollback rules.

## Authorization boundary

This skill creates only local, auditable artifacts. `IMPORT_READY_STATIC` is not import, render, interaction testing, acceptance, release, or publication. Use a separately authorized RunS client skill for any live operation.

## Finish with a receipt

Report the release version, status, frozen inputs, artifact paths, SHA-256 values where required, commands, blockers, and unexecuted downstream authorization boundaries.
