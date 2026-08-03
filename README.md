# Skills

本目录存放可供 Claude Code 调用的技能（Skill）。

## runs-page-data

把「本地图片 / 音频 / 视频 + 文案」编排成智课端页面 JSON（`pages[]` 导入结构），涵盖素材上传、占位符替换、结构校验、课件任务提交。

### 使用方式

1. 配置一次 `.env`（只需首次）：

   ```bash
   cp skills/runs-page-data/.env.example skills/runs-page-data/.env
   # 打开 https://web.dev.xruns.cn/ 登录，从浏览器复制 access token 填入 XRUNS_COURSEWARE_TOKEN
   node skills/runs-page-data/scripts/pagedata.mjs config   # 查看生效值与来源
   node skills/runs-page-data/scripts/pagedata.mjs ping     # 验证连通性
   ```

   | 变量 | 含义 | 默认值 |
   |------|------|--------|
   | `XRUNS_COURSEWARE_BASE_URL` | 接口网关 | `https://api.dev.xruns.cn/api/` |
   | `XRUNS_COURSEWARE_WEB_URL` | 智课端站点（登录取 token / 拼预览链接） | `https://web.dev.xruns.cn/` |
   | `XRUNS_COURSEWARE_TOKEN` | access token | 空，**必填** |

   优先级：命令行参数 > 环境变量 > `.env` > 默认值。`.env` 已被 `.gitignore` 忽略。

2. 在对话中直接描述需求：

   ```
   /runs-page-data 利用 runs 页面数据 skill，把课程 lesson002 上传到 runs 平台，选择银河轻课模板
   ```

   上传本地素材并按指定模板提交 pages data 的完整 Prompt 示例：

   ```
   利用 runs-page-data skill 把 `测试课程/故事关-打磨版` 中页面实际引用的素材上传 runs 服务器，并根据其中的页面内容和结构，使用「kiki-测试模板」把这节课的 pages data 提交到 runs
   ```

3. 用户按模板名称指定时，技能会查询 RunS 模板列表并按相似度解析业务 `templateId`，允许省略常见后缀、忽略标点或少量错字；找不到或多个候选接近时停止并要求明确选择，不猜测模板 ID。

4. 技能会按固定流程执行：**确定模板 → 编排页面 JSON → 解析占位符并按需上传 → 校验 → 提交**，每步产物落盘，任一步失败不进入下一步。

详细规则、命令、组件 schema 见 [runs-page-data/SKILL.md](./runs-page-data/SKILL.md)。

## ai-general-courseware-production

**AI 通识课网页课件生成**：从教师版 `final.md` 与六项课程信息，受控执行或审计 RunS R36 的 `S1 → S2 → S3 → S4 → S5 → S6`。支持仅执行已解锁的单个阶段，也支持完整串行流程；输入可来自本地或用户授权且固定 commit SHA 的 GitHub 仓库。

- 独立包：`ai-general-courseware-production/`
- 输入格式：[references/input-manifest.md](./ai-general-courseware-production/references/input-manifest.md)
- 生产合同：[references/s1-s6-contract.md](./ai-general-courseware-production/references/s1-s6-contract.md)
- 随包提供 S2—S6 校验器、S6 唯一装配器、OneShot 与无课程数据的 Demo。

该 skill 只生成本地、可审计产物；S6 的最高状态为 `IMPORT_READY_STATIC`，不自动导入、创建、渲染、测试或发布。
