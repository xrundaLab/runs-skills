# 素材流水线

## 三步上传（服务端契约）

| 步骤 | 接口 | 要点 |
|------|------|------|
| 1 | `POST v1/ai/fs/uploads/token` | 传 `filename` / `size` / `mime_type`，返回 `host` / `key` / `policy` / `signature` / `accessid` / `public_url` / `bucket_name`。凭证 60 秒过期 |
| 2 | `POST {host}`（表单直传 OSS） | 表单字段固定为 `Filename` / `key` / `OSSAccessKeyId` / `policy` / `signature` / `success_action_status=200` / `file` |
| 3 | `POST v1/ai/fs/files/commit` | 传回 `object_key` / `bucket_name` / `public_url` / `size` / `mime_type`，返回 `id`（即 `fsFileId`） |

第 3 步的 `object_key` 必须原样回传第 1 步返回的 `key`，`public_url` 必须与之匹配，否则服务端按前缀校验拒绝。

`file_category` 不传时按 `mime_type` 推断：`image/*` `audio/*` `video/*` 取同名分类，PDF / Office / `text/*` 归 `document`，其余 `other`。

## 资产清单

默认文件名 `assets.manifest.json`：

```json
{
  "version": 1,
  "baseUrl": "https://api.dev.xruns.cn/api/",
  "assets": {
    "images/step-1.png": {
      "key": "images/step-1.png",
      "url": "https://res.../creator-files/<tenant>/<uuid>.png",
      "fileId": 1234,
      "objectKey": "creator-files/<tenant>/<uuid>.png",
      "bucketName": "...",
      "mimeType": "image/png",
      "category": "image",
      "size": 20480,
      "sha256": "...",
      "uploadedAt": "2026-07-22T02:00:00.000Z"
    }
  }
}
```

- key 是「相对清单文件所在目录」的 posix 路径，跨平台可移植。
- `sha256` 决定幂等：同 key 同 hash 跳过；内容变了重传并覆盖条目。`--force` 无视清单强制重传。
- 清单只在有实际上传时写盘，`--dry-run` 不写。
- **课件正常流程中的清单只记录页面 JSON 引用到的素材**。默认用 `pages:resolve` 边解析边补齐，清单随引用增长；仅在明确需要提前取得少量素材 URL 时，才用 `assets:upload` 显式列出文件。`assets:upload --dir` 会把整目录的无关文件也写进清单，之后很难分辨哪些真的在用。

## 占位符

页面 JSON 中会被识别为素材引用的字符串形态：

| 形态 | 示例 | 说明 |
|------|------|------|
| `@asset:<路径>` | `@asset:images/cover.png` | **推荐**，显式，不会与正文混淆 |
| 相对路径 | `./assets/a.mp3`、`../shared/b.png` | 便捷写法 |
| `file://` | `file:///Users/me/a.png` | 本地绝对路径 |

其余字符串（含 `https://` 开头的线上地址、正文文案）一律不动。

查表顺序：完整 key → 去掉 `./` 前缀的 key → 文件名。**文件名在清单中命中多条时不猜**，直接报错要求改用完整相对路径。

清单里没有的引用，`pages:resolve` 会依次在「清单目录 / 页面 JSON 目录 / 当前工作目录」下找同名文件并即时上传；加 `--no-upload` 则直接报错。

**上传范围完全由引用决定**：`pages:resolve` 先遍历整份 doc 收集引用去重，再逐个查表/上传，素材目录里没被引用的文件不在它的视野内。想先确认「会传哪些」，用 `--no-upload` 预检；清单缺失的报错项就是正式执行时将即时上传的候选素材，预检失败不会写出文件。

## 音频与 TTS 的交互

creator 的 media worker 只在下列条件下调用 TTS：

- `infographic[].tts_text` 非空，且 `tts_url` 为空或 `tts_needs_regen === true`；
- `tts` 组件的 `content.text` 非空且 `content.url` 为空。

所以：

- **想用自带音频** → 把 `public_url` 填进 `tts_url` / `url`，并保证 `tts_needs_regen` 不为 `true`；
- **想让平台生成** → 只写 `tts_text` / `text`，把 url 留空；
- **改了文案要重配音** → 置 `tts_needs_regen: true`。

## 课件任务提交

用户提供模板名称时，先通过
`GET v1/business/creator/template/list?pageNum=<n>&pageSize=<n>&templateModuleType=`
遍历当前用户可用模板。脚本会忽略大小写、空格和标点，允许省略“模板 / 课件 / 课程”
等后缀，并以编辑距离容忍少量错字，再按相似度解析业务 `templateId`。名称找不到或多个
候选匹配度接近时停止，不进入写操作。

页面数据校验通过后，写操作固定分为两步，并全程复用上述 `templateId`：

1. `POST v1/business/creator/courseware/create-with-template`，传入 `title` 与 `templateId`，取得 `coursewareId`。
2. `POST v1/creator/courseware/flow/task`，在原有 `templateId`、`structuredJson` 或 `fsFileId` 基础上携带该 `coursewareId`。

creator 根据 `coursewareId` 重新读取当前用户可访问的课程详情并验证模板，客户端不传 `category`、`prompt` 或 `parsePrompt`。这样课程在 flow worker 排队前已经进入 generation-history，orchestrator 重试也复用同一课程。

## 排障

| 现象 | 原因 |
|------|------|
| `object_key is not allowed for current user` | 本地拼了 key，或复用了别的租户的凭证 |
| `public_url does not match object_key` | 改写了凭证返回的 `public_url` |
| `file too large` | 超过 100MB 上限 |
| 上传 403 / 签名错误 | 凭证超过 60 秒才用，重新取一次 |
| 校验报「仍是本地素材引用」 | 漏跑 `pages:resolve`，或 resolve 输出没用于提交 |
| 校验报「文件名在清单中命中多条」 | 不同目录下有同名素材，引用改成完整相对路径 |
