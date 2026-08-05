# 场景引入页固定模板 OneShot（V3.5）

状态：`CURRENT_PRODUCTION_ASSET`  
合同版本：`RunS-SceneIntro-FixedTemplate-OneShot-v1.6`
适用范围：Kimi / GLM 一次性、无外部上下文生成场景引入页完整 HTML。  
固定 Demo SHA-256：`0b746794a30a826b376ce6992b9fd896d3ead1a76d93b4d93540ee6eff13973a`  
变量区外 SHA-256：`edd32ece1d155f5b727a5c8e0c7f1cd91228d5e9bded49b2ebf0d72364c0d94c`

## 1. 四层产物边界

| 层级 | 必须包含 | 禁止 |
| --- | --- | --- |
| 上游有效内容 | `effective_content_full.json` 中 P02 场景引入原序段落、承接段、来源块和页面动作 | 从历史页面、研发摘要、原始教案或模型记忆补内容 |
| 提交给 Kimi / GLM 的一次性提示词 | 每次唯一模型中立版本号、无外部上下文声明、纯 HTML 输出约束、完整 Demo HTML/CSS/JavaScript、本课真实 `SCENE_INTRO_VARIABLES` | 只给路径、只给变量对象、引用历史模板、增量补丁、省略代码 |
| 模型返回 | 从 `<!doctype html>` 到 `</html>` 的纯完整 HTML，变量区外字节不变 | Markdown 围栏、解释、版本号、提示词正文、局部代码 |
| 当前 RunS JSON 的 `pages[].prompt` | 本课完整固定模板 OneShot 实际模型输入 | 裸 HTML、路径、单独变量对象或上游审计数据 |

本地确定性装配器可以直接复制同一 Demo 并只替换变量值；若通过 Kimi / GLM 执行，则必须使用本文件的一次性完整提示词，不能把“严格复制某路径 Demo”当作模型输入。

## 2. 生成与字段合同

1. `sceneParagraphs`、`lessonLead` 必须来自同一个有效场景引入页块，逐段、按原顺序注入。
2. 最后承接段只进入 `lessonLead` 一次，不得同时留在 `sceneParagraphs`。
3. `pageAction` 来自有效页面规划：`nextPage` 确定性映射为 `next`，实际末页的 `complete` 映射为 `complete`；模型不得自行推断。
4. 缺少正文段、承接段或合法页面动作时阻断，不得从课程目标、研发摘要或模型记忆补造。
5. 页面固定无新增音频、平台壳层、内部页面类型胶囊或 `Powered by RunS`。

允许变量仅为：`sceneParagraphs`、`lessonLead`、`pageAction`。

## 3. 变量区外哈希算法

1. 以 UTF-8 原始字节读取固定 Demo，不做空格、编码、内部换行或 Unicode 规范化；仅对文件末尾执行单一规范：若 `</html>` 后没有 LF，则补一个 LF，若已有一个 LF 则保持不变。
2. 变量区开始锚点为精确行 `    const SCENE_INTRO_VARIABLES = Object.freeze({`。
3. 变量区结束锚点为精确行 `    /* ======================= 变量区结束 ======================= */`。
4. 从开始锚点首字节到结束锚点所在行的换行符为止，整段从哈希输入中移除；模型输出也先按第 1 步规范末尾 LF。
5. 拼接前后剩余字节并计算 SHA-256，必须得到 `edd32ece1d155f5b727a5c8e0c7f1cd91228d5e9bded49b2ebf0d72364c0d94c`。
6. 模型输出采用同一算法复核；不一致即 `SCENE_INTRO_TEMPLATE_DRIFT`。

## 4. 完整可复制实例：lesson001 P02

实例来源：`v35_candidate_stage1_batch_20260719/lesson001/02_页面规划/effective_content_full.json` 的 P02。  
页面动作：`next`。  
实际提示词版本：`RunS-SceneIntro-L001-P02-FixedTemplate-OneShot-v1.5-20260724-R15-019f934d1a2`。

复制下面代码块内部的全部内容提交给 Kimi 或 GLM；不要复制外层 Markdown 围栏。

```text
提示词版本号：RunS-SceneIntro-L001-P02-FixedTemplate-OneShot-v1.5-20260724-R15-019f934d1a2

适用页面：lesson001｜P02｜第 2/9 页｜场景引入页。

请输出一个完整、可运行的移动端 HTML 网页。

这是一次性提示词，没有任何外部上下文。不得读取文件、路径、Demo、SOP、历史模板或其他对话。网页所需的课程内容、HTML、CSS、JavaScript、图片元素和 SDK 行为已经全部包含在本提示词中。

最终回复必须且只能包含下方完整 HTML：

- 第一个非空白字符必须属于 <!doctype html>。
- 最后一个标签必须是 </html>。
- 不得输出解释、Markdown 围栏、版本说明、调试信息或提示词正文。
- 不得重排、改写、删减或补写学生可见内容。
- 不得修改 SCENE_INTRO_VARIABLES 之外的任何 HTML、CSS、JavaScript、图片地址、固定文案、模块顺序、按钮或 SDK 行为。
- 必须保留固定情境文案、剧本纸、镜头拉近卡、长内容滚动、统一底栏和唯一课程动作按钮。
- 不得生成平台顶部壳层、页面类型胶囊、音频、播放器、TTS、字幕、CUE、输入框、Powered by RunS 或来源中不存在的模块。
- 底部按钮必须按 pageAction="next" 调用 CreatorReviewSDK.nextPage()。

请原样输出下方完整代码：

<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>场景引入页固定模板</title>
  <script src="https://res.xrunda.com/runs/plugin/creator/creator-review-sdk.js"></script>
  <style>
    /* FIXED_LAYOUT_CONTRACT: 顶部/两侧/底部留白、底栏和主按钮均为固定代码；每课只替换 SCENE_INTRO_VARIABLES。 */
    :root {
      --purple: #9260fe;
      --purple-deep: #7650d8;
      --ink: #292735;
      --muted: rgba(41, 39, 53, 0.62);
      --paper: #fffdf8;
      --safe-bottom: 0px;
      --page-bottom-rgb: 212, 247, 255;
      --page-bottom-bg: rgb(var(--page-bottom-rgb));
      --footer-h: calc(80px + var(--safe-bottom));
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "PingFang SC", "Noto Sans SC", "Microsoft YaHei", sans-serif;
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

    .scene-page {
      position: relative;
      width: 100%;
      max-width: 538px;
      height: 100%;
      min-height: 100%;
      margin: 0 auto;
      overflow: hidden;
      background:
        radial-gradient(circle at 48% 9%, rgba(255, 255, 255, 0.38) 0 9%, transparent 31%),
        radial-gradient(circle at 106% 30%, rgba(255, 255, 255, 0.27) 0 13%, transparent 33%),
        linear-gradient(180deg, #d5bfff 0%, #d3d7ff 42%, var(--page-bottom-bg) 66.667%, var(--page-bottom-bg) 100%);
    }

    .scene-page::before,
    .scene-page::after {
      position: absolute;
      z-index: 0;
      border: 1px solid rgba(255, 255, 255, 0.28);
      border-radius: 50%;
      content: "";
      pointer-events: none;
    }

    .scene-page::before {
      top: 54px;
      left: -72px;
      width: 176px;
      height: 176px;
    }

    .scene-page::after {
      right: -48px;
      bottom: 124px;
      width: 128px;
      height: 128px;
    }

    .top-safe-area {
      position: relative;
      z-index: 1;
      height: 0;
    }

    .scene-scroll {
      position: relative;
      z-index: 1;
      height: 100%;
      overflow-y: auto;
      overflow-x: hidden;
      padding: 28px 24px
        calc(var(--footer-h) + 24px);
      overscroll-behavior: contain;
      -webkit-overflow-scrolling: touch;
    }

    .scene-inner {
      width: 100%;
      max-width: 360px;
      margin: 0 auto;
    }

    .scene-header {
      position: relative;
      z-index: 2;
      margin-bottom: 21px;
      text-align: center;
    }

    .scene-emoji {
      display: grid;
      place-items: center;
      width: 76px;
      height: 92px;
      margin: 0 auto 16px;
      transform: rotate(-3deg);
    }

    .scene-kicker {
      display: inline-flex;
      align-items: center;
      margin: 0;
      color: var(--purple-deep);
      font-size: 13px;
      line-height: 1.4;
      font-weight: 850;
      letter-spacing: 0.16em;
    }

    .scene-kicker::before,
    .scene-kicker::after {
      width: 18px;
      height: 1px;
      background: rgba(118, 80, 216, 0.35);
      content: "";
    }

    .scene-kicker::before { margin-right: 7px; }
    .scene-kicker::after { margin-left: 7px; }

    .scene-header h1 {
      margin: 6px 0 0;
      color: var(--ink);
      font-size: 31px;
      line-height: 1.28;
      font-weight: 850;
    }

    .screenplay-wrap {
      position: relative;
      padding: 9px 0 0 8px;
    }

    .screenplay-shadow {
      position: absolute;
      z-index: 0;
      top: 19px;
      right: 8px;
      bottom: -8px;
      left: 18px;
      border-radius: 12px 28px 24px 18px;
      background: rgba(114, 82, 178, 0.13);
      transform: rotate(1.5deg);
      pointer-events: none;
    }

    .screenplay {
      position: relative;
      z-index: 1;
      padding: 22px 21px 22px 34px;
      border: 1px solid rgba(113, 90, 151, 0.12);
      border-radius: 12px 28px 24px 18px;
      background:
        linear-gradient(90deg, transparent 0 25px, rgba(214, 112, 121, 0.13) 25px 26px, transparent 26px),
        repeating-linear-gradient(180deg, transparent 0 30px, rgba(102, 113, 137, 0.07) 30px 31px),
        linear-gradient(145deg, #fffefa, var(--paper));
      box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.92),
        0 18px 36px rgba(78, 59, 115, 0.14);
      transform: rotate(-0.45deg);
    }

    .screenplay::after {
      position: absolute;
      top: 0;
      right: 0;
      width: 36px;
      height: 36px;
      border-radius: 0 27px 0 9px;
      background:
        linear-gradient(225deg, rgba(210, 196, 232, 0.58) 0 49%, rgba(255, 255, 255, 0.92) 50% 100%);
      box-shadow: -4px 4px 9px rgba(72, 55, 104, 0.05);
      content: "";
      pointer-events: none;
    }

    .binding-holes {
      position: absolute;
      z-index: 2;
      top: 34px;
      left: -5px;
      display: grid;
      gap: 43px;
      pointer-events: none;
    }

    .binding-holes span {
      position: relative;
      width: 15px;
      height: 15px;
      border: 3px solid rgba(114, 90, 151, 0.26);
      border-radius: 50%;
      background: #d5cefc;
      box-shadow: inset 0 1px 2px rgba(77, 58, 115, 0.16);
    }

    .binding-holes span::before {
      position: absolute;
      top: 3px;
      right: 8px;
      width: 13px;
      height: 3px;
      border-radius: 99px;
      background: rgba(114, 90, 151, 0.38);
      content: "";
    }

    .script-heading {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 17px;
      padding-bottom: 11px;
      border-bottom: 1px dashed rgba(118, 80, 216, 0.22);
    }

    .script-heading strong {
      color: var(--purple-deep);
      font-size: 13px;
      line-height: 1.4;
      font-weight: 900;
      letter-spacing: 0.1em;
    }

    .script-heading span {
      margin-left: 12px;
      color: rgba(41, 39, 53, 0.42);
      font-family: ui-monospace, "SFMono-Regular", Menlo, Monaco, Consolas, monospace;
      font-size: 10px;
      line-height: 1;
      font-weight: 800;
      letter-spacing: 0.08em;
    }

    .scene-content {
      display: grid;
      gap: 13px;
    }

    .scene-paragraph {
      margin: 0;
      color: #363340;
      font-size: 18px;
      line-height: 1.78;
      font-weight: 400;
      overflow-wrap: break-word;
    }

    .scene-paragraph:first-child {
      color: var(--ink);
    }

    .director-cue {
      position: relative;
      margin-top: 20px;
      padding: 17px 17px 17px 19px;
      border: 1px solid rgba(146, 96, 254, 0.14);
      border-radius: 18px;
      background:
        radial-gradient(circle at 92% 12%, rgba(255, 255, 255, 0.8), transparent 34%),
        linear-gradient(145deg, rgba(239, 232, 255, 0.9), rgba(246, 242, 255, 0.76));
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.88);
    }

    .director-cue::before {
      position: absolute;
      top: -10px;
      left: 16px;
      display: grid;
      place-items: center;
      width: 28px;
      height: 28px;
      border: 2px solid var(--paper);
      border-radius: 10px;
      background: var(--purple);
      box-shadow: 0 7px 14px rgba(108, 72, 185, 0.18);
      color: #fff;
      content: "✦";
      font-size: 13px;
      line-height: 1;
      font-weight: 900;
    }

    .director-cue-label {
      display: block;
      margin: 0 0 5px 30px;
      color: var(--purple-deep);
      font-size: 12px;
      line-height: 1.4;
      font-weight: 850;
      letter-spacing: 0.08em;
    }

    .director-cue p {
      margin: 0;
      color: #44375d;
      font-size: 18px;
      line-height: 1.72;
      font-weight: 680;
      overflow-wrap: break-word;
    }

    .scene-footer {
      position: absolute;
      z-index: 5;
      display: flex;
      align-items: center;
      justify-content: center;
      right: 0;
      bottom: 0;
      left: 0;
      padding: 10px 0 calc(10px + var(--safe-bottom));
      background: var(--page-bottom-bg);
    }

    #primaryButton {
      width: calc(100% - 64px);
      max-width: 260px;
      min-height: 60px;
      border: 2px solid transparent;
      border-radius: 40px;
      color: #fff;
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.18), transparent) padding-box,
        linear-gradient(180deg, #9260fe, #9260fe) padding-box,
        linear-gradient(180deg, #f2eef8, #8f5df3) border-box;
      box-shadow: 0 10px 22px rgba(111, 70, 205, 0.14);
      font: inherit;
      font-size: 16px;
      line-height: 1;
      font-weight: 800;
      cursor: pointer;
      transition: transform 150ms ease-out, filter 150ms ease-out;
      -webkit-tap-highlight-color: transparent;
    }

    #primaryButton:active {
      transform: translateY(2px);
      filter: brightness(0.98);
    }

    .scene-error {
      width: calc(100% - 36px);
      max-width: 480px;
      margin: 96px auto 0;
      padding: 22px;
      border-radius: 24px;
      background: rgba(255, 255, 255, 0.78);
      color: #792536;
      text-align: center;
      font-size: 15px;
      line-height: 1.6;
    }

    @media (max-width: 390px) {
      .scene-emoji {
        width: 66px;
        height: 66px;
        border-radius: 22px;
        font-size: 36px;
      }

      .scene-header {
        margin-bottom: 17px;
      }

      .screenplay {
        padding: 20px 17px 20px 30px;
      }

      .scene-content {
        gap: 11px;
      }
    }

    @media (orientation: landscape) and (max-height: 720px) {
      .top-safe-area {
        height: 0;
      }

      .scene-scroll {
        height: 100%;
      }

      .scene-header {
        display: grid;
        grid-template-columns: 56px minmax(0, 1fr);
        grid-template-rows: auto auto;
        column-gap: 13px;
        align-items: center;
        margin-bottom: 13px;
        text-align: left;
      }

      .scene-emoji {
        grid-row: 1 / 3;
        width: 56px;
        height: 56px;
        margin: 0;
        border-radius: 18px;
        font-size: 31px;
      }

      .scene-kicker {
        align-self: end;
        justify-self: start;
        font-size: 11px;
      }

      .scene-kicker::before,
      .scene-kicker::after {
        display: none;
      }

      .scene-header h1 {
        align-self: start;
        margin-top: 1px;
        font-size: 22px;
      }

      .screenplay-wrap {
        padding-top: 4px;
      }

      .screenplay {
        padding-top: 17px;
        padding-bottom: 17px;
      }

      .scene-paragraph,
      .director-cue p {
        font-size: 15px;
        line-height: 1.66;
      }

      .scene-content {
        gap: 9px;
      }

      .director-cue {
        margin-top: 15px;
        padding-top: 15px;
        padding-bottom: 15px;
      }

      .scene-footer {
        padding-top: 10px;
        padding-bottom: calc(10px + var(--safe-bottom));
      }

      #primaryButton {
        min-height: 60px;
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
  <main class="scene-page">
    <div class="top-safe-area" aria-hidden="true"></div>

    <div class="scene-scroll">
      <div class="scene-inner">
        <header class="scene-header">
          <div class="scene-emoji" aria-hidden="true"><img src="https://res.xrunda.com/xruns/static/image/20270724/2.png" width="92" height="92" alt=""></div>
          <p class="scene-kicker">情境开场</p>
          <h1>先看看发生了什么</h1>
        </header>

        <div class="screenplay-wrap">
          <div class="screenplay-shadow" aria-hidden="true"></div>
          <div class="binding-holes" aria-hidden="true">
            <span></span>
            <span></span>
            <span></span>
            <span></span>
          </div>

          <article class="screenplay" aria-labelledby="scriptHeading">
            <header class="script-heading">
              <strong id="scriptHeading">事情是这样的……</strong>
              <span>SCENE 01</span>
            </header>

            <div class="scene-content" id="sceneContent"></div>

            <aside class="director-cue" aria-labelledby="directorCueLabel">
              <span class="director-cue-label" id="directorCueLabel">镜头拉近</span>
              <p id="lessonLead"></p>
            </aside>
          </article>
        </div>
      </div>
    </div>

    <footer class="scene-footer" id="sceneFooter">
      <button id="primaryButton" type="button">继续看看</button>
    </footer>
  </main>

  <script>
    /* ============================================================
       每课只允许替换本变量区中的原文内容与 pageAction。
       变量名、结构、HTML、CSS、固定文案和交互均不得修改。
       ============================================================ */
    const SCENE_INTRO_VARIABLES = Object.freeze({
      sceneParagraphs: Object.freeze([
        "周日下午，社区文化中心有一场动漫配音体验。小安第一次参加，不知道该几点到、要带什么，也不清楚现场录音有什么要求。",
        "她需要一条简短提醒，帮助自己按时做好准备。",
        "前几课学过的动作，现在正好能连起来使用。",
        "先把问题说清楚，再写Prompt。看到结果后不急着采用，要先核查。发现缺口后针对追问，最后由人决定。"
      ]),
      lessonLead: "这节课不重新背定义。我们用一条新的完整过程，看看每一步为什么接在下一步前面。",
      pageAction: "next"
    });
    /* ======================= 变量区结束 ======================= */

    function validateSceneVariables(data) {
      const invalid = [];

      if (!Array.isArray(data.sceneParagraphs) || data.sceneParagraphs.length < 1) {
        invalid.push("sceneParagraphs");
      } else {
        data.sceneParagraphs.forEach((paragraph, index) => {
          if (typeof paragraph !== "string" || !paragraph.trim()) {
            invalid.push(`sceneParagraphs[${index}]`);
          }
        });
      }

      if (typeof data.lessonLead !== "string" || !data.lessonLead.trim()) {
        invalid.push("lessonLead");
      }

      if (!new Set(["next", "complete"]).has(data.pageAction)) {
        invalid.push("pageAction");
      }

      if (invalid.length) {
        throw new Error(`SCENE_FIELD_INVALID: ${invalid.join(", ")}`);
      }
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

    function renderScenePage() {
      const data = SCENE_INTRO_VARIABLES;
      validateSceneVariables(data);

      const content = document.getElementById("sceneContent");
      const fragment = document.createDocumentFragment();

      data.sceneParagraphs.forEach(text => {
        const paragraph = document.createElement("p");
        paragraph.className = "scene-paragraph";
        paragraph.textContent = text;
        fragment.appendChild(paragraph);
      });

      content.textContent = "";
      content.appendChild(fragment);
      document.getElementById("lessonLead").textContent = data.lessonLead;

      const button = document.getElementById("primaryButton");
      const action = data.pageAction === "complete" ? safeComplete : safeNextPage;
      button.textContent = data.pageAction === "complete" ? "完成学习" : "继续看看";
      button.addEventListener("click", action);
    }

    function syncLayoutMetrics() {
      const footer = document.getElementById("sceneFooter");
      const height = Math.ceil(footer.getBoundingClientRect().height || 80);
      document.documentElement.style.setProperty("--footer-h", `${height}px`);
    }

    try {
      renderScenePage();
      syncLayoutMetrics();
      if ("ResizeObserver" in window) {
        new ResizeObserver(syncLayoutMetrics).observe(document.getElementById("sceneFooter"));
      }
      window.addEventListener("resize", syncLayoutMetrics, { passive: true });
      window.addEventListener("orientationchange", syncLayoutMetrics, { passive: true });
    } catch (error) {
      document.body.innerHTML = `<div class="scene-error">场景引入页数据错误：${String(error.message || error)}</div>`;
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
5. 当前 RunS 页面模型链路把本课完整固定模板 OneShot 实际模型输入写入对应页面的 `pages[].prompt`；模型返回的纯完整 HTML 是实际生成页面结果，另层校验与留证。
6. 在 `page_data` 记录合同版本、实际提示词版本、生成模型、Demo SHA-256、变量区外 SHA-256、来源页块和页面动作。

## 6. 阻断条件

以下任一项存在时标记 `SCENE_INTRO_FIXED_ONESHOT_INVALID`，并阻断 `S3G`、`S5.1`、`final_import`、dry-run 和 create：

- 提示词依赖本地路径、Demo、SOP 或历史上下文；
- 没有内嵌完整 HTML/CSS/JavaScript 与真实变量；
- 模型返回局部代码、Markdown、解释或普通文本；
- 变量区外 SHA-256 不匹配；
- 原文丢失、改写、换序、补造或字段类型错误；
- 页面动作与有效页面规划不一致；
- 平台壳层、胶囊、音频、`Powered by RunS`、滚动、底栏、按钮或 SDK 合同漂移。
