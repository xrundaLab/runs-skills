---
name: runs-page-data
description: 当需要把本地图片 / 音频 / 视频上传到 RunS 服务，或需要编排、校验、提交智课端页面 JSON（顶层 pages[] 导入结构）时使用。覆盖素材上传、资产清单、占位符替换、组件结构校验与课件任务提交。
metadata: {"requires":{"bins":["node"]},"env":["XRUNS_COURSEWARE_BASE_URL","XRUNS_COURSEWARE_WEB_URL","XRUNS_COURSEWARE_TOKEN"]}
---

# RunS 页面数据编排

把「一堆本地图片 + 音频 + 文案」变成一份可批量导入、可直接解析的页面 JSON。

## 严格规则

### 禁止（NEVER）

- **不要把 token 明文写进对话回复、页面 JSON、报告或任何会提交的文件**。token 只落在 `.env`（已被 `.gitignore` 忽略），回显一律用掩码。
- **不要在命令行里长期硬编码 `--token` / `--base-url` / `--web-url`**。用户在对话里给了这三个值，就写进 `.env` 一次性固化，后续命令不再重复传参。
- **不要把本地路径、`file://`、`@asset:` 写进最终提交的 JSON**。所有媒体字段必须是上传后的 `public_url`；提交前 `pages:validate` 会拦截残留引用。
- **不要自己拼 `object_key` / `public_url`**。这两个值只能取上传凭证接口的返回，本地拼接会被服务端前缀校验拒绝（`object_key is not allowed for current user`）。
- **不要把 page 级组件和其他组件放在同一页**。page 级组件独占整页，混放会被前端渲染规则判为非法。
- **不要给素材开索引**。图片 / 音频 `should_index` 一律 `false`（脚本默认值），只有需要进知识库检索的文档才开。
- **不要为了「先把素材备好」而整目录扫描上传**。`assets:upload --dir` 会把目录里所有匹配后缀的文件全部上传，页面 JSON 用不到的草稿、原图、废弃配音也一并进服务端——这是浪费额度也是污染清单。默认走 `pages:resolve` 按需上传（见「标准流程」），只上传页面 JSON 真正引用到的素材。
- 不要在没有 `--yes` 的情况下认为已经提交成功；`pages:submit` 不带 `--yes` 只做校验预览。
- 不要绕过资产清单重复上传同一素材，清单是幂等与可追溯的唯一依据。
- 不要直接提交缺少 `coursewareId` 的 flow task。脚本必须先调用 `create-with-template` 创建课程，再把返回的 ID 交给 creator 继续处理。

### 必须（MUST）

- **任何写操作之前先跑 `pagedata.mjs config`**，确认 token / 网关 / 预览站点三项都已就位再动手；缺 token 就按下面的「配置」引导用户补齐，不要盲目重试。
- 用户指定模板名称时，先通过 `templates:list` 使用 `v1/business/creator/template/list` 查询，并按名称相似度解析业务 `templateId`；允许省略“模板 / 课件 / 课程”、忽略大小写、空格和标点，也容忍少量错字。找不到或多个候选匹配度接近时必须停止并报告候选项，**不要猜 ID**。
- 模板名称解析完成后，校验、创建模板课程和创建 flow task 必须复用同一个 `templateId`，不得在流程中重新选择模板。
- 流程固定为 **写页面 JSON（占位符）→ 解析占位符（按需上传）→ 校验 → 提交**，每步产物落盘，任何一步失败都不进入下一步。
- **上传范围以页面 JSON 的引用为准**：先写好带 `@asset:` 占位符的页面 JSON，再由 `pages:resolve` 只上传被引用到的素材。素材目录里有多少文件与上传多少无关。
- 素材上传与页面 JSON 编排必须共用同一份资产清单（默认 `assets.manifest.json`）。
- 无组件页（`components: []`）必须提供 `prompt`，否则该页没有任何可生成内容。
- 自带音频时把地址写进对应字段（`tts.content.url` / `infographic[].tts_url` / `immersive_explanation[].tts_url`）；**填了就不会被 media worker 重新生成**，留空才会触发 TTS。
- 提交前先跑一次 `pages:validate --template-id <id>` 或 `pages:validate --template <name>`，用模板组件白名单确认这些组件在目标模板里确实可用。
- 提交顺序固定为 **创建模板课程 → 携带 `coursewareId` 创建 flow task**；不要把 `category` / `parsePrompt` 从客户端透传给 creator。
- 报告结果时如实说明：上传了几个、跳过几个、失败几个，校验有几个错误几个告警。

---

## 操作路由

| 场景 | 命令 |
|------|------|
| 查看生效配置与来源（不发请求） | `pagedata.mjs config` |
| 验证 token / 网关连通 | `pagedata.mjs ping` |
| 查询可用模板及业务模板 ID | `pagedata.mjs templates:list` |
| **把 JSON 里的本地引用换成线上地址（同时按需上传，默认走这条）** | `pagedata.mjs pages:resolve` |
| 手动上传指定的几个文件（显式列文件名） | `pagedata.mjs assets:upload a.png b.mp3` |
| 校验页面 JSON 结构 | `pagedata.mjs pages:validate` |
| 提交课件任务并追踪 | `pagedata.mjs pages:submit` |
| 已有文档（pdf/docx/…）走做课任务 | 改用 `scripts/runs-courseware/cli.mjs tasks:create` |
| 查组件 content 结构 | [references/component-schemas.md](./references/component-schemas.md) |
| 查素材流水线细节 | [references/asset-pipeline.md](./references/asset-pipeline.md) |
| 抄一份页面 JSON 模板 | [references/example-page-data.json](./references/example-page-data.json) |

脚本入口：`.agents/skills/runs-page-data/scripts/pagedata.mjs`（Node 18+，无第三方依赖）。

---

## 配置

三项配置全部走 `.env`，用户说一次即可长期生效，不必每轮对话重复。

| 变量 | 含义 | 默认值 |
|------|------|--------|
| `XRUNS_COURSEWARE_BASE_URL` | 接口网关（脚本自动补 `/api/`） | `https://api.dev.xruns.cn/api/` |
| `XRUNS_COURSEWARE_WEB_URL` | 智课端站点：登录取 token 的地方，也用来拼课件预览链接 | `https://web.dev.xruns.cn/` |
| `XRUNS_COURSEWARE_TOKEN` | access token | **空，必填** |
| `XRUNS_COURSEWARE_USERNAME` / `_PASSWORD` | 可选，无 token 时登录换取 | 空 |

**优先级**：命令行参数 > 环境变量 > `.env` > 内置默认值。
**`.env` 查找顺序**：`$XRUNS_ENV_FILE` → `./.env` → `<技能目录>/.env` → `<仓库根>/.env`；先找到的先生效，只读 `XRUNS_` 前缀的键，已存在的真实环境变量不会被覆盖。

### 首次配置

```bash
cp .agents/skills/runs-page-data/.env.example .agents/skills/runs-page-data/.env
# 编辑 .env，填入 XRUNS_COURSEWARE_TOKEN
node .agents/skills/runs-page-data/scripts/pagedata.mjs config   # 看生效值与来源（token 掩码显示）
node .agents/skills/runs-page-data/scripts/pagedata.mjs ping     # 验证连通性
```

### 处理用户输入的三个值

- 用户在对话里给出 token / 网关地址 / 预览站点中的任意一个 → **先写进 `.env` 的对应键**（其余键保持已有值），再跑 `config` 回显确认，然后继续原任务。不要只用 `--token` 之类的临时参数把当前这条命令跑通。
- 用户只给了「预览链接」形式的地址（如 `https://web.dev.xruns.cn/creator/xxx`）→ 取其站点根写进 `XRUNS_COURSEWARE_WEB_URL`，不要把课件路径一起写进去。
- 用户没提但 `config` 显示缺 token → 停下来引导：**打开 `XRUNS_COURSEWARE_WEB_URL`（默认 https://web.dev.xruns.cn/ ）登录，DevTools → Application → Local Storage 复制 access token，或从 Network 面板任一请求的 `Authorization` 头去掉 `Bearer ` 前缀。** 拿到后由你写入 `.env`，不要让用户在对话里反复粘贴。
- 回显 token 一律掩码（`config` 命令已经这么做），不要在回复里贴完整值。

### 临时覆盖

一次性换环境（例如临时打生产）用命令行参数，不落盘：

```bash
node .agents/skills/runs-page-data/scripts/pagedata.mjs ping \
  --base-url https://api.xruns.cn/api/ --web-url https://web.xruns.cn/ --token <token>
```

或指定另一份配置文件：`XRUNS_ENV_FILE=./prod.env node ... pagedata.mjs ping`。

---

## 标准流程

### 0. 确定目标模板

用户给业务模板 ID 时直接使用：

```bash
--template-id <templateId>
```

用户给模板名称时，先查询确认：

```bash
node .agents/skills/runs-page-data/scripts/pagedata.mjs templates:list \
  --keyword "银河互动课件"
```

`pages:validate` 和 `pages:submit` 也支持直接传 `--template "模板名称"`，脚本会通过
`GET v1/business/creator/template/list` 遍历当前用户可用模板，将用户输入归一化后按名称相似度
排序并解析业务 `templateId`。完整名称唯一命中时直接使用；用户省略后缀、标点或有少量错字时，
只有最佳候选明显领先才自动使用。无匹配或多个候选过于接近时脚本会中止并列出候选 ID。

### 1. 写页面 JSON，媒体字段用占位符

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

素材目录里有 200 张图不代表要上传 200 张——**只有写进 JSON 的那几个 `@asset:` 会被上传**。所以先把页面编排定下来，再动上传。

### 2. 解析占位符（在这一步按需上传）

```bash
node .agents/skills/runs-page-data/scripts/pagedata.mjs pages:resolve ./page.json \
  --manifest ./assets.manifest.json --out ./page.resolved.json
```

- 只处理页面 JSON 里出现的引用：清单里已有的直接复用 `url`，缺的就地上传补齐并写回清单。**没被引用的文件一个都不会传。**
- 清单按「相对清单目录的路径」为 key，记录 `url` / `fileId` / `sha256`；同路径同内容重跑直接跳过，改了内容才重传。
- 想先预检且不实际上传：加 `--no-upload`。命令会复用清单中已有的 URL，并把清单缺失的引用逐条报错；这些缺失项就是去掉参数后将即时上传的候选素材。预检存在缺失项时不会写出文件。
- 存在未解析引用时不写出文件。

### 3. 校验

```bash
node .agents/skills/runs-page-data/scripts/pagedata.mjs pages:validate ./page.resolved.json \
  --template "银河互动课件"
```

也可用已知的 `--template-id <templateId>`。校验内容：顶层结构 → 组件类型是否已知、是否在模板白名单内 → content 结构与必填字段 → page 级组件独占整页 → 是否残留本地引用。`✗` 是错误（阻断提交），`!` 是告警（如音色不在推荐表、缺 `tag`、`componentId` 重复）。

### 4. 提交

```bash
# 先预览（不带 --yes 只做校验和摘要）
node .agents/skills/runs-page-data/scripts/pagedata.mjs pages:submit ./page.resolved.json \
  --template "银河互动课件"

# 确认后提交并追踪
node .agents/skills/runs-page-data/scripts/pagedata.mjs pages:submit ./page.resolved.json \
  --template "银河互动课件" --yes --watch --report ./report.csv
```

`--template <name>` 与 `--template-id <id>` 二选一。使用名称时，脚本会先打印
`模板解析：<name> → <templateId>`，后续请求统一使用解析出的 ID。

提交成功后脚本会打印 `预览链接：<XRUNS_COURSEWARE_WEB_URL>creator/<coursewareId>`，报告里也有 `coursewareUrl` 一列。**报告结果时把这个链接原样给用户**；链接域名取自 `XRUNS_COURSEWARE_WEB_URL`，不要自己拼或从网关地址推导。

实际提交时，脚本先调用 `POST v1/business/creator/courseware/create-with-template` 创建模板课程，再把返回的 `coursewareId` 放进 `POST v1/creator/courseware/flow/task`。creator 会读取该课程的模板、分类和 parsePrompt 后继续解析、建页、媒体与 HTML 流程，不会再次创建课程。

如果课程创建成功但 flow task 提交失败，脚本使用 `FAILED_TO_SUBMIT` 输出并在报告中保留 `fsFileId`、`coursewareId` 和稳定预览链接；排障时复用这些 ID，不要重新创建课程。

两种提交模式：

| 模式 | 参数 | 请求体 | 适用 |
|------|------|--------|------|
| 内联结构化 JSON | 默认 | `{ templateId, coursewareId, structuredJson, batchNo }` | 单份页面数据，链路最短 |
| 上传文件 + 直接解析 | `--as-file` | `{ templateId, coursewareId, fsFileId, direct: true, batchNo }` | 需要留存 JSON 文件、与智课端批量导入入口同一条链路 |

批量导入多份 JSON 时也可以直接复用现成 CLI：

```bash
node scripts/runs-courseware/cli.mjs tasks:create --template-id <id> --direct ./out/*.json --watch
```

---

## 什么时候才用 `assets:upload`

`pages:resolve` 已经覆盖了 99% 的上传需求，`assets:upload` 只是「手动补一发」的口子，用的时候**始终显式列出文件**：

```bash
# 只传这两个，其他文件不动
node .agents/skills/runs-page-data/scripts/pagedata.mjs assets:upload \
  ./course-assets/images/cover.png ./course-assets/audio/intro.mp3 \
  --manifest ./assets.manifest.json
```

适用场景仅限：
- 页面 JSON 还没写，但要先拿到某个素材的 `public_url` 贴到别处；
- 某个素材内容改了，想在 resolve 之前用 `--force` 单独重传覆盖清单条目。

`--dir` 是**整目录递归扫描并全部上传**，只有用户明确要求「把这个目录都传上去」时才用，且必须：

1. 先 `--dry-run` 打印待传清单；
2. 把文件数和总体积告诉用户，确认后才去掉 `--dry-run`；
3. 需要收窄范围时配合 `--ext`（如 `--ext mp3`）或换成显式文件列表。

判断标准很简单：**如果这个文件不会出现在最终页面 JSON 里，它就不该被上传。**

---

## 关键约束速查

| 事项 | 约束 |
|------|------|
| 上传凭证有效期 | 60 秒，取到即用，不要预取一批 |
| 单文件大小 | ≤ 100MB |
| `object_key` / `public_url` | 只能用凭证接口返回值，且两者必须匹配 |
| 模板选择 | `--template <name>` 与 `--template-id <id>` 二选一；名称支持模糊匹配，候选接近时必须改用明确 ID |
| `should_index` | 素材一律 `false` |
| page 级组件 | `course_intro` / `course_task` / `course_summary` / `image_save` / `infographic` / `immersive_explanation` / `select_question` / `galaxy_select_question` / `matching_question` / `ordering_question` / `categorization_question` —— 每页只能有一个，且不能与其他组件同页 |
| block 级组件 | `text` / `rich_text` / `image` / `video` / `avatar` / `tts` / `podcast` / `word_card` / `learning_report` —— 可同页组合 |
| 音频是否重生 | `tts_url` / `url` 已填 → 保留；留空且 `tts_text` 非空 → media worker 调 TTS 生成 |
| 默认音色 | `zh_female_yingyujiaoxue_uranus_bigtts` |

---

## 测试

```bash
node --test .agents/skills/runs-page-data/scripts/pagedata.test.mjs
```
