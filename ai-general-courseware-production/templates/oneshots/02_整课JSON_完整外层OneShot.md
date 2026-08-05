# 整课 JSON 完整外层 OneShot（V3.5）

状态：`CURRENT_PRODUCTION_ASSET`  
适用阶段：`P3` 整课 JSON 装配；进入 `P4` 前的外层结构基线。  
字段事实来源：`v35_real_production_pilot/lesson002/03_整课JSON/lesson002_create_ready_final_import_rc2_mobile_v2.json` 及其 `build_lesson002_rc2.py`。

课后任务页生成补充合同：`03_课后任务页_Compact直接生成OneShot.md`。该文件定义提交给 Kimi / GLM 的一次性完整提示词，以及 `TASK_STATIC_DOM_V18_PROJECTION`：阶段 6 必须将冻结 `sections[]` 投影为正式 Demo 的任务、事实、步骤/Prompt、检查和提示富卡片 DOM；当前 RunS `pages[].prompt` 保存这份完整 OneShot 实际模型输入，模型返回的纯完整 HTML 另层校验与留证。

课程小结页无上下文生成补充合同：`04_课程小结页_固定模板OneShot.md`。该文件完整内嵌冻结 Demo、真实 `COURSE_SUMMARY_VARIABLES` 实例、唯一模型中立版本号与变量区外哈希算法；当前 RunS `pages[].prompt` 保存完整 OneShot 实际模型输入，纯完整 HTML 输出不得反写覆盖该字段。

课程开篇页无上下文生成补充合同：`05_课程开篇页_固定模板OneShot.md`。场景引入页无上下文生成补充合同：`06_场景引入页_固定模板OneShot.md`。两者分别完整内嵌冻结 Demo、真实变量、页面实例唯一版本号和变量区外哈希算法；本文件的 `pages[].prompt` 保存完整 OneShot 实际模型输入，纯完整 HTML 输出另层留证。

知识讲解页动态生成补充合同：`07_知识讲解页_动态生成OneShot.md`。案例分析页动态生成补充合同：`08_案例分析页_动态生成OneShot.md`。两者分别完整内嵌单份真实 `PAGE_DATA`、共享 CSS、SDK 和纯 HTML 输出合同；动态内容区不执行变量区外哈希。当前 RunS `pages[].prompt` 保存完整动态 OneShot 实际模型输入，模型输出另层验收。

## 1. 用途与边界

这是**整课课件 JSON 的外层装配基线**：根对象、`pages[]` 页面包络、路由、动作、来源记录和 workflow 均按当前 V3.5 实例字段编写。

导入后的课件任务名只读取根 `title`。当前格式固定为 `第{lessonNumber}课｜{courseName}｜RunS_V3.5.0-S1-S6-R31-20260731`；`pages[].title` 仅是页面标题，课程任务页内部标题也不能替代根 `title`。

它**不是单题直接导入 JSON**。单题组件只可以作为某一题目页的 `pages[].components[]` 成员出现；不得把 `type`、`componentId`、`content` 提到整课根对象，也不得再用单题直接导入外层包装整课。

以下骨架是语法完整的 JSON，但故意处于 `P3_JSON_ASSEMBLY_DRAFT`：

1. 将 `{{...}}` / `<...>` 替换为通过 P1、P2 的实际数据。
2. 当前 RunS 页面模型链路中，所有非互动页的 `prompt` 必须写入对应完整 OneShot 实际模型输入，而不是模型返回 HTML。课程开篇按 `05`、场景引入按 `06`、课程小结按 `04`、课后任务按 `03`；每个页面实例版本号必须在整课内两两不同。无外部上下文声明、完整 HTML/CSS/JavaScript、真实变量或已预编译的静态学生 DOM 和纯 HTML 输出约束必须同时存在。
3. 每个知识讲解页按 `07`、每个满足生成条件的案例分析页按 `08` 将单份真实 `PAGE_DATA` 与完整运行底座写入 `prompt`。模型返回并校验通过的纯完整 HTML 作为实际页面结果另层保存；上游 `source_text` / `semantic_units` 和来源定位留在审计层，不重复进入模型输入。
4. 任何页面都不得用裸 HTML、模板路径、`参考 Demo`、单独变量对象、局部 CSS、简短生成指令或增量补丁代替完整 OneShot。每个非互动 OneShot 的“适用页面”必须从当前装配上下文写入 `lesson_id`、`Pxx`、页序/总页数和页面类型，禁止保留示例课次、页号、页数或相邻题页。固定模板的模型输出核对变量区外 SHA-256；动态页输出核对内容无损、页面边界、共享运行底座、SDK 和短页 / 长页双态。
5. 先通过 `S3G`、跨产物 diff 和适用 Gate，才能冻结为 `final_import` 并进入 P4；不得直接 create。

### 1.1 课程小结 v1.11 确定性变量投影

`COURSE_SUMMARY_V111_VARIABLE_PROJECTION`：阶段 6 装配课程小结时，必须把冻结有效内容确定性投影为 `COURSE_SUMMARY_VARIABLES`，不得把历史 `blocks` 对象原样注入 v1.11 模板。

1. 输出对象必须且只能按本合同使用 `completionTitle`、`summaryTitle`、`contentBlocks`、`nextLessonPreview`、`pageAction` 五个业务字段；`pageAction` 只取当前冻结页面动作，外层 `nextpage / complete` 分别映射为内部 `next / complete`。`next` 对应中性完成头“本课重点回顾”，仅 `complete` 对应“恭喜你完成本节课程！”。
2. `summaryTitle` 必须取有效内容中的第一个 `heading` 块的逐字 `text` 并从正文移除；缺少冻结 heading 即 `BLOCKED`，不得退化为同页“课程小结”等通用页面类型标题。
3. 除被消费为标题的首个 `heading` 外，其余块按原顺序投影：`paragraph → paragraph`、`ordered_list / orderedList → orderedList`（逐字保留 `items` 与 `sourceNumbered`）、`blockquote → blockquote`、`notice → notice`、`code_block / codeBlock → codeBlock`（保留 `language`）。未知块类型、空正文或改写 / 调序均为 `BLOCKED`。
4. `nextLessonPreview` 只可取冻结有效内容中的显式下一课预告；没有时写空字符串，不得由阶段 6 补写。`contentBlocks` 不得为空，旧字段 `blocks` 不得出现在最终变量区。
5. 静态 `#completionTitle`、`#summaryTitle`、`#summaryContent[data-summary-static="true"]` 与 `#completeButton` 必须由上述同一对象预编译；模型返回的纯 HTML是输出证据，不得覆盖 `pages[].prompt`。

去除 heading 后仅一个内容块时，OneShot 必须启用无新增文案的单块小结构图分支：仅调整既有标题/卡片比例/垂直居中，不拆改原文，不伪造列表或步骤。检查器遇到旧 `blocks`、缺少任一 v1.11 必填字段，单块分支缺失，或页面动作不一致时，必须阻断；不得以最终截图正常替代该装配检查。

课程不要求机械包含七类页面：案例分析只在互动题必要背景超过 50 个学生可见字符时生成，并紧邻对应互动题之前；课后任务只在有真实任务时生成，课程小结只在有显式小结块时生成。下面同时列出课后任务与课程小结，只是为了给出完整装配示例；无对应来源时删除整页并重编号、重算最后页动作。

## 2. 可复制 JSON 骨架

```json
{
  "version": "V3.5.0",
  "course_id": "{{课程唯一ID，例如 S1U1-L001}}",
  "title": "第{{lessonNumber}}课｜{{courseName}}｜RunS_V3.5.0-S1-S6-R31-20260731",
  "description": "{{仅作生产侧说明，不得代替学生正文}}",
  "source": {
    "preprocessed": "{{final_preprocessed.md 的可追溯路径}}",
    "page_plan": "{{page_plan_full.md 的可追溯路径}}"
  },
  "pages": [
    {
      "page_no": "P01",
      "tag": "课程开篇",
      "title": "{{页面标题}}",
      "summary": "{{页面有效内容的简短生产侧摘要}}",
      "page_kind": "course_intro",
      "runtime_type": "html_page",
      "sdk_action": "nextpage",
      "is_last_page": false,
      "prompt": "<05_课程开篇页_固定模板OneShot.md 的完整实际模型输入；不得写裸 HTML；本外层骨架不得直接提交或 create>",
      "components": [],
      "page_data": {
        "route": "fixed_template",
        "template": "COURSE_INTRO_VARIABLES",
        "template_sha256": "{{当前课程开篇 Demo SHA-256}}",
        "prompt_contract": "RunS-CourseIntro-FixedTemplate-OneShot-v1.9",
        "prompt_version": "{{本次实际使用且唯一的课程开篇页提示词版本号}}",
        "template_outside_variable_region_unchanged": true
      }
    },
    {
      "page_no": "P02",
      "tag": "场景引入",
      "title": "{{场景引入页标题}}",
      "summary": "{{场景引入页面有效内容摘要}}",
      "page_kind": "scene_intro",
      "runtime_type": "html_page",
      "sdk_action": "nextpage",
      "is_last_page": false,
      "prompt": "<06_场景引入页_固定模板OneShot.md 的完整实际模型输入；不得写裸 HTML；本外层骨架不得直接提交或 create>",
      "components": [],
      "page_data": {
        "route": "fixed_template",
        "template": "SCENE_INTRO_VARIABLES",
        "template_sha256": "{{当前场景引入 Demo SHA-256}}",
        "prompt_contract": "RunS-SceneIntro-FixedTemplate-OneShot-v1.6",
        "prompt_version": "{{本次实际使用且唯一的场景引入页提示词版本号}}",
        "template_outside_variable_region_unchanged": true,
        "sceneParagraphs": [
          "{{来自 final_preprocessed.md 同一场景内容块、按原顺序的第 1 段}}"
        ],
        "lessonLead": "{{同一内容块最后承接段，且只出现一次}}",
        "pageAction": "next"
      }
    },
    {
      "page_no": "P03",
      "tag": "知识讲解",
      "title": "{{知识讲解页标题}}",
      "summary": "{{该页学习意图或有效内容摘要}}",
      "page_kind": "knowledge_explanation",
      "runtime_type": "html_page",
      "sdk_action": "nextpage",
      "is_last_page": false,
      "prompt": "<07_知识讲解页_动态生成OneShot.md 的完整实际模型输入；不得写裸 HTML；本外层骨架不得直接提交或 create>",
      "components": [],
      "page_data": {
        "route": "dynamic_oneshot",
        "oneshot_contract": "RunS-Knowledge-Dynamic-OneShot-v1.7",
        "prompt_version": "{{本次实际使用且唯一的知识讲解页提示词版本号}}",
        "model_family": "{{Kimi 或 GLM}}",
        "output_html_complete": true,
        "source_text": "{{本页完整、按原顺序的学生正文}}",
        "semantic_units": [
          "{{本页第一个可追溯语义单元}}",
          "{{本页后续语义单元}}"
        ],
        "visual_qa": "NOT_RUN"
      }
    },
    {
      "page_no": "P04",
      "tag": "案例分析",
      "title": "{{原文有显式标题时逐字填写；没有时为空字符串}}",
      "summary": "{{对应互动题超过 50 个学生可见字符的必要背景摘要}}",
      "page_kind": "case_analysis",
      "runtime_type": "html_page",
      "sdk_action": "nextpage",
      "is_last_page": false,
      "prompt": "<08_案例分析页_动态生成OneShot.md 的完整实际模型输入；不得写裸 HTML；本外层骨架不得直接提交或 create>",
      "components": [],
      "page_data": {
        "route": "dynamic_oneshot",
        "oneshot_contract": "RunS-CaseAnalysis-Dynamic-OneShot-v1.6",
        "prompt_version": "{{本次实际使用且唯一的案例分析页提示词版本号}}",
        "model_family": "{{Kimi 或 GLM}}",
        "output_html_complete": true,
        "linked_question_page_no": "P05",
        "background_visible_chars_gt_50": true,
        "question_content_absent": true,
        "visual_qa": "NOT_RUN"
      }
    },
    {
      "page_no": "P05",
      "tag": "{{预处理教案中的 ### 试一试：…… 原文}}",
      "title": "{{题目页标题}}",
      "summary": "{{题目有效内容摘要}}",
      "page_kind": "question_component_page",
      "runtime_type": "quiz",
      "sdk_action": "nextpage",
      "is_last_page": false,
      "prompt": "",
      "components": [
        {
          "type": "matching_question",
          "componentId": "matching_question_{{课程ID}}_{{互动ID}}",
          "content": {
            "questions": [
              {
                "id": "{{互动ID}}",
                "stem": "{{完整自包含题干；背景材料与作答任务均在此处}}",
                "pairs": [
                  {
                    "id": "pair_01",
                    "left": "1. {{左侧原文}}",
                    "right": "A. {{右侧原文}}"
                  },
                  {
                    "id": "pair_02",
                    "left": "2. {{左侧原文}}",
                    "right": "B. {{右侧原文}}"
                  }
                ],
                "explanation": "{{预处理题目 JSON 中已审核的原解析}}"
              }
            ],
            "correctButtonText": "继续"
          }
        }
      ],
      "page_data": {
        "route": "component_schema",
        "source": "{{final_preprocessed.md 中对应互动的定位}}",
        "question_envelope": "whole_course_embedded",
        "unsupported_render_control_fields_absent": true
      }
    },
    {
      "page_no": "P06",
      "tag": "课后任务",
      "title": "{{显式课后任务原始标题}}",
      "summary": "{{真实课后任务页面有效内容摘要}}",
      "page_kind": "post_class_task",
      "runtime_type": "html_page",
      "sdk_action": "nextpage",
      "is_last_page": false,
      "prompt": "<03_课后任务页_Compact直接生成OneShot.md v1.9 的完整实际模型输入；第一行必须是整课唯一提示词版本号，并完整内嵌按 TASK_STATIC_DOM_V19_PROJECTION 预编译的富卡片学生 DOM 与 HTML/CSS/JavaScript>",
      "components": [],
      "page_data": {
        "route": "compact_direct_oneshot",
        "oneshot_contract": "RunS-PostClassTask-Compact-Direct-OneShot-Contract-v1.9-20260805",
        "prompt_version": "{{本次实际使用且唯一的课后任务页提示词版本号}}",
        "model_family": "{{Kimi 或 GLM}}",
        "output_html_complete": true,
        "hasTask": true,
        "pageAction": "next"
      }
    },
    {
      "page_no": "P07",
      "tag": "课程小结",
      "title": "{{显式课程小结标题}}",
      "summary": "{{小结页面有效内容摘要}}",
      "page_kind": "course_summary",
      "runtime_type": "html_page",
      "sdk_action": "complete",
      "is_last_page": true,
      "prompt": "<04_课程小结页_固定模板OneShot.md 的完整实际模型输入；不得写裸 HTML；本外层骨架不得直接提交或 create>",
      "components": [],
      "page_data": {
        "route": "fixed_template",
        "template": "COURSE_SUMMARY_VARIABLES",
        "template_sha256": "{{当前课程小结 Demo SHA-256}}",
        "prompt_contract": "RunS-CourseSummary-FixedTemplate-OneShot-v1.11",
        "prompt_version": "{{本次实际使用且在整课内唯一的课程小结页提示词版本号}}",
        "template_outside_variable_region_unchanged": true,
        "prohibited_text_absent": true,
        "pageAction": "complete"
      }
    }
  ],
  "workflow": {
    "sop_version": "V3.5.0",
    "phase": "P3_JSON_ASSEMBLY_DRAFT",
    "status": "P3_NOT_VALIDATED",
    "create_ready": false,
    "create_allowed": false,
    "environment": "test",
    "resource_binding_status": "NOT_APPLICABLE",
    "resource_binding_reason": "{{仅在确无资源绑定需求时填写；不得伪造资源 ID}}",
    "rendered_visual_qa_status": "NOT_STARTED",
    "publish_allowed": false,
    "blockers": [
      "P1_PREPROCESS_SOURCE_AND_QUESTION_QA_REQUIRED",
      "P2_PAGE_PLAN_AND_EFFECTIVE_CONTENT_REQUIRED",
      "P3_COMPLETE_HTML_OR_COMPONENT_DATA_REQUIRED",
      "S3G_AND_ARTIFACT_CHAIN_DIFF_REQUIRED",
      "P4_FINAL_IMPORT_FREEZE_REQUIRED",
      "S5_REAL_RENDER_ACCEPTANCE_REQUIRED"
    ]
  }
}
```

## 3. 页面装配硬边界

| 页面路由 | `page_kind` / `runtime_type` | `prompt` | `components` | 必要 `page_data` 要点 |
| --- | --- | --- | --- | --- |
| 课程开篇 | `course_intro` / `html_page` | `05` 完整 OneShot 实际模型输入 | `[]` | 模板 SHA、变量区外一致性 |
| 场景引入 | `scene_intro` / `html_page` | `06` 完整 OneShot 实际模型输入 | `[]` | 同一来源块的 `sceneParagraphs`、`lessonLead`、`pageAction` |
| 知识讲解 | `knowledge_explanation` / `html_page` | `07` 完整动态 OneShot 实际模型输入 | `[]` | 上游审计、单份 `PAGE_DATA`、共享运行底座、过渡句角色、视觉 QA |
| 案例分析（可选） | `case_analysis` / `html_page` | `08` 完整动态 OneShot 实际模型输入 | `[]` | 必要背景超过 50 字、紧邻对应互动题、题目内容未泄漏 |
| 互动题目 | `question_component_page` / `quiz` | 空字符串 | 单题组件对象数组 | `question_envelope: whole_course_embedded`、预处理来源 |
| 课后任务（可选） | `post_class_task` / `html_page` | `03` 完整 Compact OneShot 实际模型输入 | `[]` | 仅真实任务；阶段 6 预编译静态学生 DOM；记录 OneShot 合同、实际提示词版本和模型；`hasTask: true` |
| 课程小结（可选） | `course_summary` / `html_page` | `04` 完整固定模板 OneShot 实际模型输入 | `[]` | 仅显式小结；列表结构与禁入句检查 |

## 4. 动作与末页重算规则

1. 当前真实 JSON 的外层动作拼写为 `nextpage`，不是 `nextPage`；所有非末页使用 `sdk_action: "nextpage"` 且 `is_last_page: false`。
2. 只有实际最后一页使用 `sdk_action: "complete"` 且 `is_last_page: true`。最后页可以是课程小结，也可以是页面规划中的另一种合法页面类型。
3. 固定模板变量以及课后任务上游审计结构中的 `pageAction` 均使用 `"next"` / `"complete"`；不要把它误写成外层 `nextpage`。
4. 删除可选课后任务或课程小结页后，必须同步重编号、页面顺序、最后页 `sdk_action` / `is_last_page`、模板内部 `pageAction` 以及 P2 页面规划；只改 JSON 属于 `ARTIFACT_CHAIN_OUT_OF_SYNC`。

## 5. 进入 P4 前的最小检查

- 根对象、每页对象字段、`pages[]` 顺序与 P2 页面规划一致。
- 所有题目只位于对应 `pages[].components[]`，且组件内容与预处理题目 JSON 逐项 diff 一致；题干同时含背景材料和明确作答任务。
- 全部非互动页的 `prompt` 第一行必须是内容寻址的实际提示词版本号：`<OneShot合同>-asset-<资产SHA前12位>-prompt-<归一化完整提示词SHA前12位>-<lesson_id>-<page_no>-R36-20260731`。`page_data.prompt_instance_sha256` 保存完整实例 SHA-256；计算时只把首行版本值归一化为 `__PROMPT_VERSION__`，其余完整模型输入全部参与哈希。同一 OneShot 的实际提示词只要变化就必须得到不同版本；首行、`page_data.prompt_version`、合同、资产哈希和重算实例哈希必须一致。整课内重复使用 `V35_STAGE6_PROMPT_VERSION_DUPLICATE` 阻断，任一绑定不一致使用 `V35_STAGE6_PROMPT_VERSION_ASSET_MISMATCH` 阻断。互动题组件页继续保持 `prompt: ""`，不登记提示词版本号。
- 课程开篇、场景引入、知识讲解、案例分析和课程小结的骨架占位均已替换为对应完整 OneShot 实际模型输入；未替换前本文件仍是外层结构示例，不得提交模型、冻结为 `final_import` 或 create。
- 课程开篇的 `pages[].prompt` 必须符合 `05_课程开篇页_固定模板OneShot.md`；场景引入必须符合 `06_场景引入页_固定模板OneShot.md`。两者都要求唯一模型中立版本号、无外部上下文、完整 Demo 与真实变量一次性内嵌；模型返回的纯完整 HTML 作为实际生成页面结果另层校验与留证。
- 课程小结的 `pages[].prompt` 必须符合 `04_课程小结页_固定模板OneShot.md`：保存唯一模型中立版本号、无外部上下文声明、完整 Demo、真实变量与纯 HTML 输出约束组成的完整实际模型输入，不保存裸 HTML。
- 课后任务页的 `pages[].prompt` 符合 Compact v1.9 直接生成合同：第一行是整课唯一版本号、无外部上下文依赖、完整内嵌 HTML / CSS / JavaScript 与由冻结内容按 `TASK_STATIC_DOM_V19_PROJECTION` 预编译出的富卡片学生 DOM；运行时不得使用 `PAGE_DATA`、`document.createElement`、循环或字符串拼接构造学生正文。不得把 `task`、`facts`、`step`、`prompt`、`decision`、`safety` 或 `fallback` 压平为 `.task-intro` 或裸 `<pre>`；模型返回的纯完整 HTML 是实际生成页面结果，不回写覆盖提示词。
- 知识页模型输入符合 `07`：上游 `source_text` / `semantic_units` 与 P2 有效内容逐字、按顺序一致，但实际模型输入只携带确定性映射后的单份 `PAGE_DATA.visibleContentBlocks`；学生可见首元素为页面标题或来源明确的合法过渡句。案例分析页模型输入符合 `08`：只在必要背景超过 50 个学生可见字符时生成，紧邻对应互动题，学生 DOM 不含明确问句、作答指令、选项、答案、解析或 `linkedQuestionPageId`。
- 两类动态页均执行 `UNIFIED_PERSISTENT_BOTTOM_ACTION_BAR`：以 Android System WebView Chrome 68 为基线，页面外层使用 `height:100%` 且不滚动，footer 在 iframe 内 `position:absolute; left/right/bottom:0`，按钮自身 `position:static`；正文只有一个内部纵向滚动容器，底部预留按 footer 实测高度动态同步并额外保留 `24px`。页面主渐变必须连续覆盖到视口底部；footer 主体为 `80px`、按钮上下各 `10px`，背景透明，不得单独绘制整宽实色层或 `::before` / `::after` 羽化层。动态内容区使用 `box-sizing:border-box; width:100%; max-width:680px`，移动端保留物理方向安全边距，宽预览不得锁死 `360px`；不得使用动态视口单位、`min()` / `max()` / `clamp()`、Flex `gap`、逻辑属性或未检测的现代 DOM API。`DESIGN_BRIEF` 的构图自由不变。短页与长页在任意滚动位置都持续显示唯一课程按钮，最后内容不得被遮挡。动态内容区不执行变量区外哈希。
- `workflow.create_ready`、`create_allowed` 只有在 P3 Gate 和 P4 冻结均通过后才允许转为 `true`；这份 one-shot 骨架本身永远不能直接作为 create 输入。
