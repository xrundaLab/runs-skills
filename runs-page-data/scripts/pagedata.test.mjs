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
  buildCommitPayload,
  guessMimeType,
  inferFileCategory,
  normalizeBaseUrl,
  buildCoursewareUrl,
} from './lib/client.mjs';

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
  assert.throws(() => parseSubmitArgs(parseArgv(['pages:submit', 'p.json'])), /缺少 --template-id/);
  // 有 flag 无取值时 parseArgv 会置为 true，不能被当成合法模板 ID
  assert.throws(() => parseSubmitArgs(parseArgv(['pages:submit', 'p.json', '--template-id'])), /缺少 --template-id/);
  assert.throws(() => parseSubmitArgs(parseArgv(['pages:submit', 'p.json', '--template-id=  '])), /缺少 --template-id/);

  const options = parseSubmitArgs(parseArgv(['pages:submit', 'p.json', '--template-id', 'tpl1', '--yes', '--watch']));
  assert.equal(options.templateId, 'tpl1');
  assert.equal(options.yes, true);
  assert.equal(options.watch, true);
  assert.equal(options.asFile, false);
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
  assert.deepEqual(
    buildStructuredTaskPayload({ templateId: 'tpl1', structuredJson: { title: 'T', pages: [] }, batchNo: 'b1' }),
    { templateId: 'tpl1', structuredJson: { title: 'T', pages: [] }, batchNo: 'b1' },
  );
  assert.deepEqual(
    buildDirectTaskPayload({ templateId: 'tpl1', fsFileId: 9, batchNo: 'b1' }),
    { templateId: 'tpl1', fsFileId: 9, direct: true, batchNo: 'b1' },
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

test('validatePageData 通过合法文档', () => {
  const report = validatePageData(validDoc());
  assert.deepEqual(report.errors, []);
});

test('validatePageData 卡住顶层结构问题', () => {
  const missingTitle = validatePageData({ pages: [] });
  assert.ok(missingTitle.errors.some((item) => item.path === 'title'));
  assert.ok(missingTitle.errors.some((item) => item.path === 'pages' && /不能为空/.test(item.message)));

  const notArray = validatePageData({ title: 'T', pages: {} });
  assert.ok(notArray.errors.some((item) => item.path === 'pages'));
});

test('validatePageData 强制 page 级组件独占整页', () => {
  const doc = validDoc();
  doc.pages[0].components.push({ type: 'text', content: '不该出现' });

  const report = validatePageData(doc);
  assert.ok(report.errors.some((item) => /page 级组件独占整页/.test(item.message)));
});

test('validatePageData 允许多个 block 级组件同页', () => {
  const doc = {
    title: 'T',
    pages: [{
      tag: '讲解',
      title: '页面',
      components: [
        { type: 'text', content: '文本' },
        { type: 'image', content: [{ url: 'https://res/a.png' }] },
        { type: 'tts', content: { text: '口播' } },
      ],
    }],
  };
  assert.deepEqual(validatePageData(doc).errors, []);
});

test('validatePageData 要求无组件页提供 prompt', () => {
  const withoutPrompt = validatePageData({ title: 'T', pages: [{ tag: 'a', title: '空页', components: [] }] });
  assert.ok(withoutPrompt.errors.some((item) => item.path === 'pages[0].prompt'));

  const withPrompt = validatePageData({
    title: 'T',
    pages: [{ tag: 'a', title: '空页', prompt: '生成一页导入', components: [] }],
  });
  assert.deepEqual(withPrompt.errors, []);
});

test('validatePageData 检查组件必填字段与类型', () => {
  const missingRequired = validatePageData({
    title: 'T',
    pages: [{ tag: 'a', title: 'p', components: [{ type: 'image_save', content: { title: '缺少 img_url' } }] }],
  });
  assert.ok(missingRequired.errors.some((item) => item.path === 'pages[0].components[0].content.img_url'));

  const wrongType = validatePageData({
    title: 'T',
    pages: [{ tag: 'a', title: 'p', components: [{ type: 'text', content: { not: 'a string' } }] }],
  });
  assert.ok(wrongType.errors.some((item) => /类型应为字符串/.test(item.message)));
});

test('validatePageData 拒绝空数组类内容并逐项定位', () => {
  const emptyArray = validatePageData({
    title: 'T',
    pages: [{ tag: 'a', title: 'p', components: [{ type: 'infographic', content: [] }] }],
  });
  assert.ok(emptyArray.errors.some((item) => /数组不能为空/.test(item.message)));

  const badItem = validatePageData({
    title: 'T',
    pages: [{
      tag: 'a',
      title: 'p',
      components: [{ type: 'ordering_question', content: { questions: [{ id: 'q1', stem: '排序', items: [{ id: 'i1' }] }] } }],
    }],
  });
  assert.ok(badItem.errors.some((item) => item.path === 'pages[0].components[0].content.questions[0].items[0].name'));
});

test('validatePageData 对未知组件类型默认报错，--allow-unknown 时降级告警', () => {
  const doc = { title: 'T', pages: [{ tag: 'a', title: 'p', components: [{ type: 'mystery', content: {} }] }] };

  assert.ok(validatePageData(doc).errors.some((item) => /未知组件类型/.test(item.message)));
  const relaxed = validatePageData(doc, { allowUnknownTypes: true });
  assert.deepEqual(relaxed.errors, []);
  assert.ok(relaxed.warnings.some((item) => /未知组件类型/.test(item.message)));
});

test('validatePageData 按模板组件清单限制可用类型', () => {
  const report = validatePageData(validDoc(), {
    templateComponents: [{ componentType: 'text' }, { componentType: 'tts' }],
  });
  assert.ok(report.errors.some((item) => /模板未配置该组件类型：course_intro/.test(item.message)));
});

test('validatePageData 音色不在推荐表内只告警', () => {
  const report = validatePageData({
    title: 'T',
    pages: [{ tag: 'a', title: 'p', components: [{ type: 'tts', content: { text: '稿子', voice: 'not-a-voice' } }] }],
  });
  assert.deepEqual(report.errors, []);
  assert.ok(report.warnings.some((item) => /不在推荐枚举内/.test(item.message)));
});

test('validatePageData 对重复 componentId 告警', () => {
  const report = validatePageData({
    title: 'T',
    pages: [
      { tag: 'a', title: 'p1', components: [{ type: 'text', content: 'a', componentId: 'dup' }] },
      { tag: 'b', title: 'p2', components: [{ type: 'text', content: 'b', componentId: 'dup' }] },
    ],
  });
  assert.deepEqual(report.errors, []);
  assert.ok(report.warnings.some((item) => /componentId 重复/.test(item.message)));
});

test('validatePageData 接受选项的字符串与对象两种形态', () => {
  const build = (options) => ({
    title: 'T',
    pages: [{
      tag: 'a',
      title: 'p',
      components: [{ type: 'select_question', content: { questions: [{ question: '题干', options }] } }],
    }],
  });

  assert.deepEqual(validatePageData(build(['A', 'B'])).errors, []);
  assert.deepEqual(validatePageData(build([{ text: 'A', audio: 'https://res/a.mp3' }])).errors, []);
  assert.ok(validatePageData(build([{ audio: 'https://res/a.mp3' }])).errors.length > 0);
});

// ---- 示例比对（与前端 validate-json-by-example 同语义）----

test('validateJsonAgainstExample 放行多余字段，卡住结构种类不一致', () => {
  assert.equal(validateJsonAgainstExample({ a: '', b: 0 }, { a: 'x', b: 1, extra: true }), null);
  assert.match(validateJsonAgainstExample({ a: '' }, ['x']), /应为对象/);
  assert.match(validateJsonAgainstExample([{ a: '' }], []), /数组不能为空/);
  assert.match(validateJsonAgainstExample({ a: '' }, { b: 1 }), /与组件示例结构不匹配/);
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
