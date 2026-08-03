# 课程小结页固定模板 OneShot（V3.5）

状态：`CURRENT_PRODUCTION_ASSET`  
合同版本：`RunS-CourseSummary-FixedTemplate-OneShot-v1.10`  
适用范围：Kimi / GLM 一次性、无外部上下文生成课程小结页完整 HTML。  
固定 Demo SHA-256：`4fe01113b7712686f01406dde73b98b22ec9bc10776330166f72209d6f4cdec3`  
变量区外 SHA-256：`da54febaa5b03f21a1e0c5dfefa375c2a88465ce82cc87d5ddb3ffeddd487f9a`

## 1. 四层产物边界

| 层级 | 必须包含 | 禁止 |
| --- | --- | --- |
| 上游有效内容 | `effective_content_full.json` 中显式课程小结页块、来源块、原序内容、页面动作和审计字段 | 从历史页面、研发摘要、知识点或模型记忆补内容 |
| 提交给 Kimi / GLM 的一次性提示词 | 每次唯一模型中立版本号、无外部上下文声明、纯 HTML 输出约束、完整 Demo HTML/CSS/JavaScript、本课真实 `COURSE_SUMMARY_VARIABLES` | 只给路径、只给变量对象、引用历史模板、增量补丁、省略代码 |
| 模型返回 | 从 `<!doctype html>` 到 `</html>` 的纯完整 HTML，变量区外字节不变 | Markdown 围栏、解释、版本号、提示词正文、局部代码 |
| 当前 RunS JSON 的 `pages[].prompt` | 本课完整固定模板 OneShot 实际模型输入 | 裸 HTML、路径、单独变量对象或上游审计数据 |

本地确定性装配器可以直接复制同一 Demo 并只替换变量值；若通过 Kimi / GLM 执行，则必须使用本文件的一次性完整提示词，不能把“严格复制某路径 Demo”当作模型输入。

## 2. 生成与内容合同

1. 只有 `effective_content_full.json` 中存在显式“课堂小结”或“课程小结”页面块时生成；不存在时整页 `NOT_APPLICABLE`。
2. `summaryTitle`、`contentBlocks`、`nextLessonPreview` 逐字来自同一有效小结块；`summaryTitle` 必须优先取冻结 heading 并从正文移除，缺失即 `BLOCKED`；`pageAction` 来自有效页面规划；`completionTitle` 仅由 `pageAction` 确定。
3. `contentBlocks` 只允许 `paragraph`、`orderedList`、`blockquote`、`notice`、`codeBlock`，保持原顺序。
4. 已识别为有序列表时优先映射为有样式的 `orderedList`。来源为 Markdown 有序列表时使用模板生成的 `01/02/03` 编号；来源是连续同级、语义并列且具有稳定顺序标记的段落（如“第一/第二/第三”“首先/其次/最后”）时，保留每条原文并设置 `sourceNumbered: true`。当前过渡口径允许双重编号：来源序词逐字保留，同时仍显示模板生成的 `01/02/03` 紫色徽标，优先保证有序列表的视觉识别度。判断不唯一时必须 `BLOCKED`，阶段 6 不得自行猜测。
5. `nextLessonPreview` 只取原文明示句；没有时为空字符串并隐藏。
6. 完整句“本课没有课后练习。”不得进入变量、模型输入中的学生数据或最终 DOM。
7. 页面无音频，不生成播放器、TTS、字幕、CUE 或文字稿入口。
8. `COURSE_SUMMARY_VARIABLES.pageAction` 是唯一动作真源：值为 `next` 时调用 `CreatorReviewSDK.nextPage()`，值为 `complete` 时调用 `CreatorReviewSDK.complete()`；提示词不得再硬编码与当前页面规划冲突的动作。
9. `codeBlock.text` 等多行字符串必须通过 JSON 序列化写入变量区，以字面量 `\n` 保留换行；禁止把真实换行直接拼进 JavaScript 双引号 / 单引号字符串。内嵌脚本缺失、未转义换行或引号漂移时标记 `COURSE_SUMMARY_EMBEDDED_SCRIPT_INVALID`。
10. `completionTitle`、`summaryTitle`、`summaryContent` 与唯一底部 `#completeButton` 必须在阶段 6 按同一变量预编译为静态 DOM；正文保留 `data-summary-static="true"`。`pageAction: "next"` 时 `completionTitle` 必须是中性回顾文案、静态按钮必须直接为“继续学习”；`pageAction: "complete"` 时才可使用完成式文案“恭喜你完成本节课程！”与“完成学习”。运行时脚本只作增强；平台脚本注入失败时，静态小结和正确的课程动作语义仍必须可见。
11. 当去除 heading 后恰有一个学生可见 `contentBlocks` 块时，单一总结块时使用单块小结构图分支：保留既有奖杯、完成头、`summaryTitle` 与小结卡，只通过小结卡的比例、最小高度、内侧垂直居中和非文字装饰节奏缓解空白；不得补写、拆改或重复学生原文，不得伪造列表、步骤、下一课预告或额外按钮。两块及以上仍使用正常内容流。

## 3. 变量区外哈希算法

1. 以 UTF-8 原始字节读取固定 Demo，不做空格、编码、内部换行或 Unicode 规范化；仅对文件末尾执行单一规范：若 `</html>` 后没有 LF，则补一个 LF，若已有一个 LF则保持不变。
2. 变量区开始锚点为精确行 `    const COURSE_SUMMARY_VARIABLES = Object.freeze({`。
3. 变量区结束锚点为精确行 `    /* ======================= 变量区结束 ======================= */`。
4. 从开始锚点首字节到结束锚点所在行的换行符为止，整段从哈希输入中移除；模型输出也先按第 1 步规范末尾 LF。
5. 拼接前后剩余字节并计算 SHA-256，必须得到 `da54febaa5b03f21a1e0c5dfefa375c2a88465ce82cc87d5ddb3ffeddd487f9a`。
6. 模型输出采用同一算法复核；不一致即 `SUMMARY_TEMPLATE_DRIFT`。

## 4. 完整可复制实例：lesson001 P09

实例来源：`v35_candidate_stage1_batch_20260719/lesson001/02_页面规划/effective_content_full.json` 的 P09。  
页面动作：`complete`。  
实际提示词版本：`RunS-CourseSummary-L001-P09-FixedTemplate-OneShot-v1.8-20260724-R11-019f9191a3`。

复制下面代码块内部的全部内容提交给 Kimi 或 GLM；不要复制外层 Markdown 围栏。

```text
提示词版本号：RunS-CourseSummary-L001-P09-FixedTemplate-OneShot-v1.8-20260724-R11-019f9191a3

适用页面：lesson001｜P09｜第 9/9 页｜课程小结页。

请输出一个完整、可运行的移动端 HTML 网页。

这是一次性提示词，没有任何外部上下文。不得读取文件、路径、Demo、SOP、历史模板或其他对话。网页所需的课程内容、HTML、CSS、JavaScript、图片元素和 SDK 行为已经全部包含在本提示词中。

最终回复必须且只能包含下方完整 HTML：

- 第一个非空白字符必须是 HTML 文档声明。
- 最后一个标签必须是 </html>。
- 不得输出解释、Markdown 围栏、版本说明、调试信息或提示词正文。
- 不得重排、改写、删减或补写学生可见内容。
- 不得修改 COURSE_SUMMARY_VARIABLES 之外的任何 HTML、CSS、JavaScript、图片地址、模块顺序、按钮或 SDK 行为。
- 必须保留透明完成头部、奖杯到标题 0px、标题到小结卡 24px、长内容滚动、统一底栏和唯一课程动作按钮。
- 不得生成平台顶部壳层、页面类型胶囊、音频、播放器、TTS、字幕、CUE、输入框、Powered by RunS 或来源中不存在的模块。
- COURSE_SUMMARY_VARIABLES.pageAction 是本页唯一动作真源；值为 next 时调用 CreatorReviewSDK.nextPage() 且静态底部按钮必须直接显示“继续学习”，值为 complete 时调用 CreatorReviewSDK.complete() 且静态底部按钮必须直接显示“完成学习”。
- 单一总结块时使用单块小结构图分支；不得补写、拆改或重复学生原文。此分支只调整既有奖杯、标题和小结卡的比例与垂直居中，不生成额外列表、步骤、预告或按钮。
- 本实例冻结动作为 complete；装配其他课程时必须以该页有效页面规划为准，不得复制本实例动作。

下方 HTML 已完成本课变量注入。请直接返回这份完整 HTML，不得重新解释、修复、格式化、换引号或改写任何字符：

<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>课程小结页固定模板</title>
  <script src="https://res.xrunda.com/runs/plugin/creator/creator-review-sdk.js"></script>
  <style>
    /* FIXED_LAYOUT_CONTRACT: 顶部/两侧/底部留白、底栏和主按钮均为固定代码；每课只替换 COURSE_SUMMARY_VARIABLES。 */
    :root {
      --purple: #9260fe;
      --purple-soft: rgba(146, 96, 254, 0.12);
      --ink: #252431;
      --muted: rgba(39, 39, 52, 0.58);
      --surface: rgba(255, 255, 255, 0.58);
      --surface-strong: rgba(255, 255, 255, 0.78);
      --safe-bottom: env(safe-area-inset-bottom, 0px);
      --page-bottom-rgb: 232, 219, 255;
      --page-bottom-bg: rgb(var(--page-bottom-rgb));
      --footer-h: calc(80px + var(--safe-bottom));
      --content-max: 360px;
      --button-height: 60px;
      --button-radius: 40px;
      font-family: -apple-system, "SF Pro Text", "PingFang SC", "Noto Sans SC", "Microsoft YaHei", sans-serif;
      color: var(--ink);
    }

    * {
      box-sizing: border-box;
      min-width: 0;
    }

    html,
    body {
      width: 100%;
      height: 100%;
      margin: 0;
      overflow: hidden;
      background: var(--page-bottom-bg);
    }

    body {
      letter-spacing: 0.01em;
    }

    .summary-page {
      position: relative;
      width: 100%;
      max-width: 538px;
      height: 100dvh;
      min-height: 100%;
      margin: 0 auto;
      overflow: hidden;
      background:
        radial-gradient(circle at 50% 8%, rgba(255, 255, 255, 0.28) 0 9%, transparent 30%),
        linear-gradient(180deg, #d9f4ff 0%, #dddfff 47%, var(--page-bottom-bg) 66.667%, var(--page-bottom-bg) 100%);
    }

    .summary-scroll {
      width: 100%;
      height: 100%;
      overflow-y: auto;
      overflow-x: hidden;
      padding: 28px clamp(24px, 6vw, 35px)
        calc(var(--footer-h) + 24px);
      overscroll-behavior: contain;
      -webkit-overflow-scrolling: touch;
    }

    .top-safe-area {
      display: none;
      width: 100%;
      height: 0;
    }

    .completion-card {
      position: relative;
      width: 100%;
      max-width: var(--content-max);
      min-height: 0;
      margin: 93px auto 0;
      padding: 49px 20px 8px;
      border-radius: 20px;
      text-align: center;
    }

    .trophy-wrap {
      position: absolute;
      z-index: 3;
      top: -93px;
      left: 50%;
      width: 106px;
      height: 142px;
      transform: translateX(-50%);
      pointer-events: none;
    }

    .trophy-wrap img {
      display: block;
      width: 100%;
      height: 100%;
      object-fit: contain;
    }

    .completion-card h1 {
      margin: 0;
      color: var(--ink);
      font-size: 18px;
      line-height: 1.35;
      font-weight: 800;
    }

    .summary-card,
    .next-card {
      width: 100%;
      max-width: var(--content-max);
      margin-right: auto;
      margin-top: 16px;
      margin-left: auto;
      border: 1px solid rgba(255, 255, 255, 0.72);
      border-radius: 22px;
      background: var(--surface);
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.82),
        0 12px 30px rgba(111, 105, 177, 0.06);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
    }

    .summary-card {
      padding: 18px;
    }

    .summary-card.summary-card--single-block {
      display: grid;
      min-height: clamp(250px, 39dvh, 360px);
      align-content: center;
    }

    .summary-card.summary-card--single-block .summary-content {
      max-width: 31rem;
      margin: 0 auto;
    }

    .summary-card h2 {
      margin: 0 0 12px;
      color: var(--purple);
      font-size: clamp(17px, 3.8vw, 20px);
      line-height: 1.45;
      font-weight: 800;
      text-align: center;
      text-wrap: balance;
    }

    .next-card h2 {
      margin: 0 0 10px;
      color: var(--purple);
      font-size: clamp(16px, 3.4vw, 18px);
      line-height: 1.45;
      font-weight: 400;
      text-align: center;
      text-wrap: balance;
    }

    .summary-content {
      display: grid;
      gap: 12px;
    }

    .summary-paragraph,
    .summary-quote,
    .summary-notice {
      margin: 0;
      color: #34313f;
      font-size: clamp(15px, 3vw, 17px);
      line-height: 1.72;
      font-weight: 400;
      overflow-wrap: anywhere;
      text-wrap: pretty;
    }

    .summary-paragraph {
      padding: 0 2px;
    }

    .summary-list {
      display: grid;
      gap: 10px;
      margin: 0;
      padding: 0;
      list-style: none;
    }

    .summary-item {
      display: grid;
      grid-template-columns: 34px minmax(0, 1fr);
      gap: 11px;
      align-items: start;
      padding: 13px 14px;
      border-radius: 18px;
      background: var(--surface-strong);
      color: #34313f;
      font-size: clamp(15px, 3vw, 17px);
      line-height: 1.58;
      font-weight: 400;
      overflow-wrap: anywhere;
      text-wrap: pretty;
    }

    .summary-index {
      display: grid;
      place-items: center;
      width: 34px;
      height: 34px;
      border-radius: 11px;
      color: var(--purple);
      background: var(--purple-soft);
      font-size: 12px;
      line-height: 1;
      font-weight: 900;
    }

    .summary-quote {
      position: relative;
      padding: 16px 17px 16px 43px;
      border-radius: 20px;
      background:
        linear-gradient(145deg, rgba(255, 255, 255, 0.82), rgba(244, 239, 255, 0.82));
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.82);
    }

    .summary-quote::before {
      position: absolute;
      top: 10px;
      left: 15px;
      color: rgba(146, 96, 254, 0.36);
      content: "“";
      font-family: Georgia, "Songti SC", serif;
      font-size: 38px;
      line-height: 1;
      font-weight: 700;
    }

    .summary-notice {
      padding: 14px 16px;
      border: 1px solid rgba(255, 190, 80, 0.24);
      border-radius: 18px;
      color: #5f4a24;
      background: rgba(255, 248, 220, 0.82);
      font-weight: 600;
    }

    .summary-code {
      margin: 0;
      padding: 16px 18px;
      border: 1px solid rgba(255, 255, 255, 0.44);
      border-radius: 20px;
      color: rgba(255, 255, 255, 0.96);
      background:
        radial-gradient(circle at 92% 8%, rgba(190, 166, 255, 0.28), transparent 36%),
        linear-gradient(145deg, rgba(82, 66, 122, 0.96), rgba(111, 82, 176, 0.92));
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.18),
        0 10px 24px rgba(72, 55, 116, 0.12);
      overflow-x: hidden;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      word-break: break-word;
      text-wrap: wrap;
    }

    .summary-code code {
      font-family: ui-monospace, "SFMono-Regular", Menlo, Monaco, Consolas, "PingFang SC", "Noto Sans Mono CJK SC", monospace;
      font-size: clamp(14px, 3vw, 16px);
      line-height: 1.78;
      font-weight: 650;
    }

    .next-card {
      padding: 17px 20px 19px;
    }

    .next-card p {
      margin: 0;
      color: rgba(37, 36, 49, 0.74);
      font-size: 14px;
      line-height: 1.65;
      font-weight: 400;
      text-align: center;
      overflow-wrap: anywhere;
      text-wrap: pretty;
    }

    .summary-footer {
      position: absolute;
      z-index: 5;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      right: 0;
      bottom: 0;
      left: 0;
      padding: 10px 0 calc(10px + var(--safe-bottom));
      background: var(--page-bottom-bg);
    }

    .complete-button {
      width: min(260px, calc(100vw - 64px));
      min-height: var(--button-height);
      border: 2px solid transparent;
      border-radius: var(--button-radius);
      color: #fff;
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.2), rgba(255, 255, 255, 0)) padding-box,
        linear-gradient(180deg, #9260fe, #9260fe) padding-box,
        linear-gradient(180deg, #f2eef8, #8f5df3) border-box;
      font: inherit;
      font-size: 16px;
      line-height: 1;
      font-weight: 800;
      cursor: pointer;
      transition: transform 150ms ease-out, filter 150ms ease-out;
      -webkit-tap-highlight-color: transparent;
    }

    .complete-button:active {
      transform: translateY(2px);
      filter: brightness(0.98);
    }

    .summary-error {
      width: calc(100% - 64px);
      margin: 120px auto 0;
      padding: 24px;
      border-radius: 28px;
      background: rgba(255, 255, 255, 0.68);
      color: #792536;
      text-align: center;
      font-size: 15px;
      line-height: 1.6;
    }

    @media (max-width: 420px) {
      .summary-scroll {
        padding-right: 24px;
        padding-left: 24px;
      }

      .completion-card {
        margin-top: 93px;
      }

      .summary-card {
        padding: 15px;
      }

      .summary-content {
        gap: 10px;
      }

      .summary-item {
        grid-template-columns: 32px minmax(0, 1fr);
        padding: 12px;
      }

      .summary-index {
        width: 32px;
        height: 32px;
      }

      .summary-quote {
        padding: 14px 14px 14px 39px;
      }

      .summary-code {
        padding: 14px 15px;
      }
    }

    @media (orientation: landscape) and (max-height: 720px) {
      .completion-card {
        margin-top: 58px;
        padding-top: 38px;
        padding-bottom: 12px;
      }

      .trophy-wrap {
        top: -58px;
        width: 72px;
        height: 96px;
      }

      .completion-card h1 {
        font-size: 16px;
      }

      .summary-card,
      .next-card {
        margin-top: 12px;
      }

      .summary-card {
        padding: 14px;
      }

      .summary-item {
        padding-top: 16px;
        padding-bottom: 10px;
      }

      .summary-paragraph,
      .summary-quote,
      .summary-notice,
      .summary-code code {
        font-size: 15px;
        line-height: 1.62;
      }

      .summary-footer {
        padding-top: 10px;
        padding-bottom: calc(10px + var(--safe-bottom));
      }
    }

    @media (max-height: 660px) and (orientation: portrait) {
      .completion-card {
        margin-top: 78px;
        padding-top: 40px;
        padding-bottom: 12px;
      }

      .trophy-wrap {
        top: -78px;
        width: 88px;
        height: 118px;
      }

      .summary-card,
      .next-card {
        margin-top: 12px;
      }
    }

    @media (prefers-reduced-motion: reduce) {
      * {
        transition: none !important;
        scroll-behavior: auto !important;
      }
    }
  </style>
</head>
<body>
  <main class="summary-page">
    <div class="summary-scroll">
      <div class="top-safe-area" aria-hidden="true"></div>

      <section class="completion-card" aria-labelledby="completionTitle">
        <div class="trophy-wrap" aria-hidden="true">
          <img
            src="https://res.xrunda.com/xruns/static/image/course_summary_trophy.png"
            alt=""
          >
        </div>
        <h1 id="completionTitle">恭喜你完成本节课程！</h1>
      </section>

      <section class="summary-card" aria-label="本课小结">
        <h2 id="summaryTitle">五项信息组成完整的问题说明</h2>
        <div class="summary-content" id="summaryContent" data-summary-static="true"><p class="summary-paragraph">现在，把刚才的信息合在一起：</p><blockquote class="summary-quote">第一次参加社区桌游体验的人，不清楚不同游戏需要的人数和时长，到了现场常要重新挑选。我们希望他们出发前能根据公开说明选到合适的游戏。处理时只使用公开信息，不收集姓名等个人资料。这样可以减少等待，把更多时间留给游戏体验。</blockquote><p class="summary-paragraph">这段问题说明里有五项信息：</p><ol class="summary-list"><li class="summary-item"><span class="summary-index">01</span><span>对象：第一次参加的人。</span></li><li class="summary-item"><span class="summary-index">02</span><span>困难：不知道人数和时长，到场后重新等待。</span></li><li class="summary-item"><span class="summary-index">03</span><span>期望变化：出发前选到合适的游戏。</span></li><li class="summary-item"><span class="summary-index">04</span><span>边界：只用公开说明，不收集个人信息。</span></li><li class="summary-item"><span class="summary-index">05</span><span>处理价值：减少等待，增加游戏时间。</span></li></ol><aside class="summary-notice">注意，这里还没有决定一定要使用AI。</aside><p class="summary-paragraph">先把问题说清楚，后面才能判断该用什么方法，也才能判断AI是否适合参与。</p></div>
      </section>

      <section class="next-card" id="nextCard" aria-labelledby="nextTitle" hidden>
        <h2 id="nextTitle">下一课预告</h2>
        <p id="nextLessonPreview"></p>
      </section>
    </div>

    <footer class="summary-footer">
      <button class="complete-button" id="completeButton" type="button">完成学习</button>
    </footer>
  </main>

  <script>
    /* ============================================================
       每课只允许替换本变量区中的完成头、原文内容与 pageAction。
       contentBlocks 必须按教案原顺序逐字录入，不得概括、删句、合并或去重。
       变量名、结构、HTML、CSS、渲染逻辑均不得修改。
       ============================================================ */
    const COURSE_SUMMARY_VARIABLES = Object.freeze({
      completionTitle: "恭喜你完成本节课程！",
      summaryTitle: "五项信息组成完整的问题说明",
      contentBlocks: Object.freeze([
        Object.freeze({
          type: "paragraph",
          text: "现在，把刚才的信息合在一起："
        }),
        Object.freeze({
          type: "blockquote",
          text: "第一次参加社区桌游体验的人，不清楚不同游戏需要的人数和时长，到了现场常要重新挑选。我们希望他们出发前能根据公开说明选到合适的游戏。处理时只使用公开信息，不收集姓名等个人资料。这样可以减少等待，把更多时间留给游戏体验。"
        }),
        Object.freeze({
          type: "paragraph",
          text: "这段问题说明里有五项信息："
        }),
        Object.freeze({
          type: "orderedList",
          items: Object.freeze([
            "对象：第一次参加的人。",
            "困难：不知道人数和时长，到场后重新等待。",
            "期望变化：出发前选到合适的游戏。",
            "边界：只用公开说明，不收集个人信息。",
            "处理价值：减少等待，增加游戏时间。"
          ])
        }),
        Object.freeze({
          type: "notice",
          text: "注意，这里还没有决定一定要使用AI。"
        }),
        Object.freeze({
          type: "paragraph",
          text: "先把问题说清楚，后面才能判断该用什么方法，也才能判断AI是否适合参与。"
        })
      ]),
      nextLessonPreview: "下一课会使用一份新的完整问题说明，学习怎样用Prompt把任务交代清楚。",
      pageAction: "complete"
    });
    /* ======================= 变量区结束 ======================= */

    function validateSummaryVariables(data) {
      const missing = [];
      const invalid = [];
      const allowedTypes = new Set(["paragraph", "orderedList", "blockquote", "notice", "codeBlock"]);

      if (typeof data.completionTitle !== "string" || !data.completionTitle.trim()) missing.push("completionTitle");
      if (typeof data.summaryTitle !== "string" || !data.summaryTitle.trim()) missing.push("summaryTitle");
      if (!Array.isArray(data.contentBlocks) || data.contentBlocks.length < 1) missing.push("contentBlocks");
      if (typeof data.nextLessonPreview !== "string") missing.push("nextLessonPreview");
      if (missing.length) throw new Error(`SUMMARY_FIELD_MISSING: ${missing.join(", ")}`);

      data.contentBlocks.forEach((block, blockIndex) => {
        if (!block || typeof block !== "object" || !allowedTypes.has(block.type)) {
          invalid.push(`contentBlocks[${blockIndex}].type`);
          return;
        }

        if (block.type === "orderedList") {
          if (!Array.isArray(block.items) || block.items.length < 1) {
            invalid.push(`contentBlocks[${blockIndex}].items`);
            return;
          }
          if (block.sourceNumbered !== undefined && typeof block.sourceNumbered !== "boolean") {
            invalid.push(`contentBlocks[${blockIndex}].sourceNumbered`);
          }
          block.items.forEach((item, itemIndex) => {
            if (typeof item !== "string" || !item.trim()) {
              invalid.push(`contentBlocks[${blockIndex}].items[${itemIndex}]`);
            }
          });
          return;
        }

        if (block.type === "codeBlock" && block.language !== undefined && typeof block.language !== "string") {
          invalid.push(`contentBlocks[${blockIndex}].language`);
        }

        if (typeof block.text !== "string" || !block.text.trim()) {
          invalid.push(`contentBlocks[${blockIndex}].text`);
        }
      });

      if (!new Set(["next", "complete"]).has(data.pageAction)) invalid.push("pageAction");
      if (invalid.length) throw new Error(`SUMMARY_FIELD_INVALID: ${invalid.join(", ")}`);
    }

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

    function createTextBlock(tagName, className, text, blockType) {
      const element = document.createElement(tagName);
      element.className = className;
      element.dataset.blockType = blockType;
      element.textContent = text;
      return element;
    }

    function createOrderedListBlock(block) {
      const list = document.createElement("ol");
      list.className = "summary-list";
      list.dataset.blockType = "orderedList";
      list.dataset.numberingMode = block.sourceNumbered ? "source-plus-generated" : "generated";

      block.items.forEach((item, index) => {
        const listItem = document.createElement("li");
        listItem.className = "summary-item";

        const number = document.createElement("span");
        number.className = "summary-index";
        number.setAttribute("aria-hidden", "true");
        number.textContent = String(index + 1).padStart(2, "0");
        listItem.appendChild(number);

        const text = document.createElement("span");
        text.textContent = item;

        listItem.appendChild(text);
        list.appendChild(listItem);
      });

      return list;
    }

    function createCodeBlock(block) {
      const pre = document.createElement("pre");
      pre.className = "summary-code";
      pre.dataset.blockType = "codeBlock";
      if (block.language) pre.dataset.language = block.language;

      const code = document.createElement("code");
      code.textContent = block.text;
      pre.appendChild(code);
      return pre;
    }

    function renderContentBlocks(container, blocks) {
      const fragment = document.createDocumentFragment();

      blocks.forEach(block => {
        if (block.type === "orderedList") {
          fragment.appendChild(createOrderedListBlock(block));
          return;
        }

        if (block.type === "codeBlock") {
          fragment.appendChild(createCodeBlock(block));
          return;
        }

        const blockConfig = {
          paragraph: ["p", "summary-paragraph"],
          blockquote: ["blockquote", "summary-quote"],
          notice: ["aside", "summary-notice"]
        }[block.type];

        fragment.appendChild(createTextBlock(blockConfig[0], blockConfig[1], block.text, block.type));
      });

      container.replaceChildren(fragment);
    }

    function configurePageAction(button, pageAction) {
      if (pageAction === "next") {
        button.textContent = "继续学习";
        button.addEventListener("click", safeNextPage);
        return;
      }

      button.textContent = "完成学习";
      button.addEventListener("click", safeComplete);
    }

    function renderSummaryPage() {
      const data = COURSE_SUMMARY_VARIABLES;
      validateSummaryVariables(data);

      document.getElementById("completionTitle").textContent = data.completionTitle;
      document.getElementById("summaryTitle").textContent = data.summaryTitle;
      renderContentBlocks(document.getElementById("summaryContent"), data.contentBlocks);
      const summaryCard = document.querySelector(".summary-card");
      summaryCard.classList.toggle("summary-card--single-block", data.contentBlocks.length === 1);

      const nextCard = document.getElementById("nextCard");
      if (data.nextLessonPreview.trim()) {
        document.getElementById("nextLessonPreview").textContent = data.nextLessonPreview;
        nextCard.hidden = false;
      }

      const button = document.getElementById("completeButton");
      configurePageAction(button, data.pageAction);
    }

    function syncLayoutMetrics() {
      const footer = document.querySelector(".summary-footer");
      const height = Math.ceil(footer.getBoundingClientRect().height || 80);
      document.documentElement.style.setProperty("--footer-h", `${height}px`);
    }

    try {
      renderSummaryPage();
      syncLayoutMetrics();
      if ("ResizeObserver" in window) {
        new ResizeObserver(syncLayoutMetrics).observe(document.querySelector(".summary-footer"));
      }
      window.addEventListener("resize", syncLayoutMetrics, { passive: true });
      window.addEventListener("orientationchange", () => setTimeout(syncLayoutMetrics, 120), { passive: true });
    } catch (error) {
      document.documentElement.dataset.summaryError = "SUMMARY_FIELD_MISSING";
      document.body.innerHTML = '<main class="summary-error" role="alert">课程小结内容暂不可用</main>';
      throw error;
    }
  </script>
</body>
</html>

```

## 5. 输出校验与写入

1. 校验模型回复首尾为完整 HTML，且不含 Markdown 围栏、解释或提示词版本前缀。
2. 校验学生可见文本与上游有效内容逐字、按顺序一致，禁入句不存在。
3. 按第 3 节算法核验变量区外 SHA-256。
4. 静态检查 SDK 脚本、`safeNextPage()`、`safeComplete()`、唯一底部按钮、滚动容器、无音频和无 `Powered by RunS`。
5. 当前 RunS 页面模型链路把本课完整固定模板 OneShot 实际模型输入写入课程小结页 `pages[].prompt`；模型返回的纯完整 HTML 是实际生成页面结果，另层校验与留证。
6. 在 `page_data` 记录合同版本、实际提示词版本、生成模型、Demo SHA-256、变量区外 SHA-256、来源页块和 `pageAction`。

## 6. 阻断条件

以下任一项存在时标记 `COURSE_SUMMARY_FIXED_ONESHOT_INVALID`，并阻断 `S3G`、`S5.1`、`final_import`、dry-run 和 create：

- 提示词依赖本地路径、Demo、SOP 或历史上下文；
- 没有内嵌完整 HTML/CSS/JavaScript 与真实变量；
- 模型返回局部代码、Markdown、解释或普通文本；
- 变量区外 SHA-256 不匹配；
- 原文丢失、改写、换序、补造或块类型错误；
- 禁入句进入变量或 DOM；
- 页面动作与有效页面规划不一致；
- 平台壳层、胶囊、音频、`Powered by RunS`、滚动、底栏、按钮或 SDK 合同漂移。
