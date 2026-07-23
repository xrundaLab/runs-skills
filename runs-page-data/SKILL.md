---
name: runs-page-data
description: 当需要把本地图片 / 音频 / 视频上传到 RunS 服务，或需要编排、校验、提交智课端页面 JSON（顶层 pages[] 导入结构）时使用。覆盖素材上传、资产清单、占位符替换、组件结构校验与课件任务提交。
version: 1.0.0
metadata: {"requires":{"bins":["node"]},"env":["XRUNS_COURSEWARE_BASE_URL","XRUNS_COURSEWARE_TOKEN"]}
---

# RunS 页面数据编排

把「一堆本地图片 + 音频 + 文案」变成一份可批量导入、可直接解析的页面 JSON。

## 严格规则

### 禁止（NEVER）

- **不要把本地路径、`file://`、`@asset:` 写进最终提交的 JSON**。所有媒体字段必须是上传后的 `public_url`；提交前 `pages:validate` 会拦截残留引用。
- **不要自己拼 `object_key` / `public_url`**。这两个值只能取上传凭证接口的返回，本地拼接会被服务端前缀校验拒绝（`object_key is not allowed for current user`）。
- **不要把 page 级组件和其他组件放在同一页**。page 级组件独占整页，混放会被前端渲染规则判为非法。
- **不要给素材开索引**。图片 / 音频 `should_index` 一律 `false`（脚本默认值），只有需要进知识库检索的文档才开。
- 不要在没有 `--yes` 的情况下认为已经提交成功；`pages:submit` 不带 `--yes` 只做校验预览。
- 不要绕过资产清单重复上传同一素材，清单是幂等与可追溯的唯一依据。

### 必须（MUST）

- 流程固定为 **上传素材 → 解析占位符 → 校验 → 提交**，每步产物落盘，任何一步失败都不进入下一步。
- 素材上传与页面 JSON 编排必须共用同一份资产清单（默认 `assets.manifest.json`）。
- 无组件页（`components: []`）必须提供 `prompt`，否则该页没有任何可生成内容。
- 自带音频时把地址写进对应字段（`tts.content.url` / `infographic[].tts_url` / `immersive_explanation[].tts_url`）；**填了就不会被 media worker 重新生成**，留空才会触发 TTS。
- 提交前先跑一次 `pages:validate --template-id <id>`，用模板组件白名单确认这些组件在目标模板里确实可用。
- 报告结果时如实说明：上传了几个、跳过几个、失败几个，校验有几个错误几个告警。

---

## 操作路由

| 场景 | 命令 |
|------|------|
| 验证 token / 网关连通 | `pagedata.mjs ping` |
| 批量上传图片、音频、视频、字幕 | `pagedata.mjs assets:upload` |
| 把 JSON 里的本地引用换成线上地址 | `pagedata.mjs pages:resolve` |
| 校验页面 JSON 结构 | `pagedata.mjs pages:validate` |
| 提交课件任务并追踪 | `pagedata.mjs pages:submit` |
| 已有文档（pdf/docx/…）走做课任务 | 改用 `scripts/runs-courseware/cli.mjs tasks:create` |
| 查组件 content 结构 | [references/component-schemas.md](./references/component-schemas.md) |
| 查素材流水线细节 | [references/asset-pipeline.md](./references/asset-pipeline.md) |
| 抄一份页面 JSON 模板 | [references/example-page-data.json](./references/example-page-data.json) |

脚本入口：`.agents/skills/runs-page-data/scripts/pagedata.mjs`（Node 18+，无第三方依赖）。

---

## 鉴权

与 `scripts/runs-courseware/cli.mjs` 共用同一套环境变量：

```bash
export XRUNS_COURSEWARE_BASE_URL="https://web.dev.xruns.cn"   # 站点域名即可，脚本自动补 /api/
export XRUNS_COURSEWARE_TOKEN="智课端登录态里的 access token"
# 或者用账号密码，脚本运行时登录换取 token
export XRUNS_COURSEWARE_USERNAME="账号"
export XRUNS_COURSEWARE_PASSWORD="密码"
```

先跑 `node .agents/skills/runs-page-data/scripts/pagedata.mjs ping` 确认可用，再做任何写操作。

---

## 标准流程

### 1. 上传素材，产出资产清单

```bash
node .agents/skills/runs-page-data/scripts/pagedata.mjs assets:upload \
  --dir ./course-assets \
  --manifest ./assets.manifest.json
```

- 递归扫描目录，默认只收图片 / 音频 / 视频 / 字幕后缀（`--ext png,mp3` 可覆盖）。
- 清单按「相对清单目录的路径」为 key，记录 `url` / `fileId` / `sha256`；**同路径同内容重跑直接跳过**，改了内容才重传。
- 先 `--dry-run` 看一遍将要上传什么，再实际执行。

### 2. 写页面 JSON，媒体字段用占位符

素材位置用 `@asset:` 引用，路径相对资产清单所在目录：

```json
{
  "type": "infographic",
  "content": [
    {
      "img_url": "@asset:images/step-1.png",
      "tts_text": "叶片像一块小小的太阳能板。",
      "tts_url": "@asset:audio/step-1.mp3",
      "voice": "S_HJjtPNs22"
    }
  ]
}
```

顶层结构、各组件 content 结构见 [references/component-schemas.md](./references/component-schemas.md)。

### 3. 解析占位符

```bash
node .agents/skills/runs-page-data/scripts/pagedata.mjs pages:resolve ./page.json \
  --manifest ./assets.manifest.json --out ./page.resolved.json
```

清单里缺的素材会就地上传补齐并写回清单；只想用现成清单就加 `--no-upload`（缺条目直接报错）。存在未解析引用时不写出文件。

### 4. 校验

```bash
node .agents/skills/runs-page-data/scripts/pagedata.mjs pages:validate ./page.resolved.json \
  --template-id <templateId>
```

校验内容：顶层结构 → 组件类型是否已知、是否在模板白名单内 → content 结构与必填字段 → page 级组件独占整页 → 是否残留本地引用。`✗` 是错误（阻断提交），`!` 是告警（如音色不在推荐表、缺 `tag`、`componentId` 重复）。

### 5. 提交

```bash
# 先预览（不带 --yes 只做校验和摘要）
node .agents/skills/runs-page-data/scripts/pagedata.mjs pages:submit ./page.resolved.json \
  --template-id <templateId>

# 确认后提交并追踪
node .agents/skills/runs-page-data/scripts/pagedata.mjs pages:submit ./page.resolved.json \
  --template-id <templateId> --yes --watch --report ./report.csv
```

两种提交模式：

| 模式 | 参数 | 请求体 | 适用 |
|------|------|--------|------|
| 内联结构化 JSON | 默认 | `{ templateId, structuredJson, batchNo }` | 单份页面数据，链路最短 |
| 上传文件 + 直接解析 | `--as-file` | `{ templateId, fsFileId, direct: true, batchNo }` | 需要留存 JSON 文件、与智课端批量导入入口同一条链路 |

批量导入多份 JSON 时也可以直接复用现成 CLI：

```bash
node scripts/runs-courseware/cli.mjs tasks:create --template-id <id> --direct ./out/*.json --watch
```

---

## 关键约束速查

| 事项 | 约束 |
|------|------|
| 上传凭证有效期 | 60 秒，取到即用，不要预取一批 |
| 单文件大小 | ≤ 100MB |
| `object_key` / `public_url` | 只能用凭证接口返回值，且两者必须匹配 |
| `should_index` | 素材一律 `false` |
| page 级组件 | `course_intro` / `course_task` / `course_summary` / `image_save` / `infographic` / `immersive_explanation` / `select_question` / `galaxy_select_question` / `matching_question` / `ordering_question` / `categorization_question` —— 每页只能有一个，且不能与其他组件同页 |
| block 级组件 | `text` / `rich_text` / `image` / `video` / `avatar` / `tts` / `podcast` / `word_card` / `learning_report` —— 可同页组合 |
| 音频是否重生 | `tts_url` / `url` 已填 → 保留；留空且 `tts_text` 非空 → media worker 调 TTS 生成 |
| 默认音色 | `S_HJjtPNs22`（李晶晶克隆音色） |

---

## 测试

```bash
node --test .agents/skills/runs-page-data/scripts/pagedata.test.mjs
```
