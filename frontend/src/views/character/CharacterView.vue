<template>
  <div class="character-view">
    <Teleport defer to="#header-right-teleport">
      <AppButton variant="ai" @click="checkVisible = true">
        AI 校验
      </AppButton>
      <AppButton variant="accent" @click="openCreate">
        创建角色
      </AppButton>
    </Teleport>
    <!-- 筛选栏 -->
    <div class="char-filter">
      <el-input
        v-model="searchText"
        class="filter-search"
        placeholder="搜索角色名..."
        clearable
        :prefix-icon="Search"
      />
      <el-select v-model="roleFilter" class="filter-select" placeholder="角色定位">
        <el-option label="全部定位" value="" />
        <el-option
          v-for="r in ROLE_FILTERS"
          :key="r"
          :label="`${r} (${roleCounts[r] || 0})`"
          :value="r"
        />
      </el-select>
      <el-select v-model="factionFilter" class="filter-select" placeholder="势力/阵营">
        <el-option label="全部势力" value="" />
        <el-option v-for="f in factionOptions" :key="f" :label="f" :value="f" />
      </el-select>
    </div>

    <!-- 角色网格 -->
    <div class="char-grid" v-loading="loading" element-loading-text="加载角色列表...">
      <div
        v-for="c in activeFiltered"
        :key="c.id"
        class="char-card glass-surface"
        @click="openEdit(c.id)"
      >
        <div class="char-card-top">
          <div class="char-avatar">{{ (c.name || '?').charAt(0) }}</div>
          <div class="char-info">
            <h4 class="char-name">{{ c.name }}</h4>
            <div class="char-tags">
              <el-tag size="small" type="primary" effect="dark" round>{{ c.role_type || '配角' }}</el-tag>
              <el-tag
                v-for="f in factionsOf(c)"
                :key="f"
                size="small"
                type="warning"
                effect="plain"
                round
              >
                {{ f }}
              </el-tag>
            </div>
          </div>
        </div>
        <p v-if="c.tagline" class="char-tagline">{{ c.tagline }}</p>
      </div>
    </div>

    <EmptyState
      v-if="!loading && !characters.length"
      icon="Avatar"
      text="暂无角色，点击右上角「创建角色」按钮开始添加"
    />
    <EmptyState
      v-else-if="!loading && !filteredCharacters.length"
      icon="Search"
      text="没有找到匹配的角色，尝试调整搜索或筛选条件"
    />

    <!-- 已删除角色 -->
    <div v-if="deletedFiltered.length" class="deleted-section">
      <div class="deleted-header">
        <el-icon><Delete /></el-icon>
        <span>已删除角色</span>
        <span class="deleted-count">{{ deletedFiltered.length }}</span>
      </div>
      <div class="char-grid">
        <div v-for="c in deletedFiltered" :key="c.id" class="char-card char-card-deleted glass-surface">
          <div class="char-card-top">
            <div class="char-avatar">{{ (c.name || '?').charAt(0) }}</div>
            <div class="char-info">
              <h4 class="char-name">{{ c.name }}</h4>
              <div class="char-tags">
                <el-tag size="small" type="info" effect="plain" round>已删除</el-tag>
              </div>
            </div>
          </div>
          <AppButton variant="default" size="small" plain class="restore-btn" @click="restoreCharacter(c)">
            <el-icon><RefreshLeft /></el-icon>
            恢复
          </AppButton>
        </div>
      </div>
    </div>

    <!-- 创建角色弹窗 -->
    <AppModal v-model:visible="createVisible" title="创建角色" width="800px" height="65vh" min-height="65vh">
      <div class="edit-modal-container">
        <!-- Tab 栏固定在顶部 -->
        <el-tabs v-model="createTab" class="char-tabs-fixed">
          <el-tab-pane label="手动创建" name="manual" />
          <el-tab-pane label="AI 生成" name="ai" />
          <el-tab-pane label="批量生成" name="batch" />
        </el-tabs>
        
        <!-- 内容区可滚动 -->
        <div class="tab-content-scroll">
          <!-- 手动创建 -->
          <div v-if="createTab === 'manual'" class="tab-pane-content">
            <CharacterFormFields :form="manualForm" tab="all" />
            <div class="editor-section">
              <div class="editor-section-title"><span class="title-bar"></span>人际关系</div>
              <RelationshipEditor
                v-model="manualRels"
                :characters="createRelCharacters"
                :relationship-types="relTypes"
              />
            </div>
          </div>

          <!-- AI 生成 -->
          <div v-else-if="createTab === 'ai'" class="tab-pane-content">
            <div v-if="!aiGenerated" class="ai-desc-block">
              <p class="ai-desc-hint">描述你想要的角色：题材、身份、性格、与其他角色的关系等，AI 将生成完整设定</p>
              <el-input
                v-model="aiRequirement"
                type="textarea"
                :autosize="{ minRows: 4, maxRows: 20 }"
                maxlength="2000"
                show-word-limit
                placeholder="例如：一个表面玩世不恭、实则心思缜密的魔教少主，与主角是宿敌却又数次暗中相助..."
              />
            </div>
            <template v-else>
              <CharacterFormFields :form="aiForm" tab="all" />
              <div class="editor-section">
                <div class="editor-section-title"><span class="title-bar"></span>人际关系</div>
                <RelationshipEditor
                  v-model="aiRels"
                  :characters="createRelCharacters"
                  :relationship-types="relTypes"
                />
              </div>
            </template>
          </div>

          <!-- 批量生成 -->
          <div v-else-if="createTab === 'batch'" class="tab-pane-content">
            <div v-if="!batchList.length" class="ai-desc-block">
              <p class="ai-desc-hint">描述一组角色的需求，AI 将批量生成多个互相关联的角色</p>
              <el-input
                v-model="batchRequirement"
                type="textarea"
                :autosize="{ minRows: 4, maxRows: 20 }"
                maxlength="2000"
                show-word-limit
                placeholder="例如：生成一个修真宗门的核心人物群像，包括掌门、几位长老、核心弟子，彼此间有师承、竞争与隐秘矛盾..."
              />
            </div>
            <div v-else class="batch-list">
              <div v-for="(char, idx) in batchList" :key="idx" class="batch-card" :class="{ 'is-unchecked': !char.selected }">
                <el-checkbox v-model="char.selected" class="batch-checkbox" />
                <div class="batch-content">
                  <div class="batch-header">
                    <span class="batch-name">{{ char.name || '未命名' }}</span>
                    <el-tag size="small" type="primary" effect="dark" round>{{ normalizeRoleType(char.role_type) }}</el-tag>
                    <span v-if="char.age !== null && char.age !== '' && char.age !== undefined" class="batch-meta">年龄：{{ char.age }}</span>
                    <span v-if="char.identity" class="batch-meta">身份：{{ char.identity }}</span>
                    <span v-if="char.faction" class="batch-meta">势力：{{ char.faction }}</span>
                  </div>
                  <div v-if="char.personality" class="batch-desc">
                    <strong>性格</strong>{{ truncate(char.personality, 120) }}
                  </div>
                  <div v-if="char.backstory" class="batch-desc">
                    <strong>背景</strong>{{ truncate(char.backstory, 120) }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="modal-footer-content create-footer">
          <div class="footer-right">
            <AppButton @click="createVisible = false" class="footer-btn">取消</AppButton>
            <template v-if="createTab === 'manual'">
              <AppButton variant="ai" :loading="polishing" :disabled="!manualForm.name.trim()" @click="polishManual" class="footer-btn">
                <el-icon><MagicStick /></el-icon> AI 润色
              </AppButton>
              <AppButton variant="accent" :loading="saving" :disabled="!manualForm.name.trim()" @click="saveManual" class="footer-btn">
                保存角色
              </AppButton>
            </template>
            <template v-else-if="createTab === 'ai'">
              <AppButton
                v-if="aiGenerated"
                :loading="generating"
                @click="generateSingle"
                class="footer-btn"
              >
                <el-icon><RefreshLeft /></el-icon> 重新生成
              </AppButton>
              <AppButton
                v-else
                variant="accent"
                :loading="generating"
                :disabled="!aiRequirement.trim()"
                @click="generateSingle"
                class="footer-btn"
              >
                <el-icon><MagicStick /></el-icon> AI 生成
              </AppButton>
              <AppButton v-if="aiGenerated" variant="accent" :loading="saving" @click="saveAi" class="footer-btn">
                保存角色
              </AppButton>
            </template>
            <template v-else>
              <AppButton
                v-if="batchList.length"
                :loading="generating"
                @click="generateBatch"
                class="footer-btn"
              >
                <el-icon><RefreshLeft /></el-icon> 重新生成
              </AppButton>
              <AppButton
                v-else
                variant="accent"
                :loading="generating"
                :disabled="!batchRequirement.trim()"
                @click="generateBatch"
                class="footer-btn"
              >
                <el-icon><MagicStick /></el-icon> 批量生成
              </AppButton>
              <AppButton
                v-if="batchList.length"
                variant="accent"
                :loading="saving"
                :disabled="!batchSelectedCount"
                @click="saveBatch"
                class="footer-btn"
              >
                批量保存{{ batchSelectedCount ? `（${batchSelectedCount}）` : '' }}
              </AppButton>
            </template>
          </div>
        </div>
      </template>
    </AppModal>

    <!-- 编辑角色弹窗 -->
    <AppModal v-model:visible="editVisible" title="编辑角色" width="800px" height="65vh" min-height="65vh">
      <div class="edit-modal-container" v-loading="editLoading" element-loading-text="加载角色详情...">
        <!-- Tab 栏固定在顶部 -->
        <el-tabs v-model="editTab" class="char-tabs-fixed">
          <el-tab-pane label="基础信息" name="basic" />
          <el-tab-pane label="性格心理" name="mind" />
          <el-tab-pane label="外貌能力" name="ability" />
          <el-tab-pane label="背景经历" name="story" />
          <el-tab-pane label="关系网络" name="relations" />
          <el-tab-pane label="关系图谱" name="graph" />
        </el-tabs>
        
        <!-- 内容区可滚动 -->
        <div class="tab-content-scroll">
          <div v-if="editTab === 'basic'" class="tab-pane-content">
            <CharacterFormFields :form="editForm" tab="basic" />
          </div>
          <div v-else-if="editTab === 'mind'" class="tab-pane-content">
            <CharacterFormFields :form="editForm" tab="mind" />
          </div>
          <div v-else-if="editTab === 'ability'" class="tab-pane-content">
            <CharacterFormFields :form="editForm" tab="ability" />
          </div>
          <div v-else-if="editTab === 'story'" class="tab-pane-content">
            <CharacterFormFields :form="editForm" tab="story" />
            <div class="editor-section">
              <div class="editor-section-title"><span class="title-bar"></span>经历</div>
              <ExperienceEditor v-model="editExperiences" />
            </div>
          </div>
          <div v-else-if="editTab === 'relations'" class="tab-pane-content">
            <RelationshipEditor
              v-model="editRels"
              :characters="editRelCharacters"
              :relationship-types="relTypes"
            />
          </div>
          <div v-else-if="editTab === 'graph'" class="tab-pane-content">
            <CharacterGraphModal
              :project-id="projectId"
              :character-id="editId"
              :character-name="editForm.name"
            />
          </div>
        </div>
      </div>

      <template #footer>
        <div class="modal-footer-content">
          <AppButton variant="danger" plain @click="removeCharacter" class="footer-btn">
            <el-icon><Delete /></el-icon> 删除
          </AppButton>
          <div class="footer-right">
            <AppButton @click="editVisible = false" class="footer-btn">取消</AppButton>
            <AppButton variant="ai" :loading="polishing" :disabled="!editForm.name.trim()" @click="polishEdit" class="footer-btn">
              <el-icon><MagicStick /></el-icon> AI 润色
            </AppButton>
            <AppButton variant="accent" :loading="saving" :disabled="!editForm.name.trim()" @click="saveEdit" class="footer-btn">
              保存修改
            </AppButton>
          </div>
        </div>
      </template>
    </AppModal>

    <!-- AI 检测/优化弹窗 -->
    <CharacterCheckModal
      v-model:visible="checkVisible"
      :project-id="projectId"
      @saved="loadCharacters"
    />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, inject, nextTick } from 'vue'
// import { useRouter } from 'vue-router'
import { /* Plus, */ Search, /* Connection, */ MagicStick, Delete, RefreshLeft } from '@element-plus/icons-vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AppModal from '@/components/common/AppModal.vue'
import AppButton from '@/components/common/AppButton.vue'
import CharacterFormFields from './components/CharacterFormFields.vue'
import RelationshipEditor from './components/RelationshipEditor.vue'
import ExperienceEditor from './components/ExperienceEditor.vue'
import CharacterCheckModal from './components/CharacterCheckModal.vue'
import CharacterGraphModal from './components/CharacterGraphModal.vue'
import { characterApi } from '@/api/character'
import { useProjectId } from '@/composables/useProjectId'
import { showSuccess, showError, showWarning } from '@/utils/notify'
import { showConfirmModal } from '@/utils/modal'
import { extractJsonFromString } from '@/utils/json'

// const router = useRouter()
const { projectId } = useProjectId()
const setPageHeader = inject('setPageHeader')

const ROLE_FILTERS = ['主角', '反派', '配角', '路人']
const GENDER_VALUES = ['男', '女', '未知']

// 角色定位归一化（兼容 LLM 返回的多种写法，映射到表单四分类）
const ROLE_MAP = {
  主角: '主角', 主人公: '主角', 男主: '主角', 女主: '主角', 男主角: '主角', 女主角: '主角',
  protagonist: '主角', main: '主角', hero: '主角', heroine: '主角',
  反派: '反派', 恶人: '反派', 对手: '反派', villain: '反派', antagonist: '反派', enemy: '反派',
  配角: '配角', supporting: '配角', side: '配角',
  路人: '路人', 龙套: '路人', npc: '路人', extra: '路人',
}

function normalizeRoleType(val) {
  if (!val) return '配角'
  const key = String(val).trim()
  return ROLE_MAP[key] || ROLE_MAP[key.toLowerCase()] || '配角'
}

// 势力输入归一化：非汉字英文数字 → 逗号
function normalizeFaction(input) {
  if (!input) return ''
  return input
    .replace(/[^a-zA-Z0-9一-鿿]/g, ',')
    .replace(/(,\s*)+/g, ',')
    .replace(/^,|,$/g, '')
    .trim()
}

function parseAge(v) {
  if (v === null || v === undefined || v === '') return null
  if (typeof v === 'number') return Number.isFinite(v) ? Math.trunc(v) : null
  const nums = String(v).match(/\d+/)
  return nums ? parseInt(nums[0], 10) : null
}

// ---- 关系类型配置（后端动态获取）----
const relTypes = ref(['朋友', '恋人', '配偶', '父母', '子女', '兄弟姐妹', '师父', '徒弟', '敌人', '对手', '导师', '门生', '盟友', '亲属', '君主', '臣子', '其他'])
const enToCn = ref({
  friend: '朋友', lover: '恋人', spouse: '配偶', parent: '父母', child: '子女',
  sibling: '兄弟姐妹', master: '师父', apprentice: '徒弟', disciple: '徒弟',
  enemy: '敌人', rival: '对手', mentor: '导师', protege: '门生', partner: '盟友',
  ally: '盟友', family: '亲属', other: '其他',
})

function normalizeRelType(t) {
  if (!t) return '其他'
  if (relTypes.value.includes(t)) return t
  const cn = enToCn.value[String(t).toLowerCase()]
  return cn || '其他'
}

// 将 LLM/存储中的 relationships 解析为标准对象数组
function parseRelationships(rels) {
  if (!rels) return []

  const parseOne = (s) => {
    const m = s.match(/(.+?)是我的(.+?)(?:\s*-\s*(.+))?$/)
    if (m) {
      return {
        targetName: m[1].trim(),
        relationshipType: normalizeRelType(m[2].trim()),
        description: (m[3] || '').trim(),
        createReverse: true,
      }
    }
    const parts = s.split('-')
    if (parts.length >= 2) {
      return {
        targetName: parts[1].trim(),
        relationshipType: normalizeRelType(parts[0].trim()),
        description: parts.slice(2).join('-').trim(),
        createReverse: true,
      }
    }
    return null
  }

  if (typeof rels === 'string') {
    return rels
      .split(/[,，]/)
      .map((s) => s.trim())
      .filter(Boolean)
      .map(parseOne)
      .filter(Boolean)
  }

  if (Array.isArray(rels)) {
    return rels
      .map((r) => {
        if (r && typeof r === 'object') {
          return {
            targetName: r.targetName || '',
            relationshipType: normalizeRelType(r.relationshipType),
            description: r.description || '',
            createReverse: r.createReverse !== false,
          }
        }
        if (typeof r === 'string') return parseOne(r)
        return null
      })
      .filter(Boolean)
  }

  return []
}

function cleanRels(rels) {
  return (rels || [])
    .filter((r) => r.targetName && r.targetName.trim())
    .map((r) => ({
      targetName: r.targetName.trim(),
      relationshipType: r.relationshipType || '其他',
      description: r.description || '',
      createReverse: r.createReverse !== false,
    }))
}

// ---- 表单工厂 ----
function makeEmptyForm() {
  return {
    name: '', gender: '未知', role_type: '配角', age: null,
    identity: '', faction: '', tagline: '',
    personality: '', strengths: '', flaws: '', obsession: '',
    motivation: '', taboos: '', appearance: '', abilities: '',
    weaknesses: '', backstory: '', development: '',
  }
}

// 将 AI 生成的角色数据应用到表单
function applyAiChar(form, relsRef, char) {
  Object.assign(form, {
    name: char.name || '',
    gender: GENDER_VALUES.includes(char.gender) ? char.gender : '未知',
    role_type: normalizeRoleType(char.role_type || char.role || '配角'),
    age: parseAge(char.age),
    identity: char.identity || '',
    faction: char.faction || '',
    tagline: char.tagline ?? char.tags ?? '',
    personality: char.personality || '',
    strengths: char.strengths || '',
    flaws: char.flaws || '',
    obsession: char.obsession || '',
    motivation: char.motivation || '',
    taboos: char.taboos || '',
    appearance: char.appearance || '',
    abilities: char.abilities || '',
    weaknesses: char.weaknesses || '',
    backstory: char.backstory || '',
    development: char.development || '',
  })
  relsRef.value = parseRelationships(char.relationships)
}

function buildPayload(form, rels) {
  return {
    name: (form.name || '').trim(),
    gender: form.gender || '未知',
    role_type: form.role_type || '配角',
    age: form.age ?? '',
    identity: form.identity || '',
    faction: normalizeFaction(form.faction || ''),
    tagline: form.tagline || '',
    personality: form.personality || '',
    strengths: form.strengths || '',
    flaws: form.flaws || '',
    obsession: form.obsession || '',
    motivation: form.motivation || '',
    taboos: form.taboos || '',
    appearance: form.appearance || '',
    abilities: form.abilities || '',
    weaknesses: form.weaknesses || '',
    backstory: form.backstory || '',
    development: form.development || '',
    relationships: cleanRels(rels),
  }
}

// ---- 列表状态 ----
const loading = ref(false)
const characters = ref([])
const searchText = ref('')
const roleFilter = ref('')
const factionFilter = ref('')

const activeChars = computed(() => characters.value.filter((c) => !c.is_deleted))

const filteredCharacters = computed(() => {
  const search = searchText.value.toLowerCase().trim()
  return characters.value.filter((c) => {
    const matchName = !search || (c.name || '').toLowerCase().includes(search)
    const matchRole = !roleFilter.value || c.role_type === roleFilter.value
    let matchFaction = true
    if (factionFilter.value) {
      const fs = (c.faction || '').split(',').map((f) => f.trim())
      matchFaction = fs.includes(factionFilter.value)
    }
    return matchName && matchRole && matchFaction
  })
})

const activeFiltered = computed(() => filteredCharacters.value.filter((c) => !c.is_deleted))
const deletedFiltered = computed(() => filteredCharacters.value.filter((c) => c.is_deleted))

const roleCounts = computed(() => {
  const counts = {}
  activeChars.value.forEach((c) => {
    const r = c.role_type || '配角'
    counts[r] = (counts[r] || 0) + 1
  })
  return counts
})

const factionOptions = computed(() => {
  const counts = {}
  activeChars.value.forEach((c) => {
    ;(c.faction || '').split(',').forEach((f) => {
      const t = f.trim()
      if (t) counts[t] = (counts[t] || 0) + 1
    })
  })
  return Object.keys(counts).sort()
})

const createRelCharacters = computed(() =>
  activeChars.value.map((c) => ({ id: c.id, name: c.name })),
)

function factionsOf(c) {
  return (c.faction || '').split(',').map((f) => f.trim()).filter(Boolean)
}

function truncate(text, len) {
  if (!text) return ''
  return text.length > len ? text.slice(0, len) + '...' : text
}

// ---- 弹窗状态 ----
const createVisible = ref(false)
const createTab = ref('manual')
const saving = ref(false)
const generating = ref(false)
const polishing = ref(false)

const manualForm = reactive(makeEmptyForm())
const manualRels = ref([])
const aiForm = reactive(makeEmptyForm())
const aiRels = ref([])
const aiGenerated = ref(false)
const aiRequirement = ref('')
const batchRequirement = ref('')
const batchList = ref([])

const editVisible = ref(false)
const editLoading = ref(false)
const editTab = ref('basic')
const editId = ref(null)
const editForm = reactive(makeEmptyForm())
const editRels = ref([])
const editExperiences = ref([])

const checkVisible = ref(false)

const editRelCharacters = computed(() =>
  activeChars.value.filter((c) => c.id !== editId.value).map((c) => ({ id: c.id, name: c.name })),
)

const batchSelectedCount = computed(() => batchList.value.filter((c) => c.selected).length)

// ---- 数据加载 ----
async function loadCharacters() {
  if (!projectId.value) return
  loading.value = true
  try {
    const res = await characterApi.list(projectId.value)
    characters.value = res.characters || []
  } catch (err) {
    console.error('加载角色失败:', err)
    showError('加载角色失败')
  } finally {
    loading.value = false
  }
}

async function loadRelTypes() {
  try {
    const res = await characterApi.getRelationshipTypes(projectId.value)
    if (res?.types?.length) relTypes.value = res.types
    if (res?.en_to_cn) enToCn.value = res.en_to_cn
  } catch (err) {
    console.warn('加载关系类型配置失败，使用默认值', err)
  }
}

// function goGraph() {
//   router.push({ name: 'Graph', params: { projectId: projectId.value } })
// }

// ---- 创建 ----
function openCreate() {
  Object.assign(manualForm, makeEmptyForm())
  Object.assign(aiForm, makeEmptyForm())
  manualRels.value = []
  aiRels.value = []
  editExperiences.value = []
  aiGenerated.value = false
  aiRequirement.value = ''
  batchRequirement.value = ''
  batchList.value = []
  createTab.value = 'manual'
  createVisible.value = true
}

async function generateSingle() {
  if (!aiRequirement.value.trim()) {
    showError('请输入角色描述')
    return
  }
  generating.value = true
  try {
    const res = await characterApi.generate(projectId.value, {
      requirement: aiRequirement.value.trim(),
    })
    let result = extractJsonFromString(res?.data || '')
    if (Array.isArray(result)) result = result[0]
    if (!result || typeof result !== 'object') {
      showError('生成结果解析失败，请重试')
      return
    }
    applyAiChar(aiForm, aiRels, result)
    aiGenerated.value = true
    showSuccess('角色生成完成，请确认后保存')
  } catch (err) {
    console.error('生成角色失败:', err)
    showError(err.message || '生成失败，请重试')
  } finally {
    generating.value = false
  }
}

async function generateBatch() {
  if (!batchRequirement.value.trim()) {
    showError('请输入角色描述')
    return
  }
  generating.value = true
  batchList.value = []
  try {
    const res = await characterApi.generate(projectId.value, {
      requirement: batchRequirement.value.trim(),
      is_batch: true,
    })
    const result = extractJsonFromString(res?.data || '')
    if (Array.isArray(result) && result.length) {
      batchList.value = result.map((c) => ({ ...c, selected: true }))
      showSuccess(`成功生成 ${batchList.value.length} 个角色，请勾选后保存`)
    } else {
      showError('生成失败，返回格式错误')
    }
  } catch (err) {
    console.error('批量生成失败:', err)
    showError(err.message || '生成失败，请重试')
  } finally {
    generating.value = false
  }
}

async function saveManual() {
  if (!manualForm.name.trim()) {
    showError('请输入角色名称')
    return
  }
  saving.value = true
  try {
    await characterApi.create(projectId.value, buildPayload(manualForm, manualRels.value))
    showSuccess('角色创建成功')
    createVisible.value = false
    loadCharacters()
  } catch (err) {
    console.error('创建角色失败:', err)
  } finally {
    saving.value = false
  }
}

async function saveAi() {
  if (!aiForm.name.trim()) {
    showError('角色名称缺失，请检查生成结果')
    return
  }
  saving.value = true
  try {
    await characterApi.create(projectId.value, buildPayload(aiForm, aiRels.value))
    showSuccess('角色保存成功')
    createVisible.value = false
    loadCharacters()
  } catch (err) {
    console.error('保存角色失败:', err)
  } finally {
    saving.value = false
  }
}

async function saveBatch() {
  const selected = batchList.value.filter((c) => c.selected && (c.name || '').trim())
  if (!selected.length) {
    showError('请至少选择一个有效角色')
    return
  }
  saving.value = true
  try {
    const existingNames = new Set(activeChars.value.map((c) => c.name))
    const toSave = selected.filter((c) => !existingNames.has((c.name || '').trim()))
    const skipped = selected.length - toSave.length

    let success = 0
    let failed = 0

    const saveOne = async (char) => {
      const form = reactive(makeEmptyForm())
      const rels = ref([])
      applyAiChar(form, rels, char)
      await characterApi.create(projectId.value, buildPayload(form, rels.value))
    }

    // 并发 3 个一组，失败重试一次
    for (let i = 0; i < toSave.length; i += 3) {
      const chunk = toSave.slice(i, i + 3)
      const results = await Promise.allSettled(chunk.map((c) => saveOne(c)))
      for (let j = 0; j < results.length; j++) {
        if (results[j].status === 'fulfilled') {
          success++
        } else {
          const retry = await Promise.allSettled([saveOne(chunk[j])])
          if (retry[0].status === 'fulfilled') success++
          else failed++
        }
      }
    }

    const parts = [`成功保存 ${success} 个角色`]
    if (skipped) parts.push(`${skipped} 个同名已跳过`)
    if (failed) parts.push(`${failed} 个保存失败`)
    showSuccess(parts.join('，'))
    createVisible.value = false
    loadCharacters()
  } catch (err) {
    console.error('批量保存失败:', err)
    showError('批量保存失败，请重试')
  } finally {
    saving.value = false
  }
}

async function polishManual() {
  if (!manualForm.name.trim()) {
    showError('请先输入角色名称')
    return
  }
  polishing.value = true
  try {
    const res = await characterApi.polish(projectId.value, buildPayload(manualForm, manualRels.value))
    const result = extractJsonFromString(res?.data || '')
    if (result && typeof result === 'object' && !Array.isArray(result)) {
      applyAiChar(manualForm, manualRels, result)
      showSuccess('AI 润色完成，请检查后保存')
    } else {
      showError('润色结果解析失败，请重试')
    }
  } catch (err) {
    console.error('AI 润色失败:', err)
    showError(err.message || '润色失败，请重试')
  } finally {
    polishing.value = false
  }
}

// ---- 编辑 ----
async function openEdit(id) {
  editVisible.value = true
  editLoading.value = true
  editTab.value = 'basic'
  Object.assign(editForm, makeEmptyForm())
  editRels.value = []
  editExperiences.value = []
  editId.value = id
  try {
    const res = await characterApi.get(projectId.value, id)
    const c = res.character
    if (!c) {
      showError('加载角色失败')
      editVisible.value = false
      return
    }
    Object.assign(editForm, {
      name: c.name || '',
      gender: GENDER_VALUES.includes(c.gender) ? c.gender : '未知',
      role_type: normalizeRoleType(c.role_type || '配角'),
      age: parseAge(c.age),
      identity: c.identity || '',
      faction: c.faction || '',
      tagline: c.tagline || '',
      personality: c.personality || '',
      strengths: c.strengths || '',
      flaws: c.flaws || '',
      obsession: c.obsession || '',
      motivation: c.motivation || '',
      taboos: c.taboos || '',
      appearance: c.appearance || '',
      abilities: c.abilities || '',
      weaknesses: c.weaknesses || '',
      backstory: c.backstory || '',
      development: c.development || '',
    })
    editRels.value = parseRelationships(c.relationships)
    editExperiences.value = Array.isArray(c.experiences) ? c.experiences : []
  } catch (err) {
    console.error('加载角色详情失败:', err)
    showError('加载角色失败')
    editVisible.value = false
  } finally {
    editLoading.value = false
  }
}

async function saveEdit() {
  if (!editForm.name.trim()) {
    showError('请输入角色名称')
    return
  }
  saving.value = true
  try {
    const payload = buildPayload(editForm, editRels.value)
    payload.experiences = editExperiences.value.filter(
      (e) => (e.chapter || '').trim() || (e.event || '').trim(),
    )
    await characterApi.update(projectId.value, editId.value, payload)
    showSuccess('角色更新成功')
    editVisible.value = false
    loadCharacters()
  } catch (err) {
    console.error('保存角色失败:', err)
  } finally {
    saving.value = false
  }
}

async function polishEdit() {
  if (!editForm.name.trim()) {
    showError('请先输入角色名称')
    return
  }
  polishing.value = true
  try {
    const res = await characterApi.polish(projectId.value, buildPayload(editForm, editRels.value))
    const result = extractJsonFromString(res?.data || '')
    if (result && typeof result === 'object' && !Array.isArray(result)) {
      applyAiChar(editForm, editRels, result)
      showSuccess('AI 润色完成，请检查后保存')
    } else {
      showError('润色结果解析失败，请重试')
    }
  } catch (err) {
    console.error('AI 润色失败:', err)
    showError(err.message || '润色失败，请重试')
  } finally {
    polishing.value = false
  }
}

function removeCharacter() {
  showConfirmModal({
    title: '确认删除',
    message: '确定要删除这个角色吗？删除后可在角色列表中恢复。',
    danger: true,
    confirmText: '确认删除',
    onConfirm: async (close) => {
      try {
        await characterApi.remove(projectId.value, editId.value)
        showSuccess('角色已删除')
        close()
        editVisible.value = false
        loadCharacters()
      } catch (err) {
        console.error('删除角色失败:', err)
        showError('删除失败，请重试')
      }
    },
  })
}

async function restoreCharacter(c) {
  try {
    await characterApi.restore(projectId.value, c.id)
    showSuccess('角色已恢复')
    loadCharacters()
  } catch (err) {
    console.error('恢复角色失败:', err)
    showError(err.message || '恢复失败')
  }
}

// ---- Header 右侧：操作按钮 ----

onMounted(() => {
  setPageHeader('角色管理', 'AI 生成、润色、检测与优化角色设定')
  loadCharacters()
  loadRelTypes()
  
  // 将筛选栏移动到页面头部中间
  nextTick(() => {
    const filter = document.querySelector('.character-view .char-filter')
    const center = document.querySelector('#page-header-center')
    if (filter && center) {
      center.appendChild(filter)
    }
  })
})

onBeforeUnmount(() => {
  // 将筛选栏移回原位
  const filter = document.querySelector('#page-header-center .char-filter')
  const charView = document.querySelector('.character-view')
  if (filter && charView) {
    charView.insertBefore(filter, charView.firstChild)
  }
})
</script>

<style lang="scss" scoped>
.character-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
  height: 100%;
}

// 筛选栏
.char-filter {
  display: flex;
  gap: 12px;
  padding: 6px 12px;
  border-radius: var(--radius-md);
  align-items: center;
}

.filter-search {
  width: 200px;
}

.filter-select {
  width: 140px;
}

// 角色网格
.char-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 14px;
}

.char-card {
  padding: 16px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  display: flex;
  flex-direction: column;
  gap: 10px;

  &:hover {
    transform: translateY(-2px);
    border-color: var(--primary);
    box-shadow: 0 8px 24px rgba(99, 102, 241, 0.15);
  }
}

.char-card-top {
  display: flex;
  gap: 12px;
  align-items: center;
}

.char-avatar {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, var(--primary), #818cf8);
}

.char-info {
  min-width: 0;
  flex: 1;
}

.char-name {
  margin: 0 0 6px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.char-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.char-tagline {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.char-card-deleted {
  opacity: 0.6;
  cursor: default;

  &:hover {
    transform: none;
    border-color: var(--glass-border);
    box-shadow: none;
  }

  .char-avatar {
    background: linear-gradient(135deg, #6b7280, #9ca3af);
  }
}

.restore-btn {
  align-self: flex-start;
}

// 已删除分区
.deleted-section {
  margin-top: 8px;
}

.deleted-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-muted);
  margin-bottom: 12px;

  .deleted-count {
    background: rgba(156, 163, 175, 0.15);
    padding: 1px 8px;
    border-radius: 10px;
    font-size: 12px;
  }
}

// 编辑弹窗容器
.edit-modal-container {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

// 固定 Tab 栏
.char-tabs-fixed {
  flex-shrink: 0;
  margin-bottom: 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  padding: 0;
  
  :deep(.el-tabs__header) {
    margin-bottom: 0;
  }
  
  :deep(.el-tabs__nav-wrap) {
    padding: 0;
    overflow: visible !important;
    
    &::after {
      display: none;
    }
  }
  
  :deep(.el-tabs__nav-scroll) {
    overflow: visible !important;
  }
  
  :deep(.el-tabs__item) {
    padding: 14px 20px !important;
    font-size: 13px;
    font-weight: 500;
    transition: all 0.25s ease;
    border-radius: 0;
    margin: 0 1px;
    
    &:hover {
      color: var(--primary);
      background: rgba(129, 140, 248, 0.08);
    }
    
    &.is-active {
      color: var(--primary);
      font-weight: 600;
      background: rgba(129, 140, 248, 0.15);
    }
  }
  
  :deep(.el-tabs__active-bar) {
    height: 3px;
    border-radius: 2px 2px 0 0;
    background: linear-gradient(90deg, var(--primary), #a78bfa);
    box-shadow: 0 0 8px rgba(129, 140, 248, 0.4);
  }
}

// 可滚动内容区
.tab-content-scroll {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 16px 12px;
  scrollbar-width: thin;
  scrollbar-color: rgba(255, 255, 255, 0.15) transparent;
  background: rgba(255, 255, 255, 0.01);
  border-radius: 0 0 8px 8px;
  display: flex;
  flex-direction: column;
  
  &::-webkit-scrollbar {
    width: 6px;
  }
  
  &::-webkit-scrollbar-track {
    background: transparent;
    margin: 4px 0;
  }
  
  &::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.2);
    border-radius: 3px;
    
    &:hover {
      background: rgba(255, 255, 255, 0.35);
    }
  }
}

.tab-pane-content {
  animation: fadeIn 0.25s ease;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

// 底部按钮栏
.modal-footer-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 0px 4px;
  
  &.create-footer {
    justify-content: flex-end;
  }
}

.footer-right {
  display: flex;
  align-items: center;
  gap: 10px;
}

.footer-btn {
  height: 36px;
  padding: 0 20px;
  font-size: 13px;
  font-weight: 500;
  border-radius: 8px;
  transition: all 0.25s ease;
  
  &:hover {
    transform: translateY(-1px);
  }
  
  &:active {
    transform: scale(0.97) translateY(0);
  }
}

// .ai-btn {
//   background: rgba(129, 140, 248, 0.1);
//   border-color: rgba(129, 140, 248, 0.3);
//   color: var(--primary);
//   
//   &:hover {
//     background: rgba(129, 140, 248, 0.2);
//     border-color: rgba(129, 140, 248, 0.5);
//     box-shadow: 0 4px 12px rgba(129, 140, 248, 0.2);
//   }
// }

// .save-btn {
//   background: linear-gradient(135deg, var(--primary), #a78bfa);
//   border: none;
//   box-shadow: 0 4px 12px rgba(129, 140, 248, 0.3);
//   
//   &:hover {
//     box-shadow: 0 6px 20px rgba(129, 140, 248, 0.45);
//     transform: translateY(-2px);
//   }
// }

.editor-section {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.editor-section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 16px;

  .title-bar {
    width: 4px;
    height: 16px;
    border-radius: 2px;
    background: linear-gradient(180deg, var(--primary), #a78bfa);
    box-shadow: 0 0 8px rgba(129, 140, 248, 0.3);
  }
}

.ai-desc-block {
  padding: 8px 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;

  :deep(.el-textarea) {
    flex: 1;
    display: flex;
    flex-direction: column;
  }

  :deep(.el-textarea__inner) {
    flex: 1;
    resize: none;
  }
}

.ai-desc-hint {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0 0 10px;
  line-height: 1.6;
}

// 批量生成
.batch-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.batch-card {
  display: flex;
  gap: 12px;
  padding: 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--glass-border);
  background: rgba(255, 255, 255, 0.03);
  transition: opacity var(--transition-fast);

  &.is-unchecked {
    opacity: 0.5;
  }
}

.batch-checkbox {
  margin-top: 4px;
}

.batch-content {
  flex: 1;
  min-width: 0;
}

.batch-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.batch-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.batch-meta {
  font-size: 12px;
  color: var(--text-muted);
}

.batch-desc {
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.7;
  margin-top: 4px;

  strong {
    color: var(--primary);
    margin-right: 6px;
    font-weight: 600;
  }
}

@media (max-width: 768px) {
  .page-header-center {
    display: none;
  }
  // .btn-text {
  //   display: none;
  // }
}
</style>
