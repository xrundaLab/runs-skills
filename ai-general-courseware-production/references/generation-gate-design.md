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

## Post-class page canonical label

Teacher sources may use `课后任务`, `课后练习`, or `拓展练习`; these are input
aliases for one page category. S2 must freeze both page type and capsule as
`拓展练习`. S5 and S6 normalize legacy upstream aliases to the same value, and
S6 must emit `title: 拓展练习`, `tag: 拓展练习`, plus an OneShot context ending
in `拓展练习页`. The English runtime kind remains `post_class_task`. A mixed
semantic/display label is a blocker rather than a valid page variant.

## S5-S6 knowledge relationship projection

- S5 calculates real reading density from the frozen structured blocks; no candidate or initializer may supply or override density or design relationships.
- Mechanical `frozen_segment` groups are replaced when the source exposes comparison, process, example or role-distribution, and judgment relationships.
- S6 maps real relationships to executable `comparison_split`, `process_steps`, list-preserving, and `role_distribution_inline` recipes. Comma/semicolon-linked role clauses remain one continuous sentence with exact-source inline emphasis.
- The knowledge OneShot must carry the matching DOM class contracts. Recording recipe names without a differentiated layout is blocked.
- `sourceTextProjectionContract` forbids rendering a complete source paragraph and then copying its clauses into derivative cards. A split representation is allowed only when contiguous DOM fragments concatenate exactly to the frozen source text and each fragment is a complete sentence or natural clause rather than orphan punctuation.
- `semanticCompositionContract` makes geometry relationship-driven without a recipe-count quota: lists remain lists, comparisons and steps express their real relationships, and continuous explanations remain continuous. It blocks uniform card stacks and style-for-variety splitting.
- `visualHierarchyContract` is injected on every dynamic page and becomes required for multi-block, non-short compositions. It prioritizes source fidelity, semantic relationships, reading clarity, and typographic elegance before decoration. Exact-source in-place emphasis is preferred; CSS decoration is optional (0–2 groups) and cannot be used to manufacture richness. Real comparisons, steps, and lists must visibly preserve their relationships; a medium page must cover at least 60% of its reading area.
- The same contract blocks all-white or equal-radius card stacks, invented badge copy, generated emoji, top-heavy composition, and large unused lower areas. Frozen blockquote evidence maps to `evidence_quote_focus`; visual emphasis must not create new student-facing labels.
- S5 freezes an executable `design_brief`, not a generic style sentence: layout archetype, per-group presentation, per-block projection, exact-source emphasis, light surface policy, semantic color roles, and space balance. The S5 validator blocks missing or internally inconsistent fields.
- S6 copies those fields verbatim into `designExecutionContract`. Non-code dark-surface allowance is zero; same-block conflicting evidence remains a continuous inline flow instead of becoming two cards. Sentence sequences and role-distribution content remain one top-level section with flat nested items. The surface policy allows at most four top-level visual regions, forbids independent nested shadows, and allows at most two decorative groups.
- Side-by-side peer cards are allowed only when every peer is at most 80 Chinese characters and combined peer copy is at most 150 characters. Longer comparisons switch deterministically to full-width vertical cards with a shared left edge.
- Highlighting has one page-wide budget of at most three exact-source segments. One semantic category uses one style; highlights of at most 12 characters move as a whole and cannot leave a one- or two-character highlighted tail on its own line.

## Chrome 68 WebView compatibility Gate

All current OneShots, fixed Demos, and supplied generated HTML target untranspiled
Android System WebView Chrome 68. The baseline forbids modern JavaScript syntax
and unsupported DOM APIs as well as dynamic viewport units, CSS
`min()` / `max()` / `clamp()`, Flex `gap`, logical spacing, `env()`,
`backdrop-filter`, `text-wrap`, and modern color functions. Use physical
properties, `height:100%`, `width` plus `max-width`, guarded Observer APIs,
and visible static fallback content. Compatibility is checked on the actual
HTML/CSS/JS; a prose declaration alone does not pass the Gate.

## Content-addressed prompt instance version

Every non-interactive prompt uses:

`<OneShot contract>-asset-<asset SHA first 12>-prompt-<normalized prompt SHA first 12>-<lesson_id>-<page_no>-R36-20260731`

The complete prompt is assembled first with the version line normalized to
`提示词版本号：__PROMPT_VERSION__`. SHA-256 is calculated over that normalized
complete prompt after page context, variables, `PAGE_DATA`, `DESIGN_BRIEF`,
HTML, CSS, and JavaScript are final. The full digest is stored in
`page_data.prompt_instance_sha256`; only then is the visible version line
inserted. The static Gate recomputes the digest and compares the contract,
asset hash, full instance hash, `page_data.prompt_version`, first line, lesson,
and page. Thus the same OneShot with different model input cannot reuse a
version number.

## Post-generation DOM Gate

When an authorized external generation step returns a dynamic knowledge or case
HTML artifact, validate that supplied artifact with:

```bash
python3 scripts/validators/validate_dynamic_html.py \
  --effective-content <S5/effective_content_full.json> \
  --page-no <PXX> --html <generated_page.html>
```

This Gate blocks Chrome 68 incompatibilities, visible-copy drift or duplication,
orphan punctuation, and more than four `data-visual-region="top"` regions. It does not invoke a model,
RunS import, create, rendering, or publication and does not expand S6 static
authorization.

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

The runner must preserve both validator-style `issue_type` values and static
checker-style top-level `issues[].code` values in the stage receipt. It must not
collapse a known blocker into a generic command-failure code.

The registered entry point is:

```bash
python3 scripts/orchestrator/run_stage_gate.py --help
```

S2 records the frozen working plan; S3-S6 each require `--prior-receipt`.
S4 and S5 run the registered generator before the corresponding validator. S6
runs the registered assembler before the static checker. Generated artifacts
are first written to a temporary sibling file and moved into the final path only
after every command passes. A blocker therefore leaves a receipt but no new
stage artifact.

```bash
# S2: validate and receipt the frozen working plan
python3 scripts/orchestrator/run_stage_gate.py --stage S2 --lesson-id <lesson_id> \
  --receipt-dir <receipts> --working-plan <S2/page_plan_working_full.md>

# S3: validate the approved question artifact against the S2 receipt
python3 scripts/orchestrator/run_stage_gate.py --stage S3 --lesson-id <lesson_id> \
  --receipt-dir <receipts> --prior-receipt <receipts/s2_gate_receipt.json> \
  --working-plan <S2/page_plan_working_full.md> \
  --question-processed <S3/question_processed_full.md>

# S6: assemble and statically check only after the S5 receipt passes
python3 scripts/orchestrator/run_stage_gate.py --stage S6 --lesson-id <lesson_id> \
  --receipt-dir <receipts> --prior-receipt <receipts/s5_gate_receipt.json> \
  --effective-content <S5/effective_content_full.json> \
  --output <S6/whole_course.json>
```

Use the S4 and S5 invocations in `s1-s6-contract.md` between these commands.

S6 may report `IMPORT_READY_STATIC` only after assembly and static checking.
That status remains narrower than import, create, rendering, acceptance, or
release authority.

## Independent Skill version Gate

Use `VERSION` as the single current formal identifier in
`MAJOR.MINOR.PATCH-rNN` form. `rNN` identifies the RunS contract track; it is
not a resettable release counter. The core version therefore remains monotonic
when the RunS track changes.

Keep the release history in `references/version-registry.json`. Its schema
records the Skill name, current and released versions, permanently reserved
local numbers, and one ordered entry for every remotely traceable source
snapshot. Multiple unpublished local checkpoints may be compacted into one
non-reusable reserved range with a cumulative summary and the version they were
rolled into; they are not downloadable rollback sources and must not claim
`source_exact`, `sourceRef`, or a Tag. A `source_exact` entry contains the
version, status, summary, formation time, lowercase payload SHA-256, namespaced
source ref, validation evidence, supersession, and rollback fields. The
`0.2.1-r36` through `0.2.7-r36` range is
`legacy_audit_only`: it is permanently unavailable for reuse and does not claim
an exact historical source snapshot.

Compute `payloadSha256` from sorted Skill-relative path-plus-file-byte pairs.
Exclude only `references/version-registry.json`, Python bytecode caches, and
registered temporary validation receipts. The registry exclusion prevents a
self-referential hash; it does not exclude `VERSION`, `SKILL.md`, prompts,
scripts, tests, assets, or other references.

Run the validator in the matching mode:

```bash
# Candidate files and registry agree.
python3 scripts/validators/validate_skill_version.py \
  --skill-root . --mode local

# The candidate is strictly newer than the target branch.
python3 scripts/validators/validate_skill_version.py \
  --skill-root . --base-ref origin/main --mode pr

# Every source_exact Tag resolves and reproduces its registered payload.
python3 scripts/validators/validate_skill_version.py \
  --skill-root . --mode release
```

The immutable source-ref format is
`skill-ai-general-courseware-production-v<version>`. A pushed version Tag must
never move, be overwritten, or be deleted to reuse the identifier. If an
occupied version is wrong, allocate a higher version. To roll back, restore the
selected `source_exact` Tag on a new branch, allocate a version higher than the
current version, set `restoredFromVersion`, and rerun the current tests and
Gates before a new Issue and PR.

The canonical history, Tags, registry, Issues, and PRs live only in
`xrundaLab/runs-ai-monorepo`. The automated `runs-skills` subtree is a
latest-stable public distribution mirror, not the source of truth and not a
guaranteed arbitrary-history installer. Do not push human-authored changes or
version Tags directly to that mirror. After canonical merge, verify that its
latest `VERSION` and payload SHA-256 match the canonical Skill.

An iteration becomes valid only when the applicable generation tests, static
Gate, package validation, governance check, `VERSION`, registry, and payload
identity all agree. `IMPORT_READY_STATIC` remains a course-artifact status and
does not authorize import, create, rendering, acceptance, or publication.

### Development/install separation and release acceptance

Maintain only one canonical development worktree in `runs-ai-monorepo`; its
Git history and immutable Tags are the version archive. The installed Codex
Skill directory is a runtime copy, not a maintenance location: it must be a
separate non-symlink directory and may contain only the currently accepted
release. Do not patch an installed copy and copy it back into the worktree.

Before switching the active installation, record the immutable GitHub full
commit SHA, release Tag, `VERSION`, and relevant payload/file SHA-256 values in
the release evidence. Install afresh from that exact GitHub SHA into an
isolated test location, verify that it is not linked to the worktree and that
the recorded values match, then run the required black-box canaries with fresh
output directories. The required canaries are lesson011 and one lesson with a
different page/interaction structure; both must complete S1-S6 with every
stage receipt passing and S6 reporting `IMPORT_READY_STATIC`. Only then may the
active installed Skill be replaced or a 21-lesson batch be started.

## Required regression scenarios

- S2 routes `试一试：再连一次` to an interactive page while the preceding
  knowledge page records `none / 无`; S4 preserves both decisions.
- An action-oriented sentence incorrectly retained on the knowledge page is
  blocked by S2; after S2 routes it with the interaction page, S4 must not
  emit an interaction-boundary semantic issue.
- P01 preserves the raw knowledge-point field and projects `;` / `；` / newline-delimited values into an ordered list whose cardinality is copied exactly into the fixed-template prompt.
- P05 projects every frozen source block once and in order into `PAGE_DATA.contentBlocks`, while `DESIGN_BRIEF` and executable recipes are derived only from those blocks.
- P10 projects every source block into ordered S5 `sections[]` with deterministic semantic roles. S6 student-visible text follows that order and uses one “操作步骤” timeline; only adjacent `action → prompt`、`review → checklist`、or `condition → correctivePrompt` pairs may share a card in place. A checklist uses its own light structure and never a Prompt label. The static Gate checks roles, source indices, pair markers, and the single timeline; it does not claim screenshot or visual acceptance.
- A course-summary source paragraph contains `本课没有课后练习。` followed by
  a next-lesson preview; S5 removes only the status sentence from student
  projections and preserves the preview.
- A course summary without a structured heading is blocked at S5.
- A valid heading becomes S6 `summaryTitle` and is absent from S6 body blocks.
- A failed or stale receipt prevents the runner from invoking the next stage.
- Same-block conflicting quotes become one continuous inline sentence with two
  in-place evidence highlights and no orphan punctuation.
- A process paragraph becomes complete-sentence flat steps inside one top-level
  section; role-distribution clauses become flat nested items inside one section.
- Generated HTML with duplicated source copy, orphan punctuation, or more than
  four top-level visual regions is blocked by the DOM Gate.
