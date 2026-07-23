/**
 * 页面 JSON 校验。
 *
 * 分两层：
 * 1. 顶层导入结构（title / pages[] / components[]）+ page 级组件独占整页规则；
 * 2. 组件 content 结构，默认用内置规格表，指定模板时叠加模板组件白名单与 dataStructure 示例比对。
 *
 * errors 阻断提交，warnings 只提示（例如音色不在推荐表内、缺 tag）。
 */
import {
  COMPONENT_SPECS,
  KNOWN_COMPONENT_TYPES,
  getCompositionMode,
} from './component-spec.mjs';

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

/** 判断值是否匹配描述子，用于 union 分支选择（不产出报错）。 */
function matchesDescriptor(descriptor, value) {
  if (!descriptor || descriptor.kind === 'any') return true;
  switch (descriptor.kind) {
    case 'string': return typeof value === 'string';
    case 'number': return typeof value === 'number';
    case 'boolean': return typeof value === 'boolean';
    case 'array': return Array.isArray(value);
    case 'object': return isPlainObject(value);
    case 'union': return descriptor.options.some((option) => matchesDescriptor(option, value));
    default: return true;
  }
}

export function validateAgainstDescriptor(descriptor, value, path, report) {
  if (!descriptor) return;

  if (value === undefined || value === null) {
    if (descriptor.required) report.error(path, '必填字段缺失');
    return;
  }

  switch (descriptor.kind) {
    case 'any':
      return;

    case 'union': {
      const matched = descriptor.options.find((option) => matchesDescriptor(option, value));
      if (!matched) {
        const kinds = descriptor.options.map((option) => option.kind).join(' | ');
        report.error(path, `类型应为 ${kinds}，实际是${typeLabel(value)}`);
        return;
      }
      validateAgainstDescriptor(matched, value, path, report);
      return;
    }

    case 'string':
    case 'number':
    case 'boolean': {
      if (typeof value !== descriptor.kind) {
        const expected = { string: '字符串', number: '数字', boolean: '布尔值' }[descriptor.kind];
        report.error(path, `类型应为${expected}，实际是${typeLabel(value)}`);
        return;
      }
      if (descriptor.required && descriptor.kind === 'string' && value.trim() === '') {
        report.error(path, '必填字段不能为空字符串');
        return;
      }
      if (descriptor.softValues && value !== '' && !descriptor.softValues.includes(value)) {
        report.warn(path, `取值 ${JSON.stringify(value)} 不在推荐枚举内：${descriptor.softValues.join(' / ')}`);
      }
      return;
    }

    case 'array': {
      if (!Array.isArray(value)) {
        report.error(path, `类型应为数组，实际是${typeLabel(value)}`);
        return;
      }
      if (descriptor.required && value.length === 0) {
        report.error(path, '数组不能为空');
        return;
      }
      value.forEach((item, index) => {
        validateAgainstDescriptor(descriptor.of, item, `${path}[${index}]`, report);
      });
      return;
    }

    case 'object': {
      if (!isPlainObject(value)) {
        report.error(path, `类型应为对象，实际是${typeLabel(value)}`);
        return;
      }
      for (const [key, fieldDescriptor] of Object.entries(descriptor.fields || {})) {
        validateAgainstDescriptor(fieldDescriptor, value[key], path ? `${path}.${key}` : key, report);
      }
      return;
    }

    default:
  }
}

/**
 * 按「组件示例结构」做宽松比对，与前端 validate-json-by-example.ts 同语义：
 * 结构种类必须一致，重名字段递归比类型，示例外的多余字段放行；返回第一条错误或 null。
 */
export function validateJsonAgainstExample(example, value, path = '') {
  const label = path || '根节点';
  if (example === null || example === undefined) return null;

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
    const exampleKeys = Object.keys(example);
    if (exampleKeys.length === 0) return null;
    const matchedKeys = exampleKeys.filter((key) => key in value);
    if (matchedKeys.length === 0) {
      const hint = exampleKeys.slice(0, 5).map((k) => `「${k}」`).join('、');
      return `${label}：与组件示例结构不匹配（未包含 ${hint} 等任一字段）`;
    }
    for (const key of matchedKeys) {
      const childPath = path ? `${path}.${key}` : key;
      const err = validateJsonAgainstExample(example[key], value[key], childPath);
      if (err) return err;
    }
    return null;
  }

  if (typeof value !== typeof example) {
    return `${label}：类型应为${typeLabel(example)}，实际是${typeLabel(value)}`;
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

  const spec = COMPONENT_SPECS[type];
  if (!spec) {
    const message = `未知组件类型 ${type}；已知类型：${KNOWN_COMPONENT_TYPES.join(' / ')}`;
    if (options.allowUnknownTypes) report.warn(`${path}.type`, message);
    else report.error(`${path}.type`, message);
    return type;
  }

  if (options.allowedTypes && !options.allowedTypes.has(type)) {
    report.error(`${path}.type`, `模板未配置该组件类型：${type}`);
  }

  validateAgainstDescriptor(spec.content, component.content, `${path}.content`, report);

  const example = options.componentExamples?.[type];
  if (example !== undefined) {
    const err = validateJsonAgainstExample(
      extractComponentContentExample(example, type),
      component.content,
      `${path}.content`,
    );
    // 示例比对是补充信号：内置规格已通过时降级为告警，避免示例本身的偶发差异阻断提交。
    if (err) report.warn(`${path}.content`, `与模板示例结构不一致：${err}`);
  }

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

  const pageLevel = types.filter((type) => getCompositionMode(type) === 'page');
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
 * - allowUnknownTypes：未知组件类型降级为告警
 * - templateComponents：模板组件清单，用于限制可用类型
 * - componentExamples：{ [type]: dataStructure 示例 }，用于示例比对
 */
export function validatePageData(doc, options = {}) {
  const report = createReport();
  const allowedTypes = Array.isArray(options.templateComponents) && options.templateComponents.length > 0
    ? new Set(options.templateComponents.map((item) => item.componentType))
    : null;
  const context = { ...options, allowedTypes };

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
