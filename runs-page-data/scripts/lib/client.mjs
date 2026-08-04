/**
 * RunS 网关客户端：鉴权、OSS 直传、文件落库、课件任务。
 *
 * 使用 RunS 网关接入约定（BASE_URL / clientid / Bearer token / 三步上传）。
 * 本文件自带实现，便于 skill 整体拷贝复用。
 */
import { readFile } from 'node:fs/promises';
import { basename, extname } from 'node:path';

import { loadEnvFiles } from './env.mjs';

/** 接口网关；.env 里的 XRUNS_COURSEWARE_BASE_URL 覆盖它。 */
export const DEFAULT_BASE_URL = 'https://api.dev.xruns.cn/api/';
/** 智课端站点，用于登录取 token 和拼课件预览链接；与网关是两个域名，不能互相推导。 */
export const DEFAULT_WEB_URL = 'https://web.dev.xruns.cn/';
export const DEFAULT_CLIENT_ID = '428a8310cd442757ae699df5d894f051';

const MIME_BY_EXTENSION = {
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.gif': 'image/gif',
  '.bmp': 'image/bmp',
  '.svg': 'image/svg+xml',
  '.mp3': 'audio/mpeg',
  '.wav': 'audio/wav',
  '.m4a': 'audio/mp4',
  '.aac': 'audio/aac',
  '.ogg': 'audio/ogg',
  '.flac': 'audio/flac',
  '.mp4': 'video/mp4',
  '.mov': 'video/quicktime',
  '.m4v': 'video/x-m4v',
  '.webm': 'video/webm',
  '.srt': 'text/plain',
  '.vtt': 'text/vtt',
  '.json': 'application/json',
  '.txt': 'text/plain',
  '.md': 'text/markdown',
  '.pdf': 'application/pdf',
};

let cachedAccessToken = '';

/** 仅供测试重置模块级 token 缓存。 */
export function resetTokenCache() {
  cachedAccessToken = '';
}

export function guessMimeType(filePath) {
  return MIME_BY_EXTENSION[extname(filePath).toLowerCase()] || 'application/octet-stream';
}

/** 与后端 infer_file_category 保持一致：image/audio/video 直取大类，其余归 document/other。 */
export function inferFileCategory(mimeType) {
  if (!mimeType) return 'other';
  const major = mimeType.split('/')[0];
  if (major === 'image' || major === 'audio' || major === 'video') return major;
  const documentPrefixes = [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument',
    'application/vnd.ms-excel',
    'application/vnd.ms-powerpoint',
    'text/',
  ];
  return documentPrefixes.some((prefix) => mimeType.startsWith(prefix)) ? 'document' : 'other';
}

export function normalizeBaseUrl(input) {
  const raw = input || DEFAULT_BASE_URL;
  if (!/^https?:\/\//.test(raw)) {
    return raw.endsWith('/') ? raw : `${raw}/`;
  }
  if (/\/api\/?$/i.test(raw) || /\/api\//i.test(raw)) {
    return raw.endsWith('/') ? raw : `${raw}/`;
  }
  return raw.endsWith('/') ? `${raw}api/` : `${raw}/api/`;
}

export function normalizeSiteUrl(input) {
  const raw = input || DEFAULT_WEB_URL;
  const withoutApi = raw.replace(/\/api\/?$/i, '').replace(/\/api\/.*$/i, '');
  return withoutApi.endsWith('/') ? withoutApi : `${withoutApi}/`;
}

export function buildCoursewareUrl({ siteUrl = DEFAULT_WEB_URL, coursewareId }) {
  if (!coursewareId) return '';
  return `${normalizeSiteUrl(siteUrl)}creator/${encodeURIComponent(coursewareId)}`;
}

/**
 * 配置优先级：命令行参数 > 真实环境变量 > .env 文件 > 内置默认值。
 * 调用即触发 .env 加载，因此所有命令拿到的都是同一份解析结果。
 */
export function getRuntimeConfig(args = {}) {
  const env = loadEnvFiles();
  const webUrl = normalizeSiteUrl(
    args['web-url'] || process.env.XRUNS_COURSEWARE_WEB_URL || process.env.XRUNS_WEB_URL || DEFAULT_WEB_URL,
  );
  // 命令行传入时来源要盖掉 .env，否则 config 回显会指错地方
  const envSources = { ...env.sources };
  if (args['base-url']) envSources.XRUNS_COURSEWARE_BASE_URL = '命令行参数';
  if (args['web-url']) envSources.XRUNS_COURSEWARE_WEB_URL = '命令行参数';
  if (args.token) envSources.XRUNS_COURSEWARE_TOKEN = '命令行参数';
  return {
    baseUrl: normalizeBaseUrl(
      args['base-url'] || process.env.XRUNS_COURSEWARE_BASE_URL || process.env.XRUNS_BASE_URL,
    ),
    webUrl,
    // 兼容旧字段名：预览链接一律走 webUrl，不再从网关地址反推
    siteUrl: webUrl,
    token: args.token || process.env.XRUNS_COURSEWARE_TOKEN || process.env.XRUNS_TOKEN || '',
    clientId: args.clientid || args['client-id'] || process.env.XRUNS_COURSEWARE_CLIENT_ID || DEFAULT_CLIENT_ID,
    username: args.username || process.env.XRUNS_COURSEWARE_USERNAME || process.env.XRUNS_USERNAME || '',
    password: args.password || process.env.XRUNS_COURSEWARE_PASSWORD || process.env.XRUNS_PASSWORD || '',
    envFiles: env.files,
    envSources,
  };
}

/** token 只回显首尾，避免日志 / 对话里泄漏完整凭证。 */
export function maskToken(token) {
  if (!token) return '(未设置)';
  const bare = token.replace(/^Bearer\s+/i, '');
  if (bare.length <= 12) return `${bare.slice(0, 2)}****`;
  return `${bare.slice(0, 6)}****${bare.slice(-4)}（${bare.length} 字符）`;
}

/** 缺 token 时统一的引导文案：先说去哪拿，再说写到哪。 */
export function missingTokenMessage(config = {}) {
  const webUrl = config.webUrl || DEFAULT_WEB_URL;
  const target = config.envFiles?.[0] || '技能目录下的 .env';
  return [
    '缺少 XRUNS_COURSEWARE_TOKEN。',
    `获取方式：浏览器打开 ${webUrl} 登录智课端，`,
    'DevTools → Application → Local Storage 复制 access token（或 Network 面板任一请求的 Authorization 头，去掉 Bearer 前缀）。',
    `然后写入 ${target}：XRUNS_COURSEWARE_TOKEN=<token>`,
    '（也可临时用 --token 传入，或设置 XRUNS_COURSEWARE_USERNAME/XRUNS_COURSEWARE_PASSWORD 由脚本登录换取。）',
  ].join('\n');
}

export function buildHeaders({ token, clientId }, headers = {}) {
  return {
    'content-language': 'zh_CN',
    clientid: clientId,
    ...(token ? { Authorization: token.startsWith('Bearer ') ? token : `Bearer ${token}` } : {}),
    ...headers,
  };
}

export function buildLoginPayload({ username, password, clientId }) {
  return { phone: username, password, clientId, grantType: 'password', tenantId: '' };
}

export function extractAccessToken(payload) {
  return payload?.data?.access_token
    || payload?.data?.accessToken
    || payload?.access_token
    || payload?.accessToken
    || '';
}

async function readJsonResponse(response) {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export function errorMessage(payload, response) {
  if (payload && typeof payload === 'object') {
    return payload.error || payload.msg || payload.message || payload.detail
      || `${response.status} ${response.statusText}`;
  }
  if (typeof payload === 'string' && payload.trim()) return payload;
  return `${response.status} ${response.statusText}`;
}

export async function resolveToken(config) {
  if (config.token) return config.token;
  if (cachedAccessToken) return cachedAccessToken;
  if (!config.username || !config.password) {
    throw new Error(missingTokenMessage(config));
  }

  const response = await fetch(`${config.baseUrl}v1/user/auth/web/passwordLogin`, {
    method: 'POST',
    headers: {
      accept: 'application/json, text/plain, */*',
      clientid: config.clientId,
      'content-language': 'zh_CN',
      'content-type': 'application/json;charset=UTF-8',
    },
    body: JSON.stringify(buildLoginPayload(config)),
  });
  const payload = await readJsonResponse(response);
  if (!response.ok || (payload?.code !== undefined && ![0, 200].includes(Number(payload.code)))) {
    throw new Error(errorMessage(payload, response));
  }

  cachedAccessToken = extractAccessToken(payload);
  if (!cachedAccessToken) throw new Error('登录成功但响应中没有 access_token');
  return cachedAccessToken;
}

export async function apiRequest(path, { method = 'GET', body, json = false, config } = {}) {
  const token = await resolveToken(config);
  const url = /^https?:\/\//.test(path) ? path : `${config.baseUrl}${path}`;
  const headers = buildHeaders(
    { ...config, token },
    { 'Content-Type': json ? 'application/json' : 'application/x-www-form-urlencoded' },
  );

  let requestBody;
  if (body !== undefined) {
    requestBody = json
      ? JSON.stringify(body)
      : new URLSearchParams(
        Object.entries(body)
          .filter(([, value]) => value !== undefined && value !== null)
          .map(([key, value]) => [key, String(value)]),
      );
  }

  const response = await fetch(url, { method, headers, body: requestBody });
  const payload = await readJsonResponse(response);
  if (!response.ok) throw new Error(errorMessage(payload, response));
  return payload;
}

export function buildCommitPayload(uploaded, { folderId, shouldIndex = false, fileCategory } = {}) {
  return {
    filename: uploaded.filename,
    object_key: uploaded.objectKey,
    bucket_name: uploaded.bucketName,
    public_url: uploaded.publicUrl,
    size: uploaded.size,
    mime_type: uploaded.mimeType,
    should_index: shouldIndex,
    ...(folderId ? { folder_id: folderId } : {}),
    ...(fileCategory ? { file_category: fileCategory } : {}),
  };
}

/**
 * 三步上传的前两步：取凭证 + 表单直传 OSS。
 * object_key / public_url 一律以服务端返回为准，不在本地拼接，否则 commit 会被前缀校验拒绝。
 */
export async function uploadBytesToOss({ bytes, filename, mimeType, folderId }, config) {
  const tokenResponse = await apiRequest(`v1/ai/fs/uploads/token`, {
    method: 'POST',
    config,
    body: {
      filename,
      size: bytes.byteLength,
      mime_type: mimeType,
      ...(folderId ? { folder_id: folderId } : {}),
    },
  });
  if (tokenResponse?.code !== 0 || !tokenResponse?.data) {
    throw new Error(tokenResponse?.msg || '获取上传凭证失败');
  }

  const { host, key, accessid, policy, signature, public_url: publicUrl, bucket_name: bucketName } = tokenResponse.data;
  const formData = new FormData();
  formData.append('Filename', filename);
  formData.append('key', key);
  formData.append('OSSAccessKeyId', accessid);
  formData.append('policy', policy);
  formData.append('signature', signature);
  formData.append('success_action_status', '200');
  formData.append('file', new Blob([bytes], { type: mimeType }), filename);

  const ossResponse = await fetch(host, { method: 'POST', body: formData });
  if (!ossResponse.ok) {
    throw new Error(`上传文件到 OSS 失败：${ossResponse.status} ${ossResponse.statusText}`);
  }

  return { filename, size: bytes.byteLength, mimeType, bucketName, objectKey: key, publicUrl };
}

export async function commitFile(uploaded, config, options = {}) {
  const response = await apiRequest(`v1/ai/fs/files/commit`, {
    method: 'POST',
    config,
    body: buildCommitPayload(uploaded, options),
  });
  if (response?.code !== 0 || !response?.data) {
    throw new Error(response?.msg || '上传完成确认失败');
  }
  return response.data;
}

/** 完整三步：读文件 → 直传 OSS → commit 落库。返回资产清单条目所需的全部字段。 */
export async function uploadLocalFile(filePath, config, { folderId, shouldIndex = false, fileCategory } = {}) {
  const filename = basename(filePath);
  const mimeType = guessMimeType(filePath);
  const bytes = await readFile(filePath);
  const uploaded = await uploadBytesToOss({ bytes, filename, mimeType, folderId }, config);
  const committed = await commitFile(uploaded, config, {
    folderId,
    shouldIndex,
    fileCategory: fileCategory || inferFileCategory(mimeType),
  });
  return {
    ...uploaded,
    fileId: committed.id,
    category: committed.file_category || inferFileCategory(mimeType),
    publicUrl: committed.public_url || uploaded.publicUrl,
  };
}

export async function startFlowTask(payload, config) {
  const response = await apiRequest(`v1/creator/courseware/flow/task`, { method: 'POST', config, json: true, body: payload });
  const result = response?.data ?? response;
  if (!result?.taskId) {
    throw new Error(result?.error || result?.msg || '启动课件任务失败');
  }
  return result;
}

export function buildTemplateListPath({
  page = 1,
  pageSize = 100,
  templateModuleType = '',
} = {}) {
  const params = new URLSearchParams();
  params.set('pageNum', String(page));
  params.set('pageSize', String(pageSize));
  params.set('templateModuleType', String(templateModuleType));
  return `v1/business/creator/template/list?${params.toString()}`;
}

export function templateBusinessId(template) {
  return template?.templateId || template?.id || '';
}

export function templateDisplayName(template) {
  return template?.templateName
    || template?.name
    || template?.title
    || template?.template_name
    || '';
}

export function normalizeTemplateName(value) {
  return String(value || '')
    .normalize('NFKC')
    .toLocaleLowerCase('zh-CN')
    .replace(/[\p{P}\p{S}\s]+/gu, '');
}

function templateNameCore(value) {
  let core = normalizeTemplateName(value);
  let previous = '';
  while (core && core !== previous) {
    previous = core;
    core = core.replace(/(?:课程模板|模板|课件|课程)$/u, '');
  }
  return core;
}

function levenshteinDistance(left, right) {
  const a = Array.from(left);
  const b = Array.from(right);
  const previous = Array.from({ length: b.length + 1 }, (_, index) => index);
  for (let i = 1; i <= a.length; i += 1) {
    const current = [i];
    for (let j = 1; j <= b.length; j += 1) {
      current[j] = Math.min(
        current[j - 1] + 1,
        previous[j] + 1,
        previous[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1),
      );
    }
    previous.splice(0, previous.length, ...current);
  }
  return previous[b.length];
}

export function scoreTemplateNameMatch(templateName, query) {
  const name = normalizeTemplateName(templateName);
  const expected = normalizeTemplateName(query);
  if (!name || !expected) return 0;
  if (name === expected) return 100;

  const nameCore = templateNameCore(name);
  const expectedCore = templateNameCore(expected);
  if (nameCore && expectedCore && nameCore === expectedCore) return 95;

  let score = 0;
  for (const [left, right] of [[name, expected], [nameCore, expectedCore]]) {
    if (!left || !right) continue;
    const maxLength = Math.max(Array.from(left).length, Array.from(right).length);
    const minLength = Math.min(Array.from(left).length, Array.from(right).length);
    if (left.includes(right) || right.includes(left)) {
      score = Math.max(score, 75 + (20 * minLength) / maxLength);
    }
    const similarity = 1 - levenshteinDistance(left, right) / maxLength;
    score = Math.max(score, similarity * 85);
  }
  return Math.round(score * 10) / 10;
}

export function rankTemplatesByName(templates, query) {
  return templates
    .map((template) => ({
      template,
      score: scoreTemplateNameMatch(templateDisplayName(template), query),
    }))
    .filter((item) => item.score > 0)
    .sort((left, right) => (
      right.score - left.score
      || templateDisplayName(left.template).localeCompare(templateDisplayName(right.template), 'zh-CN')
    ));
}

export function normalizeTemplateListPayload(payload) {
  const data = payload?.data ?? payload;
  let items = [];
  if (Array.isArray(data)) items = data;
  else if (Array.isArray(data?.list)) items = data.list;
  else if (Array.isArray(data?.records)) items = data.records;
  else if (Array.isArray(data?.items)) items = data.items;
  else if (Array.isArray(data?.rows)) items = data.rows;

  const rawTotal = data?.total ?? payload?.total;
  const parsedTotal = Number(rawTotal);
  return {
    items,
    total: rawTotal !== undefined && Number.isFinite(parsedTotal) ? parsedTotal : undefined,
  };
}

export function findTemplateByName(templates, templateName) {
  const expected = String(templateName || '').trim();
  const normalizedExpected = normalizeTemplateName(expected);
  const ranked = rankTemplatesByName(templates, expected);
  const matches = ranked.filter((item) => item.score >= 60);
  if (!normalizedExpected || matches.length === 0) {
    throw new Error(`未找到模板：${expected}。请先执行 templates:list --keyword "${expected}" 查看可用模板`);
  }

  const topScore = matches[0].score;
  const topMatches = matches.filter((item) => item.score === topScore);
  const isStrongUniqueMatch = topScore >= 95 && topMatches.length === 1;
  const isClearlyAhead = matches.length === 1 || topScore - matches[1].score >= 8;
  if (!isStrongUniqueMatch && !isClearlyAhead) {
    const choices = matches
      .slice(0, 10)
      .map(({ template, score }) => (
        `${templateBusinessId(template)}: ${templateDisplayName(template)}（匹配度 ${score}）`
      ))
      .join('\n');
    throw new Error(`匹配到多个相近模板：${expected}\n${choices}\n请改用 --template-id 明确指定`);
  }
  const matched = matches[0].template;
  const templateId = String(templateBusinessId(matched)).trim();
  if (!templateId) throw new Error(`模板「${expected}」缺少业务模板 ID`);
  return matched;
}

export function summarizeTemplates(templates) {
  return templates.map((template) => ({
    templateId: templateBusinessId(template),
    templateName: templateDisplayName(template),
    templateModuleType: template.templateModuleTypeText || template.templateModuleType || '',
    typeCode: template.typeCode || template.templateCode || '',
    status: template.statusText || template.status || '',
    permission: template.permissionTypeText || template.permissionType || '',
    updateTime: template.updateTime || template.updatedAt || '',
  }));
}

export async function listTemplates({
  page = 1,
  pageSize = 100,
  templateModuleType = '',
} = {}, config) {
  const response = await apiRequest(
    buildTemplateListPath({ page, pageSize, templateModuleType }),
    { config },
  );
  if (!response || (response.code !== undefined && ![0, 200].includes(Number(response.code)))) {
    throw new Error(response?.msg || '获取模板列表失败');
  }
  return normalizeTemplateListPayload(response);
}

export async function listAllTemplates(config, {
  pageSize = 100,
  templateModuleType = '',
  maxPages = 100,
} = {}) {
  const all = [];
  for (let page = 1; page <= maxPages; page += 1) {
    const result = await listTemplates({ page, pageSize, templateModuleType }, config);
    all.push(...result.items);

    const reachedTotal = result.total !== undefined && all.length >= result.total;
    const exhaustedWithoutTotal = result.total === undefined && result.items.length < pageSize;
    if (reachedTotal || result.items.length === 0 || exhaustedWithoutTotal) return all;
  }
  throw new Error(`模板列表超过 ${maxPages} 页，已停止查询；请改用 --template-id 明确指定`);
}

export async function resolveTemplateByName(templateName, config) {
  const expected = String(templateName || '').trim();
  if (!expected) throw new Error('模板名称不能为空');
  const templates = await listAllTemplates(config);
  const template = findTemplateByName(templates, expected);
  return {
    templateId: String(templateBusinessId(template)),
    templateName: templateDisplayName(template),
    template,
  };
}

export async function createCoursewareWithTemplate({ templateId, title = '新课件' }, config) {
  const response = await apiRequest(`v1/business/creator/courseware/create-with-template`, {
    method: 'POST',
    config,
    json: true,
    body: { title, templateId },
  });
  const result = response?.data ?? response;
  if (!result?.coursewareId) {
    throw new Error(result?.error || result?.msg || '从模板创建课件失败');
  }
  return result;
}

export async function listFlowTasks({ page = 1, pageSize = 20, batchNo, status } = {}, config) {
  const params = new URLSearchParams();
  params.set('page', String(page));
  params.set('pageSize', String(pageSize));
  if (batchNo) params.set('batchNo', batchNo);
  if (status) params.set('status', status);
  const response = await apiRequest(`v1/creator/courseware/flow/tasks?${params.toString()}`, { config });
  const data = response?.data ?? response;
  if (Array.isArray(data)) return data;
  return data?.items || data?.list || data?.records || data?.rows || [];
}

export async function getFlowTask(taskId, config) {
  const response = await apiRequest(`v1/creator/courseware/flow/${encodeURIComponent(taskId)}`, { config });
  return response?.data ?? response;
}

export async function fetchTemplateComponents(templateId, config) {
  const response = await apiRequest(
    `v1/business/creator/template/${encodeURIComponent(templateId)}/components`,
    { config },
  );
  if (!response || ![0, 200].includes(Number(response.code))) {
    throw new Error(response?.msg || '获取模板组件列表失败');
  }
  const raw = Array.isArray(response.data) ? response.data : [];
  return raw.map((item) => ({
    componentKeyId: item.componentId,
    componentType: item.componentType,
    name: item.name,
    compositionMode: item.compositionMode === 'page' ? 'page' : 'block',
  }));
}

export async function fetchComponentDetail(componentKeyId, config) {
  const response = await apiRequest(
    `v1/business/creator/component/${encodeURIComponent(componentKeyId)}`,
    { config },
  );
  if (!response || ![0, 200].includes(Number(response.code))) {
    throw new Error(response?.msg || '获取组件详情失败');
  }
  return response.data || null;
}
