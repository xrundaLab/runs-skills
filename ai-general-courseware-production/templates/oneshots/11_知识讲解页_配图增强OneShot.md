# 知识讲解页动态生成 OneShot（V3.5）

状态：`CURRENT_PRODUCTION_ASSET`（已正式吸收灵活排版策略；R11 顶部三分之二渐变、同色实底 footer 与居中标题口径）  
合同版本：`RunS-Knowledge-Dynamic-OneShot-v1.19`
适用范围：Kimi / GLM 一次性、无外部上下文生成知识讲解页完整 HTML。  
页面性质：动态内容页；冻结输入、运行底座与验收 Gate，不冻结内容区 DOM，不执行变量区外哈希。

## 1. 四层产物边界

| 层级 | 必须包含 | 禁止 |
| --- | --- | --- |
| 上游有效内容 | P2 冻结页面块、原序内容、`source_text`、`semantic_units`、来源定位、页面动作与审计哈希 | 从旧页面、研发摘要、模型记忆或其他课程补内容 |
| 实际模型输入 | 每次唯一模型中立版本号、无外部上下文声明、完整 `PAGE_DATA`、完整非渲染 `DESIGN_BRIEF`、内容规则、共享页面壳 CSS、SDK 代码和纯 HTML 输出约束 | 本地路径、`source_text` / `semantic_units` 重复全文、增量补丁、上一页样式引用 |
| 模型返回 | 从 `<!doctype html>` 到 `</html>` 的纯完整单文件 HTML | Markdown 围栏、解释、版本号、`PAGE_DATA`、`DESIGN_BRIEF`、QA 报告或局部代码 |
| 当前 RunS JSON 的 `pages[].prompt` | 本课完整动态 OneShot 实际模型输入 | 裸 HTML、来源审计、路径、重复原文或历史上下文 |

`source_text`、`semantic_units`、来源路径和 SHA-256 继续留在上游审计证据。R36 的完整实际模型输入只携带单份 `PAGE_DATA.contentBlocks`：它必须等于 S5 `effective_content.blocks` 的有序对象投影，不得压缩成 `markdown` 整块、`type/text` 简化对象或第二份改写文案；模型返回的纯完整 HTML 是实际生成页面结果，另层校验与留证。

## 2. `PAGE_DATA` 合同

```json
{
  "lessonId": "lessonXXX",
  "pageId": "PXX",
  "pageIndex": 1,
  "pageCount": 1,
  "pageType": "knowledge_explanation",
  "transitionText": "",
  "transitionPlacement": "none",
  "contentBlocks": [
    {
      "type": "heading",
      "level": 2,
      "text": "原文页面标题",
      "markdown": "## 原文页面标题"
    },
    {
      "type": "paragraph",
      "text": "原文段落",
      "markdown": "原文段落"
    }
  ],
  "pageAction": "next",
  "visualRecipePlan": {
    "nonRenderable": true,
    "recipeContract": "R36_REUSABLE_DYNAMIC_VISUAL_RECIPES",
    "recipes": [
      {"recipe": "intro_observation_band"},
      {"recipe": "analysis_conclusion_emphasis"}
    ],
    "mediumReadingAreaBalance": {
      "required": false,
      "target": "60_to_75_percent_of_available_reading_area",
      "forbidFillers": true
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
    }
  },
  "footerContract": {
    "required": true,
    "footerClass": "knowledge-footer",
    "buttonClass": "knowledge-primary-button",
    "buttonText": "继续学习"
  }
}
```

硬规则：

1. `transitionText` 只允许逐字复制阶段 5 已冻结的单句过渡；`transitionPlacement` 只取 `none`、`before_title`、`after_content`。没有过渡句时两者必须分别为 `""` 和 `none`；有过渡句时必须逐字携带并按冻结位置渲染，阶段 6 不得重新识别或归属。
2. `contentBlocks` 是唯一学生可见内容源：它原样携带 S5 `effective_content.blocks` 的完整对象。`heading` 的 `text` 是唯一可渲染标题；不得从知识点、`summary` 或模型理解补标题。
3. `contentBlocks` 只允许 `heading`、`paragraph`、`ordered_list`、`unordered_list`、`blockquote`、`code_block`。每块必须保留逐字 `markdown`；列表同时保留原序 `items[]`。有序列表不得降级为段落或无序列表，无序列表不得强行编号。有序列表的可见编号只能取同一列表 `items[]` 内 `itemIndex + 1`，每个列表独立从 1 连续递增；不得使用 `contentBlockIndex`、`globalCounter` 或把 Markdown 既有序号与生成序号叠加成 `doubleNumbering`。无序列表必须保留已有文字标签（如“画面A/B/C”），不得生成 `numericBadge`、`autoOrdinal` 或其他数字序号；不得以“美化”为由改变列表性质。
4. 不得把题干、选项、答案、解析、题目组件或研发规格放入知识页。
5. `pageAction` 只取 `next` / `complete`，由有效页面规划确定，模型不得推断。
6. P3 不自行生成音频、播放器、TTS、字幕或 CUE；若后续资源阶段有显式音频合同，必须走独立资源 Gate。

## 2.1 `DESIGN_BRIEF` 非渲染合同

R6 起，每个知识讲解页必须在 `PAGE_DATA` 后完整内嵌一份 `DESIGN_BRIEF`。它由阶段 5 根据同页冻结内容生成，是“内容关系如何被页面表达”的受控设计数据，不是第二份内容真源，也不是固定组件映射。

```json
{
  "nonRenderable": true,
  "teachingAction": "本页唯一教学动作",
  "contentShape": "problem_to_method_to_result",
  "readingFlow": ["先看什么", "再理解什么", "最后得到什么"],
  "semanticGroups": [
    {
      "id": "group_id",
      "blockIndexes": [1],
      "purpose": "该组在教学叙事中的作用"
    }
  ],
  "density": "light",
  "rhythmRole": "structured",
  "shortPageComposition": "two_layer_reading（仅恰有两条独立短原文时）",
  "hierarchyFocus": ["group_id"],
  "layoutArchetype": "open_explanation",
  "groupPresentation": [
    {
      "groupId": "group_id",
      "geometry": "open_body_flow",
      "surfaceRole": "open_background",
      "visualWeight": "normal"
    }
  ],
  "sourceProjectionPlan": [
    {"blockIndex": 1, "mode": "single_region", "region": "group_id"}
  ],
  "emphasisTargets": [
    {"blockIndex": 1, "exactText": "逐字来源片段", "colorRole": "primary_judgment"}
  ],
  "surfacePolicy": {
    "lightDominant": true,
    "allowLargeDarkSurface": false,
    "nonCodeDarkSurfaceAreaPercentMax": 0,
    "minimumOpenRegions": 1,
    "maximumTopLevelVisualRegions": 4,
    "nestedItemStyle": "flat_subregion",
    "nestedItemsUseIndependentShadow": false,
    "maximumDecorativeGroups": 2,
    "forbid": [
      "largeNearBlackContentPanel",
      "allContentInsideCards",
      "uniformRoundedCardStack"
    ]
  },
  "colorRoles": {
    "primaryEmphasis": "runs_purple_inline",
    "conflictEvidence": "warm_amber_inline",
    "supportingInformation": "cool_blue_tint",
    "conclusionSurface": "light_purple_tint",
    "bodyText": "dark_neutral",
    "inlineHighlightOnly": true
  },
  "spaceBalance": {
    "readingAreaTarget": "60_to_75_percent",
    "maximumUnusedLowerAreaPercent": 12,
    "forbidTopHeavyComposition": true
  },
  "layoutFreedom": "允许按内容关系动态组合，不绑定固定组件。",
  "visualSystem": "沿用 RunS 统一视觉与固定底栏。",
  "visibleCopyPolicy": "只显示 PAGE_DATA 原文；原文已有小标题、列表名称或短标签可独立呈现，不显示本简报。"
}
```

硬规则：

1. `nonRenderable` 必须为 `true`；`DESIGN_BRIEF` 的键、值、分组 ID、教学动作和关系描述均不得进入学生可见 DOM。
2. `contentShape` 只取 `claim_to_evidence_to_judgment`、`concept_to_example_to_boundary`、`problem_to_method_to_result`、`example_to_comparison_to_boundary`、`parallel_comparison`、`process_or_sequence`、`continuous_explanation`。
3. `semanticGroups[].blockIndexes` 使用 `contentBlocks` 中除 heading/冻结过渡句之外的阅读块的 1-based 索引，必须无重叠、无越界地完整覆盖；三块及以上时至少用两个真实语义组表达阅读层级。它表达语义组合，不等于“一组一张卡”。
4. `density` 只取 `light`、`medium`、`dense`；`rhythmRole` 只取 `statement`、`structured`、`contrast`、`narrative`、`dense_reference`；`hierarchyFocus` 只能引用现有分组 ID。
5. 相邻内容块可按真实关系合并为一个完整模块；禁止“一段一张同款卡”、强制左右对称、等宽三栏、逐字对齐或预设卡片数量。
6. 允许通过字号、字重、底色、留白、位置和原文字符串内部的 `<span>` / `<strong>` 做层级；PAGE_DATA / 原文中已有的小标题、列表名称或明确短标签可以独立呈现为标签、徽章或模块名，但必须逐字来源，不得追加新词、解释或结论。原文中不存在的标签仍不得新增。
7. 页面必须实际表达 `readingFlow` 和 `hierarchyFocus`，同时保持 `PAGE_DATA.contentBlocks` 的文字、列表项、Markdown 类型、顺序和出现次数完全不变；不能只把所有正文平铺成同权重文字，也不能把 `DESIGN_BRIEF` 当模板逐字段渲染。
7a. `layoutArchetype`、`groupPresentation`、`sourceProjectionPlan`、`emphasisTargets`、`surfacePolicy`、`colorRoles` 与 `spaceBalance` 是 S5 已冻结的可执行设计，S6 不得重新推测。每个语义组必须有唯一 presentation；每个来源块必须有唯一 projection。片段拆分必须连续覆盖原文且只出现一次；强调目标必须是同块原文的逐字子串，只能在原句原位置标色。`inline_conflict_evidence` 必须用 `continuous_inline_flow` 保持为同一自然句流，只给证据子串加行内底色，严禁拆成独立左右卡；`sentence_sequence` 必须在一个 section 内使用 `single_section_flat_steps`。逗号或分号连接的媒介/角色分工必须使用 `role_distribution_inline` / `continuous_inline_highlights`，整句在一个连续文本流中只出现一次；`punctuated clauses 不得拆成独立块`，只能在原位置使用字重、下划线或柔和底色突出逐字来源片段，标点留在连续句流中。
7b. `surfacePolicy.lightDominant=true` 且 `nonCodeDarkSurfaceAreaPercentMax=0` 时，非代码内容不得使用大面积黑色、深灰或深紫背景。结论使用浅色表面与局部主题色文字；页面至少保留一个开放式非卡片区域。最终 DOM 的顶层视觉区统一标记 `data-visual-region="top"`，不得超过 `maximumTopLevelVisualRegions`；流程步骤与媒介分工子项标记 `data-visual-region="nested" data-surface="flat"`，执行 `nestedItemStyle=flat_subregion`，禁止独立阴影和重描边。无文字 CSS 装饰不得超过 `maximumDecorativeGroups` 组。
8. 当 `DESIGN_BRIEF.shortPageComposition` 为 `two_layer_reading` 时，页面恰用两条来源原文形成上下两个阅读层：第一层为主阅读层，第二层为弱结果层。两条文字必须逐字、按原顺序、各出现一次；不得拆句改写、补写、重复或硬凑成多段。两层之间只能通过无文字、无可见线条的连续留白与背景节奏连接；不得添加箭头、竖线、横线、编号、标签、图标或任何学生可见新文案。禁止“顶部单小卡＋下方大面积空白”。
9. 知识讲解与案例分析的学生内容卡一律禁止装饰性左侧彩色竖线、轨道、连接点或箭头；不得使用 `border-left`，也不得以 `::before` / `::after` 在卡片左缘制造强调线、点列或箭头。语义层级只能使用原文的字号、字重、底色、描边、阴影、间距与完整容器比例表达。
10. 当 `density` 为 `medium` 的知识讲解页含三块及以上真实阅读块时，中等篇幅知识讲解页不得让内容仅堆在上半屏；必须用已冻结原文的分层、卡片尺寸和垂直节奏平衡主要阅读区，使最后一个来源模块自然延展到固定底栏前的可见阅读区域。不得用新增文案、空白占位、强行拉高单一卡片或可见连接轨凑高度；`two_layer_reading` 短页仍按第 8 条处理，不得硬凑内容。
11. `PAGE_DATA.visualRecipePlan` 是 R36 的非渲染构图执行表，必须逐项落实为真实 DOM class，且不得把其字段或配方名显示给学生。可复用配方只按真实关系选用：列表保持列表，对比体现对象差异，步骤体现先后，`role_distribution_inline` 使用 `content-module--role-inline` 与 `continuous_inline_highlights` 保留连续句流。`semanticCompositionContract.required=true` 时由语义关系决定构图，禁止 `sameWhiteCardStack`、`positionOnlyDifferentiation` 和为了丰富而拆分连续说明。对 `ordered_list`，最终 DOM 只遍历本块 `items[]` 并从 1 连续编号；对 `unordered_list`，只显示原有文字标签，不生成数字徽标或自动序号。
11a. `sourceTextProjectionContract.required=true` 时，每个 `contentBlocks` 来源块的学生可见文字只能出现一次。关系构图若拆分同一来源块，只允许把原文连续切成 DOM 片段，片段按 DOM 顺序拼接后的 textContent 必须逐字等于该来源块原文；严禁“整块原文 + 派生子项”双重输出，严禁先显示完整段落再把其中短句复制成小卡、标签或徽章。
11b. `semanticCompositionContract.required=true` 时由语义关系决定构图。真实对比可使用并列/分区，真实步骤可使用有序节奏，真实列表必须保持列表形态；连续说明不得为了丰富而拆块，逗号连接的同一句话不得被拆成多个表面。
11c. `visualHierarchyContract.required=true` 时执行 `semanticHierarchyFirst=true`：优先级固定为来源保真、语义关系、阅读清晰、排版优雅、最后才是装饰。该突出的重点才在原句原位置使用字重、下划线或柔和底色；该体现的对比、步骤、列表才用对应关系构图。排版优雅优先，装饰不是必选项，纯 CSS 装饰只在改善构图时使用 0—2 组；不得为了丰富度增加表面，不得用装饰替代内容关系，禁止自动生成 Emoji、图标文字、标签文案或解释词。
12. `PAGE_DATA.visualRecipePlan.mediumReadingAreaBalance.required` 为 `true` 时，必须在 `.knowledge-content--medium-structured` 上使用真实分组的分布式构图（例如 `display:grid` 与 `align-content:space-between`）；只可调整模块比例、密度和真实组间距，使主体约覆盖可用阅读区的 60%—75%。不得用空块、隐藏文本、单一卡片强拉高或新增学生文案填满。
13. `PAGE_DATA.footerContract.required` 为 `true` 时，最终 HTML 必须无条件输出且只输出一个与字段匹配的 `<footer class="knowledge-footer">`、`<button class="knowledge-primary-button">` 与按钮原文；不得条件省略、运行时创建、`display:none`、`visibility:hidden`、`opacity:0`、裁到 `.knowledge-scroll` 内或被正文覆盖。`pageAction` 非空时 CTA 必须在 `scrollTop=0`、中段和最大值持续可见并可点击。

R36 必须在最终 HTML 中真实定义并按 `visualRecipePlan.recipes` 选用这些 class：`.content-module--intro-band`、`.content-module--open-flow`、`.content-module--list-compact`、`.content-module--sequence-compact`、`.content-module--emphasis`、`.content-module--comparison`、`.content-module--process-steps`、`.content-module--role-inline`、`.content-module--evidence-quote`。构图由真实语义关系决定，禁止 `sameWhiteCardStack` 与 `positionOnlyDifferentiation`；中篇内容仅用真实分组和有限间距覆盖主要阅读区。这些 class 不得作为学生可见文字；列表必须保留其原有列表语义和标签。

## 3. 固定运行底座与动态边界

每条模型提示词必须完整重复以下规则，不得只引用本文件：

- HTML 内必须包含 Creator Review SDK 脚本，并实现 `safeNextPage()`、`safeComplete()`。
- 平台壳层负责状态栏、关闭按钮、页面类型胶囊和进度条；HTML 内不生成平台壳层、`知识讲解`胶囊、Pxx、顶部安全区或空白占位。
- 第一个学生可见元素只能是非空 `transitionText`、合法的 `preTitleBlocks` 首块或原文 `title`；具体顺序必须由本页 PAGE_DATA 确定，不得写死其他课程标题。
- `before_title` 的过渡句必须作为 `.knowledge-content` 首个学生可见元素并位于标题前；`after_content` 必须作为最后正文块后的 `.knowledge-content` 最后一个元素。两者统一使用 `.knowledge-transition`，不得作为普通 `<p>`、卡片、按钮或互动题字段输出。
- 页面壳必须执行 `UNIFIED_PERSISTENT_BOTTOM_ACTION_BAR`：`html`、`body` 与 `.knowledge-page` 高度均锁定为 `100%`，不得依赖动态视口单位。
- 长短页统一使用 iframe 内绝对定位底栏；`.knowledge-footer` computed `position:absolute` 且 `left/right/bottom=0px`，按钮自身 computed `position:static`。
- 页面只有 `.knowledge-scroll` 一个内部纵向滚动容器；它必须显式使用 `box-sizing:border-box`，避免 `height:100%` 与上下 padding 按 content-box 叠加后把滚动层撑出 iframe。其底部 padding 必须由底栏真实高度动态同步，并额外保留 `24px`。滚到最大 `scrollTop` 后，最后一个正文块必须完整停在按钮上方，不得进入底栏可视区域。
- 在 `scrollTop=0`、中段和最大值时，底栏与按钮都必须保持可见、可点击且位置不漂移。
- 内容视口顶部保留且仅保留 `8px` 呼吸空间；标题按可用宽度自然换行，使用 Chrome 68 可用的普通换行和 `overflow-wrap: break-word`。只有需避免拆开的最小原文短语或英文词可使用 `.title-keep { white-space: nowrap; }`。
- 页面统一采用 `#d7c4ff → #dce4ff → #d5f5fe` 的纵向连续渐变：在页面 `66.667%` 前自然进入 `--page-bottom-bg`，其后保持同一纯色。footer 使用同一 `--page-bottom-bg` 实底，且不得有边框、阴影、模糊、`::before` / `::after` 羽化层或可见水平分界；footer 与页面底部必须视觉连续。footer 只保留按钮上下各 `10px`（下方另加 safe-area）的几何空间。课程主按钮使用实色 `#9260fe`，白字、`60px` 最小高度、`40px` 圆角。
- 页面内部不得生成任何页型胶囊；原文标题存在时必须居中，并保持原文、顺序和首个学生可见元素合同不变。
- `.knowledge-content` 必须采用 `box-sizing: border-box; width: 100%; max-width: 680px`；移动端使用固定 `24px` 左右安全边距，宽屏媒体查询可增至 `35px`。内容区仍按 `DESIGN_BRIEF` 动态构图。
- 全页只有固定底栏中的主按钮调用课程 SDK，且必须无条件保留 `<footer class="knowledge-footer">` 与 `<button class="knowledge-primary-button">` 的最终 DOM；禁止将 footer 放入 `.knowledge-scroll`、以条件分支省略按钮，或用隐藏样式替代 CTA。
- 内容区 DOM、卡片数量和排版必须根据 `DESIGN_BRIEF` 与本页语义动态变化；不得新增、删减、改写、调序或重复学生可见文案。
- 相邻页面不得机械重复同一构图；允许共享颜色、字体、圆角、阴影与底栏，但教学动作、内容形状或信息密度不同时，主构图与层级节奏应随之变化。
- 除 SDK 脚本外，不依赖外部框架、外部字体、在线图片或其他网络资源。

动态页不核对变量区外 SHA-256。通过条件是内容无损、纯 HTML、运行底座、SDK、computed style、短页 / 长页双态和真实渲染均通过。

R36 注入优先级：S6 只替换本文件第 2 节的首个 `<PAGE_DATA>` 与 `<DESIGN_BRIEF>` 区块。下列 R11 历史样例仅保留 CSS / JS 视觉参考，绝不得覆盖、补全或重解释该次注入的 `contentBlocks`、页号、课次、语义分组或学生文案。

## 4. 当前唯一 S6 注入主体（结构占位）

用途：唯一装配器读取本节 `PAGE_DATA` 与 `DESIGN_BRIEF` 后替换下方两个标记区；其中课次、页号、页序、正文、动作、视觉配方及底栏字段均只是结构占位，绝不作为 lesson020 或任何历史页面的回退数据。

```text
提示词版本号：RunS-Knowledge-L020-P03-Dynamic-OneShot-v1.7-20260724-R11-019f9191b1

适用页面：lesson020｜P03｜第 3/11 页｜知识讲解页。

配图增强合同：`PAGE_DATA.visualAsset` 为单图，`PAGE_DATA.planVisualAssets` 为组图；只允许二选一，不得增删、改写 URL、alt、displayLabel、visualReview 或 placement。图片是正文主配图，禁止缩略图、小装饰条或图标尺寸；必须按 `PAGE_DATA.visualPresentation` 使用内容区宽度、自然比例、`object-fit: contain`、`16px` 圆角和 `16px` 上下间距，不额外套独立卡片。教案配图必须按每项教师锚点插在 `insertAfterText` 与 `insertBeforeText` 之间；课件配图必须执行 resolved 中模型看图审阅后的 placement，无法唯一判断时放在页面标题下方。任何图片都不得成为正文最后一块或紧邻 CTA/footer。两张及以上图片一律按 S5 冻结顺序纵向全宽排列；禁止三列、宫格、并排或缩略图，不得自行根据故事情节把 A/B/C 调序。每张图片必须由 `<button type="button" class="image-zoom-trigger">` 触发同页 `.visual-lightbox`；必须提供圆形 × 的 `.visual-lightbox-close`，关闭控件位于图片底部与视口底部之间的纵向中点，且支持点击遮罩关闭与 `Escape` 关闭。禁止外链预览、打开新窗口或新标签页；缩放按钮不得调用 CreatorReviewSDK。

组图文案相邻合同：当 `PAGE_DATA.planVisualAssets[]` 每项都含 `pairedStudentText` 与 `pairedSource` 时，唯一 `.visual-gallery` 内必须且只能生成一个 `<ul class="visual-paired-list">`，按数组顺序为每项生成一个 `<li class="visual-paired-item" data-visual-pair-asset-id="对应 assetId">`；每个 item 内依次相邻放置本图触发器、本图 `displayLabel` 图注和唯一 `<p class="visual-paired-copy">pairedStudentText 原文</p>`，上一项的对应文案必须出现在下一张图之前。`pairedStudentText` 已消费 `pairedSource` 指向的原列表项，该原列表项不得再在普通列表或其他区域重复渲染；整页逐字原序单次投影仍成立。只有整组缺少完整、无歧义的配对字段时，才兼容使用旧式纵向 gallery，并按原位置单独渲染来源列表；不得猜配、改写或因此停止生成。

非开篇视觉基线：正文与图片共用内容区左右边界；必须声明并应用 `--runs-type-h1-size`、`--runs-type-h2-size`、`--runs-type-body-size`、`--runs-type-list-size`、`--runs-type-caption-size`。正文中的唯一 `.visual-gallery` 必须声明 `data-visual-group-layout="vertical_stack" data-visual-placement-terminal="forbidden"`。图片本体是唯一放大触发器，不显示独立查看按钮。遮罩 DOM 必须依次包含 `.visual-lightbox-dialog`、`.visual-lightbox-stage`、图片下方且不随图片移动的 `.visual-lightbox-close`，遮罩内不重复 caption。脚本必须提供 `positionVisualClose`，使用 `getBoundingClientRect` 实时计算关闭按钮中点位置；同时提供 `touchstart`、`touchmove`、1–4 倍两指缩放、放大后单指平移以及 `resetVisualTransform` 关闭复位，并保留遮罩与 `Escape` 关闭。

请根据本提示词中的 PAGE_DATA 与 DESIGN_BRIEF，生成一个完整、可运行的移动端单文件 HTML 网页。

这是一次性提示词，没有任何外部上下文。不得读取本地路径、SOP、模板、历史页面、上一轮对话或其他课程。PAGE_DATA 是唯一学生可见内容源；DESIGN_BRIEF 只指导构图，绝不渲染。

最终回复必须且只能包含从 <!doctype html> 到 </html> 的纯完整 HTML。不得输出 Markdown 围栏、解释、版本号、PAGE_DATA、DESIGN_BRIEF、QA 报告或调试信息。

<PAGE_DATA>
{
  "lessonId": "lesson020",
  "pageId": "P03",
  "pageIndex": 3,
  "pageCount": 11,
  "pageType": "knowledge_explanation",
  "transitionText": "",
  "transitionPlacement": "none",
  "title": "第一步，检查结果有没有完成原任务",
  "visibleContentBlocks": [
    {
      "type": "paragraph",
      "text": "原任务要求海报包含活动时间、地点和报名截止时间。"
    },
    {
      "type": "paragraph",
      "text": "AI生成的初版已经有标题和活动地点，却没有报名截止时间。"
    },
    {
      "type": "paragraph",
      "text": "任务达成检查，就是把结果与对象、用途和必要要求逐项对照。版面再漂亮，也不能补上缺少的关键信息。"
    }
  ],
  "pageAction": "next"
}
</PAGE_DATA>

<DESIGN_BRIEF>
{
  "nonRenderable": true,
  "teachingAction": "检查结果是否完成原任务",
  "contentShape": "problem_to_method_to_result",
  "readingFlow": ["先看原任务必要要求", "再发现初版缺口", "最后理解任务达成检查方法"],
  "semanticGroups": [
    {"id": "requirements", "blockIndexes": [1], "purpose": "原任务必要要求"},
    {"id": "gap", "blockIndexes": [2], "purpose": "AI 初版缺口"},
    {"id": "method", "blockIndexes": [3], "purpose": "检查方法与边界"}
  ],
  "density": "light",
  "rhythmRole": "structured",
  "hierarchyFocus": ["gap", "method"],
  "layoutFreedom": "允许把要求与缺口组织成对照关系，并让方法成为收束重点；不绑定左右栏或卡片数量。",
  "visualSystem": "沿用 RunS 浅紫系统、克制圆角与统一固定底栏。",
  "visibleCopyPolicy": "只显示 PAGE_DATA 原文；原文已有小标签可独立呈现，不显示本简报。"
}
</DESIGN_BRIEF>

内容硬规则：

1. `contentBlocks` 必须逐块逐字、按原顺序各显示一次；heading 只作为其原文标题显示，段落和列表不得删减、改写、合并、拆句改写、调序、重复或新增学生可见文案。
2. `transitionText` 非空时必须按 `transitionPlacement` 逐字渲染；为空时不得生成过渡句。
3. 第一个学生可见 DOM 元素必须根据本次 PAGE_DATA 动态确定，不得复制其他课程、历史样例或示例页面标题。
4. 不得生成副标题、总结、结论、解释标签、P03、知识讲解胶囊、来源、QA、semantic unit 或生产说明。
5. 不得生成题干、选项、答案、解析、互动规格或任何答题控件。
6. 内容区可以按原文关系独立设计，但只能使用 PAGE_DATA 中已有文字；装饰元素不得携带新增文字。
7. P3 不生成音频、播放器、TTS、字幕、CUE、输入框或 Powered by RunS。
8. 知识讲解与案例分析的学生内容卡一律禁止装饰性左侧彩色竖线、轨道、连接点或箭头；不得使用 `border-left`，也不得以 `::before` / `::after` 在卡片左缘制造强调线、点列或箭头。语义层级只能使用原文的字号、字重、底色、描边、阴影、间距与完整容器比例表达。
9. 中等篇幅知识讲解页不得让内容仅堆在上半屏；当本页有三块及以上真实阅读块时，必须只用原文分层、卡片尺寸和垂直节奏平衡主要阅读区。不得新增学生文案、空白占位、强拉单一卡片或可见连接轨凑高度；两条短原文 `two_layer_reading` 不硬凑内容。
10. `visualRecipePlan` 必须逐项落实，不显示字段名或配方名：`intro_observation_band` 使用 `content-module--intro-band`，`open_body_flow` 使用 `content-module--open-flow` 保留开放式非卡片正文，`inline_conflict_evidence` 使用 `content-module--inline-conflict` 保持同一自然句流并只做行内证据标色，`list_or_option_compact` 使用 `content-module--list-compact` 保留真实列表，`sequence_compact` 使用 `content-module--sequence-compact`，`analysis_conclusion_emphasis` 使用 `content-module--emphasis`，`evidence_quote_focus` 使用 `content-module--evidence-quote` 承接原文确有的引用或证据，`comparison_split` 使用 `content-module--comparison` 形成真实对比区域，`process_steps` 使用 `content-module--process-steps` 表达原文已有先后关系，`role_distribution_inline` 使用 `content-module--role-inline` 与 `continuous_inline_highlights` 在同一连续句流中表达媒介或角色分工；不得为这些结构新增学生可见标签。禁止 `sameWhiteCardStack` 和仅靠位置移动的 `positionOnlyDifferentiation`。
10a. `sourceTextProjectionContract.required=true` 时，每个 `contentBlocks` 来源块的学生可见文字只能出现一次。关系构图若拆分同一来源块，只允许把原文连续切成 DOM 片段，片段按 DOM 顺序拼接后的 textContent 必须逐字等于该来源块原文；严禁“整块原文 + 派生子项”双重输出，严禁先显示完整段落再把其中短句复制成小卡、标签或徽章。
10b. `semanticCompositionContract.required=true` 时由语义关系决定构图。真实对比可使用并列/分区，真实步骤可使用有序节奏，真实列表必须保持列表形态；连续说明不得为了丰富而拆块，逗号连接的同一句话也不得被拆成多个表面。禁止 `uniformRoundedCardStack`、嵌套同款圆角卡和仅改变底色的纵向等宽卡栈。
10b-1. `alignmentContract` 必须执行左对齐优先、顶部对齐优先：同级内容共享左边界；同级对比项顶边对齐且等宽；步骤项共享同一左边界。只有明确主次关系才允许非对称，禁止随机缩进、随机宽度和为了变化而错位。
10b-2. `comparisonLayoutContract` 允许图示这种篇幅使用顶边对齐、等宽的左右卡；任一对比项超过 80 个字符或两项合计超过 150 个字符时，必须改为上下同宽、共享左边界的纵向排列。
10b-3. `highlightContract` 要求全页最多 3 个高亮片段；同类信息使用同一种强调样式。12 个字符以内的短高亮词组整体换行，宁可整体移到下一行，也不得留下 1—2 个字的孤立高亮尾巴。
10b-4. 最终 HTML 必须兼容 Android System WebView Chrome 68。基础布局、首屏文字、正文滚动和固定按钮不得依赖新 CSS 函数、动态视口单位、新 JavaScript 语法或新 DOM API；观察器必须先检测再使用，缺失时基础内容仍直接显示。
10c. `visualHierarchyContract.required=true` 时执行 `semanticHierarchyFirst=true`：优先级固定为来源保真、语义关系、阅读清晰、排版优雅、最后才是装饰。该突出的重点才在原句原位置使用字重、下划线或柔和底色；该体现的对比、步骤、列表才用对应关系构图。排版优雅优先，装饰不是必选项，纯 CSS 装饰只在改善构图时使用 0—2 组；不得为了丰富度增加表面，不得用装饰替代内容关系，禁止自动生成 Emoji、图标文字、标签文案或解释词。
10d. `designExecutionContract.required=true` 时，S5 已完成页面设计，S6 不得重新推测：严格按 `layoutArchetype` 与 `groupPresentation` 决定几何和浅色表面；严格按 `sourceProjectionPlan` 逐块投影。`inline_conflict_evidence` 必须使用 `continuous_inline_flow` 保持同一自然句流，只给证据子串行内标色，严禁拆成独立左右卡；`sentence_sequence` 必须在一个 section 内使用 `single_section_flat_steps`；`role_distribution_inline` 必须使用 `continuous_inline_highlights`，整句作为一个连续文本流渲染，`punctuated clauses 不得拆成独立块`。所有 fragments 必须按顺序各出现一次且拼接等于来源块；任何 fragment 不得成为句首孤立标点或独立句号。`emphasisTargets` 只能在原句原位置标色，不得抽取成标签或第二份文字。`surfacePolicy.lightDominant=true` 且 `nonCodeDarkSurfaceAreaPercentMax=0` 时，非代码内容禁止大面积近黑背景；结论使用浅紫或浅蓝表面加局部主题色文字。最终 DOM 的顶层视觉区标记 `data-visual-region="top"` 且不得超过 `maximumTopLevelVisualRegions`；无文字 CSS 装饰不得超过 `maximumDecorativeGroups` 组且可以为零。必须遵守 `spaceBalance.maximumUnusedLowerAreaPercent`，不得靠扩大空白制造层级。
11. 当 `mediumReadingAreaBalance.required=true`，`.knowledge-content` 必须额外使用 `.knowledge-content--medium-structured`、`display:grid` 和 `align-content:space-between`，仅凭真实原文分组使主体约覆盖可用阅读区的 60%—75%。
12. 当 `orderedListOrdinalContract.required=true`，有序列表只能遍历该列表 `items[]` 内 `itemIndex + 1`；每个列表必须从 1 连续编号，禁止 `contentBlockIndex`、`globalCounter`、Markdown 既有序号与生成序号的 `doubleNumbering`。
13. 当 `unorderedListPresentationContract.required=true`，无序列表只显示 `items[]` 原有文字标签；不得生成 `numericBadge`、`autoOrdinal`、数字圆点或其他自动序号，特别是不得把“画面A/B/C”等已有标签转换为 `1/2/3`。

HTML 与页面壳硬规则：

- 必须包含：
  <script src="https://res.xrunda.com/runs/plugin/creator/creator-review-sdk.js"></script>
- 除上述 SDK 外，不依赖外部框架、字体、图片或网络资源。
- 页面适配 360–430px 手机宽度；不得横向滚动。
- 平台负责顶部状态栏、关闭按钮、页面类型胶囊和进度条；页面内部不得生成 top-safe-area、102px/132px 顶部占位、平台胶囊或进度条。
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
.knowledge-page {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: linear-gradient(180deg, #d7c4ff 0%, #dce4ff 42%, var(--page-bottom-bg) 66.667%, var(--page-bottom-bg) 100%);
}
.knowledge-scroll {
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 8px 0 calc(var(--footer-h) + 24px);
  -webkit-overflow-scrolling: touch;
}
.knowledge-content {
  box-sizing: border-box;
  width: 100%;
  max-width: 680px;
  margin: 0 auto;
  padding: 0 24px;
}
.knowledge-content h1 {
  overflow-wrap: break-word;
  text-align: center;
}
.title-keep {
  white-space: nowrap;
}
.knowledge-transition {
  display: block;
  margin: 0 0 16px;
  padding: 6px 0;
  color: rgba(39, 39, 52, 0.58);
  font-size: 14px;
  font-weight: 400;
  line-height: 1.65;
  letter-spacing: 0.01em;
  text-align: left;
  background: transparent;
  border: 0;
  border-radius: 0;
  box-shadow: none;
}
.knowledge-transition::before,
.knowledge-transition::after {
  content: none;
}
.knowledge-content > .knowledge-transition:last-child {
  margin: 16px 0 0;
}
.knowledge-footer {
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
.knowledge-primary-button {
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
  <main class="knowledge-page">
    <div class="knowledge-scroll">
      <article class="knowledge-content">原文标题和全部正文</article>
    </div>
    <footer class="knowledge-footer">
      <button class="knowledge-primary-button" type="button">继续学习</button>
    </footer>
  </main>
- 页面必须实现 UNIFIED_PERSISTENT_BOTTOM_ACTION_BAR：`.knowledge-footer` computed position 为 absolute 且 left/right/bottom 均为 0px；按钮自身为 static。
- 只有 `.knowledge-scroll` 可以纵向滚动；它必须使用 `box-sizing:border-box`。短页与长页在任意滚动位置都持续显示底栏。`.knowledge-scroll` 的底部预留必须用 JavaScript 同步底栏真实高度并额外保留 24px。
- 全页只有该按钮调用课程 SDK；页面动作是 next，按钮文案必须是“继续学习”。
- `footerContract.required=true` 时必须无条件输出且只输出一个与字段匹配的 `<footer class="knowledge-footer">` 与 `<button class="knowledge-primary-button">`；不得条件省略、运行时创建、`display:none`、`visibility:hidden`、`opacity:0`，也不得放进 `.knowledge-scroll`。

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
  var footer = document.querySelector(".knowledge-footer");
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
    document.querySelector(".knowledge-footer")
  );
}
</REQUIRED_JS>

请直接输出最终完整 HTML。
```

## 5. 完整可复制实例 B：lesson020 P07（长内容样例）

来源与状态同上；用于验证较长知识页的唯一内部滚动、固定底栏持续可见和末尾内容不被遮挡，不代表 P3 或真实渲染通过。

```text
提示词版本号：RunS-Knowledge-L020-P07-Dynamic-OneShot-v1.7-20260724-R11-019f9191b2

适用页面：lesson020｜P07｜第 7/11 页｜知识讲解页。

请根据本提示词中的 PAGE_DATA 与 DESIGN_BRIEF，生成一个完整、可运行的移动端单文件 HTML 网页。

这是一次性提示词，没有任何外部上下文。不得读取本地路径、SOP、模板、历史页面、上一轮对话或其他课程。PAGE_DATA 是唯一学生可见内容源；DESIGN_BRIEF 只指导构图，绝不渲染。

最终回复必须且只能包含从 <!doctype html> 到 </html> 的纯完整 HTML。不得输出 Markdown 围栏、解释、版本号、PAGE_DATA、DESIGN_BRIEF、QA 报告或调试信息。

<PAGE_DATA>
{
  "lessonId": "lesson020",
  "pageId": "P07",
  "pageIndex": 7,
  "pageCount": 11,
  "pageType": "knowledge_explanation",
  "transitionText": "",
  "transitionPlacement": "none",
  "title": "第三步，检查公开使用的个人信息和素材边界",
  "visibleContentBlocks": [
    {
      "type": "paragraph",
      "text": "社区群还有一份发布说明：公开海报只使用已经获得允许的素材，不展示个人联系方式。主要插图由AI生成或协助制作时，要标注“AI辅助插图”。"
    },
    {
      "type": "paragraph",
      "text": "对照这份说明，工作人员发现初版使用了一张未经允许的可识别儿童照片。画面里有个人手机号，也没有标注“AI辅助插图”。"
    },
    {
      "type": "paragraph",
      "text": "这些问题不属于版面美观。它们关系到个人信息、肖像素材、授权和观看者是否会被误导。"
    },
    {
      "type": "paragraph",
      "text": "公开使用前，要根据当前场景和适用规则检查这些边界。无法核实的重要事实、未获允许的素材或高风险内容，应停止使用并求助。"
    }
  ],
  "pageAction": "next"
}
</PAGE_DATA>

<DESIGN_BRIEF>
{
  "nonRenderable": true,
  "teachingAction": "检查公开使用中的个人信息和素材边界",
  "contentShape": "problem_to_method_to_result",
  "readingFlow": ["先读取发布说明", "再识别初版问题", "区分美观与合规边界", "最后形成公开使用前的处理原则"],
  "semanticGroups": [
    {"id": "policy", "blockIndexes": [1], "purpose": "当前场景的发布说明"},
    {"id": "problems", "blockIndexes": [2, 3], "purpose": "初版问题及其性质"},
    {"id": "boundary", "blockIndexes": [4], "purpose": "公开使用前的边界与行动"}
  ],
  "density": "medium",
  "rhythmRole": "narrative",
  "hierarchyFocus": ["problems", "boundary"],
  "layoutFreedom": "允许把相邻问题段组织成一个完整问题区，再用边界段收束；不绑定一段一卡或等宽布局。",
  "visualSystem": "沿用 RunS 浅紫系统、克制语义强调与统一固定底栏。",
  "visibleCopyPolicy": "只显示 PAGE_DATA 原文；原文已有小标签可独立呈现，不显示本简报。"
}
</DESIGN_BRIEF>

内容硬规则：

1. `contentBlocks` 必须逐块逐字、按原顺序各显示一次；heading 只作为其原文标题显示，段落和列表不得删减、改写、合并、拆句改写、调序、重复或新增学生可见文案。
2. `transitionText` 非空时必须按 `transitionPlacement` 逐字渲染；为空时不得生成过渡句。
3. 第一个学生可见 DOM 元素必须根据本示例 PAGE_DATA 动态确定，不得复制其他课程或示例页面标题。
4. 不得生成副标题、总结、结论、解释标签、P07、知识讲解胶囊、来源、QA、semantic unit 或生产说明。
5. 不得生成题干、选项、答案、解析、互动规格或任何答题控件。
6. 内容区可以根据四段原文的真实关系独立设计，但只能使用 PAGE_DATA 中已有文字；不得为了画面增加学生可见标签。
7. P3 不生成音频、播放器、TTS、字幕、CUE、输入框或 Powered by RunS。

HTML 与页面壳硬规则：

- 必须包含：
  <script src="https://res.xrunda.com/runs/plugin/creator/creator-review-sdk.js"></script>
- 除上述 SDK 外，不依赖外部框架、字体、图片或网络资源。
- 页面适配 360–430px 手机宽度；不得横向滚动。
- 平台负责顶部状态栏、关闭按钮、页面类型胶囊和进度条；页面内部不得生成 top-safe-area、102px/132px 顶部占位、平台胶囊或进度条。
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
.knowledge-page {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: linear-gradient(180deg, #d7c4ff 0%, #dce4ff 42%, var(--page-bottom-bg) 66.667%, var(--page-bottom-bg) 100%);
}
.knowledge-scroll {
  box-sizing: border-box;
  width: 100%;
  height: 100%;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 8px 0 calc(var(--footer-h) + 24px);
  -webkit-overflow-scrolling: touch;
}
.knowledge-content {
  box-sizing: border-box;
  width: 100%;
  max-width: 680px;
  margin: 0 auto;
  padding: 0 24px;
}
.knowledge-content h1 {
  overflow-wrap: break-word;
  text-align: center;
}
.title-keep {
  white-space: nowrap;
}
.knowledge-transition {
  display: block;
  margin: 0 0 16px;
  padding: 6px 0;
  color: rgba(39, 39, 52, 0.58);
  font-size: 14px;
  font-weight: 400;
  line-height: 1.65;
  letter-spacing: 0.01em;
  text-align: left;
  background: transparent;
  border: 0;
  border-radius: 0;
  box-shadow: none;
}
.knowledge-transition::before,
.knowledge-transition::after {
  content: none;
}
.knowledge-content > .knowledge-transition:last-child {
  margin: 16px 0 0;
}
.knowledge-footer {
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
.knowledge-primary-button {
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
  <main class="knowledge-page">
    <div class="knowledge-scroll">
      <article class="knowledge-content">原文标题和全部正文</article>
    </div>
    <footer class="knowledge-footer">
      <button class="knowledge-primary-button" type="button">继续学习</button>
    </footer>
  </main>
- 页面必须实现 UNIFIED_PERSISTENT_BOTTOM_ACTION_BAR：`.knowledge-footer` computed position 为 absolute 且 left/right/bottom 均为 0px；按钮自身为 static。
- 只有 `.knowledge-scroll` 可以纵向滚动且必须使用 `box-sizing:border-box`；本页长内容在 scrollTop=0、中段和最大值时都必须持续显示底栏，最后正文不得被遮挡。底部预留必须用 JavaScript 同步底栏真实高度并额外保留 24px。
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
  var footer = document.querySelector(".knowledge-footer");
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
    document.querySelector(".knowledge-footer")
  );
}
</REQUIRED_JS>

请直接输出最终完整 HTML。
```

## 6. 输出校验与阻断

模型回复必须通过：

1. 纯完整 HTML 与 JavaScript 语法检查。
2. `transitionText + contentBlocks` 可见文字逐字、按冻结位置与原顺序、各一次比对；`ordered_list` / `unordered_list` 语义不得互换，且每块的 `markdown` 必须与 S5 原样一致。
3. 无 `PAGE_DATA`、`DESIGN_BRIEF` 字段、内部页码、类型胶囊、来源审计、题目内容和新增教学文案。
4. SDK 脚本、唯一课程按钮、正确 `pageAction`、无第二个课程导航事件。
5. 共享 CSS 基线与 computed style 检查。
6. 约 `390×844` 短页 / 长页真实渲染检查：在 `scrollTop=0`、中段和最大值时底栏持续可见，最后正文不被遮挡。
7. `DESIGN_BRIEF` 字段与分组合法；真实页面能表达 `readingFlow` / `hierarchyFocus`，不存在强制对称、一段一卡、同权重平铺或简报泄漏。
8. 同课相邻动态页做批次节奏检查：视觉系统可一致，但主构图不得因机械复用而单一；内容形状不同却连续重复同一构图时阻断。

任一基础项失败，标记 `V35_KNOWLEDGE_DYNAMIC_ONESHOT_INVALID`；设计简报字段、分组、泄漏、可见文案、构图表达或批次重复分别标记 `V35_DYNAMIC_DESIGN_BRIEF_INVALID`、`V35_DYNAMIC_SEMANTIC_GROUP_INVALID`、`V35_DYNAMIC_DESIGN_BRIEF_LEAK`、`V35_DYNAMIC_VISIBLE_COPY_DRIFT`、`V35_DYNAMIC_SEMANTIC_PRESENTATION_MISSING`、`V35_DYNAMIC_LAYOUT_MONOTONY` 或 `V35_DYNAMIC_FORCED_SYMMETRY`；固定底栏、唯一内部滚动容器、动态底部预留、底色令牌不一致、可见水平分界 / 独立色块 / 边框 / 阴影 / 模糊或长页无遮挡失败时同时标记 `V35_PERSISTENT_FOOTER_LAYOUT_INVALID`。以上均阻断 `S3G`、`S5.1`、`final_import`、dry-run 和 create。
