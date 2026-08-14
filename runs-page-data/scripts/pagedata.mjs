#!/usr/bin/env node
/**
 * RunS 页面数据 CLI —— 把本地图片 / 音频上传到 RunS，并编排、校验、提交页面 JSON。
 *
 * 命令：
 *   assets:upload      手动上传指定素材，产出可复用的资产清单（--dir 会整目录全传，慎用）
 *   pages:resolve      把页面 JSON 里的本地引用替换成 public_url（缺失的顺手上传，只传被引用的）
 *   pages:validate     按模板组件接口与 dataStructure 校验页面 JSON
 *   pages:submit       提交课件任务（structuredJson 内联 / 上传 JSON 直接解析）—— 新建课件
 *   courseware:pull    把已有课件的当前内容导出成页面 JSON（只读）
 *   courseware:update  改已有课件：读—改—写一条命令闭环，必要时自动 fork 新版本
 */
import { readFile, writeFile, readdir, stat } from 'node:fs/promises';
import { dirname, extname, join, resolve as resolvePath } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  CoursewareSaveConflictError,
  DEFAULT_BASE_URL,
  DEFAULT_WEB_URL,
  buildCoursewareUrl,
  listAllTemplates,
  createCoursewareWithTemplate,
  getActiveFlowTask,
  getCoursewareDetail,
  getFlowTask,
  getRuntimeConfig,
  guessMimeType,
  fetchComponentDetail,
  fetchTemplateComponents,
  listTemplates,
  listFlowTasks,
  maskToken,
  missingTokenMessage,
  rankTemplatesByName,
  resolveTemplateByName,
  rollbackCourseware,
  saveCourseware,
  startFlowTask,
  startStageTask,
  summarizeTemplates,
  uploadLocalFile,
} from './lib/client.mjs';
import {
  assessForkCandidate,
  assertSupportedCoursewarePatchFields,
  buildCompositionModeMap,
  buildSavePayload,
  createRequestId,
  describeVersion,
  docFromDetail,
  hasEffectiveChanges,
  mergePatchPages,
  normalizeCoursewareVersion,
  pagesFromDetail,
  parseCoursewareRef,
  rebasePatchPages,
  resolveVersionEditability,
  splitReportByChangedPages,
  summarizeChanges,
  VERSION_REASON_LABELS,
} from './lib/courseware.mjs';
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
const COMMANDS = new Set([
  'config', 'ping', 'templates:list', 'assets:upload', 'pages:resolve', 'pages:validate', 'pages:submit',
  'courseware:pull', 'courseware:update', 'help',
]);
const BOOLEAN_FLAGS = new Set([
  'as-file', 'dry-run', 'force', 'help', 'no-upload', 'regen-html', 'regen-media', 'replace', 'strict', 'watch', 'yes',
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
  if (args.force) throw new Error('pages:submit 不支持 --force，模板 dataStructure 校验错误不能跳过');
  const selector = parseTemplateSelector(args, { required: true });
  return {
    file: String(file),
    ...selector,
    batchNo: args['batch-no'] ? String(args['batch-no']) : undefined,
    asFile: Boolean(args['as-file']),
    watch: Boolean(args.watch),
    yes: Boolean(args.yes),
    report: args.report ? String(args.report) : undefined,
  };
}

function optionalStringFlag(args, flag) {
  if (args[flag] === true) throw new Error(`--${flag} 缺少值`);
  return typeof args[flag] === 'string' && args[flag].trim() ? args[flag].trim() : undefined;
}

export function parseCoursewareTarget(args, { position = 1 } = {}) {
  const target = args._[position];
  if (!target) throw new Error('缺少课件链接或课件 ID');
  const ref = parseCoursewareRef(String(target));
  // 显式 --version-id 覆盖链接里带的那一段
  const versionId = optionalStringFlag(args, 'version-id') ?? ref.versionId;
  return { coursewareId: ref.coursewareId, ...(versionId ? { versionId } : {}) };
}

export function parseCoursewareUpdateArgs(args) {
  const target = parseCoursewareTarget(args);
  const file = args._[2];
  if (!file) throw new Error('缺少补丁 JSON 路径');
  if (args.force) {
    throw new Error('courseware:update 不支持 --force，模板 dataStructure 校验错误不能跳过');
  }
  return {
    ...target,
    file: String(file),
    ...parseTemplateSelector(args),
    replace: Boolean(args.replace),
    yes: Boolean(args.yes),
    regenMedia: Boolean(args['regen-media']),
    regenHtml: Boolean(args['regen-html']),
  };
}

export function parseTemplateSelector(args, { required = false } = {}) {
  // parseArgv 对「有 flag 无取值」的写法会置为 true，这里必须要求真实字符串
  const hasTemplateId = Object.prototype.hasOwnProperty.call(args, 'template-id');
  const hasTemplateName = Object.prototype.hasOwnProperty.call(args, 'template');
  const templateId = typeof args['template-id'] === 'string' ? args['template-id'].trim() : '';
  const templateName = typeof args.template === 'string' ? args.template.trim() : '';
  if (hasTemplateId && !templateId) throw new Error('--template-id 缺少值');
  if (hasTemplateName && !templateName) throw new Error('--template 缺少值');
  if (templateId && templateName) {
    throw new Error('--template-id 与 --template 只能提供一个');
  }
  if (required && !templateId && !templateName) {
    throw new Error('缺少 --template-id 或 --template');
  }
  return {
    templateId: templateId || undefined,
    templateName: templateName || undefined,
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

async function resolveTemplateSelection(selector, config) {
  if (selector.templateId) {
    return {
      templateId: selector.templateId,
      templateName: undefined,
      resolvedBy: 'id',
    };
  }
  if (!selector.templateName) return undefined;
  const resolved = await resolveTemplateByName(selector.templateName, config);
  return { ...resolved, resolvedBy: 'name' };
}

function printResolvedTemplate(template) {
  if (!template) return;
  if (template.resolvedBy === 'name') {
    console.log(`模板解析：${template.templateName} → ${template.templateId}`);
  } else {
    console.log(`模板 ID：${template.templateId}`);
  }
}

/** 校验并回带模板上下文；courseware:update 还要用 templateComponents 派生 renderType。 */
async function runValidationWithContext(doc, args, { templateId } = {}) {
  if (!templateId) throw new Error('组件校验必须提供 --template-id 或 --template');
  const config = getRuntimeConfig(args);
  const options = await loadTemplateContext(templateId, doc, config);

  const report = validatePageData(doc, options);
  const residual = findResidualLocalRefs(doc);
  for (const item of residual) {
    report.errors.push({ path: item.path, message: `仍是本地素材引用 ${item.raw}，请先执行 pages:resolve` });
  }
  return { report, ...options };
}

async function runValidation(doc, args, { templateId } = {}) {
  const { report } = await runValidationWithContext(doc, args, { templateId });
  return report;
}

async function handlePagesValidate(args) {
  const file = args._[1];
  if (!file) throw new Error('缺少页面 JSON 路径');
  if (args['allow-unknown']) {
    throw new Error('pages:validate 不支持 --allow-unknown，组件必须来自模板接口');
  }
  const doc = await readJsonFile(resolvePath(String(file)));
  const selector = parseTemplateSelector(args, { required: true });
  const template = await resolveTemplateSelection(selector, getRuntimeConfig(args));
  const report = await runValidation(doc, args, { templateId: template.templateId });

  printResolvedTemplate(template);
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
  const template = await resolveTemplateSelection(options, config);
  options.templateId = template.templateId;
  const jsonPath = resolvePath(options.file);
  const doc = await readJsonFile(jsonPath);

  const report = await runValidation(doc, args, { templateId: options.templateId });
  const formatted = formatReport(report);
  if (formatted) console.log(formatted);

  printResolvedTemplate(template);
  console.log(JSON.stringify(summarizePageData(doc), null, 2));

  if (report.errors.length > 0) {
    console.log(`校验未通过（${report.errors.length} 个错误），已终止提交。`);
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

// rollback 建版与详情可读之间存在瞬时不一致，与前端 use-creator-data 采用同一组重试间隔
const FORK_RETRY_DELAYS_MS = [300, 700];

function printVersion(prefix, version, editability) {
  console.log(`${prefix}${describeVersion(version)}`);
  console.log(`  版本判定：${VERSION_REASON_LABELS[editability.reason] ?? editability.reason}`);
}

async function handleCoursewarePull(args) {
  const target = parseCoursewareTarget(args);
  const config = getRuntimeConfig(args);
  const detail = await getCoursewareDetail(target, config);
  const version = normalizeCoursewareVersion(detail);
  const editability = resolveVersionEditability(version);
  const doc = docFromDetail(detail);

  const outPath = resolvePath(String(args.out || `courseware.${target.coursewareId}.json`));
  await writeFile(outPath, `${JSON.stringify(doc, null, 2)}\n`, 'utf8');

  console.log(
    `课件：${doc.title || '(无标题)'}｜coursewareId=${target.coursewareId}`
    + `｜templateId=${detail.templateId ?? '(未返回)'}`,
  );
  printVersion('版本：', version, editability);
  console.log(`页面 ${doc.pages.length} 页：`);
  for (const page of doc.pages) {
    const components = Array.isArray(page.components) ? page.components.length : 0;
    console.log(
      `  #${page.pageNumber} pageId=${page.pageId ?? '(无)'}`
      + ` renderType=${page.renderType ?? '(未设置)'} 组件 ${components} 个｜${page.title || '(无标题)'}`,
    );
  }
  console.log(`已写出：${outPath}`);
  console.log(`预览链接：${buildCoursewareUrl({ siteUrl: config.webUrl, coursewareId: target.coursewareId })}`);
}

/**
 * fork：把只读版本克隆成新的当前工作版本。
 * rollback 只回成功与否，因此必须记录操作前 current，再回查确认 versionId、版本号、
 * current 状态与源页数；否则可能把仍在返回的旧 current 当成新版本写错。
 */
async function forkWorkingVersion({ coursewareId, sourceVersion, sourcePageCount, config }) {
  const sourceNumber = Number(sourceVersion.version);
  if (!Number.isInteger(sourceNumber) || sourceNumber <= 0) {
    throw new Error('课件详情里缺少源版本号，无法创建新版本');
  }

  // rollback 只回成功与否。先记住操作前 current，避免历史源版本 V1 的回查把旧 current V2
  // 误当成新版本（V2 同样满足 `version > sourceVersion`）。
  const previousDetail = await getCoursewareDetail({ coursewareId }, config);
  const previousCurrentVersion = normalizeCoursewareVersion(previousDetail);
  if (!previousCurrentVersion.versionId || !previousCurrentVersion.version) {
    throw new Error('操作前当前版本缺少 versionId / version，无法安全确认 fork 结果');
  }
  await rollbackCourseware({ coursewareId, version: sourceNumber }, config);

  let lastAssessment = { reasons: ['尚未回读'] };
  for (let attempt = 0; ; attempt += 1) {
    const detail = await getCoursewareDetail({ coursewareId }, config);
    const version = normalizeCoursewareVersion(detail);
    const candidatePageCount = Array.isArray(detail?.pages) ? detail.pages.length : -1;
    lastAssessment = assessForkCandidate({
      sourceVersion,
      previousCurrentVersion,
      candidateVersion: version,
      sourcePageCount,
      candidatePageCount,
    });
    if (lastAssessment.ready) return { detail, version };

    if (attempt >= FORK_RETRY_DELAYS_MS.length) {
      throw new Error(
        `新版本已创建，但尚未回读到唯一且完整的新 current（源 V${sourceNumber}，`
        + `操作前 V${previousCurrentVersion.version}，当前回读 V${version.version ?? '?'}；`
        + `${lastAssessment.reasons.join('；')}），`
        + '本次未写入任何改动，请稍后重新执行',
      );
    }
    await sleep(FORK_RETRY_DELAYS_MS[attempt]);
  }
}

/** 合并补丁 → 组装完整快照 → 按模板校验；不发写请求。 */
async function buildUpdatePlan({ detail, patchDoc, patchPages, options, args, templateId }) {
  const serverPages = pagesFromDetail(detail);
  const { pages, changes } = mergePatchPages(serverPages, patchPages, { replace: options.replace });
  const serverTitle = typeof detail?.title === 'string' ? detail.title : '';
  const title = typeof patchDoc?.title === 'string' && patchDoc.title.trim()
    ? patchDoc.title
    : serverTitle;
  const titleChanged = title.trim() !== serverTitle.trim();
  const doc = { title, pages };

  const effectiveTemplateId = templateId
    || (detail?.templateId != null && String(detail.templateId).trim() ? String(detail.templateId) : '');
  if (!effectiveTemplateId) {
    throw new Error('课件详情里没有 templateId，无法按模板校验组件；请用 --template-id 或 --template 指定');
  }

  const { report, templateComponents } = await runValidationWithContext(doc, args, {
    templateId: effectiveTemplateId,
  });
  return {
    serverPages,
    doc,
    pages,
    changes,
    serverTitle,
    titleChanged,
    report,
    templateComponents,
    templateId: effectiveTemplateId,
    ...splitReportByChangedPages(report, changes),
  };
}

function printUpdatePlan(plan) {
  const summary = summarizeChanges(plan.changes);
  console.log(
    `改动：更新 ${summary.updated}，新增 ${summary.added}，删除 ${summary.removed}，`
    + `移动 ${summary.moved}，未变 ${summary.unchanged}（提交的是 ${plan.pages.length} 页完整快照）`,
  );
  if (plan.titleChanged) {
    console.log(`  ~ 课件标题：${plan.serverTitle || '(无标题)'} → ${plan.doc.title}`);
  }
  for (const item of plan.changes) {
    if (item.status === 'unchanged') continue;
    const marks = { updated: '~', added: '+', removed: '-', moved: '→' };
    const from = item.fromPageNumber ? `（原第 ${item.fromPageNumber} 页）` : '';
    console.log(
      `  ${marks[item.status] ?? '?'} #${item.pageNumber} pageId=${item.pageId ?? '(新页)'}`
      + `${from}｜${item.title || '(无标题)'}`,
    );
  }
  for (const item of plan.blocking) console.log(`  ✗ ${item.path || '根节点'}：${item.message}`);
  for (const item of plan.untouched) {
    console.log(`  ! ${item.path || '根节点'}：${item.message}（本次未改动该页，不阻断保存）`);
  }
  for (const item of plan.warnings) console.log(`  ! ${item.path || '根节点'}：${item.message}`);
  if (plan.untouchedWarnings.length > 0) {
    console.log(`  ! 另有 ${plan.untouchedWarnings.length} 条告警落在本次未改动的页上，已省略`);
  }
}

async function handleCoursewareUpdate(args) {
  const options = parseCoursewareUpdateArgs(args);
  const config = getRuntimeConfig(args);
  const patchDoc = await readJsonFile(resolvePath(options.file));
  assertSupportedCoursewarePatchFields(patchDoc);
  if (!Array.isArray(patchDoc?.pages)) throw new Error('补丁 JSON 缺少 pages 数组');
  let patchPages = patchDoc.pages;

  // 1. 活跃任务闸门：任务的阶段 job 会拿 pinned 版本原位写入，此时插一次保存
  //    要么被 CAS 拒，要么把任务顶成 CONFLICTED（生成结果直接丢弃）。
  const active = await getActiveFlowTask(options.coursewareId, config);
  if (active) {
    throw new Error(
      `课件还有未完成的任务（taskId=${active.taskId} status=${active.status}`
      + `${active.stage ? ` stage=${active.stage}` : ''}），现在写入会与任务互相覆盖。`
      + '请等它跑完，或到创作页中断该任务后重试。',
    );
  }

  // 2. 读取目标版本并判定路由：可写就原位更新，只读就 fork 新版本
  let detail = await getCoursewareDetail(
    { coursewareId: options.coursewareId, versionId: options.versionId },
    config,
  );
  let version = normalizeCoursewareVersion(detail);
  const editability = resolveVersionEditability(version);
  const template = await resolveTemplateSelection(options, config);
  if (template) printResolvedTemplate(template);

  console.log(`课件：${detail.title || '(无标题)'}｜coursewareId=${options.coursewareId}`);
  printVersion('目标版本：', version, editability);
  if (editability.reason === 'no-identity') {
    throw new Error('课件详情里没有精确版本 ID，无法安全写入；请确认课件是否正常');
  }

  const needFork = !editability.editable;
  console.log(needFork
    ? `路由：该版本只读 → 先基于 V${version.version ?? '?'} 创建新工作版本，再在新版本上更新`
    : '路由：原位更新当前工作版本');

  let plan = await buildUpdatePlan({
    detail, patchDoc, patchPages, options, args, templateId: template?.templateId,
  });
  printUpdatePlan(plan);

  if (plan.blocking.length > 0) {
    console.log(`校验未通过（${plan.blocking.length} 个错误落在本次改动的页上），已终止，未写入任何内容。`);
    process.exitCode = 1;
    return;
  }
  if (!hasEffectiveChanges(plan.changes, { titleChanged: plan.titleChanged })) {
    console.log('补丁与服务端内容完全一致，无需保存（不做空写入以免推进 revision）。');
    return;
  }
  if (!options.yes) {
    console.log('预览完成。确认无误后加 --yes 实际写入。');
    return;
  }

  // 3. 只读版本先 fork：新版本的页是克隆出来的新行，补丁里的 pageId 要按页序换算过去
  if (needFork) {
    const sourcePages = plan.serverPages;
    const forked = await forkWorkingVersion({
      coursewareId: options.coursewareId,
      sourceVersion: version,
      sourcePageCount: sourcePages.length,
      config,
    });
    detail = forked.detail;
    version = forked.version;
    console.log(`已创建新工作版本：${describeVersion(version)}`);

    patchPages = rebasePatchPages(patchPages, sourcePages, pagesFromDetail(detail));
    plan = await buildUpdatePlan({
      detail, patchDoc, patchPages, options, args, templateId: template?.templateId,
    });
    if (plan.blocking.length > 0) {
      throw new Error('新版本上的校验未通过，已停止写入；新版本已创建，可修正补丁后重试');
    }
  }

  // 4. 保存。撞 STALE_REVISION 说明期间有别的写入，重读一次并在最新内容上重放同一份补丁；
  //    内容变了必须换新的 requestId，复用会被判成 IDEMPOTENCY_CONFLICT。
  let saved;
  for (let attempt = 0; ; attempt += 1) {
    const payload = buildSavePayload({
      coursewareId: options.coursewareId,
      targetVersionId: version.versionId,
      expectedRevision: version.revision,
      requestId: createRequestId(),
      pages: plan.pages,
      title: plan.doc.title,
      modeByType: buildCompositionModeMap(plan.templateComponents),
    });
    try {
      saved = await saveCourseware(payload, config);
      break;
    } catch (err) {
      const retriable = err instanceof CoursewareSaveConflictError
        && err.reason === 'STALE_REVISION'
        && attempt < 1;
      if (!retriable) throw err;
      console.log(`  ! ${err.message}`);
      console.log('  重新读取最新内容并重放本次改动…');
      detail = await getCoursewareDetail(
        { coursewareId: options.coursewareId, versionId: version.versionId },
        config,
      );
      version = normalizeCoursewareVersion(detail);
      plan = await buildUpdatePlan({
        detail, patchDoc, patchPages, options, args, templateId: template?.templateId,
      });
      if (plan.blocking.length > 0) {
        throw new Error('重放到最新内容后校验未通过，已停止写入');
      }
    }
  }

  const savedVersion = normalizeCoursewareVersion(saved.courseware);
  console.log(`已保存：${describeVersion(savedVersion)}｜落库 ${plan.pages.length} 页`);
  if (saved.createdNewVersion) {
    console.log('  ! 服务端在 UPDATE 语义下建了新版本，请到创作页确认版本历史');
  }
  console.log(`预览链接：${buildCoursewareUrl({ siteUrl: config.webUrl, coursewareId: options.coursewareId })}`);
  if (needFork) {
    console.log('提示：新版本是 DRAFT，尚未发布；需要在创作页发布后才能作为已发布版本生效。');
  }
  console.log('提示：页面已生成的 HTML（pageData.output）与音频不会自动跟着改，需要时用 --regen-html / --regen-media 重跑。');

  // 5. 可选的单阶段重跑：服务端同步等待任务结束，页数多时会比较久
  for (const [flag, stage, label] of [
    [options.regenMedia, 'media', '媒体补全'],
    [options.regenHtml, 'html', 'HTML 生成'],
  ]) {
    if (!flag) continue;
    console.log(`触发${label}…`);
    const task = await startStageTask(stage, options.coursewareId, config);
    console.log(`  ✓ ${label}完成：taskId=${task.taskId}`);
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

function positiveInteger(value, fallback, flag) {
  if (value === true || value === '') throw new Error(`${flag} 缺少值`);
  const parsed = value === undefined ? fallback : Number(value);
  if (!Number.isInteger(parsed) || parsed < 1) throw new Error(`${flag} 必须是正整数`);
  return parsed;
}

async function handleTemplatesList(args) {
  const config = getRuntimeConfig(args);
  if (args.keyword === true) throw new Error('--keyword 缺少值');
  if (args['template-module-type'] === true) throw new Error('--template-module-type 缺少值');
  const keyword = typeof args.keyword === 'string' ? args.keyword.trim() : '';
  const pageSize = positiveInteger(args['page-size'], 100, '--page-size');
  const templateModuleType = typeof args['template-module-type'] === 'string'
    ? args['template-module-type'].trim()
    : '';

  let templates;
  if (keyword) {
    const all = await listAllTemplates(config, { pageSize, templateModuleType });
    templates = rankTemplatesByName(all, keyword)
      .filter((item) => item.score >= 60)
      .map((item) => item.template);
  } else {
    const page = positiveInteger(args.page, 1, '--page');
    templates = (await listTemplates({ page, pageSize, templateModuleType }, config)).items;
  }
  console.log(JSON.stringify(summarizeTemplates(templates), null, 2));
}

function printHelp() {
  console.log(`RunS 页面数据 CLI

用法：
  node pagedata.mjs <命令> [参数]

命令：
  assets:upload <文件...>            手动上传指定素材，写入资产清单
                                     （常规流程用 pages:resolve 按需上传，只传被引用到的素材）
    --dir <目录>                     递归扫描目录并全部上传（会连用不上的素材一起传，先 --dry-run 确认）
    --ext png,mp3                    覆盖默认后缀白名单
    --manifest <路径>                资产清单，默认 ${DEFAULT_MANIFEST}
    --folder-id <id>                 归档到指定业务文件夹
    --concurrency <n>                并发数，默认 ${DEFAULT_CONCURRENCY}
    --force                          忽略清单，强制重传
    --dry-run                        只列出将要上传的文件

  pages:resolve <page.json>          把 @asset: / 相对路径替换成 public_url，并按需上传被引用的素材
    --manifest <路径>                资产清单
    --out <路径>                     输出文件，默认原地覆盖
    --no-upload                      预检模式：不即时上传，逐条报告清单缺失的引用
    --folder-id <id>                 即时上传时的业务文件夹

  pages:validate <page.json>         校验页面 JSON
    --template-id <id>               业务模板 ID，必填；与 --template 二选一
    --template <name>                模板名称，必填；自动查询并解析 ID
    --strict                         告警也视为失败

  pages:submit <page.json>           新建课件并提交生成任务（默认只预览）
    --template-id <id>               业务模板 ID；与 --template 二选一
    --template <name>                模板名称；自动查询并解析 ID，与 --template-id 二选一
    --yes                            确认提交（不加则只做校验预览）
    --as-file                        上传 JSON 走 direct 直接解析链路
    --batch-no <no>                  指定批次号
    --watch                          轮询任务状态到终态
    --report <路径>                  写出 .csv / .json 报告

  courseware:pull <链接|课件ID>       导出已有课件的当前内容（只读，不写任何东西）
    --version-id <id>                指定精确版本；默认取当前工作版本
    --out <路径>                     输出文件，默认 courseware.<coursewareId>.json

  courseware:update <链接|课件ID> <补丁.json>
                                     改已有课件（默认只预览）。默认按 pageId / pageNumber
                                     只覆盖补丁里出现的页字段，其余原样保留；补丁文档
                                     顶层只支持 title / pages，其他字段直接报错
    --replace                        补丁即完整页面列表：未出现的页会被删除，可增页、可改页序
    --version-id <id>                指定精确版本；默认取当前工作版本
    --template-id <id> / --template <name>
                                     覆盖校验用的模板；默认取课件详情里的 templateId
    --yes                            确认写入（不加则只做合并预览与校验）
    --regen-media                    写入后重跑媒体补全（同步等待，较慢）
    --regen-html                     写入后重跑 HTML 生成（同步等待，较慢）

  templates:list                    查询当前用户可用的模板及其业务模板 ID
    --keyword <name>                 按模板名称模糊过滤并排序（会遍历模板列表）
    --page <n>                       不带关键词时查询指定页，默认 1
    --page-size <n>                  每页数量，默认 100
    --template-module-type <type>    可选模板模块类型

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
`);
}

async function main(argv) {
  const args = parseArgv(argv);
  const command = args._[0] || 'help';
  if (!COMMANDS.has(command)) throw new Error(`未知命令：${command}`);
  if (command === 'help' || args.help) return printHelp();
  if (command === 'config') return handleConfig(args);
  if (command === 'ping') return handlePing(args);
  if (command === 'templates:list') return handleTemplatesList(args);
  if (command === 'assets:upload') return handleAssetsUpload(args);
  if (command === 'pages:resolve') return handlePagesResolve(args);
  if (command === 'pages:validate') return handlePagesValidate(args);
  if (command === 'pages:submit') return handlePagesSubmit(args);
  if (command === 'courseware:pull') return handleCoursewarePull(args);
  if (command === 'courseware:update') return handleCoursewareUpdate(args);
  return printHelp();
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main(process.argv.slice(2)).catch((err) => {
    console.error(`错误：${err instanceof Error ? err.message : String(err)}`);
    process.exitCode = 1;
  });
}

export { main };
