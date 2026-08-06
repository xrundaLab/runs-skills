# 拓展练习页 Compact 直接生成 OneShot（V3.5）

状态：`CURRENT_PRODUCTION_ASSET`  
合同版本：`RunS-PostClassTask-Compact-Direct-OneShot-Contract-v1.11-20260805`
适用模型：Kimi、GLM 及同类无外部文件上下文的页面生成模型。  
适用阶段：候选阶段 6 / 正式 P3 拓展练习页模型输入装配；完整 OneShot 写入整课 JSON 的 `pages[].prompt`。

## 1. 已验证结论

拓展练习页模型调用是一次性、无上下文调用。模型不会读取本地模板路径、历史提示词、SOP 文件或装配器资产，因此每一条页面提示词必须一次性包含完整要求、完整课程内容和完整可执行 HTML / CSS / JavaScript。

以下口径已经替代“只给变量对象、依赖模型读取路径或外部 Demo”的旧口径：

1. 模型输入第一行必须是内容寻址的提示词实例版本号，包含 OneShot 合同、资产 SHA-256 短指纹、本次归一化完整提示词 SHA-256 短指纹、课次、页号与 R36 后缀；同一 OneShot 的实际输入变化后不得复用旧版本号。
2. 模型输入必须说明这是一次性提示词，没有任何外部上下文。
3. 模型输入必须直接内嵌完整 Compact HTML / CSS / JavaScript，不得只给路径、模板名、变量对象或增量修改说明。
4. 最终回复只能是从 `<!doctype html>` 到 `</html>` 的完整 HTML，不得带 Markdown 围栏、解释、版本说明或调试文字。
5. `PAGE_DATA` 只作为阶段 6 的确定性装配输入；写入完整 OneShot 前，必须把冻结标题与有序任务块编译成静态 HTML DOM。页面运行时不得再通过 `PAGE_DATA`、循环或 `document.createElement()` 构造学生正文。
6. 模型输入不得携带 `source.rawMarkdown`、Markdown 代码围栏或以转义字符串形式嵌套整段原文；这些结构曾导致模型把 `text`、`\n` 和提示词正文直接显示为页面。
7. 上游审计仍保留完整原文、来源和页面规划；只是这些审计字段不进入模型提示词或学生 DOM。

## 2. 三层产物边界

| 层级 | 必须包含 | 禁止 |
| --- | --- | --- |
| 上游有效内容 | 原始拓展练习真源、块顺序、页面动作、来源定位、审计字段 | 把研发状态或路径做成学生内容 |
| 提交给 Kimi / GLM 的页面提示词 | 唯一版本号、页面身份、纯 HTML 输出约束、由当前课冻结内容确定性编译的完整静态 DOM、Compact CSS 与仅含 SDK / footer 行为的 JS | 只给路径、只给 JSON、运行时 `PAGE_DATA`、引用“上一版”、嵌套 Markdown 围栏、`rawMarkdown` |
| 模型输出 / 页面结果证据 | 可直接运行的完整 HTML | 提示词正文、Markdown 围栏、解释、版本号前缀、普通文本；不得覆盖 `pages[].prompt` |

## 3. 每课提示词固定开头

实际提交时，先替换所有尖括号占位，再把本课完整 HTML 代码直接接在“请根据下方完整代码输出网页：”之后。不得把本段外层 Markdown 围栏复制给模型。

```text
提示词版本号：<OneShot合同>-asset-<资产SHA前12位>-prompt-<归一化完整提示词SHA前12位>-<lesson_id>-<page_no>-R36-20260731

适用页面：<lessonXXX>｜<PXX>｜第 <N/N> 页｜拓展练习页。

配图增强合同：S6 已将 `visualAsset` 或 `planVisualAssets` 及其 resolved placement 预编译进完整 HTML。图片是正文主配图，禁止缩略图、小装饰条或图标尺寸；必须使用原生 `<img>` 和原始 URL/alt/displayLabel，按内容区宽度、自然比例、`object-fit: contain`、`16px` 圆角和 `16px` 上下间距呈现，不额外套独立卡片。课件配图必须执行 resolved 中模型看图审阅后的 placement；无法唯一判断时放在第一块正文之后。任何图片都不得成为正文最后一块或紧邻 CTA/footer。两张及以上图片必须按冻结顺序纵向全宽排列，禁止并排、宫格、三列或缩略图。每张图片必须由 `<button type="button" class="image-zoom-trigger">` 触发同页 `.visual-lightbox`；必须提供圆形 × 的 `.visual-lightbox-close`，图片水平、纵向居中，关闭控件水平居中放在图片底部与视口底部之间的纵向中点，且支持点击遮罩关闭与 `Escape` 关闭。禁止外链预览、打开新窗口或新标签页；缩放按钮不得调用 CreatorReviewSDK。

非开篇视觉基线：除主标题外所有正文、二级标题、列表、检查项和支持说明左对齐；故事顺序使用独立 `story-sequence-card`，不得改名为“任务要点”。必须声明并应用 `--runs-type-h1-size`、`--runs-type-h2-size`、`--runs-type-body-size`、`--runs-type-list-size`、`--runs-type-caption-size`。正文中的唯一 `.visual-gallery` 必须声明 `data-visual-group-layout="vertical_stack" data-visual-placement-terminal="forbidden"`。图片本体是唯一放大触发器，不显示独立查看按钮。遮罩 DOM 必须依次包含 `.visual-lightbox-dialog`、`.visual-lightbox-stage`、图片下方且不随图片移动的 `.visual-lightbox-close`，遮罩内不重复 caption。脚本必须提供 `positionVisualClose`，使用 `getBoundingClientRect` 实时计算关闭按钮中点位置；同时提供 `touchstart`、`touchmove`、1–4 倍两指缩放、放大后单指平移以及 `resetVisualTransform` 关闭复位，并保留遮罩与 `Escape` 关闭。

请生成一个完整、可运行的移动端 HTML 网页。

这是一次性提示词，没有任何外部上下文。不得读取文件、路径、历史模板或其他说明。网页所需的课程内容、样式、HTML 和 JavaScript 已全部包含在本提示词中。

最终回复必须且只能包含完整 HTML：

- 第一个字符必须属于 <!doctype html>。
- 最后一个标签必须是 </html>。
- 不得输出解释、Markdown 围栏、版本说明、调试信息或提示词正文。
- 不得只输出 PAGE_DATA、promptLines、text、数组、JSON 或普通文字。
- 不得把 JavaScript 数据、字段名或转义字符直接显示在页面顶层。
- 学生正文必须已经存在于静态 HTML DOM；不得依赖 JavaScript 执行后才出现。
- 必须保留正式完整结构：`.post-task-page`、`.task-hero`、`.notebook-badge`（只含 `https://res.xrunda.com/xruns/static/image/20270724/3.png`，竖屏 CSS 视觉尺寸 `76×76px`，无底色和对号）和 `.task-content`；不得退化为只有标题与白色文本卡的简化 HTML。
- 必须完整保留下方 HTML、CSS、JavaScript 和学生可见内容。
- 不得生成教案中不存在的任务、Prompt、决定、安全提醒或其他模块。
- 底部课程按钮必须按 pageAction 调用 CreatorReviewSDK.nextPage() 或 CreatorReviewSDK.complete()。
- 不得生成手机壳、评审侧栏、平台顶部壳层、页面类型胶囊、播放器、输入框、提交表单或 Powered by RunS。
- 页面正文允许纵向滚动；固定底栏不得遮挡正文。
- 如果规则与代码发生冲突，以“输出下方完整可运行 HTML”为最高优先级。

请根据下方完整代码输出网页：

<此处必须直接内嵌当前课完整 Compact HTML，从 <!doctype html> 到 </html>；不得写路径或省略号>
```

### 3.1 配套完整实例（lesson008）

`03a_课后任务页_Compact静态DOM完整实例_lesson008.md` 是本合同的完整、可直接提交实例：包含实际模型输入和已预编译的静态学生 DOM。它用于确认完整嵌入形态，不替代每课按冻结 `effective_content_full.json` 编译出的页面实例。

- 不得把实例中的 lesson008 文案复用到其他课程；其他课必须按自身来源内容编译。
- lesson017 / P08 已用同一合同完成跨课迁移验证：单 Prompt、无独立任务卡、无 safety 模块，且标题仅保护最小语义单元“社区拼图交换”，避免整句禁止换行。

## 4. 上游数据与静态 DOM 编译合同

阶段 5 的拓展练习标题、八类有序 sections、每块确定性 `role` 和 `pageAction` 是阶段 6 的唯一装配输入。`role` 只描述源块在任务流程中的展示职责，不改写内容：`lead`、`preflight`、`action`、`prompt`、`review`、`checklist`、`condition`、`correctivePrompt`、`decision`、`safetyFallback`、`fallback`、`note`。装配器逐块做 HTML 转义后，按原顺序确定性编译为最终 HTML：

- `paragraph`、`task`、`facts`、`step`、`prompt`、`decision`、`safety`、`fallback` 只在来源真实存在时生成对应静态节点；
- 多行 Prompt 使用 `<pre class="task-prompt">` 与 `white-space:pre-wrap` 保存真实换行，不拆字、不合并、不改写；
- 标题和每个内容块在模型调用前已经存在于 HTML，模型不得新增、删除、调序或改写；
- `action→prompt`、`review→checklist`、`condition→correctivePrompt` 仅在来源中相邻时原位组成同一步；禁止跨块搜索、全局后置 Prompt 或改变 `sections[]` 顺序；
- 所有操作相关块只生成一个“操作步骤”时间线；夹在首末操作角色之间的普通 `note` 保持原位成为独立步骤，不得把时间线拆成多段；`checklist` 使用浅色责任卡/检查清单结构，不得标成 Prompt 或套用深色代码卡；`lead` 直接位于标题下，不得重复生成“任务”卡；
- 内联 JavaScript 只保留与 `pageAction` 匹配的 `safeNextPage()` 或 `safeComplete()`、footer 高度同步、`ResizeObserver` 和按钮监听，不得包含正文渲染循环；
- 最终 OneShot 中禁止 `const PAGE_DATA =`、`PAGE_DATA.blocks.forEach`、`promptLines`、为正文调用 `document.createElement()`，也不得依赖运行时 `textContent` 才显示学生内容。

硬规则：

- `taskTitle`、正文、事实、操作说明、Prompt、决定、安全提醒和 fallback 均来自通过 P2 的有效页面内容，禁止概括、润色、补写或换序。
- `titleDisplay` 只允许为明确专名补中文全角双引号；不得回写 `taskTitle`。
- `actions` 数量按来源真实存在数量生成，不机械补成两步。
- lesson017 这类没有独立 `task`、第二段 Prompt 或 `safety` 的页面不得补造对应字段或 DOM。
- `pageAction` 来自页面规划；最后一页为 `complete`，其他页为 `next`。

### 4.1 `TASK_STATIC_DOM_V20_PROJECTION`（禁止正文压平与语义误装配）

阶段 6 必须按冻结 `sections[]` 的真实块类型，确定性投影为正式 Demo 已定义的富卡片 DOM；不得把任务、事实、步骤、检查或提示一律降级为 `.task-intro`，也不得把 Prompt 直接堆放为 `.task-content > pre`。

| 冻结块类型 | 仅在来源存在时输出的静态 DOM | 约束 |
| --- | --- | --- |
| `paragraph` / `task` | `lead` 投影为标题下 `.task-intro.task-lead`；`action/review/condition` 投影进对应 `.step-group`；`note` 才使用普通 `.task-intro` | 首个任务说明不得再重复为独立“任务”卡；所有文本逐字保留。 |
| `facts` | `<section class="glass-card facts-card">…<ul class="facts-grid"><li>…</li></ul></section>` | 每条来源事实独立为一个 `li`；不得显示 Markdown `**`。 |
| `step` / `prompt` / 操作角色 | 单一 `<section class="action-section">`，标题固定“操作步骤”；相邻角色对进入同一 `<article class="step-group">` | 普通/修正 Prompt 使用深色 `prompt-block`；`checklist` 使用浅色 `checklist-block`，不得出现 `prompt-label`。视觉编号可由顺序生成，但不得补写学生文案。 |
| `decision` | 作为操作时间线中的一步 | 逐字保留检查和采用判断。 |
| `safety` / `fallback` | `<section class="support-stack"><div class="support-row">…</div></section>` | 只输出来源存在的提示；不得补造安全提醒或 fallback。 |

硬阻断：最终学生 DOM 若缺少任一实际来源块所需的富语义容器、存在裸 `<pre>`、出现 `**…**`、`undefined` 或 `null` 占位，完整正文只由 `.task-intro` 与裸 `<pre>` 组成，出现多个“操作步骤”标题，将 `checklist` 标成 Prompt，或没有按相邻角色对原位组合，必须阻断。该检查只判断静态投影结构；只有明确提供生成 HTML 时才运行动态 HTML/视觉检查，不得把静态 PASS 表述为视觉验收通过。

## 5. Compact 页面代码合同

每课提示词中的完整代码至少满足：

- 单文件 HTML，声明 UTF-8 和移动端 viewport。
- 显式引入 `https://res.xrunda.com/runs/plugin/creator/creator-review-sdk.js`。
- 使用 `height:100%` 页面容器，正文独立纵向滚动，滚动区按实测 footer 高度预留底部空间；不得使用动态视口单位。
- 使用拓展练习专属连续粉紫蓝渐变，保留 `.task-hero`、登记 HTTPS 头图 `3.png`（竖屏 CSS 视觉尺寸 `76×76px`，无底色和对号）、玻璃卡、深色 Prompt 卡、浅色责任卡、浅黄色辅助卡和统一紫色课程按钮。头图不得挤占首屏主要阅读空间。
- 主内容两侧使用物理属性固定 `24px`，必要时仅用低版本可识别的媒体查询调整；主按钮使用 `width:calc(100% - 64px); max-width:260px`、最小高度 `60px`、圆角 `40px`、主体色 `#9260fe`。
- 页面主渐变必须连续覆盖到视口底部，并使用 `--page-bottom-rgb: 236, 227, 255` 和派生的 `--page-bottom-bg` 作为最后一个色标；footer 只承载按钮及其上方 `10px`、下方 `10px + safe-area` 的几何空间，背景必须透明。
- 禁止 footer 单独绘制整宽实色背景，禁止 `footer::before` / `footer::after` 形式的 `18px` 羽化层；不得出现水平硬分界、独立色带、边框、阴影或模糊。
- 学生内容在装配阶段完成 HTML 转义并写入静态 DOM；Prompt 用 `<pre>` 配合 `white-space: pre-wrap`。
- 只保留一个课程动作按钮；不得有播放器、表单、分享、评分、额外导航或第二个 SDK 动作。
- `pageAction === "complete"` 时只绑定 `safeComplete()`；否则只绑定 `safeNextPage()`。
- 实际使用的安全函数必须先判断 SDK 可用性和目标函数类型。
- 必须适配窄屏与横屏，不得横向溢出；底栏不得遮挡最后一段正文。

## 6. 提示词版本规则

- 每次生成的新提示词必须使用未使用过的唯一版本号；版本号至少包含页面类型、`lessonXXX`、`PXX`、合同版本、日期和本次运行唯一标识。
- 同一整课 JSON 中，任意两个非互动页的实际提示词版本号不得相同；同一 OneShot 即使仍用于同一页，只要完整模型输入改变，归一化提示词实例哈希和版本号就必须改变。重复时标记 `V35_STAGE6_PROMPT_VERSION_DUPLICATE`，合同/资产/实例哈希/首行任一不一致时标记 `V35_STAGE6_PROMPT_VERSION_ASSET_MISMATCH`。互动题组件页保持 `prompt: ""`，不分配页面提示词版本号。
- 新版本号使用模型中立前缀 `RunS-PostClassTask-...`，不得把 Kimi、GLM 或误写的 Kiki 固化为通用合同名。
- `v1.11` 是新装配唯一允许的拓展练习合同；历史版本仅作已发布产物追溯，不得用于新的 Stage 6 装配。
- 已经用于验证的旧版本号只作为证据保留，不得复用：
  - `RunS-Kiki-PostClassTask-Compact-OneShot-v2.0-20260723`：lesson004；其中 `Kiki` 是已确认的历史误写，不反向修改验证证据。
  - `RunS-PostClassTask-L017-Compact-OneShot-v1.0-20260723`：lesson017。

## 7. 写入整课 JSON

1. 把完整一次性提示词提交给 Kimi 或 GLM。
2. 验证模型回复首尾分别为 `<!doctype html>` 和 `</html>`，且没有 Markdown 围栏或解释文字。
3. 验证页面内容、模块数量、顺序、SDK 动作、滚动和底栏。
4. 当前 RunS 页面模型链路把本课完整 Compact OneShot 实际模型输入写入拓展练习页 `pages[].prompt`；模型返回的完整 HTML 是实际生成页面结果，另层校验与留证，不得回写覆盖提示词。
5. 在 `page_data` 记录本次 OneShot 合同版本、实际提示词版本和内容来源；不再声称输出与旧 Demo 变量区外字节完全一致。

## 8. 阻断条件

出现以下任一情况，拓展练习页 P3 阻断：

- 提示词仍依赖模型读取本地路径、Demo 或历史上下文；
- 提示词没有内嵌完整 HTML / CSS / JavaScript；
- 模型只返回普通文本、JSON、`text\n...`、Markdown 围栏或局部代码；
- 页面显示 `PAGE_DATA`、字段名、转义字符或提示词正文，或学生正文依赖运行时 JS 拼装；
- `task` / `facts` / `step` / `prompt` / `decision` / `safety` / `fallback` 被压平为普通段落或裸 `<pre>`，或学生 DOM 出现 Markdown、`undefined` / `null` 占位；
- 缺失来源中的任务块，或补造来源不存在的模块；
- 最终按钮 SDK 动作与页面规划不一致；
- 正文无法滚动、底栏遮挡内容、底色令牌不一致、出现可见水平分界 / 独立色块 / 边框 / 阴影 / 模糊或横向溢出。

阻断码：`POST_CLASS_TASK_COMPACT_ONESHOT_INVALID`。

## 9. 验证记录

- 2026-07-23：lesson004 首次使用 Compact OneShot 后，Kimi / GLM 链路能够生成完整 HTML；此前包含 `rawMarkdown`、嵌套围栏和转义原文的长提示词只生成普通文字。
- 2026-07-23：lesson017 按单 Prompt、检查与修订、fallback 的真实内容形态继续验证，采用同一完整自包含嵌入方式。
- 2026-07-23：lesson008、lesson021 的旧 `FixedTemplate` 分支在真实页面模型中退化为 `text\n...` 普通文本；v1.1 明确将该分支、旧 SDK、`markdown` / `rawMarkdown`、代码围栏和对象直接写入 `textContent` 全部列为静态阻断。
- 2026-07-23：lesson008 真实回归确认，运行时 `PAGE_DATA` / DOM 拼装会被页面模型改写并造成脚本语法失败；R10 正式改为阶段 6 先编译静态学生 DOM，运行时 JS 只保留 SDK、footer 同步和按钮监听。
- 2026-07-24：lesson008 静态 DOM 完整实例已登记；lesson017 / P08 的不同内容形态迁移提交通过。首次迁移发现整条标题套用防断行会造成横向截断，已改为仅保护“社区拼图交换”，验证通过。
- 当前结论只确认拓展练习页直接生成合同；不自动证明其他页面类型已经采用同一方式。
