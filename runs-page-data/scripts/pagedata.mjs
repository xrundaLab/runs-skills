#!/usr/bin/env node
/**
 * RunS 页面数据 CLI —— 把本地图片 / 音频上传到 RunS，并编排、校验、提交页面 JSON。
 *
 * 命令：
 *   assets:upload   批量上传素材，产出可复用的资产清单
 *   pages:resolve   把页面 JSON 里的本地引用替换成 public_url（缺失的顺手上传）
 *   pages:validate  校验页面 JSON（内置规格 + 可选模板组件白名单与示例比对）
 *   pages:submit    提交课件任务（structuredJson 内联 / 上传 JSON 直接解析）
 */
import { readFile, writeFile, readdir, stat } from 'node:fs/promises';
import { dirname, extname, join, resolve as resolvePath } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  DEFAULT_BASE_URL,
  DEFAULT_WEB_URL,
  buildCoursewareUrl,
  createCoursewareWithTemplate,
  getFlowTask,
  getRuntimeConfig,
  guessMimeType,
  fetchComponentDetail,
  fetchTemplateComponents,
  listFlowTasks,
  maskToken,
  missingTokenMessage,
  startFlowTask,
  uploadLocalFile,
} from './lib/client.mjs';
import {
  createManifest,
  findAsset,
  hashBytes,
  isUploaded,
  readManifest,
  summarizeManifest,
  toManifestKey,
  upsertAsset,
  writeManifest,
} from './lib/manifest.mjs';
import { applyAssetResolutions, collectAssetRefs, findResidualLocalRefs } from './lib/resolve.mjs';
import { formatReport, validatePageData } from './lib/validate.mjs';
import { KNOWN_COMPONENT_TYPES, PAGE_LEVEL_TYPES } from './lib/component-spec.mjs';

const COMMANDS = new Set([
  'config', 'ping', 'assets:upload', 'pages:resolve', 'pages:validate', 'pages:submit', 'help',
]);
const BOOLEAN_FLAGS = new Set([
  'allow-unknown', 'as-file', 'dry-run', 'force', 'help', 'no-upload', 'strict', 'watch', 'yes',
]);
const DEFAULT_MANIFEST = 'assets.manifest.json';
const DEFAULT_CONCURRENCY = 4;
const WATCH_INTERVAL_MS = 5000;
const WATCH_TIMEOUT_MS = 30 * 60 * 1000;

export const TERMINAL_TASK_STATUSES = new Set([
  'COMPLETED', 'COMPLETED_WITH_ERRORS', 'FAILED', 'INTERRUPTED',
]);

/** 默认允许上传的素材后缀；--ext 可覆盖。 */
export const MEDIA_EXTENSIONS = new Set([
  '.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.svg',
  '.mp3', '.wav', '.m4a', '.aac', '.ogg', '.flac',
  '.mp4', '.mov', '.m4v', '.webm',
  '.srt', '.vtt',
]);

export function parseArgv(argv) {
  const args = { _: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith('--')) {
      args._.push(token);
      continue;
    }
    const eq = token.indexOf('=');
    if (eq > -1) {
      args[token.slice(2, eq)] = token.slice(eq + 1);
      continue;
    }
    const key = token.slice(2);
    if (BOOLEAN_FLAGS.has(key)) {
      args[key] = true;
      continue;
    }
    const next = argv[i + 1];
    if (!next || next.startsWith('--')) {
      args[key] = true;
      continue;
    }
    args[key] = next;
    i += 1;
  }
  return args;
}

export function createBatchNo(now = Date.now) {
  return `batch-${now()}`;
}

export function parseAssetsUploadArgs(args) {
  const files = args._.slice(1);
  if (files.length === 0 && !args.dir) {
    throw new Error('至少提供一个素材路径，或用 --dir 指定目录');
  }
  const extensions = args.ext
    ? new Set(String(args.ext).split(',').map((item) => {
      const trimmed = item.trim().toLowerCase();
      return trimmed.startsWith('.') ? trimmed : `.${trimmed}`;
    }))
    : MEDIA_EXTENSIONS;
  const concurrency = Number(args.concurrency || DEFAULT_CONCURRENCY);
  if (!Number.isInteger(concurrency) || concurrency < 1) {
    throw new Error('--concurrency 必须是正整数');
  }
  return {
    files,
    dir: args.dir ? String(args.dir) : undefined,
    // 字段名刻意区别于 uploadOne 参数里的 manifest 对象，避免 spread 时被路径字符串覆盖
    manifestPath: String(args.manifest || DEFAULT_MANIFEST),
    folderId: args['folder-id'] ? String(args['folder-id']) : undefined,
    extensions,
    concurrency,
    force: Boolean(args.force),
    dryRun: Boolean(args['dry-run']),
  };
}

export function parseSubmitArgs(args) {
  const file = args._[1];
  if (!file) throw new Error('缺少页面 JSON 路径');
  // parseArgv 对「有 flag 无取值」的写法会置为 true，这里必须要求真实字符串
  const templateId = typeof args['template-id'] === 'string' ? args['template-id'].trim() : '';
  if (!templateId) throw new Error('缺少 --template-id');
  return {
    file: String(file),
    templateId,
    batchNo: args['batch-no'] ? String(args['batch-no']) : undefined,
    asFile: Boolean(args['as-file']),
    watch: Boolean(args.watch),
    yes: Boolean(args.yes),
    force: Boolean(args.force),
    report: args.report ? String(args.report) : undefined,
  };
}

/**
 * 组装提交用的 structuredJson。
 * 只保留 creator StructuredJsonSchema 关心的字段形态：pages 必须非空，
 * page 内 tag/title/summary/components 补默认值，其余字段原样透传（服务端 passthrough）。
 */
export function buildStructuredJson(doc) {
  return {
    ...doc,
    title: doc.title ?? '',
    pages: (doc.pages || []).map((page) => ({
      ...page,
      tag: page.tag ?? '',
      title: page.title ?? '',
      summary: page.summary ?? '',
      components: Array.isArray(page.components) ? page.components : [],
    })),
  };
}

export function buildStructuredTaskPayload({ templateId, coursewareId, structuredJson, batchNo }) {
  if (!coursewareId) throw new Error('创建 flow task 前必须先创建课程并提供 coursewareId');
  return { templateId, coursewareId, structuredJson, ...(batchNo ? { batchNo } : {}) };
}

export function buildDirectTaskPayload({ templateId, coursewareId, fsFileId, batchNo }) {
  if (!coursewareId) throw new Error('创建 flow task 前必须先创建课程并提供 coursewareId');
  return { templateId, coursewareId, fsFileId, direct: true, ...(batchNo ? { batchNo } : {}) };
}

export function summarizePageData(doc) {
  const pages = Array.isArray(doc?.pages) ? doc.pages : [];
  const componentCounts = {};
  let componentTotal = 0;
  for (const page of pages) {
    for (const component of Array.isArray(page?.components) ? page.components : []) {
      const type = component?.type || 'unknown';
      componentCounts[type] = (componentCounts[type] || 0) + 1;
      componentTotal += 1;
    }
  }
  return { title: doc?.title || '', pageCount: pages.length, componentTotal, componentCounts };
}

/** 极简并发闸门，避免为几十个素材引入依赖。 */
function createLimiter(concurrency) {
  let active = 0;
  const queue = [];
  const next = () => {
    if (active >= concurrency || queue.length === 0) return;
    active += 1;
    const { task, resolve: done, reject } = queue.shift();
    task().then(done, reject).finally(() => {
      active -= 1;
      next();
    });
  };
  return (task) => new Promise((done, reject) => {
    queue.push({ task, resolve: done, reject });
    next();
  });
}

async function collectFilesFromDir(dir, extensions) {
  const entries = await readdir(dir, { withFileTypes: true });
  const found = [];
  for (const entry of entries) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      found.push(...await collectFilesFromDir(full, extensions));
    } else if (extensions.has(extname(entry.name).toLowerCase())) {
      found.push(full);
    }
  }
  return found.sort();
}

async function fileExists(path) {
  try {
    const info = await stat(path);
    return info.isFile();
  } catch {
    return false;
  }
}

/** 素材引用可能相对清单目录、页面 JSON 目录或 cwd，依次尝试。 */
async function locateAssetFile(ref, searchDirs) {
  if (ref.startsWith('/')) return (await fileExists(ref)) ? ref : null;
  for (const dir of searchDirs) {
    const candidate = resolvePath(dir, ref);
    if (await fileExists(candidate)) return candidate;
  }
  return null;
}

async function loadManifest(manifestPath, config) {
  const existing = await readManifest(manifestPath);
  return existing || createManifest({ baseUrl: config.baseUrl });
}

async function uploadOne(filePath, { manifest, manifestPath, config, folderId, force, dryRun }) {
  const key = toManifestKey(manifestPath, filePath);
  const bytes = await readFile(filePath);
  const sha256 = hashBytes(bytes);

  if (!force && isUploaded(manifest, key, sha256)) {
    return { key, file: filePath, skipped: true, entry: manifest.assets[key] };
  }
  if (dryRun) {
    return {
      key,
      file: filePath,
      dryRun: true,
      entry: { url: '', sha256, size: bytes.byteLength, mimeType: guessMimeType(filePath) },
    };
  }

  const uploaded = await uploadLocalFile(filePath, config, { folderId });
  return {
    key,
    file: filePath,
    entry: {
      url: uploaded.publicUrl,
      fileId: uploaded.fileId,
      objectKey: uploaded.objectKey,
      bucketName: uploaded.bucketName,
      mimeType: uploaded.mimeType,
      category: uploaded.category,
      size: uploaded.size,
      sha256,
      uploadedAt: new Date().toISOString(),
    },
  };
}

async function handleAssetsUpload(args) {
  const options = parseAssetsUploadArgs(args);
  const config = getRuntimeConfig(args);
  const manifestPath = resolvePath(options.manifestPath);

  const explicit = options.files.map((file) => resolvePath(file));
  const scanned = options.dir ? await collectFilesFromDir(resolvePath(options.dir), options.extensions) : [];
  const targets = [...new Set([...explicit, ...scanned])];
  if (targets.length === 0) throw new Error('没有匹配到任何素材文件');

  let manifest = await loadManifest(manifestPath, config);
  const limit = createLimiter(options.concurrency);
  const results = await Promise.all(targets.map((file) => limit(async () => {
    try {
      return await uploadOne(file, {
        manifest,
        manifestPath,
        config,
        folderId: options.folderId,
        force: options.force,
        dryRun: options.dryRun,
      });
    } catch (err) {
      return { file, error: err instanceof Error ? err.message : String(err) };
    }
  })));

  for (const result of results) {
    if (result.error || result.skipped || result.dryRun) continue;
    manifest = upsertAsset(manifest, result.key, result.entry);
  }

  const uploaded = results.filter((item) => !item.error && !item.skipped && !item.dryRun);
  const skipped = results.filter((item) => item.skipped);
  const planned = results.filter((item) => item.dryRun);
  const failed = results.filter((item) => item.error);

  if (!options.dryRun && uploaded.length > 0) {
    await writeManifest(manifestPath, manifest);
  }

  console.log(`资产清单：${manifestPath}`);
  console.log(
    `总计 ${targets.length}，上传 ${uploaded.length}，待上传 ${planned.length}，跳过（未变更）${skipped.length}，失败 ${failed.length}`,
  );
  for (const item of uploaded) console.log(`  ✓ ${item.key} → ${item.entry.url}`);
  for (const item of planned) console.log(`  · ${item.key}（${item.entry.size} 字节，${item.entry.mimeType}）`);
  for (const item of skipped) console.log(`  = ${item.key}（已存在）`);
  for (const item of failed) console.log(`  ✗ ${item.file}：${item.error}`);
  if (options.dryRun) console.log('（--dry-run：未实际上传，也未写入清单）');
  console.log(JSON.stringify(summarizeManifest(manifest), null, 2));

  if (failed.length > 0) process.exitCode = 1;
}

/** 解析页面 JSON 中的素材引用；缺失条目默认就地上传补齐。返回新 doc 与统计。 */
async function resolveDocAssets(doc, { jsonPath, manifestPath, config, folderId, allowUpload }) {
  let manifest = await loadManifest(manifestPath, config);
  const refs = collectAssetRefs(doc);
  const uniqueRefs = [...new Set(refs.map((item) => item.ref))];
  const searchDirs = [dirname(manifestPath), dirname(resolvePath(jsonPath)), process.cwd()];

  const urlByRef = new Map();
  const missing = [];
  const ambiguous = [];
  const uploadedNow = [];

  for (const ref of uniqueRefs) {
    const hit = findAsset(manifest, ref);
    if (hit.ambiguous) {
      ambiguous.push({ ref, candidates: hit.candidates });
      continue;
    }
    if (hit.entry?.url) {
      urlByRef.set(ref, hit.entry.url);
      continue;
    }

    const localPath = await locateAssetFile(ref, searchDirs);
    if (!localPath) {
      missing.push({ ref, reason: '清单里没有该条目，本地也找不到对应文件' });
      continue;
    }
    if (!allowUpload) {
      missing.push({ ref, reason: '清单里没有该条目（--no-upload 已禁用即时上传）' });
      continue;
    }

    const result = await uploadOne(localPath, { manifest, manifestPath, config, folderId, force: false });
    manifest = upsertAsset(manifest, result.key, result.entry);
    urlByRef.set(ref, result.entry.url);
    uploadedNow.push({ ref, key: result.key, url: result.entry.url });
  }

  const { value, state } = applyAssetResolutions(doc, (ref) => urlByRef.get(ref));
  if (uploadedNow.length > 0) await writeManifest(manifestPath, manifest);

  return { doc: value, replaced: state.replaced, unresolved: state.unresolved, missing, ambiguous, uploadedNow };
}

async function readJsonFile(path) {
  const raw = await readFile(path, 'utf8');
  try {
    return JSON.parse(raw);
  } catch (err) {
    throw new Error(`解析 JSON 失败：${path} —— ${err instanceof Error ? err.message : String(err)}`);
  }
}

async function handlePagesResolve(args) {
  const file = args._[1];
  if (!file) throw new Error('缺少页面 JSON 路径');

  const config = getRuntimeConfig(args);
  const jsonPath = resolvePath(String(file));
  const manifestPath = resolvePath(String(args.manifest || DEFAULT_MANIFEST));
  const outPath = resolvePath(String(args.out || file));
  const doc = await readJsonFile(jsonPath);

  const result = await resolveDocAssets(doc, {
    jsonPath,
    manifestPath,
    config,
    folderId: args['folder-id'] ? String(args['folder-id']) : undefined,
    allowUpload: !args['no-upload'],
  });

  console.log(`替换 ${result.replaced.length} 处引用，其中即时上传 ${result.uploadedNow.length} 个素材`);
  for (const item of result.replaced) console.log(`  ✓ ${item.path} ← ${item.ref}`);
  for (const item of result.ambiguous) {
    console.log(`  ✗ ${item.ref}：文件名在清单中命中多条（${item.candidates.join(', ')}），请改用完整相对路径`);
  }
  for (const item of result.missing) console.log(`  ✗ ${item.ref}：${item.reason}`);

  if (result.missing.length > 0 || result.ambiguous.length > 0) {
    process.exitCode = 1;
    console.log('存在未解析引用，未写出文件');
    return;
  }

  await writeFile(outPath, `${JSON.stringify(result.doc, null, 2)}\n`, 'utf8');
  console.log(`已写出：${outPath}`);
}

/** dataStructure 是 JSON 转义字符串，偶有双重编码，解析两次兜底。 */
function parseDataStructure(raw) {
  if (!raw || typeof raw !== 'string') return undefined;
  try {
    const first = JSON.parse(raw);
    return typeof first === 'string' ? JSON.parse(first) : first;
  } catch {
    return undefined;
  }
}

async function loadTemplateContext(templateId, doc, config) {
  const templateComponents = await fetchTemplateComponents(templateId, config);
  const usedTypes = new Set();
  for (const page of Array.isArray(doc?.pages) ? doc.pages : []) {
    for (const component of Array.isArray(page?.components) ? page.components : []) {
      if (typeof component?.type === 'string') usedTypes.add(component.type);
    }
  }

  const componentExamples = {};
  for (const item of templateComponents) {
    if (!usedTypes.has(item.componentType)) continue;
    try {
      const detail = await fetchComponentDetail(item.componentKeyId, config);
      const example = parseDataStructure(detail?.dataStructure);
      if (example !== undefined) componentExamples[item.componentType] = example;
    } catch (err) {
      console.log(`  ! 获取组件示例失败（${item.componentType}）：${err instanceof Error ? err.message : String(err)}`);
    }
  }
  return { templateComponents, componentExamples };
}

async function runValidation(doc, args) {
  const options = { allowUnknownTypes: Boolean(args['allow-unknown']) };
  const templateId = typeof args['template-id'] === 'string' ? args['template-id'].trim() : '';
  if (templateId) {
    const config = getRuntimeConfig(args);
    Object.assign(options, await loadTemplateContext(templateId, doc, config));
  }

  const report = validatePageData(doc, options);
  const residual = findResidualLocalRefs(doc);
  for (const item of residual) {
    report.errors.push({ path: item.path, message: `仍是本地素材引用 ${item.raw}，请先执行 pages:resolve` });
  }
  return report;
}

async function handlePagesValidate(args) {
  const file = args._[1];
  if (!file) throw new Error('缺少页面 JSON 路径');
  const doc = await readJsonFile(resolvePath(String(file)));
  const report = await runValidation(doc, args);

  console.log(JSON.stringify(summarizePageData(doc), null, 2));
  const formatted = formatReport(report);
  if (formatted) console.log(formatted);

  if (report.errors.length > 0) {
    console.log(`校验未通过：${report.errors.length} 个错误，${report.warnings.length} 个告警`);
    process.exitCode = 1;
    return;
  }
  if (args.strict && report.warnings.length > 0) {
    console.log(`--strict：${report.warnings.length} 个告警被视为失败`);
    process.exitCode = 1;
    return;
  }
  console.log(`校验通过（${report.warnings.length} 个告警）`);
}

const sleep = (ms) => new Promise((done) => { setTimeout(done, ms); });

async function watchTask(taskId, config, { intervalMs = WATCH_INTERVAL_MS, timeoutMs = WATCH_TIMEOUT_MS } = {}) {
  const deadline = Date.now() + timeoutMs;
  let last = null;
  while (Date.now() < deadline) {
    last = await getFlowTask(taskId, config);
    const status = last?.status || 'UNKNOWN';
    console.log(`  [${new Date().toISOString()}] ${status}${last?.stage ? ` stage=${last.stage}` : ''}`);
    if (TERMINAL_TASK_STATUSES.has(status)) return last;
    await sleep(intervalMs);
  }
  console.log(`  ! 追踪超时（${Math.round(timeoutMs / 60000)} 分钟），任务仍在进行`);
  return last;
}

function toCsv(rows) {
  if (rows.length === 0) return '';
  const headers = Object.keys(rows[0]);
  const escape = (value) => {
    const text = value === undefined || value === null ? '' : String(value);
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  return [headers.join(','), ...rows.map((row) => headers.map((h) => escape(row[h])).join(','))].join('\n');
}

async function writeReport(reportPath, rows) {
  const content = extname(reportPath).toLowerCase() === '.json'
    ? `${JSON.stringify(rows, null, 2)}\n`
    : `${toCsv(rows)}\n`;
  await writeFile(reportPath, content, 'utf8');
}

async function handlePagesSubmit(args) {
  const options = parseSubmitArgs(args);
  const config = getRuntimeConfig(args);
  const jsonPath = resolvePath(options.file);
  const doc = await readJsonFile(jsonPath);

  const report = await runValidation(doc, args);
  const formatted = formatReport(report);
  if (formatted) console.log(formatted);

  console.log(JSON.stringify(summarizePageData(doc), null, 2));

  if (report.errors.length > 0 && !options.force) {
    console.log(`校验未通过（${report.errors.length} 个错误），已终止提交。确认无误可加 --force 跳过。`);
    process.exitCode = 1;
    return;
  }

  const batchNo = options.batchNo || createBatchNo();
  const mode = options.asFile ? '上传 JSON + direct 直接解析' : 'structuredJson 内联';
  console.log(`提交模式：${mode}｜模板：${options.templateId}｜批次：${batchNo}`);

  if (!options.yes) {
    console.log('预览完成。确认无误后加 --yes 实际提交。');
    return;
  }

  let payload;
  let fsFileId;
  if (options.asFile) {
    const uploaded = await uploadLocalFile(jsonPath, config, { shouldIndex: false });
    fsFileId = uploaded.fileId;
  }

  const prepared = await createCoursewareWithTemplate({
    templateId: options.templateId,
    title: typeof doc.title === 'string' && doc.title.trim() ? doc.title.trim() : '新课件',
  }, config);
  const preparedCoursewareId = prepared.coursewareId;

  if (options.asFile) {
    payload = buildDirectTaskPayload({
      templateId: options.templateId,
      coursewareId: preparedCoursewareId,
      fsFileId,
      batchNo,
    });
  } else {
    payload = buildStructuredTaskPayload({
      templateId: options.templateId,
      coursewareId: preparedCoursewareId,
      structuredJson: buildStructuredJson(doc),
      batchNo,
    });
  }

  let task;
  try {
    task = await startFlowTask(payload, config);
  } catch (err) {
    const failedRow = {
      file: options.file,
      batchNo,
      taskId: '',
      fsFileId: fsFileId ?? '',
      status: 'FAILED_TO_SUBMIT',
      coursewareId: preparedCoursewareId,
      coursewareUrl: buildCoursewareUrl({
        siteUrl: config.webUrl,
        coursewareId: preparedCoursewareId,
      }),
      failedStage: '',
      error: err instanceof Error ? err.message : String(err),
    };
    console.error(JSON.stringify(failedRow, null, 2));
    if (options.report) {
      await writeReport(resolvePath(options.report), [failedRow]);
      console.error(`失败报告已写出：${resolvePath(options.report)}`);
    }
    throw err;
  }
  console.log(`已创建任务：taskId=${task.taskId} status=${task.status}`);

  let finalTask = task;
  if (options.watch) {
    finalTask = await watchTask(task.taskId, config) || task;
  }

  const coursewareId = finalTask?.coursewareId || preparedCoursewareId;
  const row = {
    file: options.file,
    batchNo,
    taskId: task.taskId,
    fsFileId: fsFileId ?? '',
    status: finalTask?.status || task.status,
    coursewareId,
    coursewareUrl: buildCoursewareUrl({ siteUrl: config.webUrl, coursewareId }),
    failedStage: finalTask?.failedStage || '',
    error: finalTask?.error || '',
  };
  console.log(JSON.stringify(row, null, 2));
  if (row.coursewareUrl) console.log(`预览链接：${row.coursewareUrl}`);
  if (options.report) {
    await writeReport(resolvePath(options.report), [row]);
    console.log(`报告已写出：${resolvePath(options.report)}`);
  }
}

/** 打印生效配置及其来源，不发任何请求。 */
function printConfig(config) {
  const source = (key) => {
    const from = config.envSources?.[key];
    if (!from) return '默认值';
    return from === 'environment' ? '环境变量' : from;
  };
  console.log(
    config.envFiles.length > 0
      ? `.env：${config.envFiles.join('、')}`
      : '.env：未找到（可复制技能目录下的 .env.example）',
  );
  console.log(`网关地址 XRUNS_COURSEWARE_BASE_URL = ${config.baseUrl}（来源：${source('XRUNS_COURSEWARE_BASE_URL')}）`);
  console.log(`预览站点 XRUNS_COURSEWARE_WEB_URL  = ${config.webUrl}（来源：${source('XRUNS_COURSEWARE_WEB_URL')}）`);
  console.log(
    config.token
      ? `访问令牌 XRUNS_COURSEWARE_TOKEN    = ${maskToken(config.token)}（来源：${source('XRUNS_COURSEWARE_TOKEN')}）`
      : '访问令牌 XRUNS_COURSEWARE_TOKEN    = (未设置)',
  );
  if (config.username) console.log(`兜底账号 XRUNS_COURSEWARE_USERNAME = ${config.username}`);
}

async function handleConfig(args) {
  const config = getRuntimeConfig(args);
  printConfig(config);
  if (!config.token && !(config.username && config.password)) {
    console.log('');
    console.log(missingTokenMessage(config));
    process.exitCode = 1;
    return;
  }
  console.log('');
  console.log('配置完整，可执行 ping 验证连通性。');
}

async function handlePing(args) {
  const config = getRuntimeConfig(args);
  printConfig(config);
  if (!config.token && !(config.username && config.password)) {
    throw new Error(missingTokenMessage(config));
  }
  const tasks = await listFlowTasks({ page: 1, pageSize: 1 }, config);
  console.log(`鉴权可用，任务列表返回 ${tasks.length} 条`);
}

function printHelp() {
  console.log(`RunS 页面数据 CLI

用法：
  node pagedata.mjs <命令> [参数]

命令：
  assets:upload <文件...>            批量上传图片 / 音频 / 视频 / 字幕，写入资产清单
    --dir <目录>                     递归扫描目录（与显式文件可同时使用）
    --ext png,mp3                    覆盖默认后缀白名单
    --manifest <路径>                资产清单，默认 ${DEFAULT_MANIFEST}
    --folder-id <id>                 归档到指定业务文件夹
    --concurrency <n>                并发数，默认 ${DEFAULT_CONCURRENCY}
    --force                          忽略清单，强制重传
    --dry-run                        只列出将要上传的文件

  pages:resolve <page.json>          把 @asset: / 相对路径替换成 public_url
    --manifest <路径>                资产清单
    --out <路径>                     输出文件，默认原地覆盖
    --no-upload                      缺失素材不即时上传，直接报错
    --folder-id <id>                 即时上传时的业务文件夹

  pages:validate <page.json>         校验页面 JSON
    --template-id <id>               叠加模板组件白名单与 dataStructure 示例比对
    --allow-unknown                  未知组件类型降级为告警
    --strict                         告警也视为失败

  pages:submit <page.json>           提交课件任务（默认只预览）
    --template-id <id>               必填
    --yes                            确认提交（不加则只做校验预览）
    --as-file                        上传 JSON 走 direct 直接解析链路
    --batch-no <no>                  指定批次号
    --watch                          轮询任务状态到终态
    --report <路径>                  写出 .csv / .json 报告
    --force                          校验有错误时仍然提交

  config                             打印生效配置与来源（不发请求）
  ping                               验证 token 与网关连通性
  help                               显示帮助

配置优先级：命令行参数 > 环境变量 > .env 文件 > 内置默认值
.env 查找顺序：$XRUNS_ENV_FILE > ./.env > <技能目录>/.env > <仓库根>/.env（只读 XRUNS_ 前缀的键）

  XRUNS_COURSEWARE_BASE_URL          接口网关，默认 ${DEFAULT_BASE_URL}
  XRUNS_COURSEWARE_WEB_URL           智课端站点（登录取 token / 拼预览链接），默认 ${DEFAULT_WEB_URL}
  XRUNS_COURSEWARE_TOKEN             access token，必填，登录 ${DEFAULT_WEB_URL} 后从浏览器复制
  XRUNS_COURSEWARE_USERNAME/PASSWORD 无 token 时用账号密码登录换取

对应命令行参数：--base-url / --web-url / --token / --username / --password

已知组件类型（${KNOWN_COMPONENT_TYPES.length} 个）：
  page 级（独占整页）：${PAGE_LEVEL_TYPES.join(' / ')}
  block 级（可组合）：${KNOWN_COMPONENT_TYPES.filter((t) => !PAGE_LEVEL_TYPES.includes(t)).join(' / ')}
`);
}

async function main(argv) {
  const args = parseArgv(argv);
  const command = args._[0] || 'help';
  if (!COMMANDS.has(command)) throw new Error(`未知命令：${command}`);
  if (command === 'help' || args.help) return printHelp();
  if (command === 'config') return handleConfig(args);
  if (command === 'ping') return handlePing(args);
  if (command === 'assets:upload') return handleAssetsUpload(args);
  if (command === 'pages:resolve') return handlePagesResolve(args);
  if (command === 'pages:validate') return handlePagesValidate(args);
  if (command === 'pages:submit') return handlePagesSubmit(args);
  return printHelp();
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main(process.argv.slice(2)).catch((err) => {
    console.error(`错误：${err instanceof Error ? err.message : String(err)}`);
    process.exitCode = 1;
  });
}

export { main };
