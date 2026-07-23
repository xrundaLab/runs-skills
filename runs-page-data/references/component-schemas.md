# 页面 JSON 与组件结构速查

完整字段说明以 [doc/feat/制课端组件工具schema.md](../../../../doc/feat/制课端组件工具schema.md) 为准，本页只保留编排时最常查的部分。
运行时权威定义在 `frontend/app/components/page-runtime/widgets/*/schema.ts` 与模板组件接口返回的 `dataStructure`。

## 顶层结构

```json
{
  "title": "课程标题",
  "description": "课程描述（可选）",
  "pages": [
    {
      "tag": "课程导入",
      "title": "页面标题",
      "summary": "页面摘要，供 AI 上下文使用",
      "prompt": "无组件页必填：给 AI 生成该页 HTML 的提示词",
      "components": [
        { "type": "tts", "content": {}, "componentId": "tts_lesson001_p02" }
      ]
    }
  ]
}
```

| 字段 | 必填 | 说明 |
|------|------|------|
| `title` | 是 | 课程标题 |
| `pages` | 是 | 非空数组 |
| `pages[].title` | 是 | 页面标题 |
| `pages[].tag` | 建议 | 分类标签，如「课程导入」「知识讲解」「小练习」「课程总结」 |
| `pages[].summary` | 否 | 页面摘要 |
| `pages[].prompt` | 无组件页必填 | 该页 HTML 生成提示词 |
| `pages[].components` | 否 | 无组件时为 `[]` |
| `components[].componentId` | 否 | 建议 `{type}_{lessonId}_{pageIndex}`，全文档唯一 |

## 组件级别

**page 级（独占整页，同页不得再有任何组件）**

`course_intro` · `course_task` · `course_summary` · `image_save` · `infographic` · `immersive_explanation` · `select_question` · `galaxy_select_question` · `matching_question` · `ordering_question` · `categorization_question`

**block 级（可同页组合）**

`text` · `rich_text` · `image` · `video` · `avatar` · `tts` · `podcast` · `word_card` · `learning_report`

> 权威来源是模板组件接口的 `compositionMode`；用 `pages:validate --template-id` 可直接按目标模板核对。

## 常用组件 content

### text / rich_text（block）

```json
{ "type": "text", "content": "纯文本" }
{ "type": "rich_text", "content": "<p>HTML <strong>片段</strong></p>" }
```

### image（block）

```json
{ "type": "image", "content": [{ "url": "https://...", "desc": "图片描述" }] }
```

### tts（block）

```json
{
  "type": "tts",
  "content": {
    "text": "口播稿（必填）",
    "url": "https://.../audio.mp3",
    "voice": "S_HJjtPNs22",
    "rate": "default",
    "volume": "100",
    "is_follow": false,
    "subtitle_url": "https://.../subtitle.srt"
  }
}
```

`url` 填了就用自带音频；留空且 `text` 非空才会触发平台 TTS。

### infographic（page）

```json
{
  "type": "infographic",
  "content": [
    {
      "img_url": "https://.../step-1.png",
      "img_desc": "图片描述",
      "tts_text": "配音文本",
      "tts_url": "https://.../step-1.mp3",
      "subtitle_url": "https://.../step-1.srt",
      "tts_needs_regen": false,
      "voice": "S_HJjtPNs22",
      "is_follow": true
    }
  ]
}
```

### immersive_explanation（page）

卡片列表，`card_type` 为 `text` 时 `content` 传字符串，为 `grid` 时传 `[{icon, text}]`。批量配音只读 `tts_text`。

```json
{
  "type": "immersive_explanation",
  "content": [
    { "stage": "观察", "card_type": "text", "icon": "🎯", "title": "先看目标", "content": "讲解正文", "tts_text": "解说文案" },
    { "stage": "拆解", "card_type": "grid", "title": "三个关键点", "content": [{ "icon": "1️⃣", "text": "第一点" }] }
  ]
}
```

### image_save（page）

```json
{ "type": "image_save", "content": { "img_url": "https://...", "title": "保存本课知识锦囊", "buttonText": "保存图片", "description": "课后可回看" } }
```

### course_intro / course_task / course_summary（page）

```json
{ "type": "course_intro", "content": { "packageFigureUrl": "https://...", "packageName": "", "unitName": "", "courseNumber": "01", "courseName": "", "coreQuestion": "", "body": "" } }
{ "type": "course_task", "content": { "title": "", "subtitle": "", "steps": ["步骤一", "步骤二"] } }
{ "type": "course_summary", "content": { "title": "", "subtitle": "", "body": "" } }
```

### 题目类（均为 page 级）

```json
// select_question：题干与选项支持音频
{ "type": "select_question", "content": { "title": "", "questions": [{ "question": "题干", "questionAudio": "", "options": [{ "text": "A", "audio": "" }], "answerIndex": 0, "answer": "A" }] } }

// galaxy_select_question：支持多选与解析
{ "type": "galaxy_select_question", "content": { "questions": [{ "question": "题干", "options": [{ "text": "A" }], "isMultiple": false, "answerIndex": [0], "answer": ["A"], "explanation": "" }], "correctButtonText": "继续" } }

// matching_question
{ "type": "matching_question", "content": { "questions": [{ "id": "q1", "stem": "题干", "pairs": [{ "id": "p1", "left": "苹果", "right": "Apple" }], "explanation": "" }] } }

// categorization_question
{ "type": "categorization_question", "content": { "questions": [{ "id": "q1", "stem": "题干", "groups": [{ "name": "动物", "desc": "", "options": ["猫", "狗"] }], "explanation": "" }] } }

// ordering_question：items 按正确顺序给出
{ "type": "ordering_question", "content": { "questions": [{ "id": "q1", "stem": "题干", "items": [{ "id": "i1", "name": "步骤一", "desc": "" }], "explanation": "" }] } }
```

选项列表 `options` 同时接受纯字符串数组和对象数组两种形态。

## 枚举

**voice**（`tts` / `infographic` / `immersive_explanation` 共用）

`S_HJjtPNs22`· `zh-CN-XiaoxiaoNeural` · `zh-CN-XiaoxiaoMultilingualNeural` · `zh-CN-YunyeNeural` · `zh-CN-YunyangNeural` · `zh-CN-YunzeNeural` · `zh-CN-YunfanMultilingualNeural` · `zh-CN-YunjianNeural` · `en-US-EmmaMultilingualNeural` · `en-US-AndrewMultilingualNeural` `zh_female_yingyujiaoxue_uranus_bigtts`

**rate**：`default`（默认）· `x-slow` · `slow` · `medium` · `fast` · `x-fast`

**volume**：`100`（默认）· `75` · `50` · `25`

**virtualman_key**（`avatar`）：`D3-NoTrain-3213b214-3dc3-48e7-927f-8`（默认，李晶晶）等六个，详见原文档。
