# Skills

本目录存放可供 Claude Code 调用的技能（Skill）。

## runs-page-data

把「本地图片 / 音频 / 视频 + 文案」编排成智课端页面 JSON（`pages[]` 导入结构），涵盖素材上传、占位符替换、结构校验、课件任务提交。

### 使用方式

1. 配置鉴权环境变量（与 `scripts/runs-courseware/cli.mjs` 共用）：

   ```bash
   export XRUNS_COURSEWARE_BASE_URL="https://web.dev.xruns.cn"
   export XRUNS_COURSEWARE_TOKEN="智课端登录态里的 access token"
   ```

2. 在对话中直接描述需求（如「把这批图片和文案做成 infographic 页面」），Claude 会自动识别并加载 `runs-page-data` 技能；也可以显式触发：

   ```
   /runs-page-data
   ```

3. 技能会按固定流程执行：**上传素材 → 解析占位符 → 校验 → 提交**，每步产物落盘，任一步失败不进入下一步。

详细规则、命令、组件 schema 见 [runs-page-data/SKILL.md](./runs-page-data/SKILL.md)。
