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

3. 技能会按固定流程执行：**上传素材 → 解析占位符 → 校验 → 提交**，每步产物落盘，任一步失败不进入下一步。

详细规则、命令、组件 schema 见 [runs-page-data/SKILL.md](./runs-page-data/SKILL.md)。
