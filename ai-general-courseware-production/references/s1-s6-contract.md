# AI 通识课网页课件生成：R36 六阶段合同

本文件是公开 skill 包内唯一的 R36 阶段合同快照。仅适用于 `ai-general-courseware-production` 同包的模板、Demo、装配器和校验器；升级合同必须发布新的 skill 版本，不能混读安装者本机的历史文件。

当前合同：`RunS_V3.5.0-S1-S6-R36-20260731`。

本文是当前六阶段的唯一执行正文。其他当前文档只承担入口、范围、资产或质量索引职责，不能另行解释、改写或补充阶段处理动作。

`S1 → S2 → S3 → S4 → S5 → S6`

## 0. 通用执行规则

- 上游声明的唯一输入必须完整、相互一致且已冻结；缺失、冲突、未冻结或读取了未声明输入，一律 `BLOCKED`。
- 每阶段只生成本阶段声明的输出。下游产物、页面提示词、整课 JSON、导入、运行、渲染、测试与发布均不得提前生成或执行。
- 原始教师版 `final.md` 只读。学生版只在 S2 作结构辅助核查，不能成为课程语义真源。
- 产物发生内容变更时，从发生变更的阶段开始，按阶段顺序重新冻结和验证；不得只补下游文件。

| 阶段 | 唯一/主要输入 | 唯一输出 | 放行条件 |
| --- | --- | --- | --- |
| S1 教案预处理 | 教师版 `final.md`、课程信息 | `source_manifest.json`、`final_preprocessed.md`、`preprocess_comparison.json` | 来源、六项课程信息和教师正文可逐项追溯。 |
| S2 页面规划工作版 | 冻结 `final_preprocessed.md`；学生版仅辅助 | `page_plan_working_full.md`、`student_structure_check.md` | 页面边界、类型、顺序及过渡句归属明确。 |
| S3 题目处理 | 仅 `page_plan_working_full.md` | `question_processed_full.md` | 完整继承 S2 页面规划；每个互动页原位追加自然语言与 JSON 数据，题干完整。 |
| S4 最终有效页面规划 | 冻结工作版、已批准题目 JSON | `page_plan_full.md` | 页面元数据与题目归属一致，互动 JSON 原样冻结。 |
| S5 有效内容 JSON | 仅 `page_plan_full.md` | `effective_content_full.json` | 内容无损投影及模板前置编排完成。 |
| S6 整课 JSON 装配 | 冻结且 S5 通过的 `effective_content_full.json` | 整课 JSON、装配校验结果 | 仅到 `IMPORT_READY_STATIC`。 |

## S1 教案预处理

### 输入合同

S1 只读取以下两类输入：

1. 教师版 `final.md`：唯一课程语义真源，原文件只读。
2. 课程信息：必须完整提供且冻结以下六项原文值：`课包名称`、`单元名称`、`课程编号`、`课程标题`、`课程目标`、`知识点`。`lesson_id` 可作为机器标识登记，但不替代六项课程信息。

学生版、历史“题目处理版教案”、题目组件 JSON、页面模板和单课执行证据均不是 S1 输入。

### 处理动作

1. 读取并登记教师版和课程信息的绝对路径、SHA-256 与当前合同版本；确认课程编号/标题与教师正文一致。
2. 将六项课程信息原文写入预处理头；只允许添加机器可读的来源头与边界标记，不得改写其值。
3. 在 `<!-- 教师正文开始 -->` 之后逐字节复制教师版正文，保持字序、标题层级、段落边界、标点、代码块和原有标记。不得删减、补写、概括、重排、提取题目、识别页面块或生成任何 JSON。
4. 将来源与正文比对结果写入比较文件。预处理头不属于教师正文，也不得被后续阶段当作学生可见正文。

### 输出字段合同

`source_manifest.json` 必须含：

- `schema_version`、`lesson_id`、`stage: "S1"`、`sop_version`、`status`；
- `source_authority.teacher_final: "唯一课程语义真源"`；
- `sources.teacher_final`、`sources.course_info`、`sources.sop_entry` 及各自 SHA-256；学生版如登记，只能标注 `S2 辅助结构核查，不在 S1 分析`；
- 原文六项 `course_info`；
- 三个输出路径与 SHA-256；
- `checks.six_course_fields_complete`、`checks.teacher_body_byte_preserved`、`checks.teacher_body_sha256_matches`；
- `blocking_points`。不得含题目、场景、课后任务、页面块、声明/推断或资源分支字段。

`final_preprocessed.md` 必须由两部分组成：

1. `S1` 来源预处理头：合同版本、`source_manifest.json` 引用及六项课程信息原文；
2. `<!-- 教师正文开始 -->` 后的教师正文逐字节副本。

`preprocess_comparison.json` 必须含：`schema_version`、`lesson_id`、`sop_version`、教师源路径/SHA-256、预处理文件 SHA-256、教师正文前后字节数与 SHA-256、六项字段完整性、允许变化清单（仅预处理头与边界标记）、`status`、`blocking_points`。正文摘要、块类型、题目数据或页面判断都不得写入该文件。

### S1 Gate

以下任一情况为 `BLOCKED`：教师版或课程信息缺失；六项字段缺失/与教师版冲突；源 SHA 未登记；正文哈希或字节数不一致；出现未授权正文改写；输出含 S2 以后字段。仅当三个 S1 输出齐全、比对为 `PASS` 才能进入 S2。

## S2 页面规划工作版

### 输入、输出与页面块格式

S2 的冻结验证只读取同课 `source_manifest.json` 的 `outputs.final_preprocessed.path`、`bytes`、`sha256`，确认工作输入未漂移；课程语义只读取该声明指向的冻结 `final_preprocessed.md`。学生版只用于结构辅助核查，不得覆盖教师版语义或补写课程内容。输出仅为 `page_plan_working_full.md` 与 `student_structure_check.md`；不得生成题目 JSON、最终页面计划、有效内容 JSON、整课 JSON 或页面提示词。

工作版由一个不面向学生的“输入冻结声明”、来源路由表、互动题边界决策表、页面交接清单及连续页面块组成。四个声明块必须置于首个页面块之前。S2 只拥有“页面路由与切分”权，不拥有内容删留权：从 S1 接收到的学生正文必须逐字、按原顺序完整流经 S2、S3、S4；不得摘要、概括、补写、重排、合并或提前剔除任何看似干扰的句子。只有 S5 才能按冻结的有效内容规则处理非学生可见研发注释、状态句等不进入最终有效内容的部分，同时保留 `source.rawMarkdown` 作为上游审计真源。页面块按连续页序使用下列单行标记；标记后的内容必须按原文顺序保留该页完整学生可见内容：

```markdown
<mark>页面块 P03｜页面类型：知识讲解｜胶囊文案：知识讲解</mark>
```

输入冻结声明采用下列唯一格式；值必须逐字等于同课 S1 `source_manifest.json` 的 `outputs.final_preprocessed` 声明：

```markdown
<!-- S2_INPUT_FREEZE
source_manifest: <绝对路径>/source_manifest.json
final_preprocessed: <绝对路径>/final_preprocessed.md
bytes: 1234
sha256: <64位十六进制>
-->
```

当冻结 S1 已提供 `<!-- 内容块开始｜内容块编号：…｜类型：… -->` 标记时，输入冻结声明之后必须先写“来源路由表”。它是先路由、后落页的执行依据：每个 S1 内容块恰有一行，`来源块` 与 `原始类型` 逐字继承 S1，`路由页` 以页码顺序列出承载该块的全部页面。原始类型为“开场”的真实教学情境必须路由为“场景引入”；不得改写为知识讲解、并入课程开篇或省略。没有内容块标记的历史输入不得猜造标记，应先按完整学生正文建立等价的原文范围，再进入页面编排。

```markdown
<!-- S2_SOURCE_ROUTE_MANIFEST
| 来源块 | 原始类型 | 路由页 | 路由说明 |
| --- | --- | --- | --- |
| S1U1-L001-B01 | 开场 | P02 | 完整真实情境，作为场景引入。 |
| S1U1-L001-B02 | 知识讲解 | P03、P04 | 前段为知识讲解，完整题块连续承载为互动题。 |
-->
```

互动题边界决策表采用下列唯一格式，并包含每一个 `互动题目` 页面一行；它是研发可见的规划证据，不是学生可见内容，也不进入 S4/S5 的有效内容：

```markdown
<!-- S2_INTERACTION_BOUNDARY_AUDIT
| 互动页 | 紧邻前页 | 删除后对象 | 删除后操作 | 删除后判断标准 | 路由结论 |
| --- | --- | --- | --- | --- | --- |
| P04 | P03 | 是 | 否 | 是 | 并入互动题 |
| P06 | P05 | 是 | 是 | 是 | 案例分析前置 |
-->
```

字段只允许使用 `是/否` 与以下三种路由结论：`知识页保留`、`并入互动题`、`案例分析前置`。`紧邻前页` 为 `无` 时只允许互动题为 P01；否则必须为实际紧邻的前一页。

互动题边界决策表之后、首个页面块之前，必须紧接下列“页面交接清单”。它是 S2→S3/S4 的唯一技术交接证据，不面向学生；每个页面恰一行，按页号连续排列：

```markdown
<!-- S2_PAGE_MANIFEST
| 页号 | 页面类型 | 胶囊文案 | 来源块 | 内容块类型 | 布局意图 | 过渡句位置 | 过渡句原文 | 互动编号 | 组件类型 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| P01 | 课程开篇 | 课程开篇 | course_info_header | 课程信息头 | 六项课程信息按原顺序展示。 | none | 无 | 无 | 无 |
| P04 | 互动题目 | 试一试：选择答案 | B02 | 题目完整块 | 独立互动题页面。 | none | 无 | L001-I01 | galaxy_select_question |
-->
```

`来源块` 是稳定可追溯 ID；`内容块类型`、`布局意图`不可为空。过渡句位置只能为 `none`、`before_title`、`after_content`；为 `none` 时原文必须为 `无`，否则原文必须逐字给出。非互动页的互动编号和组件类型都为 `无`；互动题目页两者均不得为空，组件类型仅可为 `galaxy_select_question`、`matching_question`、`categorization_question`、`ordering_question`。

`student_structure_check.md` 只登记学生版路径/SHA-256、与教师版的章节或页面顺序对照、发现的结构差异及 `PASS/BLOCKED`；不得写入课程语义判断、页面内容补写、题目 JSON 或页面类型替代结论。

### 先执行、后落页的规划步骤

S2 不是把教师正文直接切成页面后再靠 Gate 纠错。每课必须依次执行下列步骤，完成上一步才可写下一步：

1. **核验并建立 P01**：先以同课 `source_manifest.json` 核验冻结 `final_preprocessed.md` 的路径、字节数和 SHA-256；再从其 S1 头部逐字复制六项课程信息，建立 `课程开篇` P01；课程开篇只允许出现在 P01。
2. **先建立完整来源路由**：逐个读取 S1 学生正文内容块，先写 `S2_SOURCE_ROUTE_MANIFEST`，为每块决定全部目标页及理由；不写概述，不删句，不先生成页面。真实开场情境必须先落为场景引入；知识、案例、互动、小结和任务的路由只决定位置与页面类型，不改变原文。
3. **圈定互动题候选块**：针对教师正文中每个有唯一标准答案的题，先圈出题目材料、问句、操作指令、选项、答案、解析、答错提示与重试方式；此时不写页面标记。
4. **逐题填写边界决策表**：对每个候选题紧邻前的动作句做删除测试，分别填写删除后作答对象、操作指令、判断标准是否仍存在；必要背景是否超过 50 字只由校验器从页面正文判断，不手填精确字数。不能用动作词本身代替删除测试。
5. **按决策表完成题目路由**：三个字段均为“是”时可用 `知识页保留`；任一字段为“否”且必要背景不超过 50 字时用 `并入互动题`，互动页起点前移至所需句子/材料；必要背景超过 50 字时用 `案例分析前置`，背景独立成紧邻互动题前的案例分析页，明确问句/操作指令从互动题开始。
6. **按来源路由逐字落页**：仅在内容脱离后续题目仍完整成立时标为知识讲解；再依正式枚举建立场景引入、课后任务、课程小结等页面。逐页复制对应原文范围，切页后串接必须与 S1 学生正文完全一致。不得为了凑页面把题干、题目背景或案例材料写成知识讲解；不得把任何块改写为摘要，也不得在此阶段剔除状态句或其他所谓干扰内容。
7. **填写页面交接清单**：为每页登记来源块、内容块类型、布局意图与过渡句元数据；为互动页登记稳定互动编号和四类组件中的目标组件。S3 只能按该互动编号处理题目；S4 只能从该清单投影页面元数据，不能重新判断来源块、布局或过渡句。
8. **课内自检再运行 Gate**：检查 P01 六项字段、来源路由表逐块覆盖、路由页存在且“开场”已成场景引入、拼回的页面正文逐字等于 S1 学生正文、页号连续、每个互动页恰有一行边界决策与一行交接清单、三表与页型/相邻关系一致、学生版未参与语义决策；确认后才运行校验器。

### 正式页面类型与路由

当前只允许以下七类页面类型；其他名称（包括“普通互动页”“轻互动页”“动态讲解页”）不是当前 S2 可输出的页面类型，若需引入必须先新增正式合同、S5 数据合同、S6 映射和校验器后再启用。

| 页面类型 | 何时使用 | 不得使用为 |
| --- | --- | --- |
| 课程开篇 | 仅 P01；承载六项课程信息。 | 一般知识页或场景页。 |
| 场景引入 | 教师正文存在用于引出本课问题的真实情境时。 | 编造情境或重复课程开篇。 |
| 知识讲解 | 可脱离后续题目独立成立的概念、方法、步骤或解释。 | 只剩题目标题、材料、问句或操作指令。 |
| 案例分析 | 某互动题必要背景超过 50 个学生可见字符时；必须紧邻该互动题之前，胶囊同为“案例分析”。 | 包含明确问句、作答指令、选项、答案、解析或研发说明。 |
| 互动题目 | 已有明确正确答案且适配四类正式题目组件的完整题块。 | 无唯一标准答案的开放互动，或只因出现动作动词而切出。 |
| 课后任务 | 教师正文存在真实课后任务时。 | 不存在任务时的“本课没有课后任务”状态页。 |
| 课程小结 | 回扣本课关键学习结果；下一课仅可作为静态预告。 | 新知识讲解、可点击的下一课入口或重复全文。 |

边界决策表是上述路由的唯一执行证据：删除后现有题干仍有作答对象、操作指令和判断标准，动作句才可留在知识页；否则随互动题前移。不得按“选择、判断、连线、排序”等动词机械路由。必要题目背景不超过 50 字时连续留在互动题；超过 50 字时改为紧邻互动题前的案例分析页。

### S2 Gate

运行：

```bash
python3 scripts/validators/validate_v35_page_plan_question_boundaries.py --working-plan-contract page_plan_working_full.md
```

以下任一情况为 `BLOCKED`：S1 冻结凭据缺失、路径/字节数/SHA-256 漂移；页面标记无法识别或页数为 0；P01 不是课程开篇或六项字段不全；页号不连续；页面类型不在七类正式枚举中；存在 S1 内容块时缺来源路由表、来源块覆盖不全/重复、原始类型或路由页不一致、“开场”未路由为场景引入、页面正文拼回后不再逐字等于 S1 学生正文；互动题缺边界决策记录、页面交接清单缺页或字段非法、记录与页面类型/相邻关系/实际背景路由不一致；学生版被当作语义真源；工作版以外的阶段产物被提前生成。校验器直接从页面正文判断是否超过 50 字；禁止人工填写或核对精确背景字数。`PASS` 后才可进入 S3。

## S3 题目处理

### 输入、输出与不可跨越边界

只读取已冻结的 `page_plan_working_full.md`，只输出 `question_processed_full.md`。不得回读教师版 `final.md`、`final_preprocessed.md`、学生版、历史题目处理版教案或任何旧页面规划；不得改动工作版中的页面块、页序、页面类型、胶囊、来源块和非互动正文。每个题目必须使用 S2 页面交接清单中该互动页登记的互动编号和组件类型；不得新编、替换或重新映射。

`question_processed_full.md` 必须是完整的 S2 派生页面规划：文件头先登记 `S3_INPUT_FREEZE`（S2 绝对路径、字节数、SHA-256），随后放置 `--- 冻结页面规划原文（只读基底） ---`，并逐字保留全部 S2 输入冻结声明、边界审计、页面交接清单和页面块。每个非互动页必须逐字不变；每个互动题页也须先逐字保留原题块，再在该页末尾原位追加一对题目数据。不得抽取为孤立题目清单、独立题目 JSON 文件、题目汇总表、页面提示词或整课 JSON。

### `question_processed_full.md` 合同

每道题必须有且仅有一对可人工审核的数据块，按题目在工作版中的顺序、紧跟其对应互动题页原文排列：

````markdown
#### 互动编号：`<interaction_id>`

##### 题目数据（自然语言版）

- 题目 ID：`<question_id>`
- 题型/组件：`<component_type>`
- 题干：<完整题干或 stem>
- 选项、分组、配对项或排序项：<完整学生作答数据>
- 答案：<正确答案或对应关系>
- 解析：<完整解析>

##### 题目数据（JSON版）

```json
{ "type": "<component_type>", "componentId": "<stable_id>", "content": {} }
```
````

自然语言版与 JSON 版必须表达同一题，且每题恰有一个 JSON 块。没有互动题时，文件只写 `NO_QUESTION_PROCESSING_REQUIRED`，不得混入空组件或伪题目。

### 题干、背景与解析规则

- 题干必须具备明确作答对象、操作指令和判断标准。判断题还必须同时包含判断对象与判断指令；被判断内容通常用引号标出。
- 默认不重复胶囊文案。只有胶囊外内容不足以独立作答时，才并入必要语境。
- 必要背景不超过 50 个学生可见字符时，写入 `question` 或 `stem`；超过 50 字的必要背景保留在紧邻互动题前的案例分析页。任何组件均禁止独立 `background` 字段。
- 题后解释答案、反馈或方法收益写入 `explanation`；引出下一知识内容的句子留在下一知识页。
- 单选必须有唯一最佳答案；多选正确项边界明确；配对/排序的可见项须足以作答。优先短句，但不得为缩短文本丢失对象、指令、标准或必要依据。

### 组件 JSON 合同

直接组件 JSON 顶层只能是 `type`、`componentId`、`content`。`componentId` 必须稳定、唯一且能回溯到课程与互动。组件内禁止课程信息、来源、QA、审核、包装字段和独立 `background`。

| 题型 | `type` | 最低合同 |
| --- | --- | --- |
| 单选/多选 | `galaxy_select_question` | `content.questions[]` 非空；每题含 `question`、`options`、`isMultiple`、`answerIndex`、`answer`。单选与多选都使用数组：单选如 `answerIndex: [0]`、`answer: ["正确选项"]`；`answer` 必须逐项对应索引选项。 |
| 配对 | `matching_question` | 每题含 `id`、`stem`、非空 `pairs[]`；每个配对项含 `id`、`left`、`right`。若解析写 `1—A`，可见配对项必须保留相应的 `1.` 与 `A.` 标签。 |
| 分类 | `categorization_question` | 每题含 `id`、`stem`、至少两组 `groups[]`；每组含名称和非空选项。`content.instruction` 必须存在且严格为 `""`。 |
| 排序 | `ordering_question` | 每题含 `id`、`stem`、至少两项 `items[]`；每项含 `id`、`name`。`questions[].instruction` 必须存在且严格为 `""`。 |

组件需要的按钮文案字段必须为字符串；不得自行增设独立操作说明字段。分类题与排序题的空 `instruction` 不得借机改变题干、选项、答案、解析、题型或题目顺序。

### S3 Gate

运行：

```bash
python3 scripts/validators/validate_question_component_json.py --stage3-contract question_processed_full.md
```

以下任一情况为 `BLOCKED`：S3 冻结凭据缺失或漂移；S2 元数据、页号、页序、页型、胶囊、非互动正文或互动题原文未逐字保留；题目数据未原位紧跟对应互动页；自然语言/JSON 证据不成对；JSON 不可解析；组件类型或字段不合规；答案与选项不一致；出现禁用字段或 `background`；分类/排序题的 `instruction` 缺失或非空；题干不完整；从未声明输入回读或越阶段输出。仅 `PASS` 可进入 S4。

## S4 最终有效页面规划

只读取冻结的 S2 `page_plan_working_full.md` 和已批准的 S3 `question_processed_full.md`；只输出 `page_plan_full.md`。输入保留在各自阶段目录，不得复制到 S4 目录或从同目录猜测输入；S4 Gate 必须显式传入这两个绝对路径。不得回读更早输入、重判页面边界或改写工作版的页号、类型、胶囊、来源块、内容块类型、布局意图、过渡句元数据及非互动原文。S4 仍不拥有删留权：研发注释不进入学生页面，但 S2 已承载的学生正文、状态句和其他原文必须逐字保留；何者不进入最终有效内容只在 S5 处理。页面交接清单是这些字段的唯一上游。

每页必须使用下列结构，`P01` 起连续编号：

```markdown
## P03
- 页面类型：知识讲解
- 胶囊文案：知识讲解
- 页面动作：nextPage
- 来源块：B03
- 内容块类型：二级标题、段落
- 布局意图：按原文顺序展示。
- 过渡句位置：none | before_title | after_content
- 过渡句原文：无 | <仅 before_title 或 after_content 时逐字登记>

### 有效内容

<完整学生可见内容>
```

所有页面冻结页号、页面类型、胶囊、页面动作、来源块、内容块类型与布局意图；最后一页仅 `complete`，此前仅 `nextPage`。P01 有效内容必须完整写出六项课程信息；没有真实课后任务时不得生成任务页或把状态句写进有效内容。

互动题页另须登记组件类型；`### 有效内容` 只能含一份来自 `question_processed_full.md` 的完整 JSON 代码块。该 JSON 必须逐字复制，禁止重新序列化、改字段/数组顺序、更换组件或从 Markdown 重建；禁止 `background`。非互动页必须逐字保留工作版学生可见原文。知识页过渡句如存在，元数据原文必须出现一次并位于 `before_title` 或 `after_content` 对应首尾。

### S4 Gate

运行：

```bash
python3 scripts/validators/validate_v35_page_plan_question_boundaries.py --effective-plan-contract \
  --working-plan <S2/page_plan_working_full.md> \
  --question-processed <S3/question_processed_full.md> \
  page_plan_full.md
```

以下任一情况为 `BLOCKED`：缺失工作版或已批准题目 JSON；元数据、P01、有效内容或页面动作不完整；页面结构或非互动原文漂移；互动 JSON 缺失、冲突、不可解析或非逐字副本；出现研发说明或下游字段。S4 不得因状态句而删改原文。`PASS` 后才可进入 S5。

## S5 有效内容 JSON

只读取冻结的 S4 `page_plan_full.md`，确定性输出唯一 `effective_content_full.json`；输入保留在 S4 目录，不得复制到 S5 目录或从同目录猜测输入，S5 Gate 必须显式传入该绝对路径。不得回读工作版、题目处理版、教师版或学生版。顶层必须含 `lesson_id`、`sop_version`、逐字指向该唯一上游的 `source_page_plan` 与非空 `pages[]`。

每页固定含六项基础字段：`page_no`、`page_type`、`capsule`、`page_action`、`source_block_ids`、`effective_content`。非互动页必须额外保留 `source.rawMarkdown`，且逐字等于上游有效内容；互动页的 `effective_content` 必须是完整题目 JSON 的有序对象投影，并使 `component_type` 等于其 `type`；所有页面禁止独立 `background`。

非互动页必须预先给出非空 `content`、有序 `sections`、`display_hints` 或 `layout_plan` 和 `source.rawMarkdown`；互动页必须给出非空 `layout_plan`。`source.rawMarkdown` 逐字保留 S4 原文；`effective_content`、`content` 与 `sections` 是本链路唯一允许依据冻结规则剔除研发说明、纯状态句或重复壳层的学生交付投影。不得改写保留的学生可见文本、改变顺序或把删留权回推到 S2—S4；不得生成 `prompt`、`components`、`sdk_action`、`is_last_page` 或任何 HTML。

R32 对知识讲解/案例分析追加确定性结构投影：必须仅从同页 `source.rawMarkdown` 按原序拆出 `heading`、`paragraph`、`ordered_list`、`unordered_list`、`blockquote` 或 `code_block`。每块必须保留逐字 `markdown`；heading 保留 `level` 与原文 `text`，列表保留原序 `items[]`，其他可见块保留原文 `text`。禁止把整页收为 `type: markdown` 单块，禁止补写、删减、跨块调序、把列表降为段落，或让 `content.blocks` 与 `effective_content.blocks` 不一致。`source.rawMarkdown` 继续保留完整审计真源；结构块是其唯一可供 S6 投影的学生内容表示。

- P01 的 `effective_content` 按固定顺序含六项课程信息，`content` 按固定顺序映射为 `packageName`、`unitName`、`lessonNumber`、`courseName`、`courseIntroduction`、`knowledgePoints`。
- 课后任务 `sections[].type` 只允许 `paragraph`、`task`、`facts`、`step`、`prompt`、`decision`、`safety`、`fallback`。
- 课程小结源内容含有序列表或连续编号条目时，`content.contentBlocks` 必须使用 `orderedList` 并保留完整 `items[]`；允许源编号与视觉编号并存。
- 知识讲解与案例分析页必须有非渲染 `design_brief`：`nonRenderable: true`、教学动作、内容形态、阅读流、语义分组、密度、节奏角色、层级焦点、布局自由度、视觉系统和学生可见文案策略。语义分组以除 heading/冻结过渡句外的阅读块为 1-based `blockIndexes`，无重叠覆盖全部可见内容块；三块及以上时至少按真实阅读关系提供两个语义组，禁止固定 `g1` 整页兜底。`contentShape` 仅可为 `claim_to_evidence_to_judgment`、`concept_to_example_to_boundary`、`problem_to_method_to_result`、`example_to_comparison_to_boundary`、`parallel_comparison`、`process_or_sequence`、`continuous_explanation`；`density` 仅 `light|medium|dense`；`rhythmRole` 仅 `statement|structured|contrast|narrative|dense_reference`。
- 对恰有两条独立短原文、且不含列表或互动内容的知识讲解页，`design_brief.shortPageComposition` 必须为 `two_layer_reading`：两条原文各自保留为一个语义组，按原顺序分别作为主阅读层和弱结果层。两层之间仅允许无文字的连续留白节奏，不得添加连接文案、可见连接线、编号、方法/步骤/结论，也不得为了填满页面把原文拆改、重复或补写。
- `page_action` 与页位一致；如 `content.pageAction` 存在，非末页为 `next`，末页为 `complete`。

### S5 Gate

运行：

```bash
python3 scripts/validators/validate_v35_effective_content.py \
  --page-plan <S4/page_plan_full.md> \
  effective_content_full.json
```

以下任一情况为 `BLOCKED`：上游缺失或不唯一；页数、顺序、六项基础字段或无损内容漂移；P01 映射、互动 JSON、模板前置数据、设计简报、课后任务 sections、课程小结有序列表或页面动作不合规；出现下游字段。`PASS` 只允许进入 S6 静态装配。

## S6 整课 JSON 装配

只读取已通过的 S5 `effective_content_full.json`，输出唯一整课 JSON 与装配校验结果；不得读取 S1--S4 或旧式 `p1/p2/s2e/p3` manifest。静态检查器以这两个绝对路径显式接收输入，不复制上游文件。整课根必须含非空 `pages[]`；当前受控包络还含 `course_id`、`title`、`description`、`source`、`workflow`。导入后的课件任务名唯一取根 `title`，格式固定为 `第{lessonNumber}课｜{courseName}｜RunS_V3.5.0-S1-S6-R36-20260731`；不得使用 `pages[].title` 或课程任务页内部标题。每页必须含 `tag`、`title`、`summary`、`page_no`、`page_kind`、`runtime_type`、`sdk_action`、`is_last_page`、`prompt`、`components`、`page_data`。

页面类型只能按下表映射；这张表是当前 S6 的唯一类型映射。

| S5 页面类型 | `page_kind` | `runtime_type` | 交付方式 |
| --- | --- | --- | --- |
| 课程开篇 | `course_intro` | `html` | 课程开篇固定模板 OneShot。 |
| 场景引入 | `scene_intro` | `html` | 场景引入固定模板 OneShot。 |
| 知识讲解 | `knowledge_explanation` | `html` | 动态知识讲解 OneShot，并逐字投影 `design_brief`。 |
| 案例分析 | `case_analysis` | `html` | 动态案例分析 OneShot，并逐字投影 `design_brief`。 |
| 互动题目 | `question_component_page` | `component` | `prompt: ""`；完整上游组件 JSON 位于 `components[]`。 |
| 课后任务 | `post_class_task` | `html` | 课后任务固定模板 OneShot。 |
| 课程小结 | `course_summary` | `html` | 课程小结固定模板 OneShot；有序内容保留样式化列表。 |

非互动页 `pages[].prompt` 必须保存“唯一提示词实例版本 + 简短生成要求 + 内嵌完整 HTML”的完整 OneShot 实际模型输入；同一整课内实例版本不得重复。裸 HTML、模板路径、变量对象或增量指令均不得写入 `prompt`。模型输出的纯 HTML 属于后续运行证据，不能反写覆盖 `prompt`。动态知识/案例页的 OneShot 还必须携带由唯一装配器产生的非渲染 `visualRecipePlan` 与 `footerContract`，不得由模型自行缺省。

所有页面须从 S5 无损映射页号、胶囊、来源块、有效内容摘要哈希与页面动作；末页 `sdk_action: complete` 且 `is_last_page: true`，此前为 `nextpage` 与 `false`。每个非互动 OneShot 的“适用页面”必须由装配上下文重绑为当前课次、页号、页序/总页数和页面类型，禁止遗留示例课次或页号。知识/案例页由唯一装配器读取同页 `effective_content.blocks` 与 `design_brief`，将完整 blocks 原样写入动态 `PAGE_DATA.contentBlocks`，并在 `page_data` 原样登记该 `design_brief`；不得压扁为 `markdown` 单块、简化为 `type/text`、退化为裸 HTML、通用替代提示词或跳过动态页。R36 必须在同一 `PAGE_DATA` 里确定性注入 `visualRecipePlan`（引入/观察信息带、列表/选项紧凑项组、分析/结论强调卡；至少两种被选配方不得同款白卡化或只靠位置移动）和 `footerContract`（动作非空即在滚动容器外无条件保留可见 CTA）。若知识页有 `ordered_list`，还必须注入 `orderedListOrdinalContract`：只遍历该列表 `items[]`，显示局部 `itemIndex + 1`，每个列表从 1 连续编号；禁止 `contentBlockIndex`、`globalCounter` 与 Markdown 序号/生成序号双重叠加。若有 `unordered_list`，还必须注入 `unorderedListPresentationContract`：保留已有文字标签，禁止数字徽标和自动编号。静态检查器必须逐页比较 `PAGE_DATA.contentBlocks` 与 S5 结构块，并核验配方可见差异、CTA 与列表合同。知识/案例页遵守唯一内部滚动容器、固定底栏、连续底色与过渡句弱化样式合同；所有学生内容卡禁止纯装饰性左侧彩色竖线、贴边色条、轨道、连接点、箭头和伪元素彩轨。三块及以上且 `density: medium` 的知识讲解页使用真实分组的分布式构图，使主体约覆盖可用阅读区 60%—75%，不得将全部内容堆在上半屏，也不得用新增文案、空白占位或单一卡片强拉高凑高度；短页 `two_layer_reading` 不硬凑内容。课程开篇只注入 `packageName`、`unitName`、`lessonNumber`、`courseName`、`courseIntroduction`、`knowledgePoints` 六个 v1.8 camelCase 字段。课程小结 v1.10 必须将 S5 冻结 heading 逐字投影为 `summaryTitle` 并从正文移除；`next` 只允许中性完成头“本课重点回顾”，仅 `complete` 可使用“恭喜你完成本节课程！”，去除 heading 后仅一个内容块时用不改写原文的单块小结构图分支。课后任务只按冻结的八类 `sections[]` 静态投影为 v1.8 富卡片 DOM；单个原始 Markdown 任务块、缺失 sections 或 facts 的空内容不得由 S6 猜测修复。固定模板的变量区、冻结版本和变量映射由资产清单登记的对应 OneShot 与 Demo 约束。

### S6 只读回归基线

lesson001、lesson008、lesson021 的已冻结整课 JSON 仅是 S6 回归夹具：在装配器或静态检查器变更后，可用于核对页面包络、`pages[]` 投影和模板合同是否退化。它们不是 Golden Baseline，不能作为 S6 输入、不能回读以补全 S5、不能替代 OneShot/Demo，也不能单独授权 `IMPORT_READY_STATIC`。唯一基线版本、路径和 SHA-256 由资产清单及版本登记锁定；任何新增版本必须先登记，不能以目录中较新的同名 JSON 自动替换。

### S6 Gate

先运行本包唯一装配器 `scripts/assembler/assemble_whole_course.py`；它是唯一允许把冻结 S5 内容、同包 OneShot/Demo 模板资产装配为整课 JSON 的执行入口。装配前若 S5 课后任务尚未形成八类结构化 `sections[]`，必须回到 S5 重新冻结，不能在 S6 从 `rawMarkdown` 重建。OneShot/Demo 只提供模板合同，`scripts/validators/check_whole_course_static.py` 只做静态验收，二者不得替代装配器或自行拼装页面。

运行：

```bash
python3 scripts/validators/check_whole_course_static.py \
  --s6-contract --lesson-id <lesson_id> \
  --effective-content <S5/effective_content_full.json> \
  --whole-course <S6/whole_course.json>
```

以下任一情况为 `BLOCKED`：根或页面包络缺失；导入任务名未使用根 `title` 或不符合“课程序号｜课程名称｜SOP版本”；页面类型映射、动作、组件、`prompt` 交付层、提示词版本唯一性、S5 无损投影、设计简报、案例卡装饰竖线禁令、课程开篇 camelCase 六字段、课后任务结构化 sections / 富卡片 DOM、固定模板变量或页面视觉合同不一致。唯一通过状态为 `IMPORT_READY_STATIC`；不自动授权资源配置、导入、运行、渲染、测试、发布或 create。
