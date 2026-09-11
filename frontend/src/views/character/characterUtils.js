/**
 * 角色模块共享工具函数
 * 供 CharacterView、CharacterTrajectoryPanel 等组件复用
 */

/** 来源标签映射 */
export const SOURCE_LABELS = {
  manual: '手动',
  ai_generate: 'AI生成',
  outline_extract: '大纲提取',
  volume_extract: '卷提取',
  chapter_discover: '章节发现',
}

/** 来源标签颜色映射 */
const SOURCE_TAG_TYPES = {
  manual: 'info',
  ai_generate: '',
  outline_extract: 'primary',
  volume_extract: 'success',
  chapter_discover: 'warning',
}

/** 来源标签颜色映射（用于轨迹面板） */
const SOURCE_COLORS = {
  chapter: '#f59e0b',
  manual: '#6b7280',
  outline_extract: '#6366f1',
  volume_extract: '#06b6d4',
}

/**
 * 获取来源中文标签
 * @param {string} source
 * @returns {string}
 */
export function sourceLabel(source) {
  return SOURCE_LABELS[source] || source || ''
}

/**
 * 获取来源 el-tag type
 * @param {string} source
 * @returns {string}
 */
export function sourceTagType(source) {
  return SOURCE_TAG_TYPES[source] || 'info'
}

/**
 * 获取来源对应的颜色（用于轨迹面板时间线）
 * @param {string} source
 * @returns {string}
 */
export function sourceColor(source) {
  return SOURCE_COLORS[source] || '#818cf8'
}

/** 角色定位归一化映射（兼容 LLM 返回的多种写法） */
const ROLE_MAP = {
  主角: '主角', 主人公: '主角', 男主: '主角', 女主: '主角', 男主角: '主角', 女主角: '主角',
  protagonist: '主角', main: '主角', hero: '主角', heroine: '主角',
  反派: '反派', 恶人: '反派', 对手: '反派', villain: '反派', antagonist: '反派', enemy: '反派',
  配角: '配角', supporting: '配角', side: '配角',
  路人: '路人', 龙套: '路人', npc: '路人', extra: '路人',
}

/**
 * 归一化角色定位（映射到标准四分类）
 * @param {string} val
 * @returns {string}
 */
export function normalizeRoleType(val) {
  if (!val) return '配角'
  const key = String(val).trim()
  return ROLE_MAP[key] || ROLE_MAP[key.toLowerCase()] || '配角'
}

/**
 * 归一化势力输入：非汉字英文数字 → 逗号分隔
 * @param {string} input
 * @returns {string}
 */
export function normalizeFaction(input) {
  if (!input) return ''
  return input
    .replace(/[^a-zA-Z0-9一-鿿]/g, ',')
    .replace(/(,\s*)+/g, ',')
    .replace(/^,|,$/g, '')
    .trim()
}

/**
 * 解析年龄值
 * @param {*} v
 * @returns {number|null}
 */
export function parseAge(v) {
  if (v === null || v === undefined || v === '') return null
  if (typeof v === 'number') return Number.isFinite(v) ? Math.trunc(v) : null
  const nums = String(v).match(/\d+/)
  return nums ? parseInt(nums[0], 10) : null
}

/** 性别选项 */
export const GENDER_VALUES = ['男', '女', '未知']
