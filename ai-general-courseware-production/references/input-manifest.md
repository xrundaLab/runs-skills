# Frozen Input Manifest

Freeze one `runs_batch_manifest.yaml` before S1. It records only the resolved user-provided sources and output destination; it does not replace the S1 `source_manifest.json` generated under this bundled Skill contract.

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
    student_structure: # optional; S2 structural check only
      path: "/absolute/path/to/lesson012/student.md"
```

All six `course_info` values are source-faithful table inputs; the knowledge-point list is the registered delimiter projection of its retained raw cell. Do not derive values from a page title, a filename, or a previous lesson. `teacher_final.path` must point to the teacher `final.md`; `p1.md` and historical processed files are not substitutes. `student_structure.path` must point to the supplied `student-playback.md` in three-input mode. `output_root` must not already contain a frozen run for the same lesson.

## GitHub source form

Use only a full commit SHA. The repository can contain a CSV, YAML, or XLSX course-information table, but resolve the selected row into the six explicit `course_info` values above before S1. Record the table path and row key in the freeze receipt.

```yaml
contract: "RunS_V3.5.0-S1-S6-R36-20260731"
source_mode: "github"
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
    student_structure:
      path: "lessons/lesson012/student.md" # optional, repository-relative
```

Retrieve only the manifest, table when declared, and paths named by this manifest at that exact commit. Save the resolved files under the fresh local output root and record: repository, commit SHA, repository paths, local frozen paths, file SHA-256 values, and the selected table row key. A private repository requires pre-existing user authorization and authentication; do not request, print, or persist a token.

## Preflight result

Report `READY_FOR_S1` only after every lesson has a readable teacher source, all six values, a unique `lesson_id`, and a writable fresh output directory. Otherwise report `BLOCKED_INPUT` with the missing fields grouped by lesson. Do not create stage artifacts during a manifest-only preflight.
