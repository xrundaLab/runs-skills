# 课程开篇页固定模板 OneShot（V3.5）

状态：`CURRENT_PRODUCTION_ASSET`  
合同版本：`RunS-CourseIntro-FixedTemplate-OneShot-v1.8`  
适用范围：Kimi / GLM 一次性、无外部上下文生成课程开篇页完整 HTML。  
固定 Demo SHA-256：`ba53ef84a86f7286839c8027460714906c1048849fd1d9c1403fe4bc555dfb89`  
变量区外 SHA-256：`070cf9823d34755856019e88d0cd24c64d1c17e6f0535776a08b1a4945cca8e3`

## 1. 四层产物边界

| 层级 | 必须包含 | 禁止 |
| --- | --- | --- |
| 上游有效内容 | `effective_content_full.json` 中 P01 课程开篇六字段、来源块和页面动作 | 从历史页面、研发摘要、原始教案或模型记忆补内容 |
| 最终导入 JSON 的 `pages[].prompt` / 提交给 RunS 页面模型、Kimi 或 GLM 的一次性提示词 | 每次唯一模型中立版本号、无外部上下文声明、纯 HTML 输出约束、完整 Demo HTML/CSS/JavaScript、本课真实 `COURSE_INTRO_VARIABLES` | 只给裸 HTML、只给路径、只给变量对象、引用历史模板、增量补丁、省略代码 |
| 模型返回 | 从 `<!doctype html>` 到 `</html>` 的纯完整 HTML，变量区外字节不变 | Markdown 围栏、解释、版本号、提示词正文、局部代码 |
| 实际生成页面 HTML | 校验通过后的模型完整 HTML | 生成指令、路径、变量对象或上游审计数据 |

当前 RunS JSON 导入后仍由页面模型消费 `pages[].prompt`，因此导入 JSON 的该字段必须保存本文件代码块内部的完整实际提示词，不能只保存裸 HTML。本地确定性装配器只有在下游已确认支持最终 HTML 原样持久化并跳过页面模型时，才可以直接复制同一 Demo、只替换变量值并提交完整 HTML；`tasks:create --direct` 本身不等于最终 HTML 直写。

## 2. 生成与字段合同

1. P01 六个内容字段必须来自同一个有效课程开篇页块；不得回读课程信息表、原始教案或历史页面补值。
2. `packageName`、`unitName`、`courseName`、`courseIntroduction` 逐字注入；`knowledgePoints` 保持原顺序。
3. `lessonNumber` 只允许把有效字段中精确格式 `第N课` 确定性转换为正整数 `N`；其他格式阻断。
4. 课程开篇固定为非末页并调用下一页；模型不得推断或改变动作。
5. 页面固定无新增音频、平台壳层、内部页面类型胶囊或 `Powered by RunS`。
6. 开篇仅保留一个主插画层，使用已登记的 HTTPS 资产 `https://res.xrunda.com/xruns/static/image/20270724/1.png`；页面提示词不得携带 `data:image` 或 Base64，模型不得改写、重编码或省略该地址。后续更换正式角色图时必须先升级合同版本并重冻 Demo。

允许变量仅为：`packageName`、`unitName`、`lessonNumber`、`courseName`、`courseIntroduction`、`knowledgePoints`。

## 3. 变量区外哈希算法

1. 以 UTF-8 原始字节读取固定 Demo，不做空格、编码、内部换行或 Unicode 规范化；仅对文件末尾执行单一规范：若 `</html>` 后没有 LF，则补一个 LF，若已有一个 LF 则保持不变。
2. 变量区开始锚点为精确行 `    const COURSE_INTRO_VARIABLES = Object.freeze({`。
3. 变量区结束锚点为精确行 `    /* ======================= 变量区结束 ======================= */`。
4. 从开始锚点首字节到结束锚点所在行的换行符为止，整段从哈希输入中移除；模型输出也先按第 1 步规范末尾 LF。
5. 拼接前后剩余字节并计算 SHA-256，必须得到 `070cf9823d34755856019e88d0cd24c64d1c17e6f0535776a08b1a4945cca8e3`。
6. 模型输出采用同一算法复核；不一致即 `INTRO_TEMPLATE_DRIFT`。

## 4. 完整可复制实例：lesson001 P01

实例来源：`v35_candidate_stage1_batch_20260719/lesson001/02_页面规划/effective_content_full.json` 的 P01。  
页面动作：固定下一页。  
实际提示词版本：`RunS-CourseIntro-L001-P01-FixedTemplate-OneShot-v1.8-20260724-R14-019f934d1a1`。

当前 RunS JSON 页面模型链路中，把下面代码块内部的全部内容原样写入 P01 的 `pages[].prompt`；直接调用 Kimi 或 GLM 时同样提交该完整内容。不要复制外层 Markdown 围栏。

```text
提示词版本号：RunS-CourseIntro-L001-P01-FixedTemplate-OneShot-v1.8-20260724-R14-019f934d1a1

适用页面：lesson001｜P01｜第 1/9 页｜课程开篇页。

请输出一个完整、可运行的移动端 HTML 网页。

这是一次性提示词，没有任何外部上下文。不得读取文件、路径、Demo、SOP、历史模板或其他对话。网页所需的课程内容、HTML、CSS、JavaScript、图片元素和 SDK 行为已经全部包含在本提示词中。

最终回复必须且只能包含下方完整 HTML：

- 第一个非空白字符必须属于 <!doctype html>。
- 最后一个标签必须是 </html>。
- 不得输出解释、Markdown 围栏、版本说明、调试信息或提示词正文。
- 不得重排、改写、删减或补写学生可见内容。
- 不得修改 COURSE_INTRO_VARIABLES 之外的任何 HTML、CSS、JavaScript、图片地址、固定文案、模块顺序、按钮或 SDK 行为。
- 不得把已登记 HTTPS 图片地址改成 Base64、`data:image`、其他 URL 或空值。
- 必须保留课程路径、课次胶囊、标题、学习目标、知识点列表、固定插画、长内容滚动、统一底栏和唯一课程动作按钮。
- 不得生成平台顶部壳层、页面类型胶囊、音频、播放器、TTS、字幕、CUE、输入框、Powered by RunS 或来源中不存在的模块。
- 底部“开始探索”按钮必须调用 CreatorReviewSDK.nextPage()。

请原样输出下方完整代码：

<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>课程开篇页固定模板</title>
  <script src="https://res.xrunda.com/runs/plugin/creator/creator-review-sdk.js"></script>
  <style>
    /* FIXED_LAYOUT_CONTRACT: 顶部/两侧/底部留白、底栏和主按钮均为固定代码；每课只替换 COURSE_INTRO_VARIABLES。 */

    :root {
      --purple: #9260fe;
      --ink: #242331;
      --safe-bottom: env(safe-area-inset-bottom, 0px);
      --page-bottom-rgb: 213, 245, 254;
      --page-bottom-bg: rgb(var(--page-bottom-rgb));
      --footer-h: calc(80px + var(--safe-bottom));
      --button-height: 60px;
      --content-max: 360px;
      --card-radius: 30px;
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

    .runs-intro-page {
      position: relative;
      width: 100%;
      max-width: 538px;
      height: 100dvh;
      margin: 0 auto;
      overflow: hidden;
      border-radius: 0;
      color: var(--ink);
      background: linear-gradient(180deg, #d7c4ff 0%, var(--page-bottom-bg) 66.667%, var(--page-bottom-bg) 100%);
      font-family: Inter, -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
    }

    .top-safe-area {
      display: none;
      height: 0;
    }

    .intro-scroll {
      width: 100%;
      height: 100%;
      overflow-y: auto;
      overflow-x: hidden;
      padding: 28px 0 calc(var(--footer-h) + 24px);
      overscroll-behavior: contain;
      -webkit-overflow-scrolling: touch;
    }

    .intro-inner {
      width: min(calc(100% - 48px), var(--content-max));
      margin: 0 auto;
      display: grid;
      gap: 16px;
    }

    .intro-header {
      text-align: center;
    }

    .intro-illustration {
      width: 180px;
      height: 134px;
      margin: 0 auto;
      background: url("https://res.xrunda.com/xruns/static/image/20270724/1.png") center / contain no-repeat;
    }

    .intro-header h2 {
      margin: 0;
      font-size: 12px;
      line-height: 21px;
      font-weight: 600;
      overflow-wrap: anywhere;
    }

    .intro-header p {
      margin: 0;
      color: rgba(36, 35, 49, 0.72);
      font-size: 12px;
      line-height: 21px;
      overflow-wrap: anywhere;
    }

    .intro-focus-card {
      position: relative;
      margin-top: 20px;
      padding-top: 0;
    }

    .lesson-chip {
      position: absolute;
      z-index: 3;
      top: -15px;
      left: 50%;
      display: grid;
      place-items: center;
      width: 82px;
      min-height: 30px;
      padding: 4px 12px;
      transform: translateX(-50%);
      border: 1px solid #b8ed55;
      border-radius: 999px;
      color: #242331;
      background: #d9f99d;
      font-size: 13px;
      line-height: 20px;
      font-weight: 700;
      white-space: nowrap;
    }

    .intro-focus-surface {
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.92);
      border-radius: var(--card-radius);
      background: rgba(255, 255, 255, 0.72);
      box-shadow: 0 12px 28px rgba(81, 57, 137, 0.06);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
    }

    .title-panel {
      display: flex;
      min-height: 108px;
      align-items: center;
      justify-content: center;
      padding: 28px 12px 20px;
      background: rgba(255, 255, 255, 0.72);
    }

    #courseTitle {
      width: 100%;
      margin: 0;
      color: var(--purple);
      text-align: center;
      font-size: 24px;
      line-height: 1.3;
      font-weight: 800;
      letter-spacing: 0.2px;
      text-wrap: balance;
      overflow-wrap: anywhere;
    }

    .content-card {
      position: relative;
      padding: 18px;
      border: 1px solid rgba(255, 255, 255, 0.92);
      border-radius: var(--card-radius);
      background: rgba(255, 255, 255, 0.72);
      box-shadow: 0 12px 28px rgba(81, 57, 137, 0.06);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
    }

    .content-card h3 {
      margin: 0 0 8px;
      color: var(--purple);
      font-size: 13px;
      line-height: 21px;
      font-weight: 700;
      text-align: center;
    }

    .core-question-panel {
      position: relative;
      padding: 18px 18px;
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.2), rgba(255, 255, 255, 0)),
        rgba(146, 96, 254, 0.2);
      backdrop-filter: blur(2px);
      -webkit-backdrop-filter: blur(2px);
    }

    .core-question-icon {
      position: absolute;
      z-index: 2;
      top: -24px;
      left: 24px;
      width: 48px;
      height: 48px;
      object-fit: contain;
      pointer-events: none;
    }

    .core-question-panel h3 {
      margin: 0 0 8px;
      color: var(--purple);
      font-size: 13px;
      line-height: 21px;
      font-weight: 700;
      text-align: center;
    }

    #learningGoal {
      margin: 0;
      text-align: center;
      font-size: 14px;
      line-height: 23px;
      overflow-wrap: anywhere;
    }

    .unlock-card {
      padding: 16px 16px 18px;
    }

    #knowledgeList {
      display: grid;
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;
    }

    #knowledgeList li {
      display: grid;
      grid-template-columns: 30px minmax(0, 1fr);
      gap: 10px;
      align-items: center;
      min-height: 44px;
      padding: 8px 12px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.78);
      font-size: 14px;
      line-height: 21px;
      overflow-wrap: anywhere;
    }

    .knowledge-index {
      display: grid;
      place-items: center;
      width: 30px;
      height: 30px;
      border-radius: 11px;
      color: var(--purple);
      background: rgba(146, 96, 254, 0.12);
      font-size: 12px;
      line-height: 1;
      font-weight: 900;
    }

    .intro-footer {
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

    #primaryButton {
      width: min(260px, calc(100vw - 64px));
      min-height: var(--button-height);
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

    #primaryButton:active {
      transform: translateY(1px);
    }

    .intro-error {
      width: min(100% - 36px, 480px);
      margin: 80px auto;
      padding: 20px;
      border-radius: 20px;
      background: rgba(255, 255, 255, 0.82);
      text-align: center;
      font-size: 16px;
      line-height: 1.6;
    }

    @media (max-width: 359px) {
      .intro-inner {
        width: min(calc(100% - 40px), var(--content-max));
      }
    }

    @media (orientation: landscape) and (max-height: 720px) {
      .intro-illustration {
        width: 130px;
        height: 92px;
      }

      .intro-character {
        top: 16px;
        width: 62px;
        height: 75px;
      }

      .content-card {
        padding: 15px;
      }

      .intro-inner {
        gap: 9px;
      }
    }

    @media (prefers-reduced-motion: reduce) {
      * {
        scroll-behavior: auto !important;
        transition: none !important;
      }
    }
  </style>
</head>
<body>
  <main class="runs-intro-page">
    <div class="top-safe-area" aria-hidden="true"></div>

    <div class="intro-scroll" id="introScroll">
      <div class="intro-inner">
        <header class="intro-header">
          <div class="intro-illustration" aria-hidden="true"></div>
          <h2 id="packageName"></h2>
          <p id="unitName"></p>
        </header>

        <section class="intro-focus-card" aria-label="本课开篇信息">
          <span class="lesson-chip" id="lessonChip"></span>
          <div class="intro-focus-surface">
            <div class="title-panel">
              <h1 id="courseTitle"></h1>
            </div>
            <div class="core-question-panel" aria-labelledby="learningGoalTitle">
              <img class="core-question-icon" src="https://res.xrunda.com/xruns/static/image/course_intro_icon.png" alt="" aria-hidden="true">
              <h3 id="learningGoalTitle">学习目标</h3>
              <p id="learningGoal"></p>
            </div>
          </div>
        </section>

        <section class="content-card unlock-card" aria-labelledby="unlockTitle">
          <h3 id="unlockTitle">本课将解锁</h3>
          <ul id="knowledgeList"></ul>
        </section>
      </div>
    </div>

    <footer class="intro-footer" id="introFooter">
      <button id="primaryButton" type="button">开始探索</button>
    </footer>
  </main>

  <script>
    /* ============================================================
       每课只允许替换本变量区。变量名、结构、HTML、CSS、交互均不得修改。
       ============================================================ */
    const COURSE_INTRO_VARIABLES = Object.freeze({
      packageName: "课包1：AI 创想家（AI Creator）",
      unitName: "单元1：认识 AI：问题发现与任务表达",
      lessonNumber: 1,
      courseName: "Workflow 和 SOP 分别解决什么问题",
      courseIntroduction: "理解 Workflow 与 SOP 的区别，能根据任务选择合适的方法，并知道何时需要建立可复用的执行标准。",
      knowledgePoints: Object.freeze([
        "Workflow 解决任务推进问题",
        "SOP 解决执行一致性问题",
        "根据任务选择合适的方法",
        "先明确任务目标，再拆解执行步骤",
        "把重复出现的步骤整理成稳定流程",
        "为关键节点补充可检查的完成标准",
        "区分需要灵活判断的环节与必须统一的环节",
        "记录流程中的输入、处理动作和输出结果",
        "用复盘结果持续更新 Workflow 和 SOP",
        "在执行前确认版本、角色和交付边界"
      ])
    });
    /* ======================= 变量区结束 ======================= */

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\"": "&quot;",
        "'": "&#39;"
      }[character]));
    }

    function assertVariables(data) {
      const textFields = ["packageName", "unitName", "courseName", "courseIntroduction"];
      const missingFields = textFields.filter(field => typeof data[field] !== "string" || !data[field].trim());
      if (!Number.isInteger(data.lessonNumber) || data.lessonNumber < 1) missingFields.push("lessonNumber");
      if (!Array.isArray(data.knowledgePoints) || data.knowledgePoints.length < 1) missingFields.push("knowledgePoints");
      if (missingFields.length) throw new Error(`INTRO_FIELD_MISSING: ${missingFields.join(", ")}`);
    }

    function safeNextPage() {
      if (window.CreatorReviewSDK && typeof window.CreatorReviewSDK.nextPage === "function") {
        window.CreatorReviewSDK.nextPage();
        return;
      }
      if (window.parent) window.parent.postMessage({ type: "nextpage" }, "*");
    }

    function safeComplete() {
      if (window.CreatorReviewSDK && typeof window.CreatorReviewSDK.complete === "function") {
        window.CreatorReviewSDK.complete();
        return;
      }
      if (window.parent) window.parent.postMessage({ type: "complete" }, "*");
    }

    function renderIntroPage() {
      const data = COURSE_INTRO_VARIABLES;
      assertVariables(data);
      document.title = data.courseName;
      document.getElementById("packageName").textContent = data.packageName;
      document.getElementById("unitName").textContent = data.unitName;
      document.getElementById("lessonChip").textContent = `第${data.lessonNumber}课`;
      document.getElementById("courseTitle").textContent = data.courseName;
      document.getElementById("learningGoal").textContent = data.courseIntroduction;
      document.getElementById("knowledgeList").innerHTML = data.knowledgePoints
        .map((item, index) => `
          <li>
            <span class="knowledge-index" aria-hidden="true">${String(index + 1).padStart(2, "0")}</span>
            <span>${escapeHtml(item)}</span>
          </li>`)
        .join("");

      document.getElementById("primaryButton").addEventListener("click", safeNextPage);
    }


    function fitCourseTitle() {
      const title = document.getElementById("courseTitle");
      const maximumSize = 24;
      const minimumSingleLineSize = 20;
      const minimumTwoLineSize = 18;
      const step = 0.5;

      let size = maximumSize;
      title.style.fontSize = size + "px";
      title.style.whiteSpace = "nowrap";
      title.style.overflowWrap = "normal";

      while (size > minimumSingleLineSize && title.scrollWidth > title.clientWidth + 1) {
        size -= step;
        title.style.fontSize = size + "px";
      }

      if (title.scrollWidth <= title.clientWidth + 1) {
        title.dataset.titleMode = "single-line";
        return;
      }

      title.style.whiteSpace = "normal";
      title.style.overflowWrap = "anywhere";
      size = maximumSize;
      title.style.fontSize = size + "px";

      const lineCount = () => {
        const range = document.createRange();
        range.selectNodeContents(title);
        const lineHeight = Number.parseFloat(getComputedStyle(title).lineHeight) || size * 1.3;
        return Math.round(range.getBoundingClientRect().height / lineHeight);
      };

      while (size > minimumTwoLineSize && lineCount() > 2) {
        size -= step;
        title.style.fontSize = size + "px";
      }

      title.dataset.titleMode = "two-line-fallback";
    }

    function syncLayoutMetrics() {
      fitCourseTitle();
      const footer = document.getElementById("introFooter");
      const height = Math.ceil(footer.getBoundingClientRect().height || 80);
      document.documentElement.style.setProperty("--footer-h", `${height}px`);
    }

    try {
      renderIntroPage();
      syncLayoutMetrics();
      if ("ResizeObserver" in window) {
        new ResizeObserver(syncLayoutMetrics).observe(document.getElementById("introFooter"));
      }
      window.addEventListener("resize", syncLayoutMetrics, { passive: true });
      window.addEventListener("orientationchange", () => setTimeout(syncLayoutMetrics, 120), { passive: true });
    } catch (error) {
      document.documentElement.dataset.introError = "INTRO_FIELD_MISSING";
      document.body.innerHTML = '<main class="intro-error" role="alert">页面内容暂不可用</main>';
      throw error;
    }
  </script>
</body>
</html>


```

## 5. 输出校验与写入

1. 校验模型回复首尾为完整 HTML，且不含 Markdown 围栏、解释或提示词版本前缀。
2. 校验学生可见文本与上游有效内容逐字、按顺序一致。
3. 按第 3 节算法核验变量区外 SHA-256。
4. 静态检查 SDK 脚本、唯一底部按钮、滚动容器、无新增音频和无 `Powered by RunS`。
5. 当前 RunS 页面模型链路把本代码块内的完整实际模型输入写入对应页面的 `pages[].prompt`；模型返回的纯完整 HTML 是实际生成页面结果，另层校验与留证。
6. 在 `page_data` 记录合同版本、实际提示词版本、生成模型、Demo SHA-256、变量区外 SHA-256、来源页块和页面动作。

## 6. 阻断条件

以下任一项存在时标记 `COURSE_INTRO_FIXED_ONESHOT_INVALID`，并阻断 `S3G`、`S5.1`、`final_import`、dry-run 和 create：

- 提示词依赖本地路径、Demo、SOP 或历史上下文；
- 没有内嵌完整 HTML/CSS/JavaScript 与真实变量；
- 含 `data:image` / Base64，或开篇插画地址不是当前登记的 HTTPS 资产；
- 模型返回局部代码、Markdown、解释或普通文本；
- 变量区外 SHA-256 不匹配；
- 原文丢失、改写、换序、补造或字段类型错误；
- 页面动作与有效页面规划不一致；
- 平台壳层、胶囊、音频、`Powered by RunS`、滚动、底栏、按钮或 SDK 合同漂移。
