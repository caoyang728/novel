<template>
  <div class="worldview-view">
    <Teleport defer to="#header-right-teleport">
      <AppButton variant="default" @click="exportMarkdown">
        导出 Markdown
      </AppButton>
      <AppButton variant="accent" @click="goChat">
        AI 对话构建
      </AppButton>
    </Teleport>
    <div class="wv-workspace" v-loading="loading" element-loading-text="加载世界观数据...">
      <!-- 左侧层级导航 -->
      <div class="wv-nav glass-surface">
        <div
          v-for="layer in LAYERS"
          :key="layer.key"
          class="nav-item"
          :class="{ active: activeTab === layer.key }"
          @click="activeTab = layer.key"
        >
          <el-icon><component :is="layer.icon" /></el-icon>
          <span>{{ layer.name }}</span>
        </div>
        <div class="nav-divider"></div>
        <div
          class="nav-item nav-tool"
          :class="{ active: activeTab === 'deepening' }"
          @click="activeTab = 'deepening'"
        >
          <el-icon><ChatLineSquare /></el-icon>
          <span>宏观缺口</span>
        </div>
        <div
          class="nav-item nav-tool"
          :class="{ active: activeTab === 'consistency' }"
          @click="activeTab = 'consistency'"
        >
          <el-icon><CircleCheck /></el-icon>
          <span>宏观一致性</span>
        </div>
      </div>

      <!-- 右侧内容区 -->
      <div class="wv-main glass-panel">
        <!-- ========== 层级表单 ========== -->
        <template v-for="layer in LAYERS" :key="layer.key">
          <div
            v-if="activeTab === layer.key"
            v-loading="polishingLayer === layer.key"
            element-loading-text="AI 正在润色字段..."
            class="layer-panel"
          >
            <div class="layer-header">
              <div>
                <h3 class="layer-title">{{ layer.name }}</h3>
                <p class="layer-hint">编辑后点击「保存」生效；AI 润色仅处理自上次保存后修改过的字段</p>
              </div>
              <div class="layer-actions">
                <AppButton variant="ai" :disabled="polishingLayer !== null || savingLayer !== null" @click="polishLayer(layer.key)">
                  <el-icon><MagicStick /></el-icon>
                  <span>AI 润色</span>
                </AppButton>
                <AppButton variant="accent" :loading="savingLayer === layer.key" :disabled="polishingLayer !== null" @click="saveLayer(layer.key)">
                  <el-icon><Check /></el-icon>
                  <span>保存</span>
                </AppButton>
              </div>
            </div>

            <div class="field-groups">
              <div
                v-for="group in layer.groups"
                :key="group.name"
                class="field-group"
                :class="{ collapsed: isGroupCollapsed(`${layer.key}-${group.name}`) }"
              >
                <div class="group-header" @click="toggleGroupCollapse(`${layer.key}-${group.name}`)">
                  <div class="group-title">
                    <el-icon class="collapse-icon">
                      <ArrowRight v-if="isGroupCollapsed(`${layer.key}-${group.name}`)" />
                      <ArrowDown v-else />
                    </el-icon>
                    {{ group.name }}
                  </div>
                  <div class="group-meta">
                    <span class="field-count">{{ group.fields.length }} 个字段</span>
                  </div>
                </div>
                <div v-show="!isGroupCollapsed(`${layer.key}-${group.name}`)" class="group-fields" :class="{ grid: group.grid }">
                  <div v-for="f in group.fields" :key="f.key" class="field-item">
                    <label class="field-label">{{ f.label }}</label>

                    <!-- 小说类型分组下拉 -->
                    <el-select
                      v-if="f.type === 'select'"
                      v-model="form[f.key]"
                      :placeholder="f.placeholder"
                      filterable
                      clearable
                      class="field-control"
                    >
                      <el-option-group v-for="g in genreGroups" :key="g.group" :label="g.group">
                        <el-option v-for="item in g.items" :key="item" :label="item" :value="item" />
                      </el-option-group>
                    </el-select>

                    <!-- 核心公理动态列表 -->
                    <div v-else-if="f.type === 'axioms'" class="axiom-list">
                      <div v-for="(a, i) in axioms" :key="i" class="axiom-row">
                        <el-input v-model="axioms[i]" :placeholder="`核心公理 ${i + 1}`" />
                        <AppButton text variant="danger" size="small" class="axiom-del" @click="removeAxiom(i)">
                          <el-icon><Close /></el-icon>
                        </AppButton>
                      </div>
                      <AppButton text variant="accent" size="small" class="axiom-add" @click="addAxiom">
                        <el-icon><Plus /></el-icon>
                        <span>添加公理</span>
                      </AppButton>
                    </div>

                    <!-- 短文本 -->
                    <el-input
                      v-else-if="f.type === 'input'"
                      v-model="form[f.key]"
                      :placeholder="f.placeholder"
                      class="field-control"
                    />

                    <!-- 长文本 -->
                    <el-input
                      v-else
                      v-model="form[f.key]"
                      type="textarea"
                      :autosize="{ minRows: 2, maxRows: 8 }"
                      :placeholder="f.placeholder"
                      class="field-control"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>

        <!-- ========== 宏观缺口检测 ========== -->
        <div v-if="activeTab === 'deepening'" class="tool-panel">
          <div class="tool-header">
            <div>
              <h3 class="layer-title">宏观缺口检测</h3>
              <p class="layer-hint">AI 扫描世界观中的结构性空缺，提出关键问题；你的回答将被整合为设定修改建议</p>
            </div>
            <div class="layer-actions">
              <AppButton variant="ai" :loading="dState === 'loading'" @click="generateQuestions">
                <el-icon><MagicStick /></el-icon>
                <span>{{ dState === 'hasQuestions' ? '重新检测' : '检测缺口' }}</span>
              </AppButton>
              <AppButton
                v-if="dState === 'hasQuestions'"
                variant="accent"
                :disabled="!hasDpAnswer || dState === 'analyzing'"
                :loading="dState === 'analyzing'"
                @click="submitAnswers"
              >
                <el-icon><Promotion /></el-icon>
                <span>提交并整合回答</span>
              </AppButton>
              <template v-if="dState === 'hasSuggestions'">
                <AppButton variant="grey" @click="resetDeepening">
                  <el-icon><RefreshLeft /></el-icon>
                  <span>清除建议</span>
                </AppButton>
                <AppButton variant="accent" :loading="applying" @click="applyDeepeningChanges">
                  <el-icon><Check /></el-icon>
                  <span>应用选中的修改</span>
                </AppButton>
              </template>
            </div>
          </div>

          <!-- 初始 -->
          <EmptyState v-if="dState === 'empty'" icon="ChatLineSquare" text="点击「检测缺口」，AI 将分析当前世界观的结构性空缺" class="glass-surface" />

          <!-- 无缺口 -->
          <EmptyState v-else-if="dState === 'noQuestions'" icon="CircleCheckFilled" text="世界观设定已经比较完善，未发现宏观缺口" class="glass-surface success" />

          <!-- 问题列表 -->
          <div v-else-if="dState === 'hasQuestions' || dState === 'analyzing'" class="question-list" v-loading="dState === 'analyzing'" element-loading-text="正在分析回答并生成修改建议...">
            <div v-for="(q, i) in dpQuestions" :key="i" class="question-card glass-surface">
              <div class="question-head">
                <span class="question-index">问题 {{ i + 1 }}</span>
                <el-tag size="small" :type="priorityType(q.priority)" effect="light">
                  {{ priorityLabel(q.priority) }}
                </el-tag>
                <el-tag size="small" type="info" effect="plain">{{ layerName(q.targetLayer) }}</el-tag>
              </div>
              <p class="question-text">{{ q.question }}</p>
              <el-input
                v-model="q.answer"
                type="textarea"
                :autosize="{ minRows: 2, maxRows: 8 }"
                placeholder="输入你的答案..."
              />
              <div v-if="q.quickOptions && q.quickOptions.length" class="quick-options">
                <span class="quick-label">快捷选择：</span>
                <AppButton
                  v-for="(opt, oi) in q.quickOptions"
                  :key="oi"
                  size="small"
                  variant="default"
                  @click="q.answer = opt"
                >
                  {{ opt }}
                </AppButton>
              </div>
            </div>
          </div>

          <!-- 修改建议 -->
          <WorldviewSuggestionList
            v-else-if="dState === 'hasSuggestions'"
            :items="dpSuggestions"
            :layer-name="layerName"
            :translate-path="translatePath"
            @select-all="selectAllDp"
          />
        </div>

        <!-- ========== 宏观一致性检测 ========== -->
        <div v-if="activeTab === 'consistency'" class="tool-panel">
          <div class="tool-header">
            <div>
              <h3 class="layer-title">宏观一致性检测</h3>
              <p class="layer-hint">AI 检查各层设定之间是否存在规则冲突、逻辑矛盾或结构不兼容</p>
            </div>
            <div class="layer-actions">
              <AppButton variant="default" :loading="cState === 'checking'" @click="checkConsistency">
                <el-icon><Search /></el-icon>
                <span>{{ cState === 'hasIssues' ? '重新检测' : '检测一致性' }}</span>
              </AppButton>
              <AppButton
                v-if="cState === 'hasIssues'"
                variant="ai"
                :loading="cState === 'fixing'"
                @click="fixConsistency"
              >
                <el-icon><MagicStick /></el-icon>
                <span>AI 修复</span>
              </AppButton>
              <template v-if="cState === 'hasSuggestions'">
                <AppButton variant="grey" @click="resetConsistency">
                  <el-icon><RefreshLeft /></el-icon>
                  <span>清除建议</span>
                </AppButton>
                <AppButton variant="accent" :loading="applying" @click="applyConsistencyChanges">
                  <el-icon><Check /></el-icon>
                  <span>应用选中的修改</span>
                </AppButton>
              </template>
            </div>
          </div>

          <!-- 初始 -->
          <EmptyState v-if="cState === 'empty'" icon="CircleCheck" text="点击「检测一致性」，AI 将审校设定之间的硬矛盾" class="glass-surface" />

          <!-- 无问题 -->
          <EmptyState v-else-if="cState === 'noIssues'" icon="CircleCheckFilled" text="设定之间逻辑自洽，未发现矛盾" class="glass-surface success" />

          <!-- 问题列表 -->
          <template v-else-if="cState === 'hasIssues' || cState === 'fixing'">
            <div class="issue-list" v-loading="cState === 'fixing'" element-loading-text="AI 正在生成修复建议...">
              <div v-for="(iss, i) in csIssues" :key="i" class="issue-card glass-surface">
                <div class="issue-head">
                  <span class="issue-index">问题 {{ i + 1 }}</span>
                  <el-tag size="small" :type="iss.severity === 'error' ? 'danger' : 'warning'" effect="dark">
                    {{ iss.severity === 'error' ? '严重' : '警告' }}
                  </el-tag>
                  <el-tag size="small" type="info" effect="plain">{{ layerName(iss.targetLayer) }}</el-tag>
                </div>
                <p class="issue-message">{{ iss.message }}</p>
                <p v-if="iss.detail" class="issue-detail">{{ iss.detail }}</p>
                <p v-if="iss.targetField" class="issue-path">
                  <code class="field-path">{{ translatePath(iss.targetField) }}</code>
                </p>
                <el-input
                  v-model="iss.note"
                  type="textarea"
                  :autosize="{ minRows: 1, maxRows: 4 }"
                  placeholder="输入你期望的修复方向...（可选）"
                />
              </div>
            </div>
          </template>

          <!-- 修复建议 -->
          <WorldviewSuggestionList
            v-else-if="cState === 'hasSuggestions'"
            :items="csSuggestions"
            :layer-name="layerName"
            :translate-path="translatePath"
            @select-all="selectAllCs"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, inject, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter } from 'vue-router'
import WorldviewSuggestionList from './components/WorldviewSuggestionList.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AppButton from '@/components/common/AppButton.vue'
import { worldviewApi, worldviewUrls } from '@/api/worldview'
import { createSseController } from '@/api/sse'

const sseController = createSseController()
import { useProjectId } from '@/composables/useProjectId'
import { extractJsonFromString } from '@/utils/json'
import { showSuccess, showError, showWarning } from '@/utils/notify'
import { ArrowRight, ArrowDown } from '@element-plus/icons-vue'

const router = useRouter()
const { projectId } = useProjectId()
const setPageHeader = inject('setPageHeader')

// ========== 层级配置 ==========
const LAYERS = [
  {
    key: 'setting',
    name: '故事设定',
    icon: 'HomeFilled',
    groups: [
      {
        name: '世界标识',
        grid: true,
        fields: [
          { key: 'world_name', label: '世界名称', type: 'input', path: 'identity.world_name', placeholder: '输入世界名称' },
          { key: 'genre', label: '小说类型', type: 'select', path: 'identity.genre', placeholder: '请选择小说类型' },
        ],
      },
      {
        name: '核心定位',
        grid: true,
        fields: [
          { key: 'identity', label: '世界身份 / 类型气质', type: 'textarea', path: 'position.identity', placeholder: '如：高武世界、修仙文明、蒸汽朋克' },
          { key: 'tone', label: '整体调性', type: 'textarea', path: 'position.tone', placeholder: '如：严肃、轻松、黑暗、光明' },
        ],
      },
      {
        name: '概述与冲突',
        fields: [
          { key: 'overview', label: '世界概述', type: 'textarea', placeholder: '详细描述这个世界的背景、特征和核心设定' },
          { key: 'conflict', label: '核心冲突', type: 'textarea', placeholder: '这个世界的主要矛盾是什么？例如：人族与妖族的对立、资源枯竭的危机...' },
        ],
      },
    ],
  },
  {
    key: 'foundation',
    name: '世界基础',
    icon: 'MapLocation',
    groups: [
      {
        name: '地理环境',
        grid: true,
        fields: [
          { key: 'continent', label: '大陆分布', type: 'textarea', path: 'geography.continent_distribution', placeholder: '世界的大陆/板块分布' },
          { key: 'terrain', label: '特殊地形', type: 'textarea', path: 'geography.special_terrain', placeholder: '禁地、秘境、特殊地貌' },
        ],
      },
      {
        name: '历法节气',
        grid: true,
        fields: [
          { key: 'era', label: '纪年方式', type: 'textarea', path: 'calendar.era', placeholder: '如：灵历、新纪元' },
          { key: 'days', label: '一年天数', type: 'input', path: 'calendar.days_per_year', placeholder: '如：365天' },
          { key: 'seasons', label: '季节划分', type: 'textarea', path: 'calendar.seasons', placeholder: '季节与气候特征' },
          { key: 'festivals', label: '特殊节气 / 节日', type: 'textarea', path: 'calendar.festivals', placeholder: '重要节日' },
        ],
      },
      {
        name: '世界法则',
        fields: [
          { key: 'laws', label: '自然法则', type: 'textarea', path: 'rules.natural_laws', placeholder: '世界运行的基本自然法则' },
          { key: 'boundary', label: '世界边界', type: 'textarea', path: 'rules.boundaries', placeholder: '世界的边界与未知区域' },
          { key: 'axioms', label: '核心公理', type: 'axioms', path: 'rules.axioms', placeholder: '' },
          { key: 'balance', label: '平衡机制', type: 'textarea', placeholder: '世界如何维持平衡' },
        ],
      },
    ],
  },
  {
    key: 'power',
    name: '力量体系',
    icon: 'Lightning',
    groups: [
      {
        name: '能量体系',
        fields: [
          { key: 'energy_types', label: '主要能量类型', type: 'textarea', path: 'energy.types', placeholder: '如：灵气、斗气、魔力' },
          { key: 'energy_distribution', label: '能量分布', type: 'textarea', path: 'energy.distribution', placeholder: '能量在世界中的分布规律' },
          { key: 'energy_properties', label: '能量特性', type: 'textarea', path: 'energy.properties', placeholder: '如：五行相生相克、阴阳互济' },
          { key: 'level', label: '修炼等级', type: 'textarea', placeholder: '等级划分' },
        ],
      },
      {
        name: '武道传承',
        grid: true,
        fields: [
          { key: 'martial_categories', label: '功法分类', type: 'textarea', path: 'martial.categories', placeholder: '功法/技能体系分类' },
          { key: 'martial_inheritance', label: '传承方式', type: 'textarea', path: 'martial.inheritance', placeholder: '师门、学院、家族等传承方式' },
        ],
      },
      {
        name: '天材地宝',
        grid: true,
        fields: [
          { key: 'treasure_categories', label: '法宝分类', type: 'textarea', path: 'treasure.categories', placeholder: '法器/法宝等级分类' },
          { key: 'treasure_pills', label: '丹药体系', type: 'textarea', path: 'treasure.pills', placeholder: '丹药、灵药体系' },
        ],
      },
      {
        name: '妖兽灵异',
        grid: true,
        fields: [
          { key: 'beast_levels', label: '妖兽等级', type: 'textarea', path: 'beast.levels', placeholder: '异兽/妖兽等级划分' },
          { key: 'beast_mythical', label: '神兽传说', type: 'textarea', path: 'beast.mythical', placeholder: '传说中的神兽、凶兽' },
        ],
      },
    ],
  },
  {
    key: 'races',
    name: '种族族群',
    icon: 'Avatar',
    groups: [
      {
        name: '种族概览',
        grid: true,
        fields: [
          { key: 'category', label: '种族分类', type: 'textarea', placeholder: '主要种族类型' },
          { key: 'value', label: '种族价值观', type: 'textarea', placeholder: '各种族的价值取向' },
        ],
      },
      {
        name: '种族特征',
        grid: true,
        fields: [
          { key: 'lifespan', label: '寿命特征', type: 'textarea', path: 'trait.lifespan', placeholder: '各种族寿命' },
          { key: 'reproduction', label: '繁衍方式', type: 'textarea', path: 'trait.reproduction', placeholder: '繁衍与生育特征' },
          { key: 'physique', label: '体质特征', type: 'textarea', path: 'trait.physique', placeholder: '外貌与体质差异' },
        ],
      },
      {
        name: '种族关系',
        fields: [
          { key: 'relation', label: '种族关系', type: 'textarea', placeholder: '种族之间的对立、同盟、奴役等关系' },
        ],
      },
    ],
  },
  {
    key: 'society',
    name: '社会结构',
    icon: 'OfficeBuilding',
    groups: [
      {
        name: '朝堂体制',
        grid: true,
        fields: [
          { key: 'government', label: '国家体制', type: 'textarea', path: 'court.political_system', placeholder: '政治体制' },
          { key: 'bureaucracy', label: '官僚体系', type: 'textarea', path: 'court.bureaucracy', placeholder: '官职与权力结构' },
        ],
      },
      {
        name: '宗门武林',
        grid: true,
        fields: [
          { key: 'sect_level', label: '门派等级', type: 'textarea', path: 'sect.levels', placeholder: '宗门/门派等级划分' },
          { key: 'sect_heritage', label: '传承关系', type: 'textarea', path: 'sect.relationships', placeholder: '门派间的渊源与关系' },
          { key: 'martial_faction', label: '武林帮派', type: 'textarea', path: 'martial.factions', placeholder: '江湖帮派' },
          { key: 'martial_guild', label: '商会联盟', type: 'textarea', path: 'martial.alliances', placeholder: '商会、联盟组织' },
        ],
      },
      {
        name: '外部与阶层',
        grid: true,
        fields: [
          { key: 'external', label: '域外势力', type: 'textarea', placeholder: '已知世界之外的势力' },
          { key: 'class_level', label: '社会等级', type: 'textarea', path: 'strata.social_classes', placeholder: '社会阶层划分' },
          { key: 'class_mobility', label: '阶层流动', type: 'textarea', path: 'strata.mobility', placeholder: '阶层之间如何流动' },
        ],
      },
      {
        name: '经济资源',
        grid: true,
        fields: [
          { key: 'currency_type', label: '货币类型', type: 'textarea', path: 'currency.types', placeholder: '货币/硬通货' },
          { key: 'currency_rule', label: '货币规则', type: 'textarea', path: 'currency.rules', placeholder: '发行与兑换规则' },
          { key: 'resource', label: '资源分布', type: 'textarea', placeholder: '关键资源的产地与争夺' },
        ],
      },
    ],
  },
  {
    key: 'culture',
    name: '文化人文',
    icon: 'Brush',
    groups: [
      {
        name: '风俗节庆',
        grid: true,
        fields: [
          { key: 'festival', label: '节日庆典', type: 'textarea', path: 'custom.festivals', placeholder: '重要节日与庆典' },
          { key: 'ritual', label: '仪式习俗', type: 'textarea', path: 'custom.rituals', placeholder: '婚丧嫁娶等仪式' },
        ],
      },
      {
        name: '语言文字',
        grid: true,
        fields: [
          { key: 'language', label: '语言文字', type: 'textarea', path: 'language.languages', placeholder: '主要语言' },
          { key: 'script', label: '书写系统', type: 'textarea', path: 'language.writing_system', placeholder: '文字与书写载体' },
        ],
      },
      {
        name: '衣食住行',
        grid: true,
        fields: [
          { key: 'clothing', label: '服饰风格', type: 'textarea', path: 'daily.clothing', placeholder: '各阶层服饰' },
          { key: 'food', label: '饮食文化', type: 'textarea', path: 'daily.cuisine', placeholder: '特色饮食' },
          { key: 'architecture', label: '建筑特色', type: 'textarea', path: 'daily.architecture', placeholder: '建筑风格' },
          { key: 'transport', label: '交通方式', type: 'textarea', path: 'daily.transportation', placeholder: '交通与传讯方式' },
        ],
      },
      {
        name: '宗教信仰',
        grid: true,
        fields: [
          { key: 'deity', label: '神祇信仰', type: 'textarea', path: 'religion.deities', placeholder: '神灵与信仰对象' },
          { key: 'religion_org', label: '宗教组织', type: 'textarea', path: 'religion.organization', placeholder: '教会、庙宇等组织' },
          { key: 'faith_diff', label: '信仰差异', type: 'textarea', path: 'religion.faith_differences', placeholder: '不同信仰的冲突与差异' },
        ],
      },
    ],
  },
  {
    key: 'history',
    name: '历史进程',
    icon: 'Clock',
    groups: [
      {
        name: '历史沿革',
        grid: true,
        fields: [
          { key: 'ancient', label: '上古往事', type: 'textarea', placeholder: '上古神话、起源事件' },
          { key: 'modern', label: '近代变故', type: 'textarea', placeholder: '近代重大历史事件' },
        ],
      },
      {
        name: '现状与未来',
        grid: true,
        fields: [
          { key: 'crisis', label: '世界隐患', type: 'textarea', placeholder: '当前世界潜藏的危机' },
          { key: 'destiny', label: '宿命轨迹', type: 'textarea', placeholder: '世界命运的走向' },
          { key: 'future', label: '未来走向', type: 'textarea', placeholder: '可预见的未来' },
        ],
      },
    ],
  },
  {
    key: 'special',
    name: '特殊规则',
    icon: 'Star',
    groups: [
      {
        name: '禁忌与秘密',
        grid: true,
        fields: [
          { key: 'taboo', label: '世界禁忌', type: 'textarea', placeholder: '不可触犯的禁忌' },
          { key: 'secret', label: '隐藏秘密', type: 'textarea', placeholder: '世界背后隐藏的真相' },
        ],
      },
      {
        name: '命运与轮回',
        grid: true,
        fields: [
          { key: 'fortune', label: '运势规则', type: 'textarea', path: 'fate.fortune_rules', placeholder: '气运、因果规则' },
          { key: 'destiny', label: '命运类型', type: 'textarea', path: 'fate.destiny_types', placeholder: '宿命的类型' },
          { key: 'soul', label: '灵魂规则', type: 'textarea', path: 'reincarnation.soul_rules', placeholder: '灵魂的本质与去向' },
          { key: 'reincarnation', label: '轮回机制', type: 'textarea', path: 'reincarnation.mechanics', placeholder: '轮回/转世机制' },
        ],
      },
      {
        name: '异能设定',
        grid: true,
        fields: [
          { key: 'transmigration', label: '穿越规则', type: 'textarea', placeholder: '穿越者相关规则' },
          { key: 'system', label: '系统规则', type: 'textarea', placeholder: '系统/金手指规则' },
          { key: 'rules', label: '其他特殊规则', type: 'textarea', placeholder: '其余特殊设定' },
        ],
      },
    ],
  },
]

const genreGroups = [
  { group: '现代都市', items: ['现代都市', '都市生活', '都市职场', '都市校园', '都市竞技', '都市言情', '都市异能', '末世都市'] },
  { group: '奇幻', items: ['玄幻', '科幻', '仙侠', '武侠', '东方玄幻', '东方科幻', '东方仙侠', '东方武侠', '西方魔幻', '西方科幻', '近未来科幻', '星际冒险', '末世科幻'] },
  { group: '历史', items: ['历史架空', '历史穿越', '朝堂权谋', '王朝争霸'] },
  { group: '悬疑惊悚', items: ['悬疑', '惊悚', '恐怖', '末世', '刑侦推理', '无限副本'] },
]

const LAYER_NAMES = {
  setting: '故事设定',
  foundation: '世界基础',
  power: '力量体系',
  races: '种族族群',
  society: '社会结构',
  culture: '文化人文',
  history: '历史进程',
  special: '特殊规则',
}

const PATH_TERMS = {
  identity: '身份', genre: '题材', world_name: '世界名称', tone: '调性', overview: '概述', conflict: '核心冲突', position: '定位',
  geography: '地理', continent_distribution: '大陆分布', special_terrain: '特殊地形',
  calendar: '历法', era: '纪年', days_per_year: '一年天数', seasons: '季节', festivals: '节日',
  rules: '法则', natural_laws: '自然法则', boundaries: '世界边界', axioms: '核心公理', balance: '平衡机制',
  energy: '能量', types: '类型', distribution: '分布', properties: '特性', level: '等级',
  martial: '武道', categories: '分类', inheritance: '传承',
  treasure: '宝物', pills: '丹药', beast: '妖兽', mythical: '神兽传说', levels: '等级',
  category: '分类', value: '价值观', trait: '特征', lifespan: '寿命', reproduction: '繁衍', physique: '体质', relation: '关系',
  court: '朝堂', political_system: '政治体制', bureaucracy: '官僚体系',
  sect: '宗门', relationships: '关系', factions: '帮派', alliances: '联盟',
  external: '外部势力', strata: '阶层', social_classes: '社会等级', mobility: '阶层流动',
  currency: '货币', resource: '资源',
  custom: '风俗', rituals: '仪式',
  language: '语言', languages: '语言', writing_system: '书写系统',
  daily: '日常', clothing: '服饰', cuisine: '饮食', food: '饮食', architecture: '建筑', transportation: '交通',
  religion: '宗教', deities: '神祇', deity: '神祇', organization: '组织', faith_differences: '信仰差异', faith_diff: '信仰差异',
  ancient: '上古', modern: '近代', crisis: '隐患', destiny: '宿命', future: '未来',
  fate: '命运', fortune_rules: '运势规则', destiny_types: '命运类型',
  reincarnation: '轮回', soul_rules: '灵魂规则', mechanics: '机制',
  taboo: '禁忌', secret: '秘密', transmigration: '穿越', system: '系统',
}

// ========== 状态 ==========
const loading = ref(false)
// const exporting = ref(false)
const activeTab = ref('setting')
const worldviewId = ref(null)

const form = reactive({})
const axioms = ref([])
const snapshots = {}

const savingLayer = ref(null)
const polishingLayer = ref(null)
const applying = ref(false)

// 宏观缺口
const dState = ref('empty') // empty | noQuestions | hasQuestions | analyzing | hasSuggestions
const dpQuestions = ref([])
const dpSuggestions = ref([])

// 宏观一致性
const cState = ref('empty') // empty | noIssues | hasIssues | fixing | hasSuggestions
const csIssues = ref([])
const csSuggestions = ref([])

const hasDpAnswer = computed(() => dpQuestions.value.some((q) => (q.answer || '').trim()))

// 监听层级切换，重置折叠状态
watch(activeTab, () => {
  collapsedGroups.value = new Set()
})

// ========== 组内折叠状态 ==========
const collapsedGroups = ref(new Set())

function toggleGroupCollapse(groupKey) {
  if (collapsedGroups.value.has(groupKey)) {
    collapsedGroups.value.delete(groupKey)
  } else {
    collapsedGroups.value.add(groupKey)
  }
}

function isGroupCollapsed(groupKey) {
  return collapsedGroups.value.has(groupKey)
}

// ========== 工具函数 ==========
function layerName(layer) {
  return LAYER_NAMES[layer] || layer || '未知层级'
}

function translatePath(path) {
  if (!path) return ''
  return path
    .split('.')
    .filter((seg) => !LAYER_NAMES[seg])
    .map((seg) => PATH_TERMS[seg] || seg)
    .join(' / ')
}

function priorityLabel(p) {
  return { required: '必要', recommended: '推荐', optional: '可选' }[p] || '推荐'
}

function priorityType(p) {
  return { required: 'danger', recommended: 'primary', optional: 'info' }[p] || 'primary'
}

function getPath(obj, path) {
  if (!obj || !path) return ''
  let cur = obj
  for (const part of path.split('.')) {
    if (cur === null || cur === undefined || typeof cur !== 'object') return ''
    cur = cur[part]
  }
  return cur === null || cur === undefined ? '' : cur
}

function allFields(layerKey) {
  const layer = LAYERS.find((l) => l.key === layerKey)
  return layer ? layer.groups.flatMap((g) => g.fields) : []
}

// ========== 数据加载 / 映射 ==========
function applyLayerData(layerKey, data) {
  const fields = allFields(layerKey)
  for (const f of fields) {
    if (f.type === 'axioms') {
      const raw = getPath(data, f.path || f.key)
      let list = []
      if (Array.isArray(raw)) list = raw.map((v) => String(v)).filter((v) => v.trim())
      else if (typeof raw === 'string') list = raw.split('\n').map((v) => v.trim()).filter(Boolean)
      axioms.value = list
    } else {
      const raw = getPath(data, f.path || f.key)
      form[f.key] = Array.isArray(raw) ? raw.join('\n') : String(raw || '')
    }
  }
}

function snapshotLayer(layerKey) {
  const fields = allFields(layerKey)
  const snap = {}
  for (const f of fields) {
    snap[f.key] = f.type === 'axioms' ? axioms.value.join('\n') : form[f.key] || ''
  }
  snapshots[layerKey] = snap
}

function collectLayerBody(layerKey) {
  const fields = allFields(layerKey)
  const body = {}
  for (const f of fields) {
    if (f.type === 'axioms') {
      body[f.key] = axioms.value.map((a) => a.trim()).filter(Boolean).join('\n')
    } else {
      body[f.key] = form[f.key] || ''
    }
  }
  return body
}

function getDirtyFields(layerKey) {
  const snap = snapshots[layerKey] || {}
  const body = collectLayerBody(layerKey)
  const dirty = {}
  const changed = []
  for (const [k, v] of Object.entries(body)) {
    if ((snap[k] || '') !== v) {
      dirty[k] = v
      changed.push(k)
    }
  }
  return { dirty, changed }
}

async function loadWorldview() {
  loading.value = true
  try {
    const data = await worldviewApi.get(projectId.value)
    if (data && data.success && data.data) {
      worldviewId.value = data.data.worldview_id || data.data.id
      for (const layer of LAYERS) {
        applyLayerData(layer.key, data.data[layer.key] || {})
        snapshotLayer(layer.key)
      }
    } else {
      showError((data && data.message) || '获取世界观失败')
    }
  } catch (e) {
    console.error('加载世界观失败:', e)
  } finally {
    loading.value = false
  }
}

async function reloadWorldview() {
  try {
    const data = await worldviewApi.get(projectId.value)
    if (data && data.success && data.data) {
      worldviewId.value = data.data.worldview_id || data.data.id
      for (const layer of LAYERS) {
        applyLayerData(layer.key, data.data[layer.key] || {})
        snapshotLayer(layer.key)
      }
    }
  } catch (e) {
    console.error('重新加载世界观失败:', e)
  }
}

// ========== 保存 / AI 润色 ==========
async function saveLayer(layerKey) {
  if (!worldviewId.value) {
    showWarning('世界观未加载')
    return
  }
  savingLayer.value = layerKey
  try {
    const body = collectLayerBody(layerKey)
    const data = await worldviewApi.updateLayer(projectId.value, worldviewId.value, layerKey, body)
    if (data && data.success) {
      const layerData = (data.data && data.data[layerKey]) || {}
      applyLayerData(layerKey, layerData)
      snapshotLayer(layerKey)
      showSuccess(`${LAYER_NAMES[layerKey]}保存成功`)
    }
  } catch (e) {
    console.error('保存失败:', e)
  } finally {
    savingLayer.value = null
  }
}

async function polishLayer(layerKey) {
  if (!worldviewId.value) {
    showWarning('世界观未加载')
    return
  }
  if (layerKey === 'foundation' && axioms.value.filter((a) => a.trim()).length === 0) {
    showWarning('请先填写核心公理')
    return
  }
  const { dirty, changed } = getDirtyFields(layerKey)
  if (changed.length === 0) {
    showWarning('没有需要润色的修改，请先编辑字段内容')
    return
  }

  polishingLayer.value = layerKey
  try {
    let resultJson = null
    await sseController.stream(
      worldviewUrls.optimize(projectId.value, worldviewId.value, layerKey),
      {
        body: {
          genre: form.genre || '',
          layer_data: dirty,
          changed_keys: changed,
        },
        onEvent: (evt) => {
          if (evt.type === 'complete' && evt.data) {
            resultJson = extractJsonFromString(evt.data)
          }
        },
      },
    )

    if (!resultJson) {
      showError('AI 返回格式错误，请重试')
      return
    }
    if (resultJson.polished_data && typeof resultJson.polished_data === 'object') {
      resultJson = resultJson.polished_data
    }
    applyLayerData(layerKey, resultJson)
    snapshotLayer(layerKey)
    showSuccess('AI 润色完成，请检查后保存')
  } catch (e) {
    console.error('AI 润色失败:', e)
    showError('AI 润色失败：' + (e.message || '未知错误'))
  } finally {
    polishingLayer.value = null
  }
}

// ========== 公理编辑 ==========
function addAxiom() {
  axioms.value.push('')
}

function removeAxiom(index) {
  axioms.value.splice(index, 1)
}

// ========== 宏观缺口 ==========
async function generateQuestions() {
  if (!worldviewId.value) return
  dState.value = 'loading'
  try {
    const data = await worldviewApi.generateDeepeningQuestions(projectId.value, worldviewId.value)
    if (data && data.success) {
      const list = Array.isArray(data.data) ? data.data : []
      dpQuestions.value = list.map((q) => ({ ...q, answer: '' }))
      dState.value = list.length === 0 ? 'noQuestions' : 'hasQuestions'
      if (list.length === 0) showSuccess('世界观已较为完善')
    } else {
      dState.value = 'empty'
      showError((data && data.message) || '生成失败')
    }
  } catch (e) {
    dState.value = 'empty'
    console.error('检测缺口失败:', e)
  }
}

async function submitAnswers() {
  if (!worldviewId.value) return
  const qaList = dpQuestions.value
    .filter((q) => (q.answer || '').trim())
    .map((q) => ({ id: q.id, question: q.question, answer: q.answer.trim() }))
  if (qaList.length === 0) {
    showWarning('请先填写至少一个问题的答案')
    return
  }
  dState.value = 'analyzing'
  try {
    const data = await worldviewApi.submitDeepening(projectId.value, worldviewId.value, { qaList })
    if (data && data.success) {
      const list = Array.isArray(data.data) ? data.data : []
      dpSuggestions.value = list.map((s) => ({ ...s, selected: true }))
      dState.value = 'hasSuggestions'
      showSuccess(`已生成 ${list.length} 条修改建议`)
    } else {
      dState.value = 'hasQuestions'
      showError((data && data.message) || '分析失败')
    }
  } catch (e) {
    dState.value = 'hasQuestions'
    console.error('提交分析失败:', e)
  }
}

function selectAllDp(selected) {
  dpSuggestions.value.forEach((s) => (s.selected = selected))
}

function resetDeepening() {
  dState.value = 'empty'
  dpQuestions.value = []
  dpSuggestions.value = []
}

async function applyDeepeningChanges() {
  const selected = dpSuggestions.value.filter((s) => s.selected)
  if (selected.length === 0) {
    showWarning('请至少选择一个修改建议')
    return
  }
  applying.value = true
  try {
    const changes = selected.map((s) => ({
      targetLayer: s.targetLayer,
      targetField: s.targetField,
      newValue: s.newValue,
    }))
    const data = await worldviewApi.applyDeepening(projectId.value, worldviewId.value, { changes })
    if (data && data.success) {
      showSuccess('修改已应用')
      resetDeepening()
      await reloadWorldview()
    }
  } catch (e) {
    console.error('应用修改失败:', e)
  } finally {
    applying.value = false
  }
}

// ========== 宏观一致性 ==========
async function checkConsistency() {
  if (!worldviewId.value) return
  cState.value = 'checking'
  try {
    const data = await worldviewApi.checkConsistency(projectId.value, worldviewId.value)
    if (data && data.success) {
      const list = (data.data && data.data.issues) || []
      csIssues.value = list.map((i) => ({ ...i, note: '' }))
      cState.value = list.length === 0 ? 'noIssues' : 'hasIssues'
      showSuccess('检查完成')
    } else {
      cState.value = 'empty'
      showError((data && data.message) || '检查失败')
    }
  } catch (e) {
    cState.value = 'empty'
    console.error('一致性检查失败:', e)
  }
}

async function fixConsistency() {
  if (!worldviewId.value) return
  const manual = csIssues.value
    .map((i) => (i.note || '').trim())
    .filter(Boolean)
    .join('\n')
  cState.value = 'fixing'
  try {
    const data = await worldviewApi.fixConsistency(projectId.value, worldviewId.value, { manual_issues: manual })
    if (data && data.success) {
      const list = Array.isArray(data.data) ? data.data : []
      if (list.length === 0) {
        showWarning('AI 未生成修复建议')
        cState.value = 'hasIssues'
        return
      }
      csSuggestions.value = list.map((s) => ({ ...s, selected: true }))
      cState.value = 'hasSuggestions'
      showSuccess(`已生成 ${list.length} 条修复建议`)
    } else {
      cState.value = 'hasIssues'
      showError((data && data.message) || '生成修复建议失败')
    }
  } catch (e) {
    cState.value = 'hasIssues'
    console.error('生成修复建议失败:', e)
  }
}

function selectAllCs(selected) {
  csSuggestions.value.forEach((s) => (s.selected = selected))
}

function resetConsistency() {
  cState.value = 'empty'
  csIssues.value = []
  csSuggestions.value = []
}

async function applyConsistencyChanges() {
  const selected = csSuggestions.value.filter((s) => s.selected)
  if (selected.length === 0) {
    showWarning('请至少选择一个修改建议')
    return
  }
  applying.value = true
  try {
    const changes = selected.map((s) => ({
      targetLayer: s.targetLayer,
      targetField: s.targetField,
      newValue: s.newValue,
    }))
    const data = await worldviewApi.applyDeepening(projectId.value, worldviewId.value, { changes })
    if (data && data.success) {
      showSuccess('修改已应用')
      resetConsistency()
      await reloadWorldview()
    }
  } catch (e) {
    console.error('应用修复失败:', e)
  } finally {
    applying.value = false
  }
}

// ========== 导出 / 导航 ==========
async function exportMarkdown() {
  exporting.value = true
  try {
    const data = await worldviewApi.exportMarkdown(projectId.value)
    if (data && data.success && data.data && data.data.markdown) {
      const blob = new Blob([data.data.markdown], { type: 'text/markdown;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${form.world_name || '世界观'}.md`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      showSuccess('导出成功')
    } else {
      showWarning('暂无可导出的世界观内容')
    }
  } catch (e) {
    console.error('导出失败:', e)
  } finally {
    exporting.value = false
  }
}

function goChat() {
  router.push({ name: 'WorldviewChat', params: { projectId: projectId.value } })
}

onMounted(() => {
  setPageHeader('世界观设定', '分层构建世界基础、力量体系、种族、社会、文化、历史与特殊规则，支持 AI 润色与宏观审校')
  loadWorldview()
})

onBeforeUnmount(() => {
  sseController.abort()
})
</script>

<style lang="scss">
// 覆盖父级布局（unscoped），锁定世界观页面为视口高度，内部滚动
.project-layout:has(.worldview-view) {
  height: 100vh;
  overflow: hidden;
}

.project-layout:has(.worldview-view) .project-topbar {
  position: relative;
  flex-shrink: 0;
}

.project-layout:has(.worldview-view) .project-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  max-width: none;
  padding: 0;
}
</style>

<style lang="scss" scoped>
.worldview-view {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.wv-workspace {
  flex: 1;
  display: flex;
  gap: 12px;
  min-height: 0;
  padding: 12px;
}

// ========== 左侧导航 ==========
.wv-nav {
  width: 180px;
  flex-shrink: 0;
  border-radius: var(--radius-md);
  padding: 12px 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);

  .el-icon {
    font-size: 16px;
  }

  &:hover {
    background: rgba(255, 255, 255, 0.06);
    color: var(--text-primary);
  }

  &.active {
    background: rgba(99, 102, 241, 0.18);
    color: var(--primary);
    font-weight: 600;
    border: 1px solid rgba(99, 102, 241, 0.35);
  }
}

.nav-divider {
  height: 1px;
  background: var(--glass-border);
  margin: 8px 12px;
}

// ========== 右侧主区 ==========
.wv-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  border-radius: var(--radius-md);
  padding: 24px 28px;
  overflow-y: auto;
  min-width: 0;
}

.layer-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.tool-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
  flex: 1;
  min-height: 0;
}

.layer-header,
.tool-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.layer-title {
  margin: 0 0 4px;
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.layer-hint {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}

.layer-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

// ========== 字段组 ==========
.field-groups {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 0;
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--glass-border);
  overflow: hidden;
  transition: all var(--transition-fast);

  &:hover {
    border-color: rgba(99, 102, 241, 0.2);
  }

  &.collapsed {
    .group-fields {
      display: none;
    }
  }
}

.group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  cursor: pointer;
  user-select: none;
  transition: background var(--transition-fast);

  &:hover {
    background: rgba(255, 255, 255, 0.04);
  }
}

.group-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: var(--primary);
  line-height: 1.2;
}

.collapse-icon {
  font-size: 14px;
  color: var(--text-muted);
  transition: transform var(--transition-fast);
}

.group-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.field-count {
  font-size: 11px;
  color: var(--text-muted);
  padding: 2px 6px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: var(--radius-sm);
}

.group-fields {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 0 16px 16px;

  &.grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 14px;
  }
}

.field-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.field-label {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}

.field-control {
  width: 100%;
}

// ========== 公理 ==========
.axiom-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.axiom-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.axiom-del {
  color: var(--danger);
  flex-shrink: 0;
}

.axiom-add {
  align-self: flex-start;
}

// ========== 工具面板 ==========
:deep(.success) {
  .empty-icon {
    color: var(--success);
    opacity: 0.9;
  }

  .empty-text {
    color: var(--text-secondary);
  }
}

.question-list,
.issue-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.question-card,
.issue-card {
  padding: 16px 18px;
  border-radius: var(--radius-sm);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.question-head,
.issue-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.question-index,
.issue-index {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}

.question-text,
.issue-message {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-primary);
  font-weight: 500;
}

.issue-detail {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-secondary);
}

.issue-path {
  margin: 0;
}

.quick-options {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.quick-label {
  font-size: 12px;
  color: var(--text-muted);
}

@media (max-width: 1200px) {
  .wv-workspace {
    flex-direction: column;
    gap: 8px;
    padding: 8px;
  }

  .wv-nav {
    width: 100%;
    flex-direction: row;
    flex-wrap: wrap;
  }

  .nav-divider {
    display: none;
  }

  .group-header {
    padding: 10px 12px;
  }

  .group-fields {
    padding: 0 12px 12px;

    &.grid {
      grid-template-columns: 1fr;
    }
  }
}
</style>
