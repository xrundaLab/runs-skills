# 润思课程后台 API 字段

All requests use the selected environment host plus `/api/v1` and that environment's dedicated admin token in the macOS Keychain. Development and production tokens are independent.

## Course package

- Detail: `GET /business/course/package/{id}`
- Create / update: `POST` / `PUT /business/course/package`
- Create required fields: `courseName`, `coverImageOssId`, and non-empty `chapterBo` whose items contain `title`.
- Package fields: `courseName`, `courseDesc`, `price`, `originPrice`, `appleProductId`, `purchaseLink`, `coverImageOssId`, `detailImageOssId`, `videoUrlOssId`, `status`, `remark`, `packageHighlightText`, `packageValueSummary`, `abilitySummaryList`, `chapterBo`.
- Detail response mappings: package fields are under `data.coursePackage`; chapters are `data.chapterAndCourseList[].chapterVo`. Preserve existing chapter `id` while editing a chapter.
- Chapter fields: `id` (updates), `title`, `sort`, `coverImageOssId`, `achievementVideoOssId`, `achievementName`, `achievementDescription`.

## Course

- Package lookup: `GET /business/admin/course_package/list?pageNum=1&pageSize=100&courseName=…`. In the observed response, results are at root `rows[]` (not `data.rows[]`); tolerate either shape. Accept only the exact match in `rows[].name`; use its `id` as `coursePackageId`.
- Course lookup: `GET /business/course/list?pageNum=1&pageSize=100&name=…`. Prefer root `rows[]` and tolerate `data.rows[]` for compatibility. Accept only the exact match in `rows[].name`; use its `id` to fetch the course detail before updating.
- Course detail: `GET /business/course/{id}`. The course is `data.courseVo`; nodes are `data.courseNodeBoList`.
- Create / update: `POST` / `PUT /business/course`.
- Create required fields: `name`, `sort`, `desc`, `coursePackageId`, `chapterId`, `coverImageOssId`.
- Common fields: `name`, `courseShortTitle`, `typeStr`, `desc`, `coverImageOssId`, `videoOssId`, `sort`, `coursePackageId`, `chapterId`, `lessonFeedbackTitle`, `lessonSummaryShort`, `lessonValueShort`, `lessonKeywords`, `lessonReportHint`, `remark`, `tipName`, `tipDescription`, `planetImageOssId`, `knowledgePointsImage`, `status`, `courseNodeBoList`.
- `lessonKeywords` must be a delimiter-joined string, not a JSON array. Preserve the source string as supplied (for example `关键词一、关键词二` or `关键词一,关键词二`); do not split it before submitting the course payload.
- For course-node learning methods, use `GET /business/admin/learning-method/enabled-list`. Preserve node `id` when updating a node.

## Assets

- Upload: `POST /console/resource/oss/upload/public` with multipart fields `assetType` (normally `image`) and `file`.
- Use returned `data.ossId` in payloads. `data.url` is for preview only.
