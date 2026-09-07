---
name: runs-course-admin
description: Manage RunSi (润思) admin course-package and course data through the management API. Use when adding, editing, inspecting, or uploading assets for online course packages or courses, including selecting development versus production before making API requests.
---

# 润思课程后台

Use the bundled script for all API calls. It keeps hosts and request headers consistent, reads the selected environment's admin token from the macOS Keychain, checks the core payload requirements, and refuses write requests without an explicit confirmation flag.

## One-time credential setup

Do not add tokens to `SKILL.md`, shell history, source code, a request payload, or chat output. Configure **each environment separately**; development and production credentials never fall back to one another:

```bash
# 通过静默交互输入 token：不回显、不进入 shell history，命令文本中也永不出现 token
# （禁止用 export 直接携带真实 token 录入，例如 export RUNS_ADMIN_TOKEN 等于号后接真实 token）
printf 'Paste the development admin token (input is hidden): '
read -rs RUNS_ADMIN_TOKEN
echo
export RUNS_ADMIN_TOKEN
python3 scripts/runs_course_admin.py --env development configure-token
# 在拿到生产管理员 token 后，再单独静默配置生产环境：
printf 'Paste the production admin token (input is hidden): '
read -rs RUNS_ADMIN_TOKEN
echo
python3 scripts/runs_course_admin.py --env production configure-token
unset RUNS_ADMIN_TOKEN
```

Use a fresh token if API responses indicate it has expired. `configure-token` never prints the token. If the selected environment has no saved token, ask the user for that environment's token; never substitute another environment's credential.

## Required interaction and safety flow

1. Before every API request, ask the user to choose **开发环境** or **生产环境**; do not infer it from prior messages. Pass the chosen value as `--env development` or `--env production`.
2. For an edit, fetch the existing object first and show a concise proposed field-level diff. Preserve unmentioned fields and IDs.
3. Upload every supplied local image/video first; put the returned `ossId` in the relevant payload field and show its preview `url`.
4. Before a create or update, show the target environment, object identifier/name, and exact changed fields. Ask for explicit confirmation. Only after confirmation, invoke the write command with `--confirm`.
5. Treat production writes as high impact: repeat the production target in the confirmation question. Never use `--confirm` based merely on the user having asked to make a change.
6. Report the API response. Fetch the object afterwards where an ID is known to verify the persisted values.

Fixed hosts: development is `https://api.dev.xruns.cn`; production is `https://api.xruns.cn`.

## Commands

Run commands from this skill directory, or use absolute paths. All results are JSON.

```bash
# Reads
python3 scripts/runs_course_admin.py --env development get-package --id PACKAGE_ID
python3 scripts/runs_course_admin.py --env development find-package --name '课包全名'
python3 scripts/runs_course_admin.py --env development get-course --id COURSE_ID
python3 scripts/runs_course_admin.py --env development find-course --name '课程全名'
python3 scripts/runs_course_admin.py --env development learning-methods

# Asset upload (returns data.ossId and data.url)
python3 scripts/runs_course_admin.py --env development upload --file /absolute/path/image.png --asset-type image

# Writes: require a reviewed JSON payload and --confirm
python3 scripts/runs_course_admin.py --env development create-package --json /absolute/path/package.json --confirm
python3 scripts/runs_course_admin.py --env production update-package --json /absolute/path/package.json --confirm
python3 scripts/runs_course_admin.py --env development create-course --json /absolute/path/course.json --confirm
python3 scripts/runs_course_admin.py --env production update-course --json /absolute/path/course.json --confirm
```

For creating a course, use `find-package` with its complete course-package name. It only succeeds on exactly one full-name match. Fetch that package and use a `chapterAndCourseList[].chapterVo.id` as `chapterId`.

When a user requests a course update by name, use `find-course` with the full course name. It only succeeds on exactly one full-name match; then use the returned `id` with `get-course` before proposing the update.

Read [references/api-fields.md](references/api-fields.md) when preparing a package/course payload or interpreting API results.
