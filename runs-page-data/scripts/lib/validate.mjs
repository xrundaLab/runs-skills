/**
 * 页面 JSON 校验。
 *
 * 分两层：
 * 1. 顶层导入结构（title / pages[] / components[]）+ page 级组件独占整页规则；
 * 2. 组件 content 结构：必须以模板组件接口为唯一来源，并按组件详情 dataStructure
 *    校验字段与容器结构完整性。
 *
 * errors 阻断提交，warnings 只提示（例如缺 tag、componentId 重复）。
 */

const typeLabel = (value) => {
  if (value === null) return 'null';
  if (Array.isArray(value)) return '数组';
  switch (typeof value) {
    case 'string': return '字符串';
    case 'number': return '数字';
    case 'boolean': return '布尔值';
    case 'object': return '对象';
    case 'undefined': return '缺失';
    default: return typeof value;
  }
};

function createReport() {
  const errors = [];
  const warnings = [];
  return {
    errors,
    warnings,
    error(path, message) { errors.push({ path, message }); },
    warn(path, message) { warnings.push({ path, message }); },
  };
}

const isPlainObject = (value) => Boolean(value) && typeof value === 'object' && !Array.isArray(value);

/**
 * 按模板 dataStructure 做结构完整性比对：
 * - 对象必须包含示例中的全部字段，额外字段放行；
 * - 数组保持数组形态，示例非空时实际数组也必须非空，并逐项检查条目结构；
 * - 标量只要求仍是标量，字符串 / 数字 / 布尔值之间不做语义或精确类型限制；
 * - 示例为 null 时只要求字段存在，不限制值。
 *
 * 返回第一条错误或 null。
 */
export function validateJsonAgainstExample(example, value, path = '') {
  const label = path || '根节点';

  if (example === null || example === undefined) {
    return value === undefined ? `${label}：字段缺失` : null;
  }

  if (Array.isArray(example)) {
    if (!Array.isArray(value)) return `${label}：应为数组，实际是${typeLabel(value)}`;
    if (example.length === 0) return null;
    if (value.length === 0) return `${label}：数组不能为空`;
    for (let i = 0; i < value.length; i += 1) {
      const err = validateJsonAgainstExample(example[0], value[i], `${path}[${i}]`);
      if (err) return err;
    }
    return null;
  }

  if (typeof example === 'object') {
    if (!isPlainObject(value)) return `${label}：应为对象，实际是${typeLabel(value)}`;
    for (const key of Object.keys(example)) {
      const childPath = path ? `${path}.${key}` : key;
      if (!(key in value)) return `${childPath}：字段缺失`;
      const err = validateJsonAgainstExample(example[key], value[key], childPath);
      if (err) return err;
    }
    return null;
  }

  if (value === undefined) return `${label}：字段缺失`;
  if (value !== null && typeof value === 'object') {
    return `${label}：应为标量，实际是${typeLabel(value)}`;
  }
  return null;
}

/** 从 dataStructure 示例中取出指定组件的 content 示例（示例常为页面级结构）。 */
export function extractComponentContentExample(example, componentType) {
  if (!isPlainObject(example)) return example;

  const components = example.components;
  if (Array.isArray(components) && components.length > 0) {
    const hit = components.find((item) => item?.type === componentType) ?? components[0];
    if (isPlainObject(hit) && 'content' in hit) return hit.content;
  }
  if ('content' in example && typeof example.type === 'string') return example.content;
  return example;
}

function validateComponent(component, path, report, options) {
  if (!isPlainObject(component)) {
    report.error(path, `组件应为对象，实际是${typeLabel(component)}`);
    return null;
  }

  const type = component.type;
  if (typeof type !== 'string' || type.trim() === '') {
    report.error(`${path}.type`, '组件缺少 type');
    return null;
  }

  if (component.componentId !== undefined && typeof component.componentId !== 'string') {
    report.error(`${path}.componentId`, `类型应为字符串，实际是${typeLabel(component.componentId)}`);
  }

  const templateComponent = options.templateComponentByType.get(type);
  if (!templateComponent) {
    report.error(`${path}.type`, `模板未配置该组件类型：${type}`);
    return type;
  }

  const example = options.componentExamples?.[type];
  if (example === undefined) {
    report.error(
      `${path}.content`,
      `模板组件 ${type} 未提供可解析的 dataStructure，无法校验 content 结构`,
    );
    return type;
  }

  const err = validateJsonAgainstExample(
    extractComponentContentExample(example, type),
    component.content,
    `${path}.content`,
  );
  if (err) report.error(`${path}.content`, `与模板 dataStructure 不一致：${err}`);

  return type;
}

function validatePage(page, path, report, options) {
  if (!isPlainObject(page)) {
    report.error(path, `页面应为对象，实际是${typeLabel(page)}`);
    return;
  }

  if (typeof page.title !== 'string' || page.title.trim() === '') {
    report.error(`${path}.title`, '页面缺少 title');
  }
  if (typeof page.tag !== 'string' || page.tag.trim() === '') {
    report.warn(`${path}.tag`, '建议填写页面分类标签 tag（如「课程导入」「知识讲解」）');
  }
  for (const key of ['summary', 'prompt']) {
    if (page[key] !== undefined && typeof page[key] !== 'string') {
      report.error(`${path}.${key}`, `类型应为字符串，实际是${typeLabel(page[key])}`);
    }
  }

  const components = page.components;
  if (components !== undefined && !Array.isArray(components)) {
    report.error(`${path}.components`, `类型应为数组，实际是${typeLabel(components)}`);
    return;
  }

  const list = Array.isArray(components) ? components : [];
  if (list.length === 0) {
    if (typeof page.prompt !== 'string' || page.prompt.trim() === '') {
      report.error(`${path}.prompt`, '无组件页必须提供 prompt，否则该页没有任何可生成内容');
    }
    return;
  }

  const types = list
    .map((component, index) => validateComponent(component, `${path}.components[${index}]`, report, options))
    .filter(Boolean);

  const pageLevel = types.filter(
    (type) => options.templateComponentByType.get(type)?.compositionMode === 'page',
  );
  if (pageLevel.length > 0 && types.length > 1) {
    report.error(
      `${path}.components`,
      `page 级组件独占整页：${pageLevel.join(' / ')} 不能与其他组件同页（当前 ${types.length} 个组件）`,
    );
  }
}

/**
 * 校验顶层导入 JSON。
 * options：
 * - templateComponents：模板组件接口结果，必须提供，是可用类型与 compositionMode 的唯一来源；
 * - componentExamples：{ [type]: dataStructure 示例 }，是组件 content 的唯一结构契约。
 */
export function validatePageData(doc, options = {}) {
  const report = createReport();
  const hasTemplateContext = Array.isArray(options.templateComponents);
  const templateComponentByType = new Map(
    hasTemplateContext
      ? options.templateComponents.map((item) => [item.componentType, item])
      : [],
  );
  const context = { ...options, templateComponentByType };

  if (!hasTemplateContext) {
    report.error('template', '组件校验必须提供模板组件接口结果，禁止使用本地兜底规格');
  }

  if (!isPlainObject(doc)) {
    report.error('', `顶层应为对象，实际是${typeLabel(doc)}`);
    return report;
  }

  if (typeof doc.title !== 'string' || doc.title.trim() === '') {
    report.error('title', '缺少课程标题 title');
  }
  if (doc.description !== undefined && typeof doc.description !== 'string') {
    report.error('description', `类型应为字符串，实际是${typeLabel(doc.description)}`);
  }

  if (!Array.isArray(doc.pages)) {
    report.error('pages', `类型应为数组，实际是${typeLabel(doc.pages)}`);
    return report;
  }
  if (doc.pages.length === 0) {
    report.error('pages', 'pages 不能为空');
    return report;
  }

  doc.pages.forEach((page, index) => validatePage(page, `pages[${index}]`, report, context));

  const seenIds = new Map();
  doc.pages.forEach((page, pageIndex) => {
    const list = Array.isArray(page?.components) ? page.components : [];
    list.forEach((component, componentIndex) => {
      const id = component?.componentId;
      if (typeof id !== 'string' || id === '') return;
      const at = `pages[${pageIndex}].components[${componentIndex}]`;
      if (seenIds.has(id)) {
        report.warn(at, `componentId 重复：${id}（已用于 ${seenIds.get(id)}）`);
      } else {
        seenIds.set(id, at);
      }
    });
  });

  return report;
}

export function formatReport(report) {
  const lines = [];
  for (const item of report.errors) {
    lines.push(`  ✗ ${item.path || '根节点'}：${item.message}`);
  }
  for (const item of report.warnings) {
    lines.push(`  ! ${item.path || '根节点'}：${item.message}`);
  }
  return lines.join('\n');
}
