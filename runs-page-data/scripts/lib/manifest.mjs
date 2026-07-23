/**
 * 资产清单：本地素材路径 → 已上传的 public_url / fsFileId 映射。
 *
 * 清单是幂等的关键：条目按「清单文件所在目录的相对路径」为 key，并记录内容 sha256，
 * 重跑时同路径同内容直接跳过上传；内容变了会重新上传并覆盖条目。
 */
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { dirname, relative, resolve, basename, sep } from 'node:path';

export const MANIFEST_VERSION = 1;

export function createManifest({ baseUrl = '' } = {}) {
  return { version: MANIFEST_VERSION, baseUrl, assets: {} };
}

export function hashBytes(bytes) {
  return createHash('sha256').update(bytes).digest('hex');
}

/** 统一用 posix 分隔符做 key，保证 macOS / Windows 生成的清单可互换。 */
export function toManifestKey(manifestPath, filePath) {
  const rel = relative(dirname(resolve(manifestPath)), resolve(filePath));
  return rel.split(sep).join('/');
}

export async function readManifest(manifestPath) {
  try {
    const raw = await readFile(manifestPath, 'utf8');
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || typeof parsed.assets !== 'object' || parsed.assets === null) {
      throw new Error('清单结构非法：缺少 assets 对象');
    }
    return { version: parsed.version ?? MANIFEST_VERSION, baseUrl: parsed.baseUrl || '', assets: parsed.assets };
  } catch (err) {
    if (err && err.code === 'ENOENT') return null;
    throw err;
  }
}

export async function writeManifest(manifestPath, manifest) {
  const sorted = Object.keys(manifest.assets).sort();
  const assets = {};
  for (const key of sorted) assets[key] = manifest.assets[key];
  await writeFile(manifestPath, `${JSON.stringify({ ...manifest, assets }, null, 2)}\n`, 'utf8');
}

export function upsertAsset(manifest, key, entry) {
  return { ...manifest, assets: { ...manifest.assets, [key]: { key, ...entry } } };
}

/** 已上传且内容未变 → 可跳过。 */
export function isUploaded(manifest, key, sha256) {
  const entry = manifest.assets[key];
  return Boolean(entry?.url) && entry.sha256 === sha256;
}

/**
 * 按引用查条目，依次尝试：完整 key → 去掉 ./ 前缀的 key → 文件名。
 * 文件名命中多条时返回 null 并标记 ambiguous，交由调用方报错，避免选错素材。
 */
export function findAsset(manifest, ref) {
  const direct = manifest.assets[ref];
  if (direct) return { entry: direct, ambiguous: false };

  const stripped = ref.replace(/^\.\//, '');
  if (manifest.assets[stripped]) return { entry: manifest.assets[stripped], ambiguous: false };

  const name = basename(ref);
  const matches = Object.values(manifest.assets).filter((entry) => basename(entry.key) === name);
  if (matches.length === 1) return { entry: matches[0], ambiguous: false };
  if (matches.length > 1) return { entry: null, ambiguous: true, candidates: matches.map((m) => m.key) };
  return { entry: null, ambiguous: false };
}

export function summarizeManifest(manifest) {
  const entries = Object.values(manifest.assets);
  const byCategory = {};
  for (const entry of entries) {
    byCategory[entry.category || 'other'] = (byCategory[entry.category || 'other'] || 0) + 1;
  }
  return { total: entries.length, byCategory };
}
