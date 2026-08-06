# 课程开篇页配图增强固定模板 OneShot（V3.5）

状态：`CURRENT_PRODUCTION_ASSET`  
合同版本：`RunS-CourseIntro-VisualEnhanced-OneShot-v1.1`
适用范围：Kimi / GLM 一次性、无外部上下文生成课程开篇页完整 HTML。  
固定 Demo SHA-256：`2928fc40e48bdf83c4fc49df4c5d9138fff0b6875f73d9db2a283dcd1a0dd2ae`  
变量区外 SHA-256：`bcf15b28b8c8fb7f075ccfb9a4b436c3acb4d694737a1ad20ea9ab063bef0975`

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
2. `packageName`、`unitName` 仍须逐字注入变量区并参与字段完整性校验，但不得在图片版页面重复显示；`courseName`、`courseIntroduction` 逐字显示，`knowledgePoints` 保持原顺序。
3. `lessonNumber` 只允许把有效字段中精确格式 `第N课` 确定性转换为正整数 `N`；其他格式阻断。
4. 课程开篇固定为非末页并调用下一页；模型不得推断或改变动作。
5. 页面固定无新增音频、平台壳层、内部页面类型胶囊或 `Powered by RunS`。
6. 开篇只使用 `VISUAL_DATA.visualAsset` 提供的 HTTPS 图片作为顶部主视觉；它位于同一圆角 `course-overview` 容器内，先于课次胶囊和标题。图片已包含课包、单元文字，因此页面不得再次显示 `packageName`、`unitName`，也不再保留旧固定装饰插画或知识点后的独立图片区。页面提示词不得携带 `data:image` 或 Base64，模型不得改写、重编码或省略该地址。

允许变量仅为：`packageName`、`unitName`、`lessonNumber`、`courseName`、`courseIntroduction`、`knowledgePoints`。

## 3. 变量区外哈希算法

1. 以 UTF-8 原始字节读取固定 Demo，不做空格、编码、内部换行或 Unicode 规范化；仅对文件末尾执行单一规范：若 `</html>` 后没有 LF，则补一个 LF，若已有一个 LF 则保持不变。
2. 配图变量开始锚点为 `    const VISUAL_DATA = Object.freeze(`，结束边界为下一行级函数 `    function renderVisualAssets()`；内容变量开始锚点为 `    const COURSE_INTRO_VARIABLES = Object.freeze(`，结束边界为 `    /* ======================= 变量区结束 ======================= */`。
3. 仅把两个变量对象分别规范为 `    const VISUAL_DATA = Object.freeze({});` 与 `    const COURSE_INTRO_VARIABLES = Object.freeze({});`；保留 `renderVisualAssets()`、结束标记及其他全部字节。
4. 模型输出先按第 1 步规范末尾 LF，再按第 3 步规范两个变量对象。
5. 对规范后的完整 Demo 计算 SHA-256，必须得到 `bcf15b28b8c8fb7f075ccfb9a4b436c3acb4d694737a1ad20ea9ab063bef0975`。
6. 模型输出采用同一算法复核；不一致即 `INTRO_TEMPLATE_DRIFT`。

## 4. 完整可复制实例：lesson001 P01

实例来源：`v35_candidate_stage1_batch_20260719/lesson001/02_页面规划/effective_content_full.json` 的 P01。  
页面动作：固定下一页。  
实际提示词版本：`RunS-CourseIntro-VisualEnhanced-OneShot-v1.1-template`。

当前 RunS JSON 页面模型链路中，把下面代码块内部的全部内容原样写入 P01 的 `pages[].prompt`；直接调用 Kimi 或 GLM 时同样提交该完整内容。不要复制外层 Markdown 围栏。

```text
提示词版本号：RunS-CourseIntro-VisualEnhanced-OneShot-v1.1-template

适用页面：lesson001｜P01｜第 1/9 页｜课程开篇页。

配图增强合同：必须把 `VISUAL_DATA.visualAsset` 原样渲染为顶部课程主视觉，不得改写 URL、alt 或 placement。图片是正文主配图，必须位于圆角 `course-overview` 容器顶部，先于课次胶囊和标题；图片已包含课包与单元文字，禁止页面再次显示 `packageName`、`unitName`。学习目标与“本课将解锁”的标题、正文字号、行高和字重复用纯文字开篇 Demo；学习目标标题保持居中，小喇叭缩小后紧邻标题，目标文案左对齐。禁止把图片放到知识点列表后，禁止缩略图、小装饰条、图标尺寸或额外独立卡片。图片使用内容区宽度、自然比例与 `object-fit: contain`。图片本体是唯一可见放大触发器，不增加“查看大图”文案；同页灯箱中的图片必须水平、纵向居中，关闭按钮必须是圆形 ×，水平居中放在图片底部与视口底部之间的纵向中点。支持点击遮罩、`Escape`、两指 1×—4× 缩放及放大后的单指拖动，关闭时复位并恢复背景滚动。禁止外链预览、打开新窗口或新标签页，放大交互不得调用 CreatorReviewSDK。

请输出一个完整、可运行的移动端 HTML 网页。

这是一次性提示词，没有任何外部上下文。不得读取文件、路径、Demo、SOP、历史模板或其他对话。网页所需的课程内容、HTML、CSS、JavaScript、图片元素和 SDK 行为已经全部包含在本提示词中。

最终回复必须且只能包含下方完整 HTML：

- 第一个非空白字符必须属于 <!doctype html>。
- 最后一个标签必须是 </html>。
- 不得输出解释、Markdown 围栏、版本说明、调试信息或提示词正文。
- 不得重排、改写、删减或补写学生可见内容。
- 不得修改 VISUAL_DATA 与 COURSE_INTRO_VARIABLES 之外的任何 HTML、CSS、JavaScript、图片地址、固定文案、模块顺序、按钮或 SDK 行为。
- 不得把已登记 HTTPS 图片地址改成 Base64、`data:image`、其他 URL 或空值。
- 必须保留顶部课程主视觉、课次胶囊、标题、学习目标、知识点列表、长内容滚动、统一底栏和唯一课程动作按钮；不得另行显示课包、单元文字。
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
    /* FIXED_LAYOUT_CONTRACT: 顶部/两侧/底部留白、底栏和主按钮均为固定代码；每课只替换 VISUAL_DATA 与 COURSE_INTRO_VARIABLES。 */

    :root {
      --purple: #9260fe;
      --ink: #242331;
      --safe-bottom: 0px;
      --page-bottom-rgb: 213, 245, 254;
      --page-bottom-bg: rgb(var(--page-bottom-rgb));
      --footer-h: calc(80px + var(--safe-bottom));
      --button-height: 60px;
      --content-max: 480px;
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
      max-width: 480px;
      height: 100%;
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
      padding: 0 0 calc(var(--footer-h) + 24px);
      overscroll-behavior: contain;
      -webkit-overflow-scrolling: touch;
    }

    .intro-inner {
      width: 100%;
      max-width: var(--content-max);
      margin: 0 auto;
    }

    .course-overview {
      margin: 10px 18px 18px;
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.92);
      border-radius: var(--card-radius);
      background: rgba(255, 255, 255, 0.76);
      box-shadow: 0 14px 30px rgba(93, 80, 161, 0.1);
    }

    .intro-hero {
      position: relative;
      width: 100%;
      min-height: 180px;
      overflow: hidden;
      background: #d8d8ff;
    }

    .hero-image-button {
      display: block;
      width: 100%;
      margin: 0;
      padding: 0;
      overflow: hidden;
      border: 0;
      background: transparent;
      cursor: zoom-in;
    }

    .hero-image {
      display: block;
      width: 100%;
      max-width: 100%;
      height: auto;
      object-fit: contain;
    }

    .intro-hero::after {
      position: absolute;
      right: 0;
      bottom: 0;
      left: 0;
      height: 38px;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0), rgba(255, 255, 255, 0.72));
      content: "";
      pointer-events: none;
    }

    .course-info-panel {
      position: relative;
      padding: 38px 20px 24px;
      text-align: center;
    }

    .lesson-chip {
      position: absolute;
      z-index: 3;
      top: -16px;
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

    #courseTitle {
      width: 100%;
      margin: 0;
      color: var(--purple);
      text-align: center;
      font-size: 24px;
      line-height: 1.3;
      font-weight: 800;
      letter-spacing: 0.2px;
      overflow-wrap: break-word;
    }

    .content-card {
      position: relative;
      margin-right: 20px;
      margin-left: 20px;
      padding: 19px 22px 21px;
      border: 1px solid rgba(255, 255, 255, 0.92);
      border-radius: var(--card-radius);
      background: rgba(255, 255, 255, 0.72);
      box-shadow: 0 12px 28px rgba(81, 57, 137, 0.06);
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
      min-height: 134px;
      background: rgba(255, 255, 255, 0.88);
    }

    .learning-goal-heading {
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .core-question-icon {
      position: static;
      width: 28px;
      height: 28px;
      margin: 0 8px 8px 0;
      object-fit: contain;
      flex: none;
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
      text-align: left;
      font-size: 14px;
      line-height: 23px;
      overflow-wrap: break-word;
    }

    .unlock-card {
      margin-top: 18px;
      padding: 19px 17px 17px;
      border-radius: 27px;
      background: rgba(255, 255, 255, 0.62);
    }

    #knowledgeList {
      display: grid;
      gap: 10px;
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
      overflow-wrap: break-word;
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
      width: calc(100% - 64px);
      max-width: 260px;
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
      width: calc(100% - 36px);
      max-width: 480px;
      margin: 80px auto;
      padding: 20px;
      border-radius: 20px;
      background: rgba(255, 255, 255, 0.82);
      text-align: center;
      font-size: 16px;
      line-height: 1.6;
    }

    @media (orientation: landscape) and (max-height: 720px) {
      .content-card {
        padding: 15px;
      }
    }

    @media (prefers-reduced-motion: reduce) {
      * {
        scroll-behavior: auto !important;
        transition: none !important;
      }
    }
  </style>
  <style>
    .visual-lightbox[hidden] { display: none; }
    .visual-lightbox {
      position: fixed;
      z-index: 9999;
      top: 0;
      right: 0;
      bottom: 0;
      left: 0;
      background: rgba(20, 16, 46, 0.9);
    }
    .visual-lightbox-stage {
      position: absolute;
      top: 0;
      right: 0;
      bottom: 0;
      left: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }
    .visual-lightbox-image-wrap {
      width: 92%;
      max-width: 720px;
      max-height: 72%;
      overflow: hidden;
      border-radius: 18px;
      touch-action: none;
    }
    .visual-lightbox-image {
      display: block;
      width: 100%;
      height: auto;
      max-height: 72vh;
      margin: 0 auto;
      object-fit: contain;
      border-radius: 18px;
      transform-origin: center center;
    }
    .visual-lightbox-close {
      position: fixed;
      z-index: 2;
      top: 82%;
      left: 50%;
      width: 46px;
      height: 46px;
      margin: 0;
      padding: 0;
      border: 0;
      border-radius: 50%;
      color: #fff;
      background: rgba(102, 100, 111, 0.94);
      font-size: 31px;
      line-height: 43px;
      font-weight: 800;
      transform: translateX(-50%);
    }
  </style>
</head>
<body>
  <main class="runs-intro-page">
    <div class="top-safe-area" aria-hidden="true"></div>

    <div class="intro-scroll" id="introScroll">
      <div class="intro-inner">
        <section class="course-overview" aria-label="本课开篇信息">
          <section class="intro-hero" id="visualHero" aria-label="课程主视觉">
            <button class="hero-image-button" id="heroImageButton" type="button" aria-label="放大查看课程主视觉">
              <img class="hero-image" id="heroImage" alt="">
            </button>
          </section>
          <div class="course-info-panel">
            <span class="lesson-chip" id="lessonChip"></span>
            <h1 id="courseTitle"></h1>
          </div>
        </section>

        <section class="content-card core-question-panel" aria-labelledby="learningGoalTitle">
          <div class="learning-goal-heading">
            <img class="core-question-icon" src="https://res.xrunda.com/xruns/static/image/course_intro_icon.png" alt="" aria-hidden="true">
            <h3 id="learningGoalTitle">学习目标</h3>
          </div>
          <p id="learningGoal"></p>
        </section>

        <section class="content-card unlock-card" aria-labelledby="unlockTitle">
          <h3 id="unlockTitle">本课将解锁</h3>
          <ul id="knowledgeList"></ul>
        </section>
      </div>
    </div>

    <div class="visual-lightbox" id="visualLightbox" hidden aria-hidden="true">
      <div class="visual-lightbox-stage">
        <div class="visual-lightbox-image-wrap" id="visualZoomArea">
          <img class="visual-lightbox-image" id="visualLightboxImage" alt="">
        </div>
        <button type="button" class="visual-lightbox-close" id="visualLightboxClose" aria-label="关闭大图"><span aria-hidden="true">×</span></button>
      </div>
    </div>

    <footer class="intro-footer" id="introFooter">
      <button id="primaryButton" type="button">开始探索</button>
    </footer>
  </main>

  <script>
    /* ============================================================
       每课只允许替换 VISUAL_DATA 与本内容变量区。变量名、结构、HTML、CSS、交互均不得修改。
       ============================================================ */
    const VISUAL_DATA = Object.freeze({});

    function renderVisualAssets() {
      var hero = document.getElementById("visualHero");
      var trigger = document.getElementById("heroImageButton");
      var image = document.getElementById("heroImage");
      var lightbox = document.getElementById("visualLightbox");
      var lightboxImage = document.getElementById("visualLightboxImage");
      var closeButton = document.getElementById("visualLightboxClose");
      var zoomArea = document.getElementById("visualZoomArea");
      var stage = lightbox.querySelector(".visual-lightbox-stage");
      var assets = VISUAL_DATA.visualAsset ? [VISUAL_DATA.visualAsset] : (VISUAL_DATA.planVisualAssets || []);
      var scale = 1;
      var translateX = 0;
      var translateY = 0;
      var startDistance = 0;
      var startScale = 1;
      var startX = 0;
      var startY = 0;
      var bodyOverflow = "";
      var asset = assets[0];

      function applyVisualTransform() {
        lightboxImage.style.transform = "translate(" + translateX + "px," + translateY + "px) scale(" + scale + ")";
      }

      function resetVisualTransform() {
        scale = 1;
        translateX = 0;
        translateY = 0;
        applyVisualTransform();
      }

      function touchDistance(touches) {
        var dx = touches[0].clientX - touches[1].clientX;
        var dy = touches[0].clientY - touches[1].clientY;
        return Math.sqrt(dx * dx + dy * dy);
      }

      function positionVisualClose() {
        var viewportHeight = window.innerHeight || document.documentElement.clientHeight;
        var imageRect = lightboxImage.getBoundingClientRect();
        var lowerSpace = Math.max(0, viewportHeight - imageRect.bottom);
        closeButton.style.top = Math.round(imageRect.bottom + lowerSpace / 2 - 23) + "px";
      }

      function closeVisualLightbox() {
        resetVisualTransform();
        lightbox.hidden = true;
        lightbox.setAttribute("aria-hidden", "true");
        document.body.style.overflow = bodyOverflow;
      }

      if (!asset) {
        hero.hidden = true;
      } else {
        image.src = asset.url;
        image.alt = asset.alt || "";
        trigger.addEventListener("click", function () {
          lightboxImage.src = asset.url;
          lightboxImage.alt = asset.alt || "";
          resetVisualTransform();
          bodyOverflow = document.body.style.overflow;
          document.body.style.overflow = "hidden";
          lightbox.hidden = false;
          lightbox.setAttribute("aria-hidden", "false");
          window.requestAnimationFrame(positionVisualClose);
        });
      }

      lightboxImage.onload = positionVisualClose;

      zoomArea.addEventListener("touchstart", function (event) {
        if (event.touches.length === 2) {
          startDistance = touchDistance(event.touches);
          startScale = scale;
          event.preventDefault();
        } else if (event.touches.length === 1 && scale > 1) {
          startX = event.touches[0].clientX - translateX;
          startY = event.touches[0].clientY - translateY;
        }
      }, false);
      zoomArea.addEventListener("touchmove", function (event) {
        if (event.touches.length === 2 && startDistance > 0) {
          scale = Math.max(1, Math.min(4, startScale * touchDistance(event.touches) / startDistance));
          if (scale <= 1) {
            translateX = 0;
            translateY = 0;
          }
          applyVisualTransform();
          event.preventDefault();
        } else if (event.touches.length === 1 && scale > 1) {
          translateX = event.touches[0].clientX - startX;
          translateY = event.touches[0].clientY - startY;
          applyVisualTransform();
          event.preventDefault();
        }
      }, false);
      zoomArea.addEventListener("touchend", function () {
        startDistance = 0;
        if (scale <= 1) resetVisualTransform();
      }, false);
      closeButton.addEventListener("click", closeVisualLightbox);
      lightbox.addEventListener("click", function (event) {
        if (event.target === lightbox) closeVisualLightbox();
      });
      stage.addEventListener("click", function (event) {
        if (event.target === stage) closeVisualLightbox();
      });
      document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" || event.keyCode === 27) closeVisualLightbox();
      });
      window.addEventListener("resize", function () {
        if (!lightbox.hidden) positionVisualClose();
      });
    }

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
      return String(value == null ? "" : value).replace(/[&<>"']/g, character => ({
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
      renderVisualAssets();
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
- 含 `data:image` / Base64，或顶部主视觉不是 `VISUAL_DATA.visualAsset` 登记的 HTTPS 资产；
- 模型返回局部代码、Markdown、解释或普通文本；
- 变量区外 SHA-256 不匹配；
- 原文丢失、改写、换序、补造或字段类型错误；
- 页面动作与有效页面规划不一致；
- 平台壳层、胶囊、音频、`Powered by RunS`、滚动、底栏、按钮或 SDK 合同漂移。
