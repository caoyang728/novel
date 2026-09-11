/**
 * 角色表单与 CRUD 逻辑 composable
 * 封装角色的创建/编辑/AI生成/润色/检测/批量操作等业务逻辑
 */
import { ref, reactive, computed } from 'vue'
import { characterApi } from '@/api/character'
import { showSuccess, showError } from '@/utils/notify'
import { showConfirmModal } from '@/utils/modal'
import { extractJsonFromString } from '@/utils/json'
import {
  GENDER_VALUES,
  normalizeRoleType,
  normalizeFaction,
  parseAge,
} from './characterUtils'

// ---- 关系类型默认值 ----
const DEFAULT_REL_TYPES = ['朋友', '恋人', '配偶', '父母', '子女', '兄弟姐妹', '师父', '徒弟', '敌人', '对手', '导师', '门生', '盟友', '亲属', '君主', '臣子', '其他']
const DEFAULT_EN_TO_CN = {
  friend: '朋友', lover: '恋人', spouse: '配偶', parent: '父母', child: '子女',
  sibling: '兄弟姐妹', master: '师父', apprentice: '徒弟', disciple: '徒弟',
  enemy: '敌人', rival: '对手', mentor: '导师', protege: '门生', partner: '盟友',
  ally: '盟友', family: '亲属', other: '其他',
}

// ---- 表单工厂 ----
export function makeEmptyForm() {
  return {
    name: '', gender: '未知', role_type: '配角', age: null,
    identity: '', faction: '', tagline: '',
    content: '',
  }
}

// 将 LLM/存储中的 relationships 解析为标准对象数组
function parseRelationships(rels, normalizeRelType) {
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

// 将 AI 生成的角色数据应用到表单
function applyAiChar(form, relsRef, char, parseRels) {
  Object.assign(form, {
    name: char.name || '',
    gender: GENDER_VALUES.includes(char.gender) ? char.gender : '未知',
    role_type: normalizeRoleType(char.role_type || char.role || '配角'),
    age: parseAge(char.age),
    identity: char.identity || '',
    faction: char.faction || '',
    tagline: char.tagline ?? char.tags ?? '',
    content: char.content || '',
  })
  relsRef.value = parseRels(char.relationships)
}

function toCreatePayload(form, rels = []) {
  const payload = {
    name: (form.name || '').trim(),
    gender: form.gender || '未知',
    role_type: form.role_type || '配角',
    age: form.age ?? '',
    identity: form.identity || '',
    faction: normalizeFaction(form.faction || ''),
    tagline: form.tagline || '',
    content: form.content || '',
    relationships: cleanRels(rels),
  }
  // AI 生成的角色带来源标记
  if (form._source) payload.source = form._source
  return payload
}

function toUpdatePayload(form, rels = []) {
  return {
    name: (form.name || '').trim(),
    gender: form.gender || '未知',
    role_type: form.role_type || '配角',
    age: form.age ?? '',
    identity: form.identity || '',
    faction: normalizeFaction(form.faction || ''),
    tagline: form.tagline || '',
    content: form.content || '',
    relationships: cleanRels(rels),
  }
}

/**
 * 角色表单与 CRUD composable
 * @param {import('vue').Ref} projectId
 */
export function useCharacterForm(projectId) {
  // ---- 关系类型配置 ----
  const relTypes = ref([...DEFAULT_REL_TYPES])
  const enToCn = ref({ ...DEFAULT_EN_TO_CN })

  function normalizeRelType(t) {
    if (!t) return '其他'
    if (relTypes.value.includes(t)) return t
    const cn = enToCn.value[String(t).toLowerCase()]
    return cn || '其他'
  }

  // ---- 列表状态 ----
  const loading = ref(false)
  const characters = ref([])

  const activeChars = computed(() => characters.value.filter((c) => !c.is_deleted))

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

  // ---- 创建弹窗状态 ----
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

  // ---- 编辑弹窗状态 ----
  const editVisible = ref(false)
  const editLoading = ref(false)
  const editTab = ref('basic')
  const editId = ref(null)
  const editForm = reactive(makeEmptyForm())
  const editRels = ref([])

  const checkVisible = ref(false)

  const batchSelectedCount = computed(() => batchList.value.filter((c) => c.selected).length)
  const batchProgress = ref({ done: 0, total: 0, active: false })

  const createRelCharacters = computed(() =>
    activeChars.value.map((c) => ({ id: c.id, name: c.name })),
  )

  const editRelCharacters = computed(() =>
    activeChars.value.filter((c) => c.id !== editId.value).map((c) => ({ id: c.id, name: c.name })),
  )

  // ---- 创建操作 ----
  function openCreate() {
    Object.assign(manualForm, makeEmptyForm())
    Object.assign(aiForm, makeEmptyForm())
    manualRels.value = []
    aiRels.value = []
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
      applyAiChar(aiForm, aiRels, result, (rels) => parseRelationships(rels, normalizeRelType))
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
      await characterApi.create(projectId.value, toCreatePayload(manualForm, manualRels.value))
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
      await characterApi.create(projectId.value, toCreatePayload(aiForm, aiRels.value))
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
    batchProgress.value = { done: 0, total: selected.length, active: true }
    try {
      const existingNames = new Set(activeChars.value.map((c) => c.name))
      const toSave = selected.filter((c) => !existingNames.has((c.name || '').trim()))
      const skipped = selected.length - toSave.length

      let success = 0
      let failed = 0

      const saveOne = async (char) => {
        const form = reactive(makeEmptyForm())
        const rels = ref([])
        applyAiChar(form, rels, char, (r) => parseRelationships(r, normalizeRelType))
        await characterApi.create(projectId.value, toCreatePayload(form, rels.value))
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
        batchProgress.value = { done: Math.min(i + 3, toSave.length), total: toSave.length, active: true }
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
      batchProgress.value = { done: 0, total: 0, active: false }
    }
  }

  async function polishManual() {
    if (!manualForm.name.trim()) {
      showError('请先输入角色名称')
      return
    }
    polishing.value = true
    try {
      const res = await characterApi.polish(projectId.value, toCreatePayload(manualForm, manualRels.value))
      const result = extractJsonFromString(res?.data || '')
      if (result && typeof result === 'object' && !Array.isArray(result)) {
        applyAiChar(manualForm, manualRels, result, (rels) => parseRelationships(rels, normalizeRelType))
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

  // ---- 编辑操作 ----
  async function openEdit(id) {
    editVisible.value = true
    editLoading.value = true
    editTab.value = 'basic'
    Object.assign(editForm, makeEmptyForm())
    editRels.value = []
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
        content: c.content || '',
      })
      editRels.value = parseRelationships(c.relationships, normalizeRelType)
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
      const payload = toUpdatePayload(editForm)
      payload.relationships = editRels.value
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
      const res = await characterApi.polish(projectId.value, toCreatePayload(editForm, editRels.value))
      const result = extractJsonFromString(res?.data || '')
      if (result && typeof result === 'object' && !Array.isArray(result)) {
        applyAiChar(editForm, editRels, result, (rels) => parseRelationships(rels, normalizeRelType))
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

  return {
    // 关系类型
    relTypes,
    enToCn,
    // 列表
    loading,
    characters,
    activeChars,
    loadCharacters,
    loadRelTypes,
    // 创建弹窗
    createVisible,
    createTab,
    saving,
    generating,
    polishing,
    manualForm,
    manualRels,
    aiForm,
    aiRels,
    aiGenerated,
    aiRequirement,
    batchRequirement,
    batchList,
    batchSelectedCount,
    batchProgress,
    createRelCharacters,
    openCreate,
    generateSingle,
    generateBatch,
    saveManual,
    saveAi,
    saveBatch,
    polishManual,
    // 编辑弹窗
    editVisible,
    editLoading,
    editTab,
    editId,
    editForm,
    editRels,
    editRelCharacters,
    checkVisible,
    openEdit,
    saveEdit,
    polishEdit,
    removeCharacter,
    restoreCharacter,
  }
}
