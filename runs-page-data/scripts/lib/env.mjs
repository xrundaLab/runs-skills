/**
 * .env 加载：让 token / 网关地址 / 预览站点只配一次，不必每次在对话里重复说明。
 *
 * 约定：
 * - 只认 XRUNS_ 前缀的键，避免把项目 .env 里的无关密钥灌进 process.env。
 * - 真实环境变量优先级最高，先找到的文件优先级高于后找到的，已有值不覆盖。
 * - 解析结果缓存在模块级，一次进程只读一次盘。
 */
import { readFileSync, existsSync } from 'node:fs';
import { dirname, join, resolve as resolvePath } from 'node:path';
import { fileURLToPath } from 'node:url';

const ENV_PREFIX = 'XRUNS_';
const ENV_FILENAME = '.env';

/** scripts/lib/env.mjs → skills/runs-page-data */
const SKILL_DIR = resolvePath(dirname(fileURLToPath(import.meta.url)), '../..');

let cached = null;

/** 仅供测试重置模块级缓存。 */
export function resetEnvCache() {
  cached = null;
}

/**
 * 按优先级列出候选 .env 路径：显式指定 > 当前工作目录 > 技能目录 > 技能所在仓库根。
 * 仓库根按 skills/<name>/ 的层级上推两级，技能被整体拷贝到别处时该路径不存在，自动忽略。
 */
export function envFileCandidates({ cwd = process.cwd(), skillDir = SKILL_DIR, explicit } = {}) {
  const paths = [];
  const explicitPath = explicit || process.env.XRUNS_ENV_FILE;
  if (explicitPath) paths.push(resolvePath(explicitPath));
  paths.push(join(cwd, ENV_FILENAME));
  paths.push(join(skillDir, ENV_FILENAME));
  paths.push(join(resolvePath(skillDir, '../..'), ENV_FILENAME));
  return [...new Set(paths)];
}

/** 支持 `export KEY=VALUE`、单/双引号、行尾注释、`\n` 转义。 */
export function parseEnvFile(text) {
  const result = {};
  for (const rawLine of String(text).split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;

    const withoutExport = line.startsWith('export ') ? line.slice(7).trim() : line;
    const eq = withoutExport.indexOf('=');
    if (eq <= 0) continue;

    const key = withoutExport.slice(0, eq).trim();
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key)) continue;

    let value = withoutExport.slice(eq + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"') && value.length > 1)
      || (value.startsWith("'") && value.endsWith("'") && value.length > 1)) {
      const quote = value[0];
      value = value.slice(1, -1);
      if (quote === '"') value = value.replace(/\\n/g, '\n').replace(/\\"/g, '"');
    } else {
      // 未加引号时 # 之后视为注释
      const hash = value.indexOf(' #');
      if (hash > -1) value = value.slice(0, hash).trim();
    }
    result[key] = value;
  }
  return result;
}

/**
 * 读取候选 .env 并写入 process.env（不覆盖已有值），返回来源信息供 config / ping 展示。
 * @returns {{ files: string[], sources: Record<string, string> }} sources 记录每个键最终来自哪里
 */
export function loadEnvFiles(options = {}) {
  if (cached && !options.force) return cached;

  const files = [];
  const sources = {};
  const preexisting = new Set(
    Object.keys(process.env).filter((key) => key.startsWith(ENV_PREFIX) && process.env[key] !== ''),
  );
  for (const key of preexisting) sources[key] = 'environment';

  for (const path of envFileCandidates(options)) {
    if (!existsSync(path)) continue;
    let parsed;
    try {
      parsed = parseEnvFile(readFileSync(path, 'utf8'));
    } catch {
      continue;
    }
    files.push(path);
    for (const [key, value] of Object.entries(parsed)) {
      if (!key.startsWith(ENV_PREFIX)) continue;
      if (sources[key]) continue;
      if (value === '') continue;
      process.env[key] = value;
      sources[key] = path;
    }
  }

  cached = { files, sources };
  return cached;
}
