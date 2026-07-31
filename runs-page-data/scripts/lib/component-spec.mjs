/**
 * 内置组件规格表（离线校验用）。
 *
 * 来源：doc/feat/制课端组件工具schema.md 与 frontend/app/components/page-runtime/widgets/*\/schema.ts。
 * 权威定义始终以模板组件接口返回的 componentType / compositionMode / dataStructure 为准；
 * 本表用于未指定模板时的离线兜底，以及已知组件的增强校验。模板新增组件不需要先登记到本表。
 */

/** 字段描述子构造器。media 标记该字段承载媒体地址，供占位符解析与本地路径残留检查复用。 */
const str = (opts = {}) => ({ kind: 'string', ...opts });
const num = (opts = {}) => ({ kind: 'number', ...opts });
const bool = (opts = {}) => ({ kind: 'boolean', ...opts });
const any = (opts = {}) => ({ kind: 'any', ...opts });
const arr = (of, opts = {}) => ({ kind: 'array', of, ...opts });
const obj = (fields, opts = {}) => ({ kind: 'object', fields, ...opts });
const union = (options, opts = {}) => ({ kind: 'union', options, ...opts });

const req = { required: true };

/** tts / infographic / immersive_explanation 共用音色表；不在表内只告警，不阻断。 */
export const VOICE_VALUES = [
  'zh_female_yingyujiaoxue_uranus_bigtts',
  'S_HJjtPNs22',
  'zh-CN-XiaoxiaoMultilingualNeural',
  'zh-CN-XiaoxiaoNeural',
  'zh-CN-YunyeNeural',
  'zh-CN-YunyangNeural',
  'zh-CN-YunzeNeural',
  'zh-CN-YunfanMultilingualNeural',
  'zh-CN-YunjianNeural',
  'en-US-EmmaMultilingualNeural',
  'en-US-AndrewMultilingualNeural',
];

export const RATE_VALUES = ['default', 'x-slow', 'slow', 'medium', 'fast', 'x-fast'];
export const VOLUME_VALUES = ['100', '75', '50', '25'];
export const VIRTUALMAN_KEYS = [
  'D3-NoTrain-3213b214-3dc3-48e7-927f-8',
  'D3-NoTrain-22707ec5-ee24-46e9-82d3-6',
  'D3-NoTrain-a1b9e276-95e1-4976-8454-0',
  'D3-NoTrain-793c659e-196b-4f91-9868-6',
  'D3-NoTrain-e30527e4-dac1-40c9-bb2e-2',
  'D3-NoTrain-0a1f8f5d-bce3-4e88-8f61-5',
];

const voice = str({ softValues: VOICE_VALUES });
const rate = str({ softValues: RATE_VALUES });
const volume = str({ softValues: VOLUME_VALUES });

/** 选项列表：纯字符串或 { text, audio? } 对象，两种形态并存。 */
const optionList = arr(
  union([str(), obj({ text: str(req), audio: str({ media: 'audio' }) })]),
  req,
);

export const COMPONENT_SPECS = {
  // ---- block 级：可与其他 block 组件同页组合 ----
  image: {
    label: '图片',
    level: 'block',
    content: arr(obj({ url: str({ ...req, media: 'image' }), desc: str() }), req),
  },
  text: { label: '文本', level: 'block', content: str(req) },
  rich_text: { label: '富文本', level: 'block', content: str(req) },
  video: {
    label: '视频',
    level: 'block',
    content: arr(
      obj({
        url: str({ ...req, media: 'video' }),
        desc: str(),
        fileName: str(),
        fileSize: num(),
        uploadTime: str(),
        sourceType: str({ softValues: ['upload', 'url'] }),
      }),
      req,
    ),
  },
  avatar: {
    label: '数字分身',
    level: 'block',
    content: obj({
      text: str(req),
      url: str({ media: 'video' }),
      virtualman_key: str({ softValues: VIRTUALMAN_KEYS }),
      rate,
      volume,
      subtitle: obj({ url: str({ ...req, media: 'subtitle' }), file_id: num(), format: str({ softValues: ['srt'] }) }),
    }),
  },
  tts: {
    label: '文本转音频',
    level: 'block',
    content: obj({
      text: str(req),
      url: str({ media: 'audio' }),
      voice,
      rate,
      volume,
      is_follow: bool(),
      audio_file_id: num(),
      subtitle_url: str({ media: 'subtitle' }),
    }),
  },
  podcast: {
    label: '播客',
    level: 'block',
    content: obj({
      query: str(req),
      speakers: arr(obj({ speakerId: str(req) })),
      language: str(),
      mode: str(),
      episodeId: str(),
      processStatus: str(),
      title: str(),
      audioUrl: str({ media: 'audio' }),
      audioStreamUrl: str(),
      scripts: arr(obj({ role: str(), text: str() })),
      failCode: str(),
    }),
  },
  word_card: {
    label: '单词卡',
    level: 'block',
    content: arr(
      obj({
        word: str(req),
        displayName: str(),
        displayNameZh: str(),
        meaning: str(req),
        part_of_speech: str(),
        imageUrl: str({ media: 'image' }),
        audioUrl: str({ media: 'audio' }),
        definitionEn: str(),
        definitionEnAudioUrl: str({ media: 'audio' }),
        exampleEn: str(),
      }),
      req,
    ),
  },
  learning_report: {
    label: '学习报告',
    level: 'block',
    content: obj({ studentInfo: str(), learningContent: str(), learningSituation: str() }),
  },

  // ---- page 级：独占整页，同页不得再有任何其他组件 ----
  course_intro: {
    label: '课程封面',
    level: 'page',
    content: obj({
      packageFigureUrl: str({ media: 'image' }),
      packageName: str(),
      unitName: str(),
      courseNumber: union([str(), num()]),
      courseName: str(),
      coreQuestion: str(),
      body: str(),
    }),
  },
  course_task: {
    label: '课程任务',
    level: 'page',
    content: obj({ title: str(), subtitle: str(), steps: arr(str()) }),
  },
  course_summary: {
    label: '课程小结',
    level: 'page',
    content: obj({ title: str(), subtitle: str(), body: str() }),
  },
  image_save: {
    label: '保存大图',
    level: 'page',
    content: obj({
      img_url: str({ ...req, media: 'image' }),
      title: str(),
      buttonText: str(),
      description: str(),
    }),
  },
  infographic: {
    label: '信息图',
    level: 'page',
    content: arr(
      obj({
        img_url: str({ media: 'image' }),
        img_desc: str(),
        tts_text: str(),
        tts_url: str({ media: 'audio' }),
        subtitle_url: str({ media: 'subtitle' }),
        tts_needs_regen: bool(),
        voice,
        is_follow: bool(),
      }),
      req,
    ),
  },
  immersive_explanation: {
    label: '沉浸式讲解',
    level: 'page',
    content: arr(
      obj({
        stage: str(),
        card_type: str({ softValues: ['text', 'grid'] }),
        icon: str(),
        title: str(req),
        content: union([str(), arr(obj({ icon: str(req), text: str(req) }))], req),
        tts_text: str(),
        tts_url: str({ media: 'audio' }),
        subtitle_url: str({ media: 'subtitle' }),
        subtitle_text: str(),
        tts_needs_regen: bool(),
        voice,
      }),
      req,
    ),
  },
  select_question: {
    label: '选择题',
    level: 'page',
    content: obj({
      title: str(),
      questions: arr(
        obj({
          question: str(req),
          questionAudio: str({ media: 'audio' }),
          options: optionList,
          answerIndex: num(),
          answer: str(),
        }),
        req,
      ),
    }),
  },
  galaxy_select_question: {
    label: 'Galaxy 选择题',
    level: 'page',
    content: obj({
      questions: arr(
        obj({
          question: str(req),
          options: optionList,
          isMultiple: bool(),
          answerIndex: union([num(), arr(num())]),
          answer: union([str(), arr(str())]),
          explanation: str(),
        }),
        req,
      ),
      correctButtonText: str(),
    }),
  },
  matching_question: {
    label: '配对题',
    level: 'page',
    content: obj({
      questions: arr(
        obj({
          id: str(req),
          stem: str(req),
          pairs: arr(obj({ id: str(req), left: str(req), right: str(req) }), req),
          explanation: str(),
        }),
        req,
      ),
      correctButtonText: str(),
    }),
  },
  categorization_question: {
    label: '分类分组题',
    level: 'page',
    content: obj({
      questions: arr(
        obj({
          id: str(req),
          stem: str(req),
          groups: arr(obj({ name: str(req), desc: str(), options: arr(str(), req) }), req),
          explanation: str(),
        }),
        req,
      ),
      instruction: str(),
      nextButtonText: str(),
      finishButtonText: str(),
    }),
  },
  ordering_question: {
    label: '排序题',
    level: 'page',
    content: obj({
      questions: arr(
        obj({
          id: str(req),
          stem: str(req),
          instruction: str(),
          items: arr(obj({ id: str(req), name: str(req), desc: str() }), req),
          explanation: str(),
        }),
        req,
      ),
      nextButtonText: str(),
      finishButtonText: str(),
    }),
  },
};

export const KNOWN_COMPONENT_TYPES = Object.keys(COMPONENT_SPECS);

export const PAGE_LEVEL_TYPES = KNOWN_COMPONENT_TYPES.filter(
  (type) => COMPONENT_SPECS[type].level === 'page',
);

export function getComponentSpec(type) {
  return COMPONENT_SPECS[type];
}

/** 组件级别；未知类型按 block 兜底，与前端 compositionMode 缺失时的兜底一致。 */
export function getCompositionMode(type) {
  return COMPONENT_SPECS[type]?.level === 'page' ? 'page' : 'block';
}
