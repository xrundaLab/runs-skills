import test from 'node:test';
import assert from 'node:assert/strict';

import {
  buildDirectTaskPayload,
  buildStructuredJson,
  buildStructuredTaskPayload,
  createBatchNo,
  parseArgv,
  parseAssetsUploadArgs,
  parseSubmitArgs,
  parseTemplateSelector,
  summarizePageData,
} from './pagedata.mjs';
import {
  applyAssetResolutions,
  collectAssetRefs,
  isAssetRef,
  normalizeAssetRef,
} from './lib/resolve.mjs';
import {
  createManifest,
  findAsset,
  hashBytes,
  isUploaded,
  toManifestKey,
  upsertAsset,
} from './lib/manifest.mjs';
import {
  extractComponentContentExample,
  validateJsonAgainstExample,
  validatePageData,
} from './lib/validate.mjs';
import {
  DEFAULT_BASE_URL,
  DEFAULT_WEB_URL,
  buildCommitPayload,
  buildTemplateListPath,
  findTemplateByName,
  getRuntimeConfig,
  guessMimeType,
  inferFileCategory,
  listAllTemplates,
  maskToken,
  missingTokenMessage,
  normalizeBaseUrl,
  normalizeTemplateName,
  normalizeTemplateListPayload,
  rankTemplatesByName,
  buildCoursewareUrl,
  resolveTemplateByName,
  scoreTemplateNameMatch,
  summarizeTemplates,
  templateBusinessId,
} from './lib/client.mjs';
import { envFileCandidates, parseEnvFile, resetEnvCache } from './lib/env.mjs';

const validDoc = () => ({
  title: '示例课程',
  pages: [
    {
      tag: '课程导入',
      title: '开场',
      summary: '课程引入',
      components: [
        { type: 'course_intro', content: { courseName: '示例课程', body: '欢迎' } },
      ],
    },
    {
      tag: '知识讲解',
      title: '讲解页',
      components: [
        { type: 'text', content: '正文' },
        { type: 'tts', content: { text: '口播稿', url: 'https://res.example.com/a.mp3' } },
      ],
    },
  ],
});

// ---- 参数解析 ----

test('parseArgv 支持布尔标记、取值、等号写法与位置参数', () => {
  assert.deepEqual(
    parseArgv(['assets:upload', './a.png', '--dir', './assets', '--manifest=m.json', '--dry-run']),
    { _: ['assets:upload', './a.png'], dir: './assets', manifest: 'm.json', 'dry-run': true },
  );
});

test('parseAssetsUploadArgs 缺少输入时报错，--ext 归一化后缀', () => {
  assert.throws(() => parseAssetsUploadArgs(parseArgv(['assets:upload'])), /至少提供一个素材路径/);

  const options = parseAssetsUploadArgs(parseArgv(['assets:upload', 'a.png', '--ext', 'png, mp3']));
  assert.deepEqual([...options.extensions], ['.png', '.mp3']);
  assert.equal(options.concurrency, 4);
});

test('parseAssetsUploadArgs 用 manifestPath 命名清单路径', () => {
  // 曾经叫 manifest，与 uploadOne 参数里的 manifest 对象在 spread 时撞名，导致清单被路径字符串覆盖
  const options = parseAssetsUploadArgs(parseArgv(['assets:upload', 'a.png', '--manifest', 'm.json']));
  assert.equal(options.manifestPath, 'm.json');
  assert.equal(options.manifest, undefined);
});

test('parseAssetsUploadArgs 拒绝非法并发数', () => {
  assert.throws(
    () => parseAssetsUploadArgs(parseArgv(['assets:upload', 'a.png', '--concurrency', '0'])),
    /--concurrency 必须是正整数/,
  );
});

test('parseSubmitArgs 校验必填项', () => {
  assert.throws(() => parseSubmitArgs(parseArgv(['pages:submit'])), /缺少页面 JSON 路径/);
  assert.throws(() => parseSubmitArgs(parseArgv(['pages:submit', 'p.json'])), /缺少 --template-id 或 --template/);
  assert.throws(
    () => parseSubmitArgs(parseArgv(['pages:submit', 'p.json', '--template-id', 'tpl1', '--force'])),
    /不支持 --force/,
  );
  // 有 flag 无取值时 parseArgv 会置为 true，不能被当成合法模板 ID
  assert.throws(
    () => parseSubmitArgs(parseArgv(['pages:submit', 'p.json', '--template-id'])),
    /--template-id 缺少值/,
  );
  assert.throws(
    () => parseSubmitArgs(parseArgv(['pages:submit', 'p.json', '--template-id=  '])),
    /--template-id 缺少值/,
  );

  const options = parseSubmitArgs(parseArgv(['pages:submit', 'p.json', '--template-id', 'tpl1', '--yes', '--watch']));
  assert.equal(options.templateId, 'tpl1');
  assert.equal(options.templateName, undefined);
  assert.equal(options.yes, true);
  assert.equal(options.watch, true);
  assert.equal(options.asFile, false);
});

test('模板选择支持名称，并拒绝 ID 与名称同时出现', () => {
  assert.deepEqual(
    parseTemplateSelector(parseArgv(['pages:validate', 'p.json', '--template', ' 银河互动课件 '])),
    { templateId: undefined, templateName: '银河互动课件' },
  );
  assert.equal(
    parseSubmitArgs(parseArgv(['pages:submit', 'p.json', '--template', '银河互动课件'])).templateName,
    '银河互动课件',
  );
  assert.throws(
    () => parseTemplateSelector(parseArgv([
      'pages:validate',
      'p.json',
      '--template-id',
      'tpl1',
      '--template',
      '银河互动课件',
    ])),
    /只能提供一个/,
  );
  assert.throws(
    () => parseTemplateSelector(parseArgv(['pages:validate', 'p.json', '--template'])),
    /--template 缺少值/,
  );
});

test('createBatchNo 使用注入的时钟', () => {
  assert.equal(createBatchNo(() => 1710000000000), 'batch-1710000000000');
});

// ---- 提交载荷 ----

test('buildStructuredJson 为 page 补齐 creator 契约要求的默认字段', () => {
  const structured = buildStructuredJson({ title: 'T', pages: [{ title: '页面' }] });
  assert.deepEqual(structured.pages[0], { tag: '', title: '页面', summary: '', components: [] });
});

test('buildStructuredJson 保留额外字段（服务端 passthrough）', () => {
  const structured = buildStructuredJson({
    title: 'T',
    description: 'D',
    pages: [{ title: '页面', prompt: '生成提示', renderType: 'html' }],
  });
  assert.equal(structured.description, 'D');
  assert.equal(structured.pages[0].prompt, '生成提示');
  assert.equal(structured.pages[0].renderType, 'html');
});

test('两种提交载荷互斥且形态正确', () => {
  assert.throws(
    () => buildStructuredTaskPayload({ templateId: 'tpl1', structuredJson: { pages: [] } }),
    /coursewareId/,
  );
  assert.deepEqual(
    buildStructuredTaskPayload({
      templateId: 'tpl1',
      coursewareId: 'cw1',
      structuredJson: { title: 'T', pages: [] },
      batchNo: 'b1',
    }),
    { templateId: 'tpl1', coursewareId: 'cw1', structuredJson: { title: 'T', pages: [] }, batchNo: 'b1' },
  );
  assert.deepEqual(
    buildDirectTaskPayload({
      templateId: 'tpl1',
      coursewareId: 'cw1',
      fsFileId: 9,
      batchNo: 'b1',
    }),
    { templateId: 'tpl1', coursewareId: 'cw1', fsFileId: 9, direct: true, batchNo: 'b1' },
  );
});

test('summarizePageData 统计页数与组件分布', () => {
  assert.deepEqual(summarizePageData(validDoc()), {
    title: '示例课程',
    pageCount: 2,
    componentTotal: 3,
    componentCounts: { course_intro: 1, text: 1, tts: 1 },
  });
});

// ---- 素材引用 ----

test('isAssetRef 只认占位符与相对/file 路径，不误伤正文与线上地址', () => {
  assert.equal(isAssetRef('@asset:assets/p1.png'), true);
  assert.equal(isAssetRef('./assets/p1.png'), true);
  assert.equal(isAssetRef('../p1.png'), true);
  assert.equal(isAssetRef('file:///tmp/p1.png'), true);
  assert.equal(isAssetRef('https://res.example.com/p1.png'), false);
  assert.equal(isAssetRef('这是一段正文，包含 ./ 字样'), false);
  assert.equal(isAssetRef(''), false);
  assert.equal(isAssetRef(42), false);
});

test('normalizeAssetRef 去掉 @asset: 前缀并还原 file:// 路径', () => {
  assert.equal(normalizeAssetRef('@asset: assets/p1.png'), 'assets/p1.png');
  assert.equal(normalizeAssetRef('./assets/p1.png'), './assets/p1.png');
  assert.equal(normalizeAssetRef('file:///tmp/p1.png'), '/tmp/p1.png');
});

test('collectAssetRefs 深度遍历并给出 JSON 路径', () => {
  const refs = collectAssetRefs({
    pages: [{ components: [{ type: 'infographic', content: [{ img_url: '@asset:a.png', tts_url: './b.mp3' }] }] }],
  });
  assert.deepEqual(refs.map((item) => item.path), [
    'pages[0].components[0].content[0].img_url',
    'pages[0].components[0].content[0].tts_url',
  ]);
  assert.deepEqual(refs.map((item) => item.ref), ['a.png', './b.mp3']);
});

test('applyAssetResolutions 替换命中项、保留未命中项且不改动入参', () => {
  const doc = { a: '@asset:a.png', b: '@asset:missing.png', c: '正文' };
  const { value, state } = applyAssetResolutions(doc, (ref) => (ref === 'a.png' ? 'https://res/a.png' : undefined));

  assert.equal(value.a, 'https://res/a.png');
  assert.equal(value.b, '@asset:missing.png');
  assert.equal(value.c, '正文');
  assert.equal(doc.a, '@asset:a.png', '入参不应被修改');
  assert.equal(state.replaced.length, 1);
  assert.deepEqual(state.unresolved.map((item) => item.ref), ['missing.png']);
});

// ---- 资产清单 ----

test('toManifestKey 生成相对清单目录的 posix 路径', () => {
  assert.equal(toManifestKey('/tmp/course/assets.manifest.json', '/tmp/course/assets/p1.png'), 'assets/p1.png');
  assert.equal(toManifestKey('/tmp/course/assets.manifest.json', '/tmp/shared/p1.png'), '../shared/p1.png');
});

test('isUploaded 只在内容未变时判定可跳过', () => {
  const sha = hashBytes(Buffer.from('demo'));
  const manifest = upsertAsset(createManifest(), 'assets/p1.png', { url: 'https://res/p1.png', sha256: sha });

  assert.equal(isUploaded(manifest, 'assets/p1.png', sha), true);
  assert.equal(isUploaded(manifest, 'assets/p1.png', hashBytes(Buffer.from('changed'))), false);
  assert.equal(isUploaded(manifest, 'assets/other.png', sha), false);
});

test('findAsset 支持完整 key、去 ./ 前缀与唯一文件名回退', () => {
  let manifest = createManifest();
  manifest = upsertAsset(manifest, 'assets/p1.png', { url: 'https://res/p1.png' });

  assert.equal(findAsset(manifest, 'assets/p1.png').entry.url, 'https://res/p1.png');
  assert.equal(findAsset(manifest, './assets/p1.png').entry.url, 'https://res/p1.png');
  assert.equal(findAsset(manifest, 'p1.png').entry.url, 'https://res/p1.png');
  assert.equal(findAsset(manifest, 'nope.png').entry, null);
});

test('findAsset 文件名歧义时不猜，交由调用方报错', () => {
  let manifest = createManifest();
  manifest = upsertAsset(manifest, 'a/p1.png', { url: 'https://res/a.png' });
  manifest = upsertAsset(manifest, 'b/p1.png', { url: 'https://res/b.png' });

  const hit = findAsset(manifest, 'p1.png');
  assert.equal(hit.ambiguous, true);
  assert.equal(hit.entry, null);
  assert.deepEqual(hit.candidates.sort(), ['a/p1.png', 'b/p1.png']);
});

// ---- 页面校验 ----

const templateOptions = () => ({
  templateComponents: [
    { componentType: 'page_demo', compositionMode: 'page' },
    { componentType: 'block_demo', compositionMode: 'block' },
  ],
  componentExamples: {
    page_demo: {
      components: [{
        type: 'page_demo',
        content: {
          title: '示例',
          media: { url: 'https://example.com/a.png', caption: '' },
          items: [{ id: '1', label: '项目' }],
        },
      }],
    },
    block_demo: {
      type: 'block_demo',
      content: { text: '示例', enabled: true },
    },
  },
});

const templateDoc = () => ({
  title: 'T',
  pages: [{
    tag: '演示',
    title: '页面',
    components: [{
      type: 'page_demo',
      componentId: 'page_demo_1',
      content: {
        title: '实际标题',
        media: { url: 'https://res.example/a.png', caption: '' },
        items: [{ id: 1, label: '项目一', extra: '允许额外字段' }],
        extra: true,
      },
    }],
  }],
});

test('validatePageData 禁止缺少模板组件接口上下文的本地兜底校验', () => {
  const report = validatePageData(templateDoc());
  assert.ok(report.errors.some((item) => item.path === 'template' && /禁止使用本地兜底规格/.test(item.message)));
});

test('validatePageData 按模板 dataStructure 通过结构完整的数据并允许额外字段和标量类型变化', () => {
  const report = validatePageData(templateDoc(), templateOptions());
  assert.deepEqual(report.errors, []);
  assert.deepEqual(report.warnings, []);
});

test('validatePageData 卡住顶层结构问题', () => {
  const missingTitle = validatePageData({ pages: [] }, { templateComponents: [], componentExamples: {} });
  assert.ok(missingTitle.errors.some((item) => item.path === 'title'));
  assert.ok(missingTitle.errors.some((item) => item.path === 'pages' && /不能为空/.test(item.message)));

  const notArray = validatePageData({ title: 'T', pages: {} }, { templateComponents: [], componentExamples: {} });
  assert.ok(notArray.errors.some((item) => item.path === 'pages'));
});

test('validatePageData 要求 dataStructure 中的对象字段完整', () => {
  const doc = templateDoc();
  delete doc.pages[0].components[0].content.media.caption;
  const report = validatePageData(doc, templateOptions());
  assert.ok(report.errors.some((item) => /content\.media\.caption：字段缺失/.test(item.message)));
});

test('validatePageData 保持对象、数组与标量的结构类别', () => {
  assert.match(validateJsonAgainstExample({ a: '' }, ['x']), /应为对象/);
  assert.match(validateJsonAgainstExample([{ a: '' }], []), /数组不能为空/);
  assert.match(validateJsonAgainstExample({ a: '' }, { a: {} }), /应为标量/);
  assert.equal(
    validateJsonAgainstExample({ count: 1, enabled: true }, { count: '01', enabled: 'yes' }),
    null,
  );
});

test('validatePageData 逐项检查非空数组的条目结构', () => {
  const doc = templateDoc();
  delete doc.pages[0].components[0].content.items[0].label;
  const report = validatePageData(doc, templateOptions());
  assert.ok(report.errors.some((item) => /content\.items\[0\]\.label：字段缺失/.test(item.message)));
});

test('validatePageData 拒绝模板未配置的组件', () => {
  const doc = templateDoc();
  doc.pages[0].components[0].type = 'not_in_template';
  const report = validatePageData(doc, templateOptions());
  assert.ok(report.errors.some((item) => /模板未配置该组件类型/.test(item.message)));
});

test('validatePageData 拒绝没有可解析 dataStructure 的模板组件', () => {
  const doc = templateDoc();
  const options = templateOptions();
  delete options.componentExamples.page_demo;
  const report = validatePageData(doc, options);
  assert.ok(report.errors.some((item) => /未提供可解析的 dataStructure/.test(item.message)));
});

test('validatePageData 使用模板 compositionMode 强制 page 组件独占整页', () => {
  const doc = templateDoc();
  doc.pages[0].components.push({
    type: 'block_demo',
    content: { text: '正文', enabled: false },
  });
  const report = validatePageData(doc, templateOptions());
  assert.ok(report.errors.some((item) => /page 级组件独占整页：page_demo/.test(item.message)));
});

test('validatePageData 允许模板声明的多个 block 组件同页', () => {
  const doc = {
    title: 'T',
    pages: [{
      tag: '演示',
      title: '页面',
      components: [
        { type: 'block_demo', content: { text: 'A', enabled: true } },
        { type: 'block_demo', content: { text: 'B', enabled: false } },
      ],
    }],
  };
  assert.deepEqual(validatePageData(doc, templateOptions()).errors, []);
});

test('validatePageData 要求无组件页提供 prompt', () => {
  const options = { templateComponents: [], componentExamples: {} };
  const withoutPrompt = validatePageData(
    { title: 'T', pages: [{ tag: 'a', title: '空页', components: [] }] },
    options,
  );
  assert.ok(withoutPrompt.errors.some((item) => item.path === 'pages[0].prompt'));

  const withPrompt = validatePageData({
    title: 'T',
    pages: [{ tag: 'a', title: '空页', prompt: '生成一页导入', components: [] }],
  }, options);
  assert.deepEqual(withPrompt.errors, []);
});

test('validatePageData 对重复 componentId 告警', () => {
  const doc = {
    title: 'T',
    pages: [
      { tag: 'a', title: 'p1', components: [{ type: 'block_demo', content: { text: 'a', enabled: true }, componentId: 'dup' }] },
      { tag: 'b', title: 'p2', components: [{ type: 'block_demo', content: { text: 'b', enabled: false }, componentId: 'dup' }] },
    ],
  };
  const report = validatePageData(doc, templateOptions());
  assert.deepEqual(report.errors, []);
  assert.ok(report.warnings.some((item) => /componentId 重复/.test(item.message)));
});

test('validateJsonAgainstExample 放行额外字段但拒绝缺失字段', () => {
  assert.equal(validateJsonAgainstExample({ a: '', b: 0 }, { a: 'x', b: 1, extra: true }), null);
  assert.match(validateJsonAgainstExample({ a: '', b: 0 }, { a: 'x' }), /b：字段缺失/);
});

test('extractComponentContentExample 从页面级示例中取出 content', () => {
  const example = { title: 'demo', components: [{ type: 'tts', content: { text: '' } }] };
  assert.deepEqual(extractComponentContentExample(example, 'tts'), { text: '' });
  assert.deepEqual(extractComponentContentExample({ type: 'tts', content: { text: '' } }, 'tts'), { text: '' });
  assert.deepEqual(extractComponentContentExample({ text: '' }, 'tts'), { text: '' });
});

// ---- 客户端工具 ----

test('normalizeBaseUrl 自动补 /api/ 并避免重复', () => {
  assert.equal(normalizeBaseUrl('https://web.dev.xruns.cn'), 'https://web.dev.xruns.cn/api/');
  assert.equal(normalizeBaseUrl('https://web.dev.xruns.cn/api'), 'https://web.dev.xruns.cn/api/');
  assert.equal(normalizeBaseUrl('https://web.dev.xruns.cn/api/'), 'https://web.dev.xruns.cn/api/');
});

test('buildCoursewareUrl 在无 coursewareId 时返回空串', () => {
  assert.equal(buildCoursewareUrl({ siteUrl: 'https://web.dev.xruns.cn/api/', coursewareId: 'cw1' }), 'https://web.dev.xruns.cn/creator/cw1');
  assert.equal(buildCoursewareUrl({ coursewareId: '' }), '');
});

test('buildCoursewareUrl 默认走 web 站点而非接口网关', () => {
  assert.equal(buildCoursewareUrl({ coursewareId: 'cw1' }), 'https://web.dev.xruns.cn/creator/cw1');
  assert.equal(DEFAULT_BASE_URL, 'https://api.dev.xruns.cn/api/');
  assert.equal(DEFAULT_WEB_URL, 'https://web.dev.xruns.cn/');
});

test('模板列表路径与响应归一化符合业务接口契约', () => {
  assert.equal(
    buildTemplateListPath({ page: 2, pageSize: 50, templateModuleType: 'galaxy interactive' }),
    'v1/business/creator/template/list?pageNum=2&pageSize=50&templateModuleType=galaxy+interactive',
  );
  assert.deepEqual(
    normalizeTemplateListPayload({
      code: 200,
      data: {
        list: [{ id: 1, templateId: 'tpl1', templateName: '银河互动课件' }],
        total: 7,
      },
    }),
    {
      items: [{ id: 1, templateId: 'tpl1', templateName: '银河互动课件' }],
      total: 7,
    },
  );
});

test('模板名称支持省略后缀、标点和少量错字，并返回业务 templateId', () => {
  const templates = [
    { id: 10001, templateId: 'tpl-normal', templateName: '普通模板' },
    { id: 10015, templateId: 'tpl-galaxy', templateName: '银河互动课件' },
  ];
  assert.equal(normalizeTemplateName(' KIKI - 测试模板 '), 'kiki测试模板');
  assert.equal(templateBusinessId(findTemplateByName(templates, '银河互动模板')), 'tpl-galaxy');
  assert.equal(templateBusinessId(findTemplateByName(templates, '银河互功课件')), 'tpl-galaxy');
  assert.ok(scoreTemplateNameMatch('KIKI-测试模板', 'kiki测试') >= 95);
  assert.throws(() => findTemplateByName(templates, '完全无关'), /未找到模板/);
});

test('模糊匹配按相似度排序，候选接近时不自动猜测', () => {
  const templates = [
    { templateId: 'tpl-galaxy', templateName: '银河互动课件' },
    { templateId: 'tpl-galaxy-test', templateName: '银河互动测试模板' },
    { templateId: 'tpl-light', templateName: '银河轻课模板' },
  ];
  const ranked = rankTemplatesByName(templates, '银河互动测');
  assert.equal(ranked[0].template.templateId, 'tpl-galaxy-test');
  assert.throws(
    () => findTemplateByName(templates, '银河互动测'),
    /匹配到多个相近模板/,
  );
  assert.equal(
    findTemplateByName(templates, '银河互动').templateId,
    'tpl-galaxy',
    '省略通用后缀后核心名称唯一命中时应自动选择',
  );
  assert.equal(
    findTemplateByName(templates, '银河互动课件').templateId,
    'tpl-galaxy',
    '完整名称唯一命中时应优先于相近候选',
  );
});

test('模板摘要不输出 prompt 等大字段', () => {
  assert.deepEqual(
    summarizeTemplates([{
      id: 10015,
      templateId: 'tpl-galaxy',
      templateName: '银河互动课件',
      templateModuleTypeText: '任务模板',
      typeCode: 'galaxy_interactive',
      statusText: '上架中',
      permissionTypeText: '共享',
      updateTime: '2026-07-31',
      prompt: '不应输出',
    }]),
    [{
      templateId: 'tpl-galaxy',
      templateName: '银河互动课件',
      templateModuleType: '任务模板',
      typeCode: 'galaxy_interactive',
      status: '上架中',
      permission: '共享',
      updateTime: '2026-07-31',
    }],
  );
});

test('模板查询复用客户端鉴权并自动翻页，名称解析返回业务 templateId', async () => {
  const originalFetch = globalThis.fetch;
  const urls = [];
  globalThis.fetch = async (url) => {
    urls.push(String(url));
    const requestUrl = new URL(String(url));
    const page = requestUrl.searchParams.get('pageNum');
    const pageSize = requestUrl.searchParams.get('pageSize');
    const data = pageSize === '2'
      ? page === '1'
        ? {
          list: [
            { id: 1, templateId: 'tpl1', templateName: '普通模板' },
            { id: 2, templateId: 'tpl2', templateName: '另一个模板' },
          ],
          total: 3,
        }
        : {
          list: [{ id: 3, templateId: 'tpl-galaxy', templateName: '银河互动课件' }],
          total: 3,
        }
      : {
        list: [
          { id: 1, templateId: 'tpl1', templateName: '普通模板' },
          { id: 2, templateId: 'tpl2', templateName: '另一个模板' },
          { id: 3, templateId: 'tpl-galaxy', templateName: '银河互动课件' },
        ],
        total: 3,
      };
    return new Response(JSON.stringify({ code: 200, data }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    });
  };

  const config = {
    baseUrl: 'https://api.example.com/api/',
    webUrl: 'https://web.example.com/',
    token: 'test-token',
    clientId: 'test-client',
  };
  try {
    const all = await listAllTemplates(config, { pageSize: 2 });
    assert.equal(all.length, 3);
    assert.equal(urls.length, 2);

    urls.length = 0;
    const resolved = await resolveTemplateByName('银河互动课件', config);
    assert.equal(resolved.templateId, 'tpl-galaxy');
    assert.equal(resolved.templateName, '银河互动课件');
    assert.equal(urls.length, 1, '默认每页 100 条时一页即可取完');
  } finally {
    globalThis.fetch = originalFetch;
  }
});

// ---- 配置与 .env ----

test('parseEnvFile 支持 export、引号与行尾注释', () => {
  const parsed = parseEnvFile([
    '# 注释行',
    '',
    'export XRUNS_COURSEWARE_TOKEN="abc123"',
    "XRUNS_COURSEWARE_WEB_URL='https://web.dev.xruns.cn/'",
    'XRUNS_COURSEWARE_BASE_URL=https://api.dev.xruns.cn/api/ # 网关',
    '不是键值对',
    '=空键',
  ].join('\n'));

  assert.deepEqual(parsed, {
    XRUNS_COURSEWARE_TOKEN: 'abc123',
    XRUNS_COURSEWARE_WEB_URL: 'https://web.dev.xruns.cn/',
    XRUNS_COURSEWARE_BASE_URL: 'https://api.dev.xruns.cn/api/',
  });
});

test('envFileCandidates 按显式 > cwd > 技能目录 排序且去重', () => {
  const candidates = envFileCandidates({ cwd: '/work', skillDir: '/repo/skills/runs-page-data', explicit: '/custom.env' });
  assert.equal(candidates[0], '/custom.env');
  assert.equal(candidates[1], '/work/.env');
  assert.equal(candidates[2], '/repo/skills/runs-page-data/.env');
  assert.equal(candidates[3], '/repo/.env');
  assert.equal(new Set(candidates).size, candidates.length);
});

test('getRuntimeConfig 按 参数 > 环境变量 > 默认值 取值', () => {
  resetEnvCache();
  const saved = { ...process.env };
  process.env.XRUNS_COURSEWARE_TOKEN = 'env-token';
  process.env.XRUNS_COURSEWARE_WEB_URL = 'https://web.example.com';
  delete process.env.XRUNS_COURSEWARE_BASE_URL;
  delete process.env.XRUNS_BASE_URL;
  try {
    const fromEnv = getRuntimeConfig({});
    assert.equal(fromEnv.token, 'env-token');
    assert.equal(fromEnv.webUrl, 'https://web.example.com/');
    assert.equal(fromEnv.baseUrl, DEFAULT_BASE_URL);
    // siteUrl 是 webUrl 的别名，不再从网关地址反推
    assert.equal(fromEnv.siteUrl, fromEnv.webUrl);

    const fromArgs = getRuntimeConfig({ token: 'arg-token', 'web-url': 'https://web.other.com' });
    assert.equal(fromArgs.token, 'arg-token');
    assert.equal(fromArgs.webUrl, 'https://web.other.com/');
    assert.equal(fromArgs.envSources.XRUNS_COURSEWARE_TOKEN, '命令行参数');
    assert.equal(fromArgs.envSources.XRUNS_COURSEWARE_WEB_URL, '命令行参数');
  } finally {
    process.env = saved;
    resetEnvCache();
  }
});

test('maskToken 不泄漏完整凭证', () => {
  assert.equal(maskToken(''), '(未设置)');
  assert.equal(maskToken('short'), 'sh****');
  const masked = maskToken('Bearer abcdefghijklmnopqrstuvwxyz');
  assert.ok(!masked.includes('abcdefghijklmnopqrstuvwxyz'));
  assert.ok(masked.startsWith('abcdef'));
});

test('missingTokenMessage 指向 web 站点与 .env 写入位置', () => {
  const message = missingTokenMessage({ webUrl: 'https://web.dev.xruns.cn/', envFiles: ['/repo/.env'] });
  assert.ok(message.includes('https://web.dev.xruns.cn/'));
  assert.ok(message.includes('/repo/.env'));
  assert.ok(message.includes('XRUNS_COURSEWARE_TOKEN'));
});

test('guessMimeType 与 inferFileCategory 覆盖图片音频视频', () => {
  assert.equal(guessMimeType('a/b/p1.PNG'), 'image/png');
  assert.equal(guessMimeType('a/b/voice.mp3'), 'audio/mpeg');
  assert.equal(guessMimeType('a/b/unknown.xyz'), 'application/octet-stream');

  assert.equal(inferFileCategory('image/png'), 'image');
  assert.equal(inferFileCategory('audio/mpeg'), 'audio');
  assert.equal(inferFileCategory('video/mp4'), 'video');
  assert.equal(inferFileCategory('application/pdf'), 'document');
  assert.equal(inferFileCategory('application/json'), 'other');
  assert.equal(inferFileCategory(undefined), 'other');
});

test('buildCommitPayload 默认不触发索引，并透传归档字段', () => {
  const uploaded = {
    filename: 'p1.png',
    objectKey: 'creator-files/t1/uuid.png',
    bucketName: 'bucket',
    publicUrl: 'https://res/creator-files/t1/uuid.png',
    size: 100,
    mimeType: 'image/png',
  };

  assert.deepEqual(buildCommitPayload(uploaded), {
    filename: 'p1.png',
    object_key: 'creator-files/t1/uuid.png',
    bucket_name: 'bucket',
    public_url: 'https://res/creator-files/t1/uuid.png',
    size: 100,
    mime_type: 'image/png',
    should_index: false,
  });

  const archived = buildCommitPayload(uploaded, { folderId: 'f1', fileCategory: 'image' });
  assert.equal(archived.folder_id, 'f1');
  assert.equal(archived.file_category, 'image');
});
