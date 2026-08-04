# S4-S6 Deterministic Generation and Gate Design

This reference defines the generation boundary for the R36 Skill. It complements
`s1-s6-contract.md`; it does not authorize RunS import, create, rendering, or
release.

## Goal

Prevent a correct S2 page boundary from drifting during S3-S5 processing, and
prevent S6 assembly unless the immediately preceding Gate actually passed.

## Stage ownership

- S2 owns page boundaries, page metadata, transition placement, and the exact
  non-interactive student body.
- S3 may only append an approved natural-language question and component JSON
  to the matching interactive page. It may not change S2 metadata or other page
  bodies.
- S4 deterministically merges frozen S2 and approved S3. It copies every S2
  page field verbatim and replaces only the effective body of an interactive
  page with its approved S3 component JSON.
- S5 deterministically projects frozen S4 into structured JSON. It preserves
  `source.rawMarkdown` verbatim while applying only the registered student
  projection rules.
- S6 consumes only an S5 artifact whose Gate receipt records `PASS` for the
  same path and SHA-256.

## S4 invariants

The S4 generator must preserve the S2 value of every one of these fields:

- page number and order;
- page type and capsule;
- source block IDs and content-block type;
- layout intent;
- transition placement and transition text;
- non-interactive effective body.

An interactive heading such as `试一试：再连一次` belongs to the interactive
page once S2 routed it there. S3 or S4 must not infer it as transition text for
the preceding knowledge page. If S2 records `none / 无`, S4 must emit exactly
`none / 无`.

## S5 course-summary projection

For a `课程小结` page:

1. Keep the complete S4 body verbatim in `source.rawMarkdown`.
2. Require a non-empty structured heading that can be projected verbatim to
   S6 `summaryTitle`.
3. Keep the heading in S5 structured blocks for audit and S6 mapping.
4. Ensure S6 consumes that heading as `summaryTitle` and excludes it from the
   student body to avoid duplicate rendering.
5. Remove only an exact non-student status sentence such as
   `本课没有课后练习。` from student projections.
6. If that status sentence shares a paragraph with a next-lesson preview,
   preserve the remainder verbatim and in order.

## Gate receipt

Each Gate execution writes one JSON receipt containing:

- contract version and lesson ID;
- stage and status;
- command and exit code;
- absolute input and output paths;
- SHA-256 fingerprints;
- issue codes and blocker text;
- previous receipt path and SHA-256 when a previous stage is required.

The official runner must verify the preceding receipt, referenced artifact path,
and SHA-256 before invoking the next stage. A missing receipt, non-`PASS`
status, path mismatch, or hash mismatch blocks execution without creating the
next-stage artifact.

S6 may report `IMPORT_READY_STATIC` only after assembly and static checking.
That status remains narrower than import, create, rendering, acceptance, or
release authority.

## Required regression scenarios

- S2 routes `试一试：再连一次` to an interactive page while the preceding
  knowledge page records `none / 无`; S4 preserves both decisions.
- A course-summary source paragraph contains `本课没有课后练习。` followed by
  a next-lesson preview; S5 removes only the status sentence from student
  projections and preserves the preview.
- A course summary without a structured heading is blocked at S5.
- A valid heading becomes S6 `summaryTitle` and is absent from S6 body blocks.
- A failed or stale receipt prevents the runner from invoking the next stage.
