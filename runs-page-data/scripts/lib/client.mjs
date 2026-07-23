/**
 * RunS 网关客户端：鉴权、OSS 直传、文件落库、课件任务。
 *
 * 与 scripts/runs-courseware/cli.mjs 保持同一套接入约定（BASE_URL / clientid /
 * Bearer token / 三步上传），但本文件自带实现，不依赖该 CLI，便于 skill 整体拷贝复用。
 */
import { readFile } from 'node:fs/promises';
import { basename, extname } from 'node:path';

export const DEFAULT_BASE_URL = 'https://web.dev.xruns.cn';
export const DEFAULT_CLIENT_ID = '428a8310cd442757ae699df5d894f051';

/** 上传凭证有效期只有 60s，因此每个文件都在上传前现取凭证，不做批量预取。 */
export const UPLOAD_TOKEN_PATH = 'v1/ai/fs/uploads/token';
export const FILE_COMMIT_PATH = 'v1/ai/fs/files/commit';
export const FLOW_TASK_PATH = 'v1/creator/courseware/flow/task';

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
  const raw = input || DEFAULT_BASE_URL;
  const withoutApi = raw.replace(/\/api\/?$/i, '').replace(/\/api\/.*$/i, '');
  return withoutApi.endsWith('/') ? withoutApi : `${withoutApi}/`;
}

export function buildCoursewareUrl({ siteUrl = DEFAULT_BASE_URL, coursewareId }) {
  if (!coursewareId) return '';
  return `${normalizeSiteUrl(siteUrl)}creator/${encodeURIComponent(coursewareId)}`;
}

export function getRuntimeConfig(args = {}) {
  return {
    baseUrl: normalizeBaseUrl(
      args['base-url'] || process.env.XRUNS_COURSEWARE_BASE_URL || process.env.XRUNS_BASE_URL,
    ),
    siteUrl: normalizeSiteUrl(
      args['base-url'] || process.env.XRUNS_COURSEWARE_BASE_URL || process.env.XRUNS_BASE_URL,
    ),
    token: args.token || process.env.XRUNS_COURSEWARE_TOKEN || process.env.XRUNS_TOKEN || '',
    clientId: args.clientid || args['client-id'] || process.env.XRUNS_COURSEWARE_CLIENT_ID || DEFAULT_CLIENT_ID,
    username: args.username || process.env.XRUNS_COURSEWARE_USERNAME || process.env.XRUNS_USERNAME || '',
    password: args.password || process.env.XRUNS_COURSEWARE_PASSWORD || process.env.XRUNS_PASSWORD || '',
  };
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
    throw new Error(
      '缺少 token：请传 --token，设置 XRUNS_COURSEWARE_TOKEN，或设置 XRUNS_COURSEWARE_USERNAME/XRUNS_COURSEWARE_PASSWORD',
    );
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
  const tokenResponse = await apiRequest(UPLOAD_TOKEN_PATH, {
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
  const response = await apiRequest(FILE_COMMIT_PATH, {
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
  const response = await apiRequest(FLOW_TASK_PATH, { method: 'POST', config, json: true, body: payload });
  const result = response?.data ?? response;
  if (!result?.taskId) {
    throw new Error(result?.error || result?.msg || '启动课件任务失败');
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
