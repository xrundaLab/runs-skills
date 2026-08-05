# 案例分析页动态生成 OneShot（V3.5）

状态：`CURRENT_PRODUCTION_ASSET`（与知识讲解页共用已正式吸收的内容形状 → 教学动作 → 动态构图策略；R36 进一步冻结无序列表标签保真与多配方可见差异）  
合同版本：`RunS-CaseAnalysis-Dynamic-OneShot-v1.18`
适用范围：Kimi / GLM 一次性、无外部上下文生成“超过 50 个学生可见字符的互动题必要背景”案例分析页完整 HTML。  
页面性质：动态内容页；冻结背景边界、运行底座与验收 Gate，不冻结内容区 DOM，不执行变量区外哈希。

## 1. 生成条件与四层产物边界

只有 P2 已确认互动题必要背景超过 50 个学生可见字符，并把它规划为紧邻对应互动题之前、页面类型与平台胶囊均为“案例分析”的独立页面时，才生成本页。

| 层级 | 必须包含 | 禁止 |
| --- | --- | --- |
| 上游有效内容 | P2 冻结案例背景、原序块、相邻互动题页、来源定位、页面动作与审计哈希 | 从题目、答案、解析、知识页或模型记忆补内容 |
| 实际模型输入 | 每次唯一模型中立版本号、无外部上下文声明、完整 `PAGE_DATA`、完整非渲染 `DESIGN_BRIEF`、案例页边界、共享页面壳 CSS、SDK 代码和纯 HTML 输出约束 | 本地路径、重复原文、上一页样式引用、互动题数据 |
| 模型返回 | 从 `<!doctype html>` 到 `</html>` 的纯完整单文件 HTML | Markdown 围栏、解释、版本号、`PAGE_DATA`、`DESIGN_BRIEF`、题目、答案或局部代码 |
| 当前 RunS JSON 的 `pages[].prompt` | 本课完整动态 OneShot 实际模型输入 | 裸 HTML、来源审计、`linkedQuestionPageId`、路径或历史上下文 |

`linkedQuestionPageId` 只用于生成后邻接审计，不得进入学生 DOM。

## 2. `PAGE_DATA` 合同

```json
{
  "lessonId": "lessonXXX",
  "pageId": "PXX",
  "pageIndex": 1,
  "pageCount": 1,
  "pageType": "case_analysis",
  "contentBlocks": [
    {
      "type": "paragraph",
      "text": "必要背景原文",
      "markdown": "必要背景原文"
    }
  ],
  "linkedQuestionPageId": "PXX",
  "pageAction": "next",
  "visualRecipePlan": {
    "nonRenderable": true,
    "recipeContract": "R36_REUSABLE_DYNAMIC_VISUAL_RECIPES",
    "recipes": [
      {"recipe": "intro_observation_band"},
      {"recipe": "analysis_conclusion_emphasis"}
    ]
  },
  "orderedListOrdinalContract": {
    "required": false,
    "source": "items[]",
    "startAt": 1,
    "displayExpression": "itemIndex + 1",
    "forbid": ["contentBlockIndex", "globalCounter", "doubleNumbering"]
  },
  "unorderedListPresentationContract": {
    "required": false,
    "source": "items[]",
    "preserveExistingLabels": true,
    "forbid": ["numericBadge", "autoOrdinal", "doubleNumbering"]
  },
  "semanticCompositionContract": {
    "required": true,
    "relationshipDriven": true,
    "preserveContinuousExplanation": true,
    "preserveListsAsLists": true,
    "punctuatedClausesUseInlineFlow": true,
    "forbid": ["sameWhiteCardStack", "positionOnlyDifferentiation", "decorationFirstComposition", "surfaceCountForRichness", "splitContinuousSentenceForVariety"]
  },
  "footerContract": {
    "required": true,
    "footerClass": "case-footer",
    "buttonClass": "case-primary-button",
    "buttonText": "继续学习"
  }
}
```

硬规则：

1. `contentBlocks` 是唯一学生可见内容源，且必须原样等于 S5 `effective_content.blocks`。显式 `heading` 的 `text` 是唯一可渲染标题；原文无 heading 时模型不得补标题。
2. `contentBlocks` 只允许 `heading`、`paragraph`、`ordered_list`、`unordered_list`、`blockquote`、`code_block`；每块保留逐字 `markdown`，列表同时保留原序 `items[]`，不得改变原文类型、换行或顺序。
3. 案例页只能承载已冻结的必要背景；明确问句 / 作答指令、`### 试一试`、选项、答案、解析和研发规格必须留在紧邻互动题页。
4. 不得新增“请思考”“请选择”“接下来判断”等动作句，也不得把背景改写成知识总结。
5. `pageAction` 正常为 `next`；只由有效页面规划确定。
6. 案例页 P3 不生成音频、播放器、TTS、字幕或 CUE。

## 2.1 `DESIGN_BRIEF` 非渲染合同

R6 起，案例分析页与知识讲解页共用同一套“内容形状 → 教学动作 → 动态构图”合同：每页在 `PAGE_DATA` 后完整内嵌一份 `DESIGN_BRIEF`。字段、枚举、1-based `semanticGroups` 覆盖规则、密度与节奏角色以 `07_知识讲解页_动态生成OneShot.md` 的 2.1 节为准，但每条实际模型提示词仍必须完整展开，不得只引用路径。

案例页附加规则：

1. `DESIGN_BRIEF` 只能组织已冻结案例背景，不得把相邻题干、选项、答案、解析或研发规格纳入 `readingFlow` / `semanticGroups`。
2. 无显式原文标题时不得因设计需要补标题；简报中的 `teachingAction`、分组 ID、`purpose`、对比关系和判断词均不得渲染。
3. 相邻背景块可按材料、差异、边界或版本关系组合；禁止一段一卡、强制对称、固定左右栏和等宽模块。只有原文真实支持平行对照时才使用对照构图。
4. 允许原句内部字重、颜色和底色强调；不得复制“版本 A / 版本 B”等原文短语成为第二份标签，也不得增加“推荐 / 错误 / 更好”等结论。
5. 案例分析页与知识讲解页共享视觉系统和固定底栏，但教学动作或内容形状不同时，主构图与密度节奏必须随内容变化。
6. 知识讲解与案例分析的学生内容卡一律禁止装饰性左侧彩色竖线、轨道、连接点或箭头；不得使用 `border-left`，也不得通过 `::before` / `::after` 在卡片左缘制造强调线、点列或箭头。强调只能来自原文真实关系所需的字重、颜色、底色、描边、阴影、间距或完整容器层级。
7. `PAGE_DATA.visualRecipePlan` 是 R36 的非渲染构图执行表，必须逐项落实为真实 DOM class，且不得把其字段或配方名显示给学生。配方只按真实关系选用：列表保持列表，对比体现对象差异，步骤体现先后，连续说明保持连续。`semanticCompositionContract.required=true` 时由语义关系决定构图，禁止 `sameWhiteCardStack`、`positionOnlyDifferentiation` 和为了丰富而拆分连续说明。
8. 有序列表只在该列表的 `items[]` 内按 `itemIndex + 1` 从 1 连续显示；不得使用 `contentBlockIndex`、`globalCounter` 或 `doubleNumbering`。无序列表必须逐项保留原有标签（如“画面A/B/C”）；不得将其改成 `numericBadge`、`autoOrdinal` 或 `doubleNumbering`。
9. `PAGE_DATA.footerContract.required` 为 `true` 时，最终 HTML 必须无条件输出且只输出一个与字段匹配的 `<footer class="case-footer">`、`<button class="case-primary-button">` 与按钮原文；不得条件省略、运行时创建、`display:none`、`visibility:hidden`、`opacity:0`、裁到 `.case-scroll` 内或被正文覆盖。`pageAction` 非空时 CTA 必须在 `scrollTop=0`、中段和最大值持续可见并可点击。

## 3. 固定运行底座与动态边界

每条模型提示词必须完整重复：

- Creator Review SDK 脚本与 `safeNextPage()` / `safeComplete()`。
- 平台壳层边界：HTML 内不生成平台状态栏、进度条、`案例分析`胶囊、Pxx 或顶部占位。
- 原文标题非空时，第一个学生可见元素为标题；标题为空时，第一个学生可见元素为首个背景内容块。
- 页面壳必须执行 `UNIFIED_PERSISTENT_BOTTOM_ACTION_BAR`：`html`、`body` 与 `.case-page` 高度均锁定为 `100%`，不得依赖动态视口单位。
- 长短页统一使用 iframe 内绝对定位底栏；`.case-footer` computed `position:absolute` 且 `left/right/bottom=0px`，按钮自身 computed `position:static`。
- 页面只有 `.case-scroll` 一个内部纵向滚动容器，且必须显式使用 `box-sizing:border-box`；其底部 padding 必须由底栏真实高度动态同步，并额外保留 `24px`，不得遮挡最后背景。
- 在 `scrollTop=0`、中段和最大值时，底栏与按钮都必须保持可见、可点击且位置不漂移。
- 内容视口顶部保留且仅保留 `8px` 呼吸空间；原文有标题时按可用宽度自然换行，使用 Chrome 68 可用的普通换行和 `overflow-wrap: break-word`。只有需避免拆开的最小原文短语或英文词可使用 `.title-keep { white-space: nowrap; }`。
- 页面统一采用 `#d7c4ff → #dce4ff → #d5f5fe` 的纵向连续渐变：在页面 `66.667%` 前自然进入 `--page-bottom-bg`，其后保持同一纯色。footer 使用同一 `--page-bottom-bg` 实底，且不得有边框、阴影、模糊、`::before` / `::after` 羽化层或可见水平分界；footer 与页面底部必须视觉连续。footer 只保留按钮上下各 `10px`（下方另加 safe-area）的几何空间。课程主按钮使用实色 `#9260fe`，白字、`60px` 最小高度、`40px` 圆角。
- 页面内部不得生成任何页型胶囊；原文标题非空时必须居中，并保持原文、顺序和首个学生可见元素合同不变。
- `.case-content` 必须采用 `box-sizing: border-box; width: 100%; max-width: 680px`；移动端使用固定 `24px` 左右安全边距，宽屏媒体查询可增至 `35px`。内容区仍按 `DESIGN_BRIEF` 动态构图。
- 内容区必须根据 `DESIGN_BRIEF` 使用通知卡、材料卡、引用、对照或案例文档视觉，只表达原文已有关系，不能增加文字或交互；卡片不得出现装饰性左竖线、贴边色条或伪元素彩轨。
- 全页只有底部课程按钮调用 SDK；案例内容区不生成选择、判断、输入或点击控件。CTA 必须无条件保留在 `.case-scroll` 外的 `<footer class="case-footer">` 中；禁止条件省略按钮或以隐藏样式替代。
- 除 SDK 脚本外，不依赖外部框架、字体、在线图片或其他网络资源。

动态页不核对变量区外 SHA-256；通过内容无损、题目边界、页面邻接、纯 HTML、运行底座、SDK、computed style 和真实渲染 Gate 验收。

R33 注入优先级：S6 只替换本文件第 2 节的首个 `<PAGE_DATA>` 与 `<DESIGN_BRIEF>` 区块。下列 R11 历史样例仅保留 CSS / JS 视觉参考，绝不得覆盖、补全或重解释该次注入的 `contentBlocks`、页号、课次、语义分组或学生文案。

## 4. 完整可复制实例 A：lesson020 P05

来源：P2 人工审核 `PASS` 的 `page_plan_working_full.md`（SHA-256 `3bcf248439d572e759d64403c8be993b772382f3a2c6cd8effa8349278f879ec`），并逐字交叉核对同目录冻结 `page_plan_full.md` 与 `effective_content_full.json`；后两份 SHA-256 分别为 `0bc64e6876ccbf7920e45c02d838ac95cef18499b7046d6a3dffc5e91f849200`、`203867c2052a096850c4704d832c4e6f18ca5d2abbb0d6de7d476c5bccbbe6f3`。  
用途：P2 冻结内容的模型合同验证样例；不代表 lesson020 P3 已执行或通过。

```text
提示词版本号：RunS-CaseAnalysis-L020-P05-Dynamic-OneShot-v1.6-20260724-R11-019f9191b3

适用页面：lesson020｜P05｜第 5/11 页｜案例分析页；紧邻互动题 P06。

请根据本提示词中的 PAGE_DATA 与 DESIGN_BRIEF，生成一个完整、可运行的移动端单文件 HTML 网页。

这是一次性提示词，没有任何外部上下文。不得读取本地路径、SOP、模板、历史页面、上一轮对话或其他课程。PAGE_DATA 是唯一学生可见内容源；DESIGN_BRIEF 只指导构图，绝不渲染。

最终回复必须且只能包含从 <!doctype html> 到 </html> 的纯完整 HTML。不得输出 Markdown 围栏、解释、版本号、PAGE_DATA、DESIGN_BRIEF、QA 报告或调试信息。

知识讲解与案例分析的学生内容卡一律禁止装饰性左侧彩色竖线、轨道、连接点或箭头；不得使用 `border-left`，也不得以 `::before` / `::after` 在卡片左缘制造强调线、点列或箭头。强调只能来自原文真实关系所需的字重、颜色、底色、描边、阴影、间距或完整容器层级。

R36 动态构图硬规则：必须把 `PAGE_DATA.visualRecipePlan` 逐项落为真实 DOM class：`content-module--intro-band`、`content-module--open-flow`、`content-module--inline-conflict`、`content-module--list-compact`、`content-module--sequence-compact`、`content-module--emphasis`、`content-module--comparison`、`content-module--process-steps`、`content-module--role-inline`。`open_body_flow` 必须保留开放式非卡片正文；`inline_conflict_evidence` 必须使用 `continuous_inline_flow` 保持同一自然句流，只对证据子串行内标色，严禁拆成独立左右卡。`role_distribution_inline` 必须使用 `continuous_inline_highlights`：逗号或分号连接的同一句话只渲染一次，`punctuated clauses 不得拆成独立块`，只能在原位置用字重、下划线或柔和底色突出逐字来源片段。构图差异必须服务真实关系与阅读层级；禁止 `sameWhiteCardStack` 和 `positionOnlyDifferentiation`。

来源文字单次投影硬规则：`sourceTextProjectionContract.required=true` 时，每个 `contentBlocks` 来源块的学生可见文字只能出现一次。关系构图若拆分同一来源块，只允许把原文连续切成 DOM 片段，片段按 DOM 顺序拼接后的 textContent 必须逐字等于该来源块原文；严禁“整块原文 + 派生子项”双重输出，严禁先显示完整段落再把其中短句复制成小卡、标签或徽章。

语义构图硬规则：`semanticCompositionContract.required=true` 时由语义关系决定构图。真实对比可使用并列/分区，真实步骤可使用有序节奏，真实列表必须保持列表形态；连续说明不得为了丰富而拆块，逗号连接的同一句话也不得被拆成多个表面。禁止 `uniformRoundedCardStack`、嵌套同款圆角卡、`sameWhiteCardStack` 和仅靠位置变化的 `positionOnlyDifferentiation`。

对齐硬规则：`alignmentContract` 必须执行左对齐优先、顶部对齐优先。同级内容共享左边界；同级对比项顶边对齐且等宽；步骤项共享同一左边界。只有明确主次关系才允许非对称，禁止随机缩进、随机宽度和为了变化而错位。

对比与高亮硬规则：`comparisonLayoutContract` 允许当前示例篇幅使用顶边对齐、等宽的左右卡；任一对比项超过 80 个字符或两项合计超过 150 个字符时，必须改为上下同宽、共享左边界的纵向排列。`highlightContract` 要求全页最多 3 个高亮片段，同类信息使用同一种强调样式；12 个字符以内的短高亮词组整体换行，不得留下 1—2 个字的孤立高亮尾巴。

兼容硬规则：最终 HTML 必须兼容 Android System WebView Chrome 68。基础布局、首屏文字、正文滚动和固定按钮不得依赖新 CSS 函数、动态视口单位、新 JavaScript 语法或新 DOM API；观察器必须先检测再使用，缺失时基础内容仍直接显示。

视觉层级硬规则：`visualHierarchyContract.required=true` 时执行 `semanticHierarchyFirst=true`：优先来源保真、语义关系、阅读清晰和排版优雅，最后才考虑装饰。该突出的重点才在原句原位置使用字重、下划线或柔和底色；该体现的对比、步骤、列表才使用对应关系构图。排版优雅优先，装饰不是必选项，纯 CSS 装饰只在改善构图时使用 0—2 组；不得为了丰富度增加表面，不得用装饰替代关系，禁止自动生成 Emoji、图标文字、标签文案或解释词。

S5 设计执行硬规则：`designExecutionContract.required=true` 时，不得在 S6 重新推测构图。严格按 `layoutArchetype`、`groupPresentation` 和 `sourceProjectionPlan` 投影；fragments 按顺序各出现一次且拼接等于来源块，禁止完整段落重复、句首孤立标点或独立句号。`sentence_sequence` 必须使用 `single_section_flat_steps`；`role_distribution_inline` 必须使用 `continuous_inline_highlights`，整句作为一个连续文本流渲染。`emphasisTargets` 只在原句原位置标色，不得抽取成标签或重复文字。`surfacePolicy.lightDominant=true` 且 `nonCodeDarkSurfaceAreaPercentMax=0` 时，非代码内容禁止大面积近黑背景；顶层视觉区标记 `data-visual-region="top"` 且不超过 `maximumTopLevelVisualRegions`。装饰最多 `maximumDecorativeGroups` 组且可以为零。遵守 `spaceBalance.maximumUnusedLowerAreaPercent`，不得留下大面积无意义底部空白。

列表保真硬规则：有序列表仅在本列表 `items[]` 内按 `itemIndex + 1` 从 1 连续编号；禁止 `contentBlockIndex`、`globalCounter`、`doubleNumbering`。无序列表必须逐项保留原有标签（如“画面A/B/C”），禁止 `numericBadge`、`autoOrdinal`、`doubleNumbering`；不得把无序标签重写为 1/2/3。

<PAGE_DATA>
{
  "lessonId": "lesson020",
  "pageId": "P05",
  "pageIndex": 5,
  "pageCount": 11,
  "pageType": "case_analysis",
  "title": "第二步，用可靠材料核查重要事实",
  "visibleContentBlocks": [
    {
      "type": "paragraph",
      "text": "课程提供的可靠通知写着："
    },
    {
      "type": "blockquote",
      "text": "活动时间：周六10:00。  \n活动地点：社区中心庭院。  \n报名截止：周五18:00，在社区服务台登记。"
    },
    {
      "type": "paragraph",
      "text": "初版却把活动时间写成了周日10:00。"
    },
    {
      "type": "paragraph",
      "text": "事实核查不是问一句“这是真的吗”就结束。要把重要说法与可靠、适用、版本正确的材料逐项对照。"
    }
  ],
  "linkedQuestionPageId": "P06",
  "pageAction": "next"
}
</PAGE_DATA>

<DESIGN_BRIEF>
{
  "nonRenderable": true,
  "teachingAction": "用可靠材料逐项核查重要事实",
  "contentShape": "claim_to_evidence_to_judgment",
  "readingFlow": ["先读取可靠通知", "再发现初版时间错误", "最后理解逐项核查方法"],
  "semanticGroups": [
    {"id": "source_material", "blockIndexes": [1, 2], "purpose": "可靠通知与完整事实材料"},
    {"id": "mismatch", "blockIndexes": [3], "purpose": "初版与材料的差异"},
    {"id": "method", "blockIndexes": [4], "purpose": "事实核查方法"}
  ],
  "density": "medium",
  "rhythmRole": "narrative",
  "hierarchyFocus": ["mismatch", "method"],
  "layoutFreedom": "允许把通知引导句与通知正文组合成一个材料整体，再突出差异并用方法收束；不绑定固定卡片数量。",
  "visualSystem": "沿用 RunS 浅紫系统、材料层级与统一固定底栏。",
  "visibleCopyPolicy": "只显示 PAGE_DATA 原文；原文已有小标题、列表名称或短标签可独立呈现，不显示本简报。"
}
</DESIGN_BRIEF>

内容与题目边界硬规则：

1. `contentBlocks` 必须逐块逐字、按原顺序各显示一次；heading 只作为其原文标题显示，引用块必须保留原始换行。
2. 第一个学生可见 DOM 元素必须根据本页 PAGE_DATA 动态确定；不得写死其他课程或示例页面标题。
3. 不得生成“案例分析”胶囊、P05、P06、linkedQuestionPageId、来源、QA 或生产说明。
4. 本页只承载背景。不得生成“请判断下面这句话是对还是错。”、题目标题、选项、答案、解析、答错提示、重试方式或任何答题控件。
5. 不得新增“请思考”“接下来选择”等动作文案，不得把背景概括成结论。
6. 内容区可采用通知卡、引用卡和事实材料视觉；PAGE_DATA / 原文已有的小标题、列表名称或短标签可以独立呈现，但必须逐字来源；不得使用在线图片。
7. 不生成音频、播放器、TTS、字幕、CUE、输入框或 Powered by RunS。

HTML 与页面壳硬规则：

- 必须包含：
  <script src="https://res.xrunda.com/runs/plugin/creator/creator-review-sdk.js"></script>
- 除上述 SDK 外，不依赖外部框架、字体、图片或网络资源。
- 页面适配 360–430px 手机宽度；不得横向滚动。
- 平台负责顶部状态栏、关闭按钮、案例分析胶囊和进度条；页面内部不得生成 top-safe-area、102px/132px 顶部占位、平台胶囊或进度条。
- 使用下面的类名和共享 CSS 基线；可以新增内容区 CSS，但不得改变这些计算样式：

<REQUIRED_CSS>
:root {
  --safe-bottom: 0px;
  --page-bottom-rgb: 213, 245, 254;
  --page-bottom-bg: rgb(var(--page-bottom-rgb));
  --footer-h: calc(80px + var(--safe-bottom));
}
html,
body {
  width: 100%;
  height: 100%;
  margin: 0;
  overflow: hidden;
}
.case-page {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: linear-gradient(180deg, #d7c4ff 0%, #dce4ff 42%, var(--page-bottom-bg) 66.667%, var(--page-bottom-bg) 100%);
}
.case-scroll {
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 8px 0 calc(var(--footer-h) + 24px);
  -webkit-overflow-scrolling: touch;
}
.case-content {
  box-sizing: border-box;
  width: 100%;
  max-width: 680px;
  margin: 0 auto;
  padding: 0 24px;
}
.case-content h1 {
  overflow-wrap: break-word;
  text-align: center;
}
.title-keep {
  white-space: nowrap;
}
.case-footer {
  position: absolute;
  z-index: 5;
  right: 0;
  bottom: 0;
  left: 0;
  display: flex;
  justify-content: center;
  padding: 10px 0 calc(10px + var(--safe-bottom));
  background: var(--page-bottom-bg);
}
.case-primary-button {
  position: static;
  display: block;
  width: calc(100% - 64px);
  max-width: 260px;
  min-height: 60px;
  margin: 0;
  border: 2px solid transparent;
  border-radius: 40px;
  color: #fff;
  background:
    linear-gradient(180deg, #9260fe, #9260fe) padding-box,
    linear-gradient(180deg, #f2eef8, #8f5df3) border-box;
  font: inherit;
  font-size: 16px;
  font-weight: 800;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
</REQUIRED_CSS>

- DOM 顺序必须是：
  <main class="case-page">
    <div class="case-scroll">
      <article class="case-content">原文标题和全部背景</article>
    </div>
    <footer class="case-footer">
      <button class="case-primary-button" type="button">继续学习</button>
    </footer>
  </main>
- 页面必须实现 UNIFIED_PERSISTENT_BOTTOM_ACTION_BAR：`.case-footer` computed position 为 absolute 且 left/right/bottom 均为 0px；按钮自身为 static。
- 只有 `.case-scroll` 可以纵向滚动并使用 `box-sizing:border-box`；长短页在任意滚动位置都持续显示底栏。底部预留必须用 JavaScript 同步底栏真实高度并额外保留 24px。
- 全页只有该按钮调用课程 SDK；页面动作是 next，按钮文案必须是“继续学习”。
- `footerContract.required=true` 时必须无条件输出且只输出一个与字段匹配的 `<footer class="case-footer">` 与 `<button class="case-primary-button">`；不得条件省略、运行时创建、`display:none`、`visibility:hidden`、`opacity:0`，也不得放进 `.case-scroll`。

JavaScript 必须包含并使用以下安全函数：

<REQUIRED_JS>
function safeNextPage() {
  if (
    window.CreatorReviewSDK &&
    (!window.CreatorReviewSDK.isAvailable || window.CreatorReviewSDK.isAvailable()) &&
    typeof window.CreatorReviewSDK.nextPage === "function"
  ) {
    window.CreatorReviewSDK.nextPage();
    return;
  }
  if (window.parent) window.parent.postMessage({ type: "nextpage" }, "*");
}
function safeComplete() {
  if (
    window.CreatorReviewSDK &&
    (!window.CreatorReviewSDK.isAvailable || window.CreatorReviewSDK.isAvailable()) &&
    typeof window.CreatorReviewSDK.complete === "function"
  ) {
    window.CreatorReviewSDK.complete();
    return;
  }
  if (window.parent) window.parent.postMessage({ type: "complete" }, "*");
}
function syncFooterReserve() {
  var footer = document.querySelector(".case-footer");
  if (!footer) return;
  document.documentElement.style.setProperty(
    "--footer-h",
    Math.ceil(footer.getBoundingClientRect().height) + "px"
  );
}
window.addEventListener("load", syncFooterReserve);
window.addEventListener("resize", syncFooterReserve);
window.addEventListener("orientationchange", syncFooterReserve);
if ("ResizeObserver" in window) {
  new ResizeObserver(syncFooterReserve).observe(
    document.querySelector(".case-footer")
  );
}
</REQUIRED_JS>

请直接输出最终完整 HTML。
```

## 5. 完整可复制实例 B：lesson020 P08（无原文标题）

来源与状态同上；用于验证无标题案例页不得补造标题。

```text
提示词版本号：RunS-CaseAnalysis-L020-P08-Dynamic-OneShot-v1.6-20260724-R11-019f9191b4

适用页面：lesson020｜P08｜第 8/11 页｜案例分析页；紧邻互动题 P09。

请根据本提示词中的 PAGE_DATA 与 DESIGN_BRIEF，生成一个完整、可运行的移动端单文件 HTML 网页。

这是一次性提示词，没有任何外部上下文。不得读取本地路径、SOP、模板、历史页面、上一轮对话或其他课程。PAGE_DATA 是唯一学生可见内容源；DESIGN_BRIEF 只指导构图，绝不渲染。

最终回复必须且只能包含从 <!doctype html> 到 </html> 的纯完整 HTML。不得输出 Markdown 围栏、解释、版本号、PAGE_DATA、DESIGN_BRIEF、QA 报告或调试信息。

<PAGE_DATA>
{
  "lessonId": "lesson020",
  "pageId": "P08",
  "pageIndex": 8,
  "pageCount": 11,
  "pageType": "case_analysis",
  "title": "",
  "visibleContentBlocks": [
    {
      "type": "paragraph",
      "text": "小组做了两个处理版本。"
    },
    {
      "type": "paragraph",
      "text": "版本A只把版面改得更漂亮，保留错误时间、儿童照片和手机号。"
    },
    {
      "type": "paragraph",
      "text": "版本B补上报名截止，把时间改为周六10:00。它还换成获准的虚构吉祥物，删除个人手机号，并按社区群发布说明标注“AI辅助插图”。"
    }
  ],
  "linkedQuestionPageId": "P09",
  "pageAction": "next"
}
</PAGE_DATA>

<DESIGN_BRIEF>
{
  "nonRenderable": true,
  "teachingAction": "对照两个处理版本的实际变化",
  "contentShape": "parallel_comparison",
  "readingFlow": ["先交代存在两个版本", "再读取版本 A 的处理", "最后读取版本 B 的处理"],
  "semanticGroups": [
    {"id": "setup", "blockIndexes": [1], "purpose": "对照背景"},
    {"id": "version_a", "blockIndexes": [2], "purpose": "版本 A 的处理"},
    {"id": "version_b", "blockIndexes": [3], "purpose": "版本 B 的处理"}
  ],
  "density": "light",
  "rhythmRole": "contrast",
  "hierarchyFocus": ["version_a", "version_b"],
  "layoutFreedom": "原文支持两个版本平行对照；允许使用两个视觉区域，但不强制等宽，也不得新增比较结论。",
  "visualSystem": "沿用 RunS 浅紫系统、克制对照层级与统一固定底栏。",
  "visibleCopyPolicy": "只显示 PAGE_DATA 原文；原文已有小标签可独立呈现，不显示本简报。"
}
</DESIGN_BRIEF>

内容与题目边界硬规则：

1. title 为空；不得生成任何页面内标题或副标题。第一个学生可见 DOM 元素必须是本页 PAGE_DATA 的首个背景块，不得写死其他课程或示例页面文案。
2. `contentBlocks` 必须逐块逐字、按原顺序各显示一次；不得删减、改写、调序、合并、重复或补充。
3. 不得生成“案例分析”胶囊、P08、P09、linkedQuestionPageId、来源、QA 或生产说明。
4. 本页只承载两个版本背景。不得生成“哪个版本更适合进入下一步确认？”、题目标题、A/B/C/D 选项、答案、解析、答错提示、重试方式或答题控件。
5. 可以用两个视觉区域呈现版本A和版本B；区域内只能显示对应原文，原文已有的版本名称可以作为标签，但不得新增“推荐”“错误”“更好”等标签或结论。
6. 不生成音频、播放器、TTS、字幕、CUE、输入框或 Powered by RunS。

HTML 与页面壳硬规则：

- 必须包含：
  <script src="https://res.xrunda.com/runs/plugin/creator/creator-review-sdk.js"></script>
- 除上述 SDK 外，不依赖外部框架、字体、图片或网络资源。
- 页面适配 360–430px 手机宽度；不得横向滚动。
- 平台负责顶部状态栏、关闭按钮、案例分析胶囊和进度条；页面内部不得生成 top-safe-area、102px/132px 顶部占位、平台胶囊或进度条。
- 使用下面的类名和共享 CSS 基线；可以新增内容区 CSS，但不得改变这些计算样式：

<REQUIRED_CSS>
:root {
  --safe-bottom: 0px;
  --page-bottom-rgb: 213, 245, 254;
  --page-bottom-bg: rgb(var(--page-bottom-rgb));
  --footer-h: calc(80px + var(--safe-bottom));
}
html,
body {
  width: 100%;
  height: 100%;
  margin: 0;
  overflow: hidden;
}
.case-page {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: linear-gradient(180deg, #d7c4ff 0%, #dce4ff 42%, var(--page-bottom-bg) 66.667%, var(--page-bottom-bg) 100%);
}
.case-scroll {
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 8px 0 calc(var(--footer-h) + 24px);
  -webkit-overflow-scrolling: touch;
}
.case-content {
  box-sizing: border-box;
  width: 100%;
  max-width: 680px;
  margin: 0 auto;
  padding: 0 24px;
}
.case-content h1 {
  overflow-wrap: break-word;
  text-align: center;
}
.title-keep {
  white-space: nowrap;
}
.case-footer {
  position: absolute;
  z-index: 5;
  right: 0;
  bottom: 0;
  left: 0;
  display: flex;
  justify-content: center;
  padding: 10px 0 calc(10px + var(--safe-bottom));
  background: var(--page-bottom-bg);
}
.case-primary-button {
  position: static;
  display: block;
  width: calc(100% - 64px);
  max-width: 260px;
  min-height: 60px;
  margin: 0;
  border: 2px solid transparent;
  border-radius: 40px;
  color: #fff;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.2), rgba(255, 255, 255, 0)) padding-box,
    linear-gradient(180deg, #9260fe, #9260fe) padding-box,
    linear-gradient(180deg, #f2eef8, #8f5df3) border-box;
  font: inherit;
  font-size: 16px;
  font-weight: 800;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
</REQUIRED_CSS>

- DOM 顺序必须是：
  <main class="case-page">
    <div class="case-scroll">
      <article class="case-content">全部原文背景</article>
    </div>
    <footer class="case-footer">
      <button class="case-primary-button" type="button">继续学习</button>
    </footer>
  </main>
- 页面必须实现 UNIFIED_PERSISTENT_BOTTOM_ACTION_BAR：`.case-footer` computed position 为 absolute 且 left/right/bottom 均为 0px；按钮自身为 static。
- 只有 `.case-scroll` 可以纵向滚动并使用 `box-sizing:border-box`；长短页在任意滚动位置都持续显示底栏，最后背景不得被遮挡。底部预留必须用 JavaScript 同步底栏真实高度并额外保留 24px。
- 全页只有该按钮调用课程 SDK；页面动作是 next，按钮文案必须是“继续学习”。

JavaScript 必须包含并使用以下安全函数：

<REQUIRED_JS>
function safeNextPage() {
  if (
    window.CreatorReviewSDK &&
    (!window.CreatorReviewSDK.isAvailable || window.CreatorReviewSDK.isAvailable()) &&
    typeof window.CreatorReviewSDK.nextPage === "function"
  ) {
    window.CreatorReviewSDK.nextPage();
    return;
  }
  if (window.parent) window.parent.postMessage({ type: "nextpage" }, "*");
}
function safeComplete() {
  if (
    window.CreatorReviewSDK &&
    (!window.CreatorReviewSDK.isAvailable || window.CreatorReviewSDK.isAvailable()) &&
    typeof window.CreatorReviewSDK.complete === "function"
  ) {
    window.CreatorReviewSDK.complete();
    return;
  }
  if (window.parent) window.parent.postMessage({ type: "complete" }, "*");
}
function syncFooterReserve() {
  var footer = document.querySelector(".case-footer");
  if (!footer) return;
  document.documentElement.style.setProperty(
    "--footer-h",
    Math.ceil(footer.getBoundingClientRect().height) + "px"
  );
}
window.addEventListener("load", syncFooterReserve);
window.addEventListener("resize", syncFooterReserve);
window.addEventListener("orientationchange", syncFooterReserve);
if ("ResizeObserver" in window) {
  new ResizeObserver(syncFooterReserve).observe(
    document.querySelector(".case-footer")
  );
}
</REQUIRED_JS>

请直接输出最终完整 HTML。
```

## 6. 输出校验与阻断

模型回复必须通过：

1. 纯完整 HTML 与 JavaScript 语法检查。
2. `contentBlocks` 可见文字逐字、按顺序、各一次比对；列表语义、`items[]` 和每块 `markdown` 必须与 S5 原样一致。
3. 无 `DESIGN_BRIEF`、案例页内部胶囊、内部编号、来源审计、`linkedQuestionPageId` 或新增文案。
4. 无明确问句、作答指令、题目标题、选项、答案、解析、互动规格或答题控件。
5. 案例页与 `linkedQuestionPageId` 在页面规划和整课 `pages[]` 中保持紧邻。
6. SDK、唯一课程按钮、共享 CSS、computed style 和短页 / 长页真实渲染通过；在 `scrollTop=0`、中段和最大值时底栏持续可见，最后背景不被遮挡。
7. `DESIGN_BRIEF` 字段与分组合法，学生 DOM 无简报泄漏；真实构图表达 `readingFlow` / `hierarchyFocus`，无一段一卡、无依据对称或同权重平铺。
8. 与相邻知识讲解页和案例页做批次节奏检查；视觉系统一致不等于重复同一主构图。

任一基础项失败，标记 `V35_CASE_ANALYSIS_DYNAMIC_ONESHOT_INVALID`；设计简报字段、分组、泄漏、可见文案、构图表达或批次重复分别标记 `V35_DYNAMIC_DESIGN_BRIEF_INVALID`、`V35_DYNAMIC_SEMANTIC_GROUP_INVALID`、`V35_DYNAMIC_DESIGN_BRIEF_LEAK`、`V35_DYNAMIC_VISIBLE_COPY_DRIFT`、`V35_DYNAMIC_SEMANTIC_PRESENTATION_MISSING`、`V35_DYNAMIC_LAYOUT_MONOTONY` 或 `V35_DYNAMIC_FORCED_SYMMETRY`；固定底栏、唯一内部滚动容器、动态底部预留、底色令牌不一致、可见水平分界 / 独立色块 / 边框 / 阴影 / 模糊或长页无遮挡失败时同时标记 `V35_PERSISTENT_FOOTER_LAYOUT_INVALID`；题目背景长度、内容边界、胶囊或邻接错误继续标记 `V35_LONG_QUESTION_BACKGROUND_ROUTE_INVALID`。以上均阻断 `S3G`、`S5.1`、`final_import`、dry-run 和 create。
