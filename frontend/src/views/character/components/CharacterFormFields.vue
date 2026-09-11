<template>
  <div class="char-fields">
    <!-- 结构化字段 -->
    <div v-if="tab === 'all' || tab === 'basic'" class="fields-section-title">
      <span class="title-bar"></span>基础身份
    </div>
    <div v-if="tab === 'all' || tab === 'basic'" class="fields-grid">
      <div class="field-item">
        <label class="field-label">角色名称<span class="req">*</span></label>
        <el-input v-model="form.name" placeholder="输入角色名称" :maxlength="100" />
      </div>
      <div class="field-item">
        <label class="field-label">性别</label>
        <el-select v-model="form.gender" placeholder="选择性别">
          <el-option v-for="o in GENDER_OPTIONS" :key="o" :label="o" :value="o" />
        </el-select>
      </div>
      <div class="field-item">
        <label class="field-label">角色定位</label>
        <el-select v-model="form.role_type" placeholder="选择定位">
          <el-option v-for="o in ROLE_OPTIONS" :key="o" :label="o" :value="o" />
        </el-select>
      </div>
      <div class="field-item">
        <label class="field-label">年龄</label>
        <el-input-number v-model="form.age" class="field-control" :min="0" :max="9999" controls-position="right" placeholder="如：25" />
      </div>
      <div class="field-item field-full">
        <label class="field-label">身份/称号</label>
        <el-input v-model="form.identity" placeholder="如：青云门执法堂首座" />
      </div>
      <div class="field-item field-full">
        <label class="field-label">势力/阵营</label>
        <el-input v-model="form.faction" placeholder="多个势力用逗号分隔" />
      </div>
      <div class="field-item field-full">
        <label class="field-label">标签</label>
        <el-input v-model="form.tagline" placeholder="一句话人物签名/标签" />
      </div>
    </div>

    <!-- Markdown 内容 -->
    <div v-if="tab === 'all' || tab === 'content'" class="fields-section-title">
      <span class="title-bar"></span>角色内容
      <span class="section-hint">Markdown 格式，## 标题划分章节</span>
      <el-button size="small" text class="template-btn" @click="handleInsertTemplate">
        插入{{ genreLabel }}模板
      </el-button>
    </div>
    <div v-if="tab === 'all' || tab === 'content'" class="content-editor">
      <el-input
        v-model="form.content"
        type="textarea"
        :autosize="{ minRows: 15, maxRows: 40 }"
        resize="vertical"
        placeholder="## 性格特点&#10;&#10;## 外貌特征&#10;&#10;## 背景故事&#10;&#10;..."
      />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, watch, nextTick } from 'vue'
import AppButton from '@/components/common/AppButton.vue'

const props = defineProps({
  form: { type: Object, required: true },
  tab: { type: String, default: 'all' },
  genre: { type: String, default: 'general' },
})

// 题材 → 模板 key 映射
const GENRE_TEMPLATE_MAP = {
  xuanhuan: 'xianxia',
  wuxia: 'wuxia',
  fantasy: 'general',
  scifi: 'scifi',
  history: 'history',
  urban: 'urban',
  apocalypse: 'scifi',
  general: 'general',
}

// 题材 → 中文标签映射
const GENRE_LABEL_MAP = {
  xuanhuan: '修仙/玄幻',
  wuxia: '武侠/江湖',
  fantasy: '奇幻',
  scifi: '科幻/末日',
  history: '历史/架空',
  urban: '都市/现实',
  apocalypse: '末日',
  general: '通用',
}

// 计算当前题材的中文标签
const genreLabel = computed(() => {
  return GENRE_LABEL_MAP[props.genre] || '通用'
})

// 根据题材获取模板内容
function getTemplateByGenre(genre) {
  const key = GENRE_TEMPLATE_MAP[genre] || 'general'
  return TEMPLATE_MAP[key] || TEMPLATE_MAP.general
}

// 插入模板的通用函数
function insertTemplateIfEmpty() {
  if (!props.form.content || !props.form.content.trim()) {
    const template = getTemplateByGenre(props.genre)
    if (template) {
      props.form.content = template
    }
  }
}

// 点击"插入模板"按钮时，根据题材直接插入
function handleInsertTemplate() {
  if (props.form.content && props.form.content.trim()) {
    if (!confirm('当前内容不为空，插入模板将覆盖现有内容，确定吗？')) return
  }
  props.form.content = getTemplateByGenre(props.genre)
}

// 创建弹窗 (tab=all) 首次挂载时自动插入模板
onMounted(() => {
  if (props.tab === 'all') {
    nextTick(() => {
      insertTemplateIfEmpty()
    })
  }
})

// 编辑弹窗切换到 content tab 时，如果 content 为空则自动插入模板
watch(() => props.tab, (val) => {
  if (val === 'content') {
    nextTick(() => {
      insertTemplateIfEmpty()
    })
  }
})

// 题材变化时，如果 content 仍为空则自动切换模板
watch(() => props.genre, () => {
  nextTick(() => {
    insertTemplateIfEmpty()
  })
})

const GENDER_OPTIONS = ['未知', '男', '女']
const ROLE_OPTIONS = ['配角', '主角', '反派', '路人']

const TEMPLATE_MAP = {
  general: `## 性格特点
表面沉稳冷静，遇事不慌；内心实则极度不安，害怕失去掌控。
矛盾核心：理性与感性的反复拉扯。

## 外貌特征
身高约一米八，面容清瘦，眉骨高挺。
习惯性微蹙眉头，右手食指有常年握笔留下的薄茧。

## 背景故事
出身普通家庭，父亲是小镇教师，母亲早逝。
大学毕业后进入一家创业公司，凭借过人能力三年升至总监。
后因公司内斗被迫离职，带着不甘独自创业。

## 核心动机
打造属于自己的事业，证明自己的价值。
终极目标：让跟随自己的人都能过上好日子。

## 优点/特长
商业嗅觉敏锐，擅长谈判和资源整合。
记忆力极强，过目不忘。

## 缺点
控制欲强，不善于放权。
过于追求完美，常因细节拖延整体进度。

## 执念/软肋
母亲的遗物——一块旧怀表，从不离身。
妹妹是他唯一的逆鳞，触之必怒。

## 禁忌
绝不做违法的事，绝不出卖朋友。
不接受任何以伤害无辜为代价的合作。

## 能力
精通 Python 和数据分析，能独立搭建系统。
擅长写作，曾出版过一本商业畅销书。

## 弱点/代价
长期高强度工作导致严重失眠。
一旦陷入情绪低谷，决策能力大幅下降。

## 秘密
创业资金来源有一部分灰色地带，从未对任何人提及。
当年离职的真正原因并非内斗，而是发现了公司的财务造假。

## 过往黑历史
大学时曾举报导师学术造假，导致导师被解聘，自己也被排挤。
第一份工作时因过于信任合伙人，差点被骗走全部积蓄。

## 成长轨迹
从冲动莽撞的职场新人 → 学会隐忍和布局的创业者。
从独来独往 → 学会信任团队、依靠伙伴。
最终明白：成功不是一个人的战斗。`,

  xianxia: `## 性格特点
表面玩世不恭、嬉皮笑脸，实则心思缜密、算无遗策。
矛盾核心：自由洒脱的天性与沉重使命之间的撕裂。

## 外貌特征
黑发披肩，眼眸深处偶有金光一闪而过。
常穿一袭洗得发白的青衫，腰间挂着一枚古朴玉佩。

## 背景故事
出身没落修仙世家，幼年家族遭灭门，被散修老者收养。
老者实为隐世大能，临终前将毕生修为封印于他体内。
独自踏上修仙路，一边修炼一边追查灭门真相。

## 核心动机
查清家族灭门的幕后黑手，为亲人复仇。
终极追求：打破天道束缚，证得大自在。

## 优点/特长
悟性极高，能举一反三，修炼速度远超同辈。
对阵法有天生的直觉，能以弱胜强。

## 缺点
过于自信，有时会低估对手。
情感上逃避，不敢面对真心。

## 执念/软肋
养父临终前的那句"活下去"是他所有行动的根源。
对灭门之事的执念几乎成了心魔。

## 禁忌
绝不修炼吞噬他人修为的邪功。
绝不伤害无辜凡人，即使被逼到绝境。

## 功法境界
当前境界：金丹中期。
主修功法：《太虚剑诀》（上古残卷，威力极大但有反噬）。
特殊神通：剑意化形、空间挪移（未完全觉醒）。

## 法宝灵器
本命法宝：古朴玉佩（内含养父残留的一缕剑意，关键时刻可护主一次）。
随身兵器：一柄无名铁剑（材质特殊，随修为提升而进化）。

## 弱点/代价
每次动用封印之力，都会折损寿元。
太虚剑诀修炼至深处，有走火入魔的风险。

## 秘密
体内封印着上古剑仙的一缕残魂，是他悟性超凡的真正来源。
灭门的幕后黑手竟是修仙界正道魁首。

## 过往黑历史
曾为获取情报，眼睁睁看着同伴被敌人折磨致死。
一次走火入魔中误杀了养父的故交，至今无法释怀。

## 成长轨迹
从只想复仇的孤狼 → 学会为更多人而战的剑仙。
从逃避情感 → 敢于直面内心，守护所爱之人。
最终领悟：剑道即人道，真正的强大是守护而非毁灭。`,

  wuxia: `## 性格特点
侠义心肠，路见不平必拔刀相助。
但内心深处藏着对江湖的厌倦，渴望归隐却身不由己。

## 外貌特征
剑眉星目，面容刚毅，左颊有一道浅疤。
身形修长，常穿劲装，腰悬长剑，走路带风。

## 背景故事
出身武林世家，父亲是名震江湖的"铁臂神拳"。
十五岁时父亲被仇家暗算身亡，家传武功秘籍被夺。
独自闯荡江湖，一边寻仇一边寻找失落的秘籍。

## 核心动机
查明父亲被害的真相，夺回家传秘籍。
终极追求：退隐江湖，与心爱之人种田度日。

## 优点/特长
家传拳法根基扎实，后得高人指点习得剑法。
轻功了得，江湖人称"踏雪无痕"。

## 缺点
过于重情重义，容易被利用。
嗜酒如命，醉后常误事。

## 执念/软肋
父亲的遗物——一枚残缺的玉佩，是寻找秘籍的唯一线索。
师父临终前托付的遗愿是他放不下的重担。

## 禁忌
绝不滥杀无辜，即使对方是仇人的手下。
不用暗器伤人，认为这是小人行径。

## 武学体系
门派：无门无派，融合多家之长。
武功：铁臂拳（家传）、落叶剑法（师承）、轻功踏雪无痕。
内力：二十年精纯内力，擅长以柔克刚。

## 兵刃暗器
佩剑：青锋剑（父亲遗物，百炼精钢锻造）。
暗器：从不使用（原则问题）。

## 弱点/代价
左肩旧伤未愈，阴雨天会剧痛，影响出剑速度。
内力虽精纯但总量不足，持久战是短板。

## 秘密
父亲并非被仇家所杀，而是被最信任的结义兄弟出卖。
家传秘籍中藏有前朝宝藏的线索，这才是真正的祸根。

## 过往黑历史
曾因醉酒误入陷阱，导致师妹被敌人掳走，虽最终救回但师妹自此与他断交。
寻仇时错杀了一个无辜之人，虽是误杀但终生愧疚。

## 成长轨迹
从满腔仇恨的复仇少年 → 历经江湖风雨的成熟侠客。
从执着于复仇 → 明白放下才是真正的解脱。
最终选择放下仇恨，守护身边人。`,

  urban: `## 性格特点
表面是雷厉风行的职场女强人，实则内心渴望平淡生活。
矛盾核心：事业野心与家庭责任之间的拉扯。

## 外貌特征
干练短发，戴一副细框眼镜，妆容精致得体。
衣着以黑白灰为主，永远踩着一双八厘米高跟鞋。

## 背景故事
出生于小县城，父母是普通工人，从小成绩优异。
考入名校后凭全额奖学金完成学业，进入顶级投行。
从分析师一路做到副总裁，用了整整十年。

## 核心动机
在三十五岁前晋升为合伙人，实现财务自由。
为父母在省城买一套大房子，让他们安享晚年。

## 优点/特长
数据分析能力极强，PPT 做得像艺术品。
谈判桌上从不吃亏，被对手称为"微笑的狐狸"。

## 缺点
工作狂，经常加班到凌晨，忽略身体健康。
对下属要求过高，团队离职率偏高。

## 执念/软肋
母亲的一句"妈不图你挣大钱，只图你平平安安"是她深夜加班时最大的安慰。
父亲的心脏病是她不敢停下来的原因。

## 禁忌
绝不在工作中造假数据，即使面临巨大压力。
不出卖同事换取晋升机会。

## 职业背景
公司：某顶级投资银行，北京总部。
职位：投行部副总裁，核心团队负责人。
年收入：税后约两百万，另有项目奖金。

## 社会关系
同事：与三位合伙人关系微妙，既是合作者也是竞争者。
朋友：大学室友群是她唯一的倾诉出口。
家庭：父亲心脏不好，母亲退休在家，有一个在读高中的弟弟。

## 弱点/代价
长期高压导致严重的焦虑症，靠药物维持。
与男友因聚少离多分手，至今单身。

## 秘密
手中掌握着公司一个大客户的财务造假证据，一旦曝光将引发行业地震。
三年前的一次投资决策失误导致客户巨亏，她一直用其他项目的收益填补。

## 过往黑历史
大学时为了保研名额，曾暗中举报竞争对手学术不端（虽然后来证明是事实）。
入职第一年因经验不足，导致一个小型项目亏损，被前辈严厉训斥。

## 成长轨迹
从只追求KPI的冷血高管 → 学会关注团队和自我。
从逃避家庭责任 → 主动承担起照顾父母的重担。
最终明白：成功不是只有升职加薪，还有爱与被爱。`,

  scifi: `## 性格特点
理性到近乎冷酷，做决策完全基于数据和逻辑。
但内心深处藏着对人性的信任，只是不愿承认。

## 外貌特征
左眼是机械义眼，能扫描分析环境数据。
右臂有大面积烧伤疤痕，常年穿长袖遮盖。

## 背景故事
曾是军方最年轻的生物工程师，参与"新人类计划"。
实验失控导致基地沦陷，他带着核心数据逃出。
如今在废墟中建立了一个小型庇护所，收留幸存者。

## 核心动机
找到拯救人类的方法，阻止变异体扩散。
终极目标：研发出逆转变异的血清。

## 优点/特长
生物工程和机械改装双料专家，能用废品制造武器。
精通多种语言，是末世中少有的"全能型"人才。

## 缺点
过度理性，有时会做出"牺牲少数保全多数"的冷血决策。
对变异体研究过于投入，有被感染的风险。

## 执念/软肋
妻子在灾变中为保护他而变异，他一直在寻找治愈她的方法。
女儿的照片是他最后的温情。

## 禁忌
绝不放弃任何一个庇护所的成员。
不拿活人做实验，即使是为了全人类。

## 科技装备
机械义眼：具备夜视、扫描、通讯功能。
改装皮卡：装甲加固，装有太阳能电池板。
实验室：便携式生物分析仪、基因测序设备。

## 生存技能
生物工程：能识别变异类型，研发基础解毒剂。
机械维修：改装车辆、修复电子设备。
战斗：近战格斗和射击能力中等，擅长用陷阱和战术。

## 弱点/代价
机械义眼需要定期维护，否则会失灵。
右臂烧伤导致力量不足，近战是短板。

## 秘密
"新人类计划"的真正目的不是拯救人类，而是制造超级战士。
他手中的核心数据包含了变异体的弱点，是各方势力争夺的目标。

## 过往黑历史
灾变初期为逃命，曾关闭了基地的逃生舱门，导致数十人未能撤离。
发现妻子变异后，他曾试图亲手了结她，最终没能下手。

## 成长轨迹
从独善其身的冷血科学家 → 承担起领袖责任的庇护者。
从只相信数据 → 承认人性的力量和温度。
最终明白：人类的未来不在于技术，而在于彼此守护。`,

  history: `## 性格特点
表面仁厚宽和，实则城府极深，善于隐忍。
矛盾核心：仁君理想与帝王手段之间的平衡。

## 外貌特征
面容方正，目光深邃，蓄短须。
常穿玄色常服，不喜奢华，但气度自成。

## 背景故事
皇子中最不受宠的一个，母妃出身低微。
被外放边疆十年，暗中经营势力，结交边将。
先帝驾崩后，凭借军方支持和朝中暗桩夺嫡成功。

## 核心动机
巩固皇权，铲除世家门阀的垄断。
终极目标：推行新政，让寒门子弟有出头之日。

## 优点/特长
知人善任，能容忍直言进谏的臣子。
军事眼光长远，善于从全局布局。

## 缺点
多疑，尤其在晚年愈发严重。
对亲情淡漠，为了权力可以牺牲任何人。

## 执念/软肋
母妃临终前的遗愿——"做一个好皇帝"是他毕生的枷锁。
对发妻的愧疚是他唯一的柔软。

## 禁忌
不杀直谏之臣，不辱先帝旧臣。
不以百姓为棋子，即使在夺嫡之争中。

## 权力地位
身份：当朝天子，年号"永平"。
在位二十三年，朝中分为改革派与保守派两大阵营。
军权在握，但世家门阀仍掌握着地方实权。

## 军事/政务
兵力：中央禁军三十万，边军五十万。
谋士团：以丞相为首的文官集团，暗中还有情报机构"暗卫"。
治理成果：推行均田制，打压门阀，百姓生活有所改善。

## 弱点/代价
过度操政务导致身体每况愈下。
多疑性格导致晚年开始清洗功臣，寒了人心。

## 秘密
先帝并非正常驾崩，而是他暗中加速了进程。
当年夺嫡时曾与敌国暗中结盟，这个秘密一旦暴露将动摇国本。

## 过往黑历史
夺嫡之夜，他下令关闭了皇城侧门，导致数十名无辜宫人被乱兵杀害。
为稳坐皇位，曾赐死了对自己有拥立之功的功臣。

## 成长轨迹
从隐忍蛰伏的皇子 → 铁腕手段的帝王。
从雄心勃勃推行新政 → 晚年陷入猜忌与孤独。
最终在病榻上写下罪己诏，将皇位传给最不看好却最仁厚的皇子。`,
}
</script>

<style lang="scss" scoped>
.char-fields {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.fields-section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 18px 0 12px;
  flex-shrink: 0;

  &:first-child {
    margin-top: 0;
  }

  .title-bar {
    width: 3px;
    height: 14px;
    border-radius: 2px;
    background: var(--primary);
  }

  .section-hint {
    font-size: 11px;
    font-weight: 400;
    color: var(--text-muted);
    flex: 1;
  }

  .template-btn {
    font-size: 12px;
    color: var(--primary);
    padding: 0;
    gap: 2px;

    &:hover {
      color: var(--primary-dark);
    }
  }
}

.fields-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 16px;
  flex-shrink: 0;
}

.field-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-full {
  grid-column: 1 / -1;
}

.field-label {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;

  .req {
    color: var(--danger);
    margin-left: 2px;
  }
}

.field-control {
  width: 100%;
}

.content-editor {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;

  :deep(.el-textarea) {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  :deep(.el-textarea__inner) {
    flex: 1;
    min-height: 200px;
    resize: none;
  }
}

@media (max-width: 768px) {
  .fields-grid {
    grid-template-columns: 1fr;
  }
}
</style>
