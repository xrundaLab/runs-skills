---
name: runs-page-data
description: 当需要把本地图片 / 音频 / 视频上传到 RunS 服务，需要编排、校验、提交智课端页面 JSON（顶层 pages[] 导入结构），或需要修改某个已有课件（用户给出 /creator/<coursewareId> 链接或课件 ID）的页面数据时使用。覆盖素材上传、资产清单、占位符替换、组件结构校验、课件任务提交与已有课件的读—改—写。
metadata: {"requires":{"bins":["node"]},"env":["XRUNS_COURSEWARE_BASE_URL","XRUNS_COURSEWARE_WEB_URL","XRUNS_COURSEWARE_TOKEN"]}
---

# RunS 页面数据编排

把「一堆本地图片 + 音频 + 文案」变成一份可批量导入、可直接解析的页面 JSON；也负责改已经建好的课件。

**先分清用户要哪一件事**：

| 用户的说法 | 走哪条链路 |
|------------|-----------|
| 「把这门课上传 / 提交到 RunS」「用某模板生成课件」 | 新建：`pages:submit`，见「标准流程」 |
| 「改一下 https://web.dev.xruns.cn/creator/xxx 的第 3 页」「把这个课件的某段文案换掉」 | 修改：`courseware:update`，见「修改已有课件」 |

拿到 `/creator/<id>` 链接却去跑 `pages:submit`，会**新建一个课件**（另一个链接），而不是改用户给的那一个。

## 严格规则

### 禁止（NEVER）

- **不要把 token 明文写进对话回复、页面 JSON、报告或任何会提交的文件**。token 只落在 `.env`（已被 `.gitignore` 忽略），回显一律用掩码。
- **不要在命令行里长期硬编码 `--token` / `--base-url` / `--web-url`**。用户在对话里给了这三个值，就写进 `.env` 一次性固化，后续命令不再重复传参。
- **不要把本地路径、`file://`、`@asset:` 写进最终提交的 JSON**。所有媒体字段必须是上传后的 `public_url`；提交前 `pages:validate` 会拦截残留引用。
- **不要自己拼 `object_key` / `public_url`**。这两个值只能取上传凭证接口的返回，本地拼接会被服务端前缀校验拒绝（`object_key is not allowed for current user`）。
- **不要把 page 级组件和其他组件放在同一页**。page 级组件独占整页，混放会被前端渲染规则判为非法。
- **不要给素材开索引**。图片 / 音频 `should_index` 一律 `false`（脚本默认值），只有需要进知识库检索的文档才开。
- **不要为了「先把素材备好」而整目录扫描上传**。`assets:upload --dir` 会把目录里所有匹配后缀的文件全部上传，页面 JSON 用不到的草稿、原图、废弃配音也一并进服务端——这是浪费额度也是污染清单。默认走 `pages:resolve` 按需上传（见「标准流程」），只上传页面 JSON 真正引用到的素材。
- 不要在没有 `--yes` 的情况下认为已经提交成功；`pages:submit` / `courseware:update` 不带 `--yes` 只做校验预览。
- 不要绕过资产清单重复上传同一素材，清单是幂等与可追溯的唯一依据。
- 不要直接提交缺少 `coursewareId` 的 flow task。脚本必须先调用 `create-with-template` 创建课程，再把返回的 ID 交给 creator 继续处理。
- **不要用 `pages:submit` 去「改」已有课件**。它必然新建课件；把已有 coursewareId 交给 flow task 也只是整体重刷（页面全替换、pageId 全丢、媒体与 HTML 全量重跑）。改已有课件只能走 `courseware:update`。
- **不要在课件还有未完成任务时写入**。`courseware:update` 会先查 `flow/active` 并在有任务时中止：任务的阶段 job 拿着 pinned 版本原位写库，这时插一次保存，要么自己被 CAS 拒，要么把任务顶成 `CONFLICTED`（生成结果直接作废）。让用户等任务跑完或去创作页中断，不要自己去 abort。
- **不要手工拼保存请求或自己维护 revision**。`expectedRevision` 只能来自本次读回的详情，`courseware:update` 在一条命令里完成读—改—写；不要把版本号、pageId 存到文件里跨命令复用。

### 必须（MUST）

- **任何写操作之前先跑 `pagedata.mjs config`**，确认 token / 网关 / 预览站点三项都已就位再动手；缺 token 就按下面的「配置」引导用户补齐，不要盲目重试。
- 用户指定模板名称时，先通过 `templates:list` 使用 `v1/business/creator/template/list` 查询，并按名称相似度解析业务 `templateId`；允许省略“模板 / 课件 / 课程”、忽略大小写、空格和标点，也容忍少量错字。找不到或多个候选匹配度接近时必须停止并报告候选项，**不要猜 ID**。
- 模板名称解析完成后，校验、创建模板课程和创建 flow task 必须复用同一个 `templateId`，不得在流程中重新选择模板。
- 组件校验必须指定模板，并且只使用 `GET v1/business/creator/template/{templateId}/components` 返回的 `componentType` / `compositionMode` 与 `GET v1/business/creator/component/{componentId}` 返回的 `dataStructure`。**没有模板、不在模板内、没有可解析 `dataStructure` 都必须停止，不允许本地规格兜底或强制跳过。**
- 流程固定为 **写页面 JSON（占位符）→ 解析占位符（按需上传）→ 校验 → 提交**，每步产物落盘，任何一步失败都不进入下一步。
- **上传范围以页面 JSON 的引用为准**：先写好带 `@asset:` 占位符的页面 JSON，再由 `pages:resolve` 只上传被引用到的素材。素材目录里有多少文件与上传多少无关。
- 素材上传与页面 JSON 编排必须共用同一份资产清单（默认 `assets.manifest.json`）。
- 无组件页（`components: []`）必须提供 `prompt`，否则该页没有任何可生成内容。
- 自带音频时把地址写进对应字段（`tts.content.url` / `infographic[].tts_url` / `immersive_explanation[].tts_url`）；**填了就不会被 media worker 重新生成**，留空才会触发 TTS。
- 提交前先跑一次 `pages:validate --template-id <id>` 或 `pages:validate --template <name>`，用模板组件白名单确认这些组件在目标模板里确实可用。
- 提交顺序固定为 **创建模板课程 → 携带 `coursewareId` 创建 flow task**；不要把 `category` / `parsePrompt` 从客户端透传给 creator。
- 改已有课件前**先 `courseware:pull` 看一眼**：页序、`pageId`、每页有哪些组件都以服务端为准，补丁要按 `pageId` 定位，不要按记忆或页序猜。
- 改完之后**主动告诉用户「已生成的 HTML 和音频不会跟着变」**，并说明需要时可以加 `--regen-html` / `--regen-media` 重跑；fork 了新版本还要说明「线上仍读旧的已发布版本，需要重新发布」。
- 报告结果时如实说明：上传了几个、跳过几个、失败几个，校验有几个错误几个告警；改课件还要说清改了哪几页、是原位更新还是 fork 了新版本、落库后的版本与 revision。

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
| 新建课件并提交生成任务 | `pagedata.mjs pages:submit` |
| **看已有课件现在长什么样（只读）** | `pagedata.mjs courseware:pull <链接\|课件ID>` |
| **改已有课件的页面数据** | `pagedata.mjs courseware:update <链接\|课件ID> <补丁.json>` |
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

也可用已知的 `--template-id <templateId>`；二者必须提供一个。脚本先读取模板组件清单，再按实际用到的 `componentType` 拉取组件详情：模板清单决定组件是否可用及 `compositionMode`，`dataStructure` 是 content 的唯一结构依据。

校验只关注结构完整性：`dataStructure` 对象中的字段必须全部存在、对象/数组层级必须一致、示例数组非空时实际数组也必须非空且逐项结构完整；允许额外字段，也允许字符串/数字/布尔值等标量类型互换，不检查 URL 格式、枚举、文案语义等业务取值。缺模板、模板未配置组件、缺少/损坏 `dataStructure`、结构缺字段都会以 `✗` 阻断提交，不能用 `--force` 绕过。`!` 只用于缺 `tag`、`componentId` 重复等非结构告警。

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

---

## 修改已有课件

用户给了 `/creator/<coursewareId>` 链接或课件 ID 要改内容时走这条。整条链路是**读—改—写在一条命令里闭环**：命令自己拉最新详情、合并你的改动、校验、提交，中间不落任何状态文件，因此不存在「版本号过期了要重新拉」这种用户流程。

### 1. 先看现状

```bash
node .agents/skills/runs-page-data/scripts/pagedata.mjs courseware:pull \
  https://web.dev.xruns.cn/creator/e7c6c8f9f0c44905aaa73edc403fab3c --out ./current.json
```

只读，不写任何东西。会打印版本状态、模板 ID，以及每页的 `pageId` / `renderType` / 组件数，并把课件导出成和页面 JSON 同构的 `{ title, pages[] }`——**补丁就照着这份文件里的 `pageId` 写**。

链接第二段（`/creator/<id>/<version>`）是精确 versionId，不是 V1/V2 这种版本号；不带它就是当前工作版本。

### 2. 写补丁，只写要改的页

```json
{
  "pages": [
    {
      "pageId": "1893...",
      "title": "光合作用的两个阶段",
      "components": [{ "type": "infographic", "content": [{ "img_url": "@asset:images/step-1.png" }] }]
    }
  ]
}
```

合并规则：

- 按 `pageId` 定位（没有就按 `pageNumber`），**不做隐式按位置匹配**；
- 只在**顶层字段**合并：补丁里出现的键覆盖，没出现的键保留服务端值 —— 已生成的 `output`（HTML）、`tts_url`（音频）因此不会被抹掉；
- `components` 是整个数组替换，不做逐组件深合并；
- 默认模式只能改已有页。**新增页、删除页、调整页序要用 `--replace`**：那时补丁就是完整页面列表，未出现的页会被删除（服务端保存语义就是「缺页 = 删页」）。

补丁里可以照常写 `@asset:` 占位符，提交前先跑一次 `pages:resolve`（校验会拦下残留的本地引用）。

### 3. 预览 → 写入

```bash
# 不带 --yes：只做合并、校验和差异预览，不写任何东西
node .agents/skills/runs-page-data/scripts/pagedata.mjs courseware:update \
  https://web.dev.xruns.cn/creator/e7c6c8f9f0c44905aaa73edc403fab3c ./patch.json

# 确认后写入
node .agents/skills/runs-page-data/scripts/pagedata.mjs courseware:update \
  https://web.dev.xruns.cn/creator/e7c6c8f9f0c44905aaa73edc403fab3c ./patch.json --yes
```

命令内部按这个顺序执行，任何一步不过就地停下，不会留下半成品：

1. **活跃任务闸门** —— `GET flow/active`，有未完成任务就中止并报出 `taskId`；
2. **读目标版本**并判定可写性（唯一谓词：`isCurrentVersion && status=DRAFT && !isPublished`）：
   - 可写 → **原位更新**当前工作版本；
   - 只读（已发布 / 历史版本）→ **自动 fork**：`rollback` 把该版本克隆成新的 DRAFT 当前版本，回查确认版本号确实变大后，把补丁里的 `pageId` 按页序换算到新版本，再在新版本上更新；
3. **按模板校验**（模板取课件详情里的 `templateId`，可用 `--template-id` / `--template` 覆盖）。存量课件常有早于当前模板契约的老页面，因此只有**本次改动到的页**的结构错误会阻断保存，未改动页的问题降级为 `!` 告警照常报出；
4. **提交完整页面快照** `UPDATE_VERSION` + `expectedRevision` CAS。撞 `40901 STALE_REVISION` 会自动重读一次、在最新内容上重放同一份补丁并换新 `requestId` 再提交；其余冲突码（版本已发布 / 已不是当前版本）直接停下，重跑命令即可（那时会自动走 fork）。

补丁与服务端内容完全一致时命令会直接结束，不做空写入（避免白白推进 revision）。

### 4. 改完之后

页面已生成的 HTML 和音频**不会**跟着内容自动更新。需要时显式重跑（服务端同步等待任务结束，页多会比较慢）：

```bash
node .agents/skills/runs-page-data/scripts/pagedata.mjs courseware:update <链接> ./patch.json --yes --regen-html
```

fork 出的新版本是 DRAFT，线上课程仍在读原来那个已发布版本，需要用户到创作页重新发布才会生效——这句一定要跟用户讲清楚。

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
| page / block 级别 | 只认模板组件接口的 `compositionMode`；page 级每页只能有一个且不能混放 |
| 模板组件结构 | 只认组件详情接口的 `dataStructure`；字段和容器结构必须完整，额外字段与标量值放行 |
| 音频是否重生 | `tts_url` / `url` 已填 → 保留；留空且 `tts_text` 非空 → media worker 调 TTS 生成 |
| 默认音色 | `zh_female_yingyujiaoxue_uranus_bigtts` |
| 改课件的写入语义 | 只有 `UPDATE_VERSION`；请求体是**完整页面快照**，缺页 = 删页 |
| 版本可写谓词 | `isCurrentVersion && status === "DRAFT" && isPublished !== true`，三者缺一即只读 |
| 只读版本怎么改 | `rollback` 克隆成新的 DRAFT 当前版本（`courseware:update` 自动完成），原已发布版本不受影响 |
| 保存冲突码 | `40901` revision 过期（自动重放一次）／`40902` requestId 撞内容／`40903` 已非当前版本／`40904` 已发布，后三者不重试 |
| 改完的媒体与 HTML | 不会自动更新，要显式 `--regen-media` / `--regen-html` |

---

## 测试

```bash
node --test .agents/skills/runs-page-data/scripts/pagedata.test.mjs
```
