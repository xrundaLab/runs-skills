# Visual Asset Return Contract

This contract is owned by S1 and applies only when the frozen run manifest selects `visualMode: visual_enhanced`. It does not change S2, S3, or S4 business inputs, outputs, filenames, content, or SHA rules.

## Immutable lifecycle

The one logical image-management artifact is retained as three non-overwriting snapshots:

- `lessonNNN__S1__visual_asset_manifest.initial.json`: freezes the teacher visual script, teacher `final.md` SHA, lesson-plan assets, lesson-plan URLs, exact `教案位置` text, source anchors, render placements, reuse, and group order. It does not assign S4 page numbers.
- `lessonNNN__S1__visual_asset_manifest.request.json`: after S4 PASS, binds every lesson-plan anchor to one final non-interactive page and gives every S4 page exactly one decision: `lesson_plan_image`, `courseware_image`, or `interaction_no_image`. Fixed page types already carry final page-type placement; knowledge, case, and task pages carry only `candidate_only` placement with `placementStatus: pending_visual_review`.
- `lessonNNN__S1__visual_placement_review.json`: after the explicitly named external return exists, the executing model visually inspects each returned courseware image for knowledge, case, and task pages, records the semantic relationship and embedded-text conflict result, and freezes either exact neighboring text anchors or the allowed fallback. It is hash-bound to the request and external return.
- `lessonNNN__S1__visual_asset_manifest.resolved.json`: after validating the external return and required placement review, copies only approved courseware metadata and freezes reviewed placement evidence. This is the only visual manifest S5 may read.

Each Gate invocation preserves `visual_manifest_gate_receipt_attempt-NNN.json` and updates `visual_manifest_gate_receipt.json`. Snapshot outputs are never overwritten. `text_only` writes only the receipt status `SKIPPED_BY_VISUAL_MODE` and creates no visual manifest.

Request binding accepts a legacy S4 PASS receipt that has no `visualMode` key only as a narrow compatibility case: the initial manifest must explicitly be `visual_enhanced`, and the receipt contract, lesson, stage, output absolute path, and output SHA-256 must all match the supplied S4 plan. A receipt that contains any explicit non-`visual_enhanced` value still stops with `VISUAL_MODE_DRIFT`. Do not rewrite or backfill the immutable legacy receipt.

## Authority and decisions

- `lesson_plan_image` URL and classification authority: the teacher visual script.
- `courseware_image` URL and classification authority: the frozen request plus validated external return.
- Lesson-plan images have priority. One page cannot mix the two course-image classes.
- Interactive component pages remain image-free and override both image classes. A teacher placement uniquely recognized inside an interaction page is retained in the request/resolved audit trail with `placementStatus: suppressed_on_interaction_page`, but it is excluded from that page's assets and the page decision remains `interaction_no_image`. A genuinely missing or ambiguous surviving anchor still blocks as `LESSON_PLAN_IMAGE_ANCHOR_INVALID`.
- Formal post-class page type is always `拓展练习`; `课后任务` and `课后练习` are teacher-source aliases only. Visual tools reuse `scripts/page_type_contract.py`.

## Placement and minimal presentation

Lesson-plan image placement is teacher-owned. Every initial placement retains `sourceLocationText`, the placement-specific `sourceLocationDetail`, `sourceAnchor.beforeText/afterText`, and `renderPlacement` with `authority: teacher_visual_script`. Request, resolved, S5, and S6 must carry it unchanged. If S4 legitimately omits one transition-side anchor, request may identify the page from the other side only when the omitted side has zero matches and the surviving side has exactly one page match; this is page-binding evidence, not a placement fallback, and the teacher render placement remains unchanged. A missing or ambiguous surviving anchor has no fallback and blocks; downstream stages must not replace it with a generic bottom-of-page insertion.

Courseware-image placement has two routes. The page-type contract fixes intro, scene, and summary placement without inspecting the returned image. Knowledge, case, and task receive only a candidate in request; after return, the model must inspect the actual image and freeze the final placement in the placement-review artifact before resolved may pass.

| Page type | Rule | Required position |
| --- | --- | --- |
| 课程开篇 | `course_intro_primary_image` | Inside the rounded course-overview container as the top hero, before the lesson chip and title; the image already carries course-package and unit copy, so the image-enhanced page does not repeat those two text fields visibly. Replaces the legacy decorative image slot. |
| 场景引入 | `scene_context_image` | Inside the script paper, after context paragraphs and before the director cue. |
| 知识讲解 | `knowledge_inline_image` | After the visually related concept, list, or process selected during returned-image review; fallback directly after the page title. |
| 案例分析 | `case_title_image` | After the visually related analysis text selected during returned-image review; fallback directly after the page title. |
| 课程小结 | `summary_card_image` | Inside the summary card, after its title and before its body. |
| 拓展练习 | `extension_contextual_image` | At the visually related task position selected during returned-image review; fallback after the first text block. |
| 互动题目 | none | Course images are forbidden. |

All course images use the same minimal `visualPresentation`: primary content image, content-width, natural ratio, `object-fit: contain`, 16px radius, 16px vertical spacing, no default standalone card, no thumbnail/tiny decorative treatment, and same-page lightbox. Every placement carries `terminalPlacementForbidden: true`: an image must never be the final content block, appear after the last paragraph, or sit next to the CTA/footer. Two or more images always use `groupLayout: vertical_stack` in frozen order at content width. When every asset label uniquely matches one item in the same frozen unordered-list block, S5 adds the exact `pairedStudentText` plus `pairedSource {blockIndex,itemIndex,blockType}` to each asset. S6 then renders one ordered `visual-paired-item` per asset as image → caption → corresponding copy before the next image, and removes that consumed item from any separate list rendering so it appears only once. Missing, partial, or ambiguous matching produces no pairing fields and is not a blocker; downstream uses the legacy vertical gallery and unchanged source list. Horizontal rows, equal-width grids, three-column galleries, and thumbnail treatment are forbidden, including square-image groups.

The returned-image review may record whether visible text embedded in the image overlaps with student-visible page copy as `embeddedTextOverlapDetected`. This is audit-only evidence: image text and page text overlap is not a conflict, never blocks resolved, S5, or S6, and does not require regenerating or correcting the returned image. The legacy input field `embeddedTextConflict` is accepted as a backward-compatible alias and is normalized to the non-blocking overlap record. Downstream exact-source projection still forbids the HTML itself from rendering the same student sentence more than once.

## External return

The collaborator normally receives the selected S4 `page_plan_full.md` and request snapshot. The finalizer accepts one explicit absolute `--external-return` path; it never scans a directory. For independent-stage or local-adjustment work, that return may originate from another compatible S4 chain. The selected current S4 remains the content authority; the return is an image-metadata source only.

The collaborator may add one candidate courseware image to every non-interactive page. The finalizer uses the frozen request snapshot as the classification authority: it consumes the candidate only on pages classified as `courseware_image`, and deterministically ignores candidate courseware metadata on pages classified as `lesson_plan_image` because the teacher visual script has priority. Ignored page numbers are retained in `externalReturn.ignoredCoursewarePages` for audit. Each candidate uses one HTTPS URL and optional values:

```markdown
- 课件配图地址：https://...
- 课件配图宽度：1672
- 课件配图高度：941
- 课件配图 alt：...
- 课件配图生成版本：...
```

The compatibility alias `- 图片地址：https://...` is accepted as candidate courseware metadata under the same rules. After removing these allowlisted lines, exact equality with the selected S4 records `externalReturn.bindingMode: exact_page_plan`. If the body differs, resolved uses cross-chain mode only when the ordered page-number set and canonical page type of every page match the selected S4; it records `bindingMode: cross_chain_page_metadata`, source-base and target S4 hashes, and never copies the returned body. Page-set drift is `BLOCKED:EXTERNAL_RETURN_PAGE_SET_MISMATCH`; page-type drift is `BLOCKED:EXTERNAL_RETURN_PAGE_TYPE_MISMATCH`. Content wording, component IDs, JSON formatting, or other body differences do not by themselves block image-metadata reuse because S5 reads only the selected S4 plus resolved visual manifest.

Courseware-image `alt` is recommended but optional. When it is omitted, resolved and S5 retain `null` as provenance; S6 deterministically serializes it as the valid empty alternative `alt=""` and must not invent an image description. A supplied non-empty alt is projected unchanged.

The finalizer blocks missing URLs on requested courseware-image pages, page-set or canonical-page-type drift, metadata on interactions, explicit lesson-plan URL override, unrequested pages, invalid counts, and duplicate URLs among consumed courseware images. Candidate courseware metadata on lesson-plan-image pages is ignored rather than copied or treated as a conflict. The resolved snapshot records the external path, SHA, binding mode, source-base/target hashes, and ignored page numbers only as provenance. Downstream validation and S5 must not open `externalReturn.path`.

## Returned-image placement review

The review is required only for courseware images on `知识讲解`, `案例分析`, and `拓展练习`. Intro, scene, and summary use their fixed placement and record `reviewNotRequiredReason: fixed_page_type_placement`. Lesson-plan images keep teacher anchors and are not re-positioned by this review.

The review JSON uses schema `1.0`, records the exact absolute path and SHA-256 of both request and external return, and contains exactly one row for every review-required courseware asset. Each row must set `imageReviewed: true`, a non-empty `semanticRelation`, Boolean `embeddedTextOverlapDetected`, Boolean `fallbackUsed`, and a `renderPlacement` with `authority: model_visual_review`, `anchorType: reviewed_semantic_anchor`, the unchanged page rule, the page-type fallback, and `terminalPlacementForbidden: true`. Text overlap remains non-blocking regardless of that Boolean. A non-fallback row freezes `insertAfterText` and optional `insertBeforeText` from the current S4 page body. A fallback row uses `insertAfter: page_title` for knowledge/case or `insertAfter: first_text_block` for task.

This review is a semantic image-inspection step, not a browser preview or visual acceptance run. It updates only the S1-owned image-management evidence; S2, S3, and S4 stay unchanged.

## Commands

```bash
python3 scripts/orchestrator/run_visual_manifest_gate.py --phase initial \
  --lesson-id <lesson_id> --visual-mode visual_enhanced \
  --teacher-final <final.md> --teacher-visual-script <teacher-visual.md> \
  --receipt-dir <receipts> --output <visual.initial.json>

python3 scripts/orchestrator/run_visual_manifest_gate.py --phase request \
  --lesson-id <lesson_id> --visual-mode visual_enhanced \
  --initial-manifest <visual.initial.json> --page-plan <S4/page_plan_full.md> \
  --s4-receipt <receipts/s4_gate_receipt.json> \
  --receipt-dir <receipts> --output <visual.request.json>

python3 scripts/orchestrator/run_visual_manifest_gate.py --phase resolved \
  --lesson-id <lesson_id> --visual-mode visual_enhanced \
  --request-manifest <visual.request.json> --page-plan <S4/page_plan_full.md> \
  --external-return <absolute-return.md> \
  --placement-review <lessonNNN__S1__visual_placement_review.json> \
  --receipt-dir <receipts> --output <visual.resolved.json>
```

These commands create only local static artifacts. They do not authorize import, create, render, preview, installation, release, or publication.
