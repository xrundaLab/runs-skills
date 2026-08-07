# Frozen Input Manifest

Freeze one `runs_batch_manifest.yaml` before S1. It records only the resolved user-provided sources and output destination; it does not replace the S1 `source_manifest.json` generated under this bundled Skill contract.

Every run must explicitly freeze `visualMode: text_only` or `visualMode: visual_enhanced`. A Gate or manifest freeze attempted without the confirmed selection is `BLOCKED:VISUAL_MODE_NOT_SELECTED`; a later Gate receipt that differs from the frozen mode is `BLOCKED:VISUAL_MODE_DRIFT`. An initial natural-language request that omits the selection is handled by the startup-confirmation protocol below and is not itself a Gate attempt. `text_only` must not read a teacher visual script. `visual_enhanced` requires one explicitly named teacher visual script source and freezes its absolute path and SHA-256 before S1; the same batch script may serve multiple lessons. A missing target-lesson section means that lesson declares zero teacher-owned lesson-plan images and proceeds with courseware images only. It is not a missing-input blocker.

## Startup confirmation before preflight

When the user has authorized a run but omitted `visualMode`, do not stop with a receipt-like blocker and do not create files. Return `STARTUP_MODE_SELECTION_NEEDED` and present exactly:

1. 配图增强模式（推荐）
2. 纯文字模式

Ask the user to 回复数字 `1` 或 `2`. Do not infer the selection from the supplied files, choose on the user's behalf, or hide the non-recommended option. Do not recommend or confirm an output root in the same message as the mode selection.

Map the confirmed selection only in technical state: `1` → `visual_enhanced`; `2` → `text_only`. Do not present `text_only` or `visual_enhanced` as user-facing choice labels.

After mode selection, if `output_root` is absent, return `STARTUP_OUTPUT_CONFIRMATION_NEEDED` with one concrete, collision-free absolute `recommendedOutputRoot`, normally derived from the target lesson, internal mode slug, requested final stage, and current timestamp. Ask one concise confirmation question. For example, recommend an output root shaped like `<absolute-workspace>/runs_prompt_updates/<lesson_id>_<mode>_s1_s4_<YYYYMMDD-HHMMSS>` and print the resolved absolute path, not the placeholder.

The three-input set describes semantic course sources. A separately supplied teacher visual script is a valid conditional input in 配图增强模式, not a forbidden fourth semantic source. Inspect only enough of its declared scope after mode selection to determine whether it contains the target lesson:

- if it contains the target lesson, recommend `visual_enhanced` and freeze it only after confirmation;
- if it does not contain a section for the target lesson, explain that the lesson has no declared teacher-owned lesson-plan images and will proceed in 配图增强模式 with courseware images only; freeze the shared script path/SHA and do not fabricate an empty lesson section;
- if an unknown extra file has no registered role, explain that it will not be used as a semantic source and ask whether to exclude it.

Only after the user confirms the mode and then the output root may the manifest preflight begin. Missing operational choices at either conversational step must not report `BLOCKED_INPUT` or a Gate blocker. True source failures discovered after confirmation still use the existing blocker contract.

## Three-input mode

The minimum self-contained source set is exactly:

1. one course-information table in CSV, YAML, or XLSX form;
2. one teacher `final.md`;
3. one student `student-playback.md`, used only for the S2 structural cross-check.

The invocation must name the target `lesson_id` and a fresh output root. Select exactly one table row whose course number matches that lesson; if zero or multiple rows match, report `BLOCKED_INPUT` instead of guessing. Resolve the row into the six explicit fields below, preserving their source values. For `知识点` / `knowledgePoints`, retain the raw cell value in S1 evidence and deterministically split semicolons (`;` / `；`) or line breaks into the ordered manifest list. Write the manifest into the fresh output root as freeze evidence; it is derived from the three inputs and is not an additional user source.

## Required form

```yaml
contract: "RunS_V3.5.0-S1-S6-R36-20260731"
source_mode: "local" # local | github
visualMode: "text_only" # text_only | visual_enhanced; explicit, never inferred
output_root: "/absolute/path/to/a-new-output-directory"
lessons:
  - lesson_id: "lesson012"
    course_info:
      packageName: "..."
      unitName: "..."
      lessonNumber: 12
      courseName: "..."
      courseIntroduction: "..."
      knowledgePoints:
        - "..."
    teacher_final:
      path: "/absolute/path/to/lesson012/final.md" # local only
    teacher_visual_script: # required only for visual_enhanced; may be a shared batch file with no section for this lesson
      path: "/absolute/path/to/lesson012/teacher-visual-script.md"
    student_structure: # optional; S2 structural check only
      path: "/absolute/path/to/lesson012/student.md"
```

All six `course_info` values are source-faithful table inputs; the knowledge-point list is the registered delimiter projection of its retained raw cell. Do not derive values from a page title, a filename, or a previous lesson. `teacher_final.path` must point to the teacher `final.md`; `p1.md` and historical processed files are not substitutes. `student_structure.path` must point to the supplied `student-playback.md` in three-input mode. `output_root` must not already contain a frozen run for the same lesson.

## GitHub source form

Use only a full commit SHA. The repository can contain a CSV, YAML, or XLSX course-information table, but resolve the selected row into the six explicit `course_info` values above before S1. Record the table path and row key in the freeze receipt.

```yaml
contract: "RunS_V3.5.0-S1-S6-R36-20260731"
source_mode: "github"
visualMode: "visual_enhanced"
github:
  repo: "owner/repository"
  commit: "0123456789abcdef0123456789abcdef01234567"
  manifest_path: "inputs/runs_batch_manifest.yaml"
  course_info_table_path: "inputs/course_info.csv" # optional traceability
output_root: "/absolute/path/to/a-new-output-directory"
lessons:
  - lesson_id: "lesson012"
    course_info:
      packageName: "..."
      unitName: "..."
      lessonNumber: 12
      courseName: "..."
      courseIntroduction: "..."
      knowledgePoints:
        - "..."
    teacher_final:
      path: "lessons/lesson012/final.md" # repository-relative
    teacher_visual_script:
      path: "inputs/teacher-visual-script.md" # required for visual_enhanced; shared batch source allowed
    student_structure:
      path: "lessons/lesson012/student.md" # optional, repository-relative
```

Retrieve only the manifest, table when declared, and paths named by this manifest at that exact commit. Save the resolved files under the fresh local output root and record: repository, commit SHA, repository paths, local frozen paths, file SHA-256 values, and the selected table row key. A private repository requires pre-existing user authorization and authentication; do not request, print, or persist a token.

## Preflight result

Report `READY_FOR_S1` only after the mode and output root have been confirmed, every lesson has a readable teacher source, all six values, a unique `lesson_id`, and a writable fresh output directory. In `visual_enhanced`, also require a readable teacher visual script whose path and SHA can be frozen; in `text_only`, do not open or freeze that script. After confirmation, report `BLOCKED_INPUT` only for actual missing, unreadable, conflicting, or ambiguous required sources, grouped by lesson. Do not create stage artifacts during a manifest-only preflight.
