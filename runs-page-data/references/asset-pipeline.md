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
  "baseUrl": "https://web.dev.xruns.cn/api/",
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

## 音频与 TTS 的交互

creator 的 media worker 只在下列条件下调用 TTS：

- `infographic[].tts_text` 非空，且 `tts_url` 为空或 `tts_needs_regen === true`；
- `tts` 组件的 `content.text` 非空且 `content.url` 为空。

所以：

- **想用自带音频** → 把 `public_url` 填进 `tts_url` / `url`，并保证 `tts_needs_regen` 不为 `true`；
- **想让平台生成** → 只写 `tts_text` / `text`，把 url 留空；
- **改了文案要重配音** → 置 `tts_needs_regen: true`。

## 排障

| 现象 | 原因 |
|------|------|
| `object_key is not allowed for current user` | 本地拼了 key，或复用了别的租户的凭证 |
| `public_url does not match object_key` | 改写了凭证返回的 `public_url` |
| `file too large` | 超过 100MB 上限 |
| 上传 403 / 签名错误 | 凭证超过 60 秒才用，重新取一次 |
| 校验报「仍是本地素材引用」 | 漏跑 `pages:resolve`，或 resolve 输出没用于提交 |
| 校验报「文件名在清单中命中多条」 | 不同目录下有同名素材，引用改成完整相对路径 |
