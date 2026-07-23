/**
 * 占位符解析：把页面 JSON 里的本地素材引用替换成已上传的 public_url。
 *
 * 识别为素材引用的字符串形态（其余字符串一律不动，避免误伤正文）：
 * - `@asset:assets/p1.png`  推荐写法，显式且不会与正文混淆
 * - `./assets/p1.png` / `../a.mp3`  相对路径
 * - `file:///abs/path.png`  本地绝对路径
 */
import { fileURLToPath } from 'node:url';

const ASSET_PREFIX = '@asset:';

export function isAssetRef(value) {
  if (typeof value !== 'string') return false;
  const trimmed = value.trim();
  if (trimmed === '') return false;
  return trimmed.startsWith(ASSET_PREFIX)
    || trimmed.startsWith('./')
    || trimmed.startsWith('../')
    || trimmed.startsWith('file://');
}

/** 归一化为「相对清单的路径」形态，供 findAsset 查表与本地读盘复用。 */
export function normalizeAssetRef(value) {
  const trimmed = String(value).trim();
  if (trimmed.startsWith(ASSET_PREFIX)) return trimmed.slice(ASSET_PREFIX.length).trim();
  if (trimmed.startsWith('file://')) return fileURLToPath(trimmed);
  return trimmed;
}

/** 深度遍历，收集所有素材引用及其 JSON 路径。 */
export function collectAssetRefs(node, path = '', found = []) {
  if (typeof node === 'string') {
    if (isAssetRef(node)) found.push({ path, raw: node, ref: normalizeAssetRef(node) });
    return found;
  }
  if (Array.isArray(node)) {
    node.forEach((item, index) => collectAssetRefs(item, `${path}[${index}]`, found));
    return found;
  }
  if (node && typeof node === 'object') {
    for (const [key, value] of Object.entries(node)) {
      collectAssetRefs(value, path ? `${path}.${key}` : key, found);
    }
  }
  return found;
}

/**
 * 用 resolver 替换所有素材引用，返回新对象（不修改入参）。
 * resolver(ref) 返回 url 时替换；返回空值时保留原字符串并记入 unresolved。
 */
export function applyAssetResolutions(node, resolver, path = '', state = { replaced: [], unresolved: [] }) {
  if (typeof node === 'string') {
    if (!isAssetRef(node)) return { value: node, state };
    const ref = normalizeAssetRef(node);
    const url = resolver(ref, path);
    if (url) {
      state.replaced.push({ path, ref, url });
      return { value: url, state };
    }
    state.unresolved.push({ path, ref, raw: node });
    return { value: node, state };
  }

  if (Array.isArray(node)) {
    const value = node.map((item, index) => applyAssetResolutions(item, resolver, `${path}[${index}]`, state).value);
    return { value, state };
  }

  if (node && typeof node === 'object') {
    const value = {};
    for (const [key, item] of Object.entries(node)) {
      value[key] = applyAssetResolutions(item, resolver, path ? `${path}.${key}` : key, state).value;
    }
    return { value, state };
  }

  return { value: node, state };
}

/** 提交前的兜底检查：JSON 里不允许残留任何本地引用。 */
export function findResidualLocalRefs(doc) {
  return collectAssetRefs(doc);
}
