/**
 * 已有课件的「读—改—写」纯逻辑：链接解析、版本可写性判定、页面合并、保存载荷组装。
 *
 * 这里不发任何请求，全部可单测；HTTP 调用在 client.mjs，编排在 pagedata.mjs。
 * 契约对齐 business#80（前端 frontend/app/components/creator/save/courseware-save-contract.ts
 * 与 creator/src/clients/business-client.ts）：保存永远是 UPDATE_VERSION + 完整页面快照 + CAS。
 */

/** 页面身份字段：属于保存请求的外层，不能混进 pageData。 */
export const PAGE_IDENTITY_FIELDS = [
  'pageId',
  'pageKey',
  'pageNumber',
  'renderType',
  'coursewareId',
  'coursewareVersionId',
];

const ID_PATTERN = /^[A-Za-z0-9_-]+$/;

const isPlainObject = (value) => Boolean(value) && typeof value === 'object' && !Array.isArray(value);

/**
 * 从预览链接或裸 ID 解析目标课件。
 * 支持 `https://web.dev.xruns.cn/creator/<coursewareId>[/<versionId>]`、`creator/<id>` 片段和裸 ID。
 * 链接第二段是精确 versionId（版本记录主键），不是 V1/V2 这种版本号。
 */
export function parseCoursewareRef(input) {
  const raw = String(input ?? '').trim();
  if (!raw) throw new Error('缺少课件链接或课件 ID');

  const withoutQuery = raw.split(/[?#]/)[0];
  const isUrl = /^https?:\/\//i.test(withoutQuery);
  const path = isUrl ? withoutQuery.replace(/^https?:\/\/[^/]+/i, '') : withoutQuery;
  const segments = path.split('/').filter(Boolean);
  const creatorAt = segments.lastIndexOf('creator');

  if (creatorAt === -1 && (isUrl || segments.length > 2)) {
    throw new Error(`无法从「${raw}」解析课件 ID，请给出 /creator/<coursewareId> 形式的链接或裸 ID`);
  }
  const rest = creatorAt === -1 ? segments : segments.slice(creatorAt + 1);
  const [coursewareId, versionId] = rest.map((item) => decodeURIComponent(item));

  if (!coursewareId || !ID_PATTERN.test(coursewareId)) {
    throw new Error(`课件 ID 不合法：${coursewareId || '(空)'}`);
  }
  if (versionId !== undefined && !ID_PATTERN.test(versionId)) {
    throw new Error(`版本 ID 不合法：${versionId}`);
  }
  return versionId ? { coursewareId, versionId } : { coursewareId };
}

function optionalIdentity(value) {
  if (value === null || value === undefined) return undefined;
  if (typeof value !== 'string' && typeof value !== 'number' && typeof value !== 'bigint') return undefined;
  const normalized = String(value).trim();
  return normalized || undefined;
}

function normalizeBoolean(value) {
  if (value === true || value === 1 || value === '1' || value === 'true') return true;
  if (value === false || value === 0 || value === '0' || value === 'false') return false;
  return undefined;
}

/** 统一课件详情 / 保存响应里的版本身份字段（bigint 跨 JSON 边界一律按字符串处理）。 */
export function normalizeCoursewareVersion(value) {
  const source = isPlainObject(value) ? value : {};
  const version = {
    versionId: optionalIdentity(source.id ?? source.versionId),
    coursewareId: optionalIdentity(source.coursewareId),
    version: optionalIdentity(source.version),
    revision: optionalIdentity(source.revision),
    status: typeof source.status === 'string' ? source.status : undefined,
    isPublished: normalizeBoolean(source.isPublished),
    isCurrentVersion: normalizeBoolean(source.isCurrentVersion),
    updateTime: typeof source.updateTime === 'string' ? source.updateTime : undefined,
  };
  return Object.fromEntries(Object.entries(version).filter(([, item]) => item !== undefined));
}

function isPublishedVersion(version) {
  if (version.isPublished === true) return true;
  return typeof version.status === 'string' && version.status.trim().toUpperCase() === 'PUBLISHED';
}

// status 缺失按 DRAFT 处理：兼容期旧响应不带该字段，按「非 DRAFT 即只读」会把所有课件判成不可改。
function isDraftStatus(status) {
  if (status === undefined || status === null || status === '') return true;
  return typeof status === 'string' && status.trim().toUpperCase() === 'DRAFT';
}

/**
 * 版本可写性。唯一谓词与前端 version-editability.ts 一致：
 * `isCurrentVersion === true && status === "DRAFT" && isPublished !== true`。
 *
 * 三个字段整体缺失时返回 editable + reason=unknown（兼容期旧响应），真正的守卫是服务端
 * 40903 / 40904；缺 versionId 则无法定位写入目标，直接判不可写。
 */
export function resolveVersionEditability(version) {
  const snapshot = isPlainObject(version) ? version : {};
  if (!snapshot.versionId) {
    return { editable: false, reason: 'no-identity' };
  }
  if (isPublishedVersion(snapshot)) return { editable: false, reason: 'published' };
  if (snapshot.isCurrentVersion === false) return { editable: false, reason: 'historical' };
  if (!isDraftStatus(snapshot.status)) return { editable: false, reason: 'historical' };
  if (
    snapshot.isCurrentVersion === undefined
    && snapshot.status === undefined
    && snapshot.isPublished === undefined
  ) {
    return { editable: true, reason: 'unknown' };
  }
  return { editable: true, reason: 'editable' };
}

export const VERSION_REASON_LABELS = {
  editable: '当前工作版本，可直接更新',
  unknown: '服务端未返回版本状态字段，按可更新处理（真正的守卫是服务端 CAS）',
  published: '该版本已发布，不可修改',
  historical: '该版本不是当前工作版本（历史版本），不可修改',
  'no-identity': '课件详情里没有精确版本 ID，无法定位写入目标',
};

/** 一行版本摘要，预览与结果都用它，避免各处自己拼。 */
export function describeVersion(version) {
  const parts = [
    version.version ? `V${version.version}` : 'V?',
    version.versionId ? `versionId=${version.versionId}` : 'versionId=?',
    `revision=${version.revision ?? '?'}`,
    `status=${version.status ?? '?'}`,
  ];
  if (version.isPublished === true) parts.push('已发布');
  if (version.isCurrentVersion === false) parts.push('非当前版本');
  return parts.join(' ');
}

function parsePageData(raw) {
  if (typeof raw === 'string') {
    if (!raw.trim()) return {};
    try {
      const parsed = JSON.parse(raw);
      return isPlainObject(parsed) ? parsed : {};
    } catch (err) {
      throw new Error(`pageData 解析失败：${err instanceof Error ? err.message : String(err)}`);
    }
  }
  return isPlainObject(raw) ? raw : {};
}

/** 读取接口带回的 renderType 归一化：只认 component / html。 */
export function normalizeRenderType(value) {
  return value === 'component' || value === 'html' ? value : undefined;
}

/**
 * 把课件详情的 pages[] 摊平成本地可编辑的页面对象：pageData 展开到顶层，
 * 再挂上 pageId / pageNumber / renderType 三个身份字段（保存时会被剥离）。
 * 已生成内容（pageData.output、tts_url 等）原样保留，回写时才不会被抹掉。
 */
export function pagesFromDetail(detail) {
  const raw = Array.isArray(detail?.pages) ? detail.pages : [];
  return raw.map((item, index) => {
    const pageData = parsePageData(item?.pageData);
    const pageId = optionalIdentity(item?.pageId);
    const renderType = normalizeRenderType(item?.renderType);
    return {
      ...pageData,
      title: typeof pageData.title === 'string' ? pageData.title : (item?.title ?? ''),
      ...(pageId ? { pageId } : {}),
      pageNumber: Number(item?.pageNumber) || index + 1,
      ...(renderType ? { renderType } : {}),
    };
  });
}

/** 课件详情 → 顶层导入结构（与 pages:validate / pages:resolve 吃的形态一致）。 */
export function docFromDetail(detail) {
  return {
    title: typeof detail?.title === 'string' ? detail.title : '',
    pages: pagesFromDetail(detail),
  };
}

/** componentType → 组合级别；缺失或未知值兜底 block，与前端、creator 一致。 */
export function buildCompositionModeMap(templateComponents) {
  const map = new Map();
  for (const item of Array.isArray(templateComponents) ? templateComponents : []) {
    if (!item?.componentType) continue;
    map.set(item.componentType, item.compositionMode === 'page' ? 'page' : 'block');
  }
  return map;
}

/** 含 page 级组件 → component；只有 block → html；空页返回 undefined（由业务侧定默认值）。 */
export function derivePageRenderType(components, modeByType) {
  if (!Array.isArray(components) || components.length === 0) return undefined;
  const hasPageComponent = components.some(
    (item) => typeof item?.type === 'string' && modeByType.get(item.type) === 'page',
  );
  return hasPageComponent ? 'component' : 'html';
}

function stripIdentity(page) {
  const content = { ...page };
  for (const field of PAGE_IDENTITY_FIELDS) delete content[field];
  return content;
}

function locateServerPage(patch, index, { byPageId, byPageNumber }) {
  const pageId = optionalIdentity(patch?.pageId);
  if (pageId) {
    const hit = byPageId.get(pageId);
    if (!hit) throw new Error(`补丁 pages[${index}] 的 pageId=${pageId} 在服务端不存在`);
    return hit;
  }
  const pageNumber = Number(patch?.pageNumber);
  if (Number.isInteger(pageNumber) && pageNumber > 0) {
    return byPageNumber.get(pageNumber) ?? null;
  }
  return null;
}

/**
 * 把补丁页合并到服务端页面快照上。
 *
 * 两种模式只在「页集合与顺序」上不同，合并规则完全一样：
 * - 默认（patch）：结果 = 服务端全部页面、顺序不变，只有被匹配到的页被覆盖；不允许增删页；
 * - `--replace`：结果的集合与顺序 = 补丁文件，未出现的页会被删除，没匹配上的补丁页是新增页。
 *
 * 合并只在顶层字段：补丁里出现的键覆盖，没出现的键保留服务端值（output / tts_url 因此不会被抹掉）；
 * components 作为整个数组替换，不做逐组件深合并。
 *
 * 定位一律靠 pageId → pageNumber，不做隐式按位置匹配：插入一页就会整体错位，
 * 让新页悄悄继承别人的 output 是最难查的一类事故。
 */
export function mergePatchPages(serverPages, patchPages, { replace = false } = {}) {
  const base = Array.isArray(serverPages) ? serverPages : [];
  const patches = Array.isArray(patchPages) ? patchPages : [];
  if (patches.length === 0) throw new Error('补丁 JSON 的 pages 为空，没有任何可应用的改动');

  const byPageId = new Map();
  const byPageNumber = new Map();
  base.forEach((page, index) => {
    const pageId = optionalIdentity(page?.pageId);
    if (pageId) byPageId.set(pageId, page);
    byPageNumber.set(Number(page?.pageNumber) || index + 1, page);
  });

  const matched = new Map();
  const claim = (target, index) => {
    if (!target) return;
    const previous = matched.get(target);
    if (previous !== undefined) {
      throw new Error(`补丁 pages[${index}] 与 pages[${previous}] 命中了同一页，无法判断以哪一份为准`);
    }
    matched.set(target, index);
  };

  const resolved = patches.map((patch, index) => {
    if (!isPlainObject(patch)) throw new Error(`补丁 pages[${index}] 应为对象`);
    const target = locateServerPage(patch, index, { byPageId, byPageNumber });
    claim(target, index);
    return { patch, target };
  });

  if (!replace) {
    const orphan = resolved.findIndex((item) => !item.target);
    if (orphan !== -1) {
      throw new Error(
        `补丁 pages[${orphan}] 没有匹配到服务端页面（缺 pageId / pageNumber）；`
        + '默认模式只能改已有页，新增、删除或调整页序请改用 --replace 提交完整页面列表',
      );
    }
  }

  const changes = [];
  const mergeOne = (patch, target, pageNumber) => {
    if (!target) {
      changes.push({ status: 'added', pageNumber, title: patch.title ?? '' });
      return { ...patch, pageNumber };
    }
    const merged = { ...target, ...patch, pageNumber };
    const contentChanged = JSON.stringify(stripIdentity(target)) !== JSON.stringify(stripIdentity(merged));
    const moved = (Number(target.pageNumber) || 0) !== pageNumber;
    changes.push({
      status: contentChanged ? 'updated' : (moved ? 'moved' : 'unchanged'),
      pageNumber,
      pageId: optionalIdentity(target.pageId),
      title: merged.title ?? '',
      ...(moved ? { fromPageNumber: Number(target.pageNumber) || undefined } : {}),
    });
    return merged;
  };

  let pages;
  if (replace) {
    pages = resolved.map((item, index) => mergeOne(item.patch, item.target, index + 1));
    base.forEach((page, index) => {
      if (matched.has(page)) return;
      changes.push({
        status: 'removed',
        pageNumber: Number(page?.pageNumber) || index + 1,
        pageId: optionalIdentity(page?.pageId),
        title: page?.title ?? '',
      });
    });
  } else {
    const patchByTarget = new Map(resolved.map((item) => [item.target, item.patch]));
    pages = base.map((page, index) => {
      const patch = patchByTarget.get(page);
      const pageNumber = index + 1;
      if (!patch) {
        changes.push({
          status: 'unchanged',
          pageNumber,
          pageId: optionalIdentity(page?.pageId),
          title: page?.title ?? '',
        });
        return { ...page, pageNumber };
      }
      return mergeOne(patch, page, pageNumber);
    });
  }

  changes.sort((left, right) => left.pageNumber - right.pageNumber);
  return { pages, changes };
}

/**
 * fork 之后把补丁里的 pageId 换成新版本对应页的 pageId。
 *
 * rollback 是「克隆成新版本」，页面是新行、pageId 全变；补丁却是照着源版本写的。
 * 克隆保持页序 1:1，因此按位置换算是安全的；页数对不上说明拿到的不是那份克隆，必须停手。
 */
export function rebasePatchPages(patchPages, sourcePages, targetPages) {
  const source = Array.isArray(sourcePages) ? sourcePages : [];
  const target = Array.isArray(targetPages) ? targetPages : [];
  if (source.length !== target.length) {
    throw new Error(
      `新版本页数（${target.length}）与源版本（${source.length}）不一致，无法安全对应 pageId，请重新 pull 后再改`,
    );
  }

  const indexByPageId = new Map();
  source.forEach((page, index) => {
    const pageId = optionalIdentity(page?.pageId);
    if (pageId) indexByPageId.set(pageId, index);
  });

  return (Array.isArray(patchPages) ? patchPages : []).map((patch, patchIndex) => {
    const pageId = optionalIdentity(patch?.pageId);
    if (!pageId) return patch;
    const index = indexByPageId.get(pageId);
    if (index === undefined) {
      throw new Error(`补丁 pages[${patchIndex}] 的 pageId=${pageId} 在源版本中不存在`);
    }
    const rebasedId = optionalIdentity(target[index]?.pageId);
    if (!rebasedId) throw new Error(`新版本第 ${index + 1} 页缺少 pageId，无法对应补丁改动`);
    return { ...patch, pageId: rebasedId };
  });
}

/** 变更计数，供预览与最终报告使用。 */
export function summarizeChanges(changes) {
  const summary = { updated: 0, added: 0, removed: 0, moved: 0, unchanged: 0 };
  for (const item of changes) {
    if (summary[item.status] !== undefined) summary[item.status] += 1;
  }
  return summary;
}

/** 有实际写入意义的改动（unchanged 不算）。 */
export function hasEffectiveChanges(changes) {
  return changes.some((item) => item.status !== 'unchanged');
}

/** 一次业务保存动作一个 requestId；内容变了必须换新值，只有网络重试才复用。 */
export function createRequestId() {
  const cryptoApi = globalThis.crypto;
  if (cryptoApi && typeof cryptoApi.randomUUID === 'function') return cryptoApi.randomUUID();
  return `req-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * 组装 `POST v1/business/creator/courseware/save` 的 UPDATE_VERSION 请求体。
 *
 * pages 是**完整快照**：缺页 = 删页。已持久化的页用 pageId 兼作 pageKey（与 creator worker 一致），
 * 新增页按页序派生 `page-N`。
 */
export function buildSavePayload({
  coursewareId,
  targetVersionId,
  expectedRevision,
  requestId,
  pages,
  title,
  modeByType,
}) {
  if (!coursewareId) throw new Error('缺少 coursewareId');
  if (!targetVersionId) throw new Error('缺少 targetVersionId');
  if (expectedRevision === undefined || expectedRevision === null || expectedRevision === '') {
    throw new Error('缺少 expectedRevision');
  }
  if (!requestId) throw new Error('缺少 requestId');
  if (!Array.isArray(pages) || pages.length === 0) throw new Error('pages 不能为空');

  const seen = new Set();
  const payloadPages = pages.map((page, index) => {
    const pageId = optionalIdentity(page?.pageId);
    const pageKey = pageId || `page-${index + 1}`;
    if (seen.has(pageKey)) throw new Error(`pageKey 重复：${pageKey}`);
    seen.add(pageKey);

    const derived = modeByType ? derivePageRenderType(page?.components, modeByType) : undefined;
    // 派生不出来（空页 / 没有模板上下文）就透传原有 renderType，避免被业务侧默认值重置成 html
    const renderType = derived ?? normalizeRenderType(page?.renderType);

    return {
      pageKey,
      ...(pageId ? { pageId } : {}),
      pageNumber: index + 1,
      title: typeof page?.title === 'string' ? page.title : '',
      pageData: stripIdentity(page ?? {}),
      ...(renderType ? { renderType } : {}),
    };
  });

  return {
    operation: 'UPDATE_VERSION',
    coursewareId: String(coursewareId),
    targetVersionId: String(targetVersionId),
    expectedRevision: String(expectedRevision),
    requestId,
    pages: payloadPages,
    ...(typeof title === 'string' && title.trim() ? { title: title.trim() } : {}),
  };
}

/** 校验报告里 `pages[3].components[0]` 这类路径属于第几页；取不到返回 null。 */
export function pageIndexFromPath(path) {
  const match = /^pages\[(\d+)\]/.exec(String(path ?? ''));
  return match ? Number(match[1]) : null;
}

/**
 * 按「这一页这次改没改」拆分校验结果。
 *
 * 存量课件里常有早于当前模板契约的历史页面，把它们的错误也算作阻断，会导致
 * 「只想改第 3 页文案」永远保存不了；但它们仍要出现在报告里（降级为告警）。
 * 页外错误（title / pages 等顶层问题）一律阻断。
 */
export function splitReportByChangedPages(report, changes) {
  const changedIndexes = new Set(
    changes.filter((item) => item.status !== 'unchanged' && item.status !== 'removed')
      .map((item) => item.pageNumber - 1),
  );
  const split = (items) => {
    const touched = [];
    const untouched = [];
    for (const item of Array.isArray(items) ? items : []) {
      const index = pageIndexFromPath(item.path);
      if (index === null || changedIndexes.has(index)) touched.push(item);
      else untouched.push(item);
    }
    return { touched, untouched };
  };

  const errors = split(report?.errors);
  const warnings = split(report?.warnings);
  return {
    blocking: errors.touched,
    untouched: errors.untouched,
    warnings: warnings.touched,
    untouchedWarnings: warnings.untouched,
  };
}
