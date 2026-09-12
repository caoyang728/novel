/**
 * 文本对比工具 — 基于 jsdiff（npm 包名 `diff`）
 *
 * 所有需要文本对比的场景统一使用本模块，不要在组件内重复实现。
 *
 * 两层 diff 策略：
 *   1. 行级 diff（diffArrays）   — 识别哪些行新增/删除/未变，保证块级结构完整
 *   2. 词级 diff（diffArrays）   — 在行内做细粒度高亮
 *
 * 词级 diff 的关键设计：先把行拆成 token 再对比，其中
 *   - `**粗体**`、`*斜体*`、`` `代码` ``、`~~删除~~` 整体作为一个原子 token，
 *     避免 Markdown 标记被拆到不同片段里导致渲染出字面星号
 *   - 中文按单字切分，英文按单词切分，兼顾粒度
 *
 * 典型用法（Markdown 预览高亮）：
 *   const groups = computeMarkdownDiffGroups(baseline, content)
 *   // 遍历 groups，按 type 渲染：equal / added / removed / replaced
 */
import { diffArrays, diffWords } from 'diff'

/** 相似度阈值：低于此值的 removed+added 视为真正的新增+删除，而非替换 */
export const SIMILARITY_THRESHOLD = 0.3

/** 块级 Markdown 前缀：标题 #、列表 - * 1.、引用 > */
const BLOCK_PREFIX_RE = /^(\s*(?:#{1,6}\s+|[-*]\s+|\d+\.\s+|>\s+))/

/** 内联 Markdown 结构（作为原子 token，不参与拆分） */
const INLINE_MD_RE = /\*\*[^*\n]+\*\*|\*[^*\n]+\*|`[^`\n]+`|~~[^~\n]+~~/

/** HTML 转义 */
export function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

/** 提取行首的块级 Markdown 前缀（标题/列表/引用），无前缀返回 '' */
export function getLinePrefix(line) {
  const m = String(line).match(BLOCK_PREFIX_RE)
  return m ? m[1] : ''
}

/** 去掉行首的块级 Markdown 前缀 */
export function stripLinePrefix(line) {
  return String(line).replace(BLOCK_PREFIX_RE, '')
}

/**
 * 把纯文本切成 token：中文按单字、英文/数字按单词、空白与符号各自成 token
 * @returns {string[]}
 */
function tokenizePlain(text) {
  return text.match(/[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]|[A-Za-z0-9_']+|\s+|[^\s]/g) || []
}

/**
 * 把一行拆成 token 数组，内联 Markdown 结构保持完整不被拆散
 * @returns {string[]}
 */
export function tokenizeInline(line) {
  const tokens = []
  let rest = String(line)
  while (rest) {
    const idx = rest.search(INLINE_MD_RE)
    if (idx === -1) {
      tokens.push(...tokenizePlain(rest))
      break
    }
    if (idx > 0) tokens.push(...tokenizePlain(rest.slice(0, idx)))
    const matched = rest.slice(idx).match(INLINE_MD_RE)[0]
    tokens.push(matched)
    rest = rest.slice(idx + matched.length)
  }
  return tokens
}

/**
 * 词级 diff：对比两行文本
 * 块级前缀（如 "### "、"- "）单独返回，避免前后缀差异干扰对比结果
 *
 * @param {string} oldLine 旧行
 * @param {string} newLine 新行
 * @returns {{ oldPrefix: string, newPrefix: string, parts: Array<{type: 'equal'|'added'|'removed', text: string}> }}
 */
export function computeWordDiff(oldLine, newLine) {
  if (oldLine === newLine) {
    return { oldPrefix: '', newPrefix: '', parts: [{ type: 'equal', text: oldLine }] }
  }

  const oldPrefix = getLinePrefix(oldLine)
  const newPrefix = getLinePrefix(newLine)
  const oldContent = stripLinePrefix(oldLine)
  const newContent = stripLinePrefix(newLine)

  const parts = diffArrays(tokenizeInline(oldContent), tokenizeInline(newContent)).map((part) => ({
    type: part.added ? 'added' : part.removed ? 'removed' : 'equal',
    text: part.value.join(''),
  }))

  return { oldPrefix, newPrefix, parts }
}

/**
 * 行级相似度（0~1），用于判断 removed+added 是否应视为"替换"
 * 会剥离块级前缀后比较，避免前缀干扰相似度
 */
export function lineSimilarity(a, b) {
  if (a === b) return 1
  if (!a || !b) return 0
  const ca = stripLinePrefix(a)
  const cb = stripLinePrefix(b)
  if (!ca || !cb) return 0
  let commonLen = 0
  for (const part of diffWords(ca, cb)) {
    if (!part.added && !part.removed) commonLen += part.value.length
  }
  return (2 * commonLen) / (ca.length + cb.length)
}

/**
 * 行级 diff：返回扁平的变更项
 *
 * @param {string} oldText 旧文本
 * @param {string} newText 新文本
 * @returns {Array<{type: 'equal'|'added'|'removed'|'replaced', text: string, oldText?: string}>}
 */
export function computeLineDiff(oldText, newText) {
  const parts = diffArrays(String(oldText || '').split('\n'), String(newText || '').split('\n'))
  const raw = []
  for (const part of parts) {
    const type = part.added ? 'added' : part.removed ? 'removed' : 'equal'
    for (const line of part.value) raw.push({ type, text: line })
  }
  return mergeReplacements(raw)
}

/** 将相邻的 removed+added 行对合并为 replaced 项 */
function mergeReplacements(raw) {
  const result = []
  let i = 0
  while (i < raw.length) {
    if (
      i + 1 < raw.length &&
      raw[i].type === 'removed' &&
      raw[i + 1].type === 'added' &&
      lineSimilarity(raw[i].text, raw[i + 1].text) >= SIMILARITY_THRESHOLD
    ) {
      result.push({ type: 'replaced', text: raw[i + 1].text, oldText: raw[i].text })
      i += 2
    } else {
      result.push(raw[i])
      i++
    }
  }
  return result
}

/**
 * Markdown 感知的 diff：按块分组，供渲染层直接消费
 *
 * 分组规则：
 *   1. 连续同类型（equal / added / removed）的行合并为一个 group，保证列表、段落等块级结构完整
 *   2. 相邻的 removed-group + added-group 按行配对，相似行合并为 replaced，其余保留 removed / added
 *
 * @param {string} oldText 基线内容
 * @param {string} newText 当前内容
 * @returns {Array<
 *   { type: 'equal'|'added'|'removed', lines: string[] } |
 *   { type: 'replaced', items: Array<{type: 'replaced'|'removed'|'added', text: string, oldText?: string}> }
 * >}
 */
export function computeMarkdownDiffGroups(oldText, newText) {
  const diffResult = computeLineDiff(oldText, newText)

  // 第一轮分组：连续同类型行合并（replaced 单独成组）
  const groups = []
  let i = 0
  while (i < diffResult.length) {
    const item = diffResult[i]
    if (item.type === 'replaced') {
      groups.push({ type: 'replaced', items: [item] })
      i++
    } else {
      const lines = [item.text || '']
      i++
      while (
        i < diffResult.length &&
        diffResult[i].type === item.type &&
        diffResult[i].type !== 'replaced'
      ) {
        lines.push(diffResult[i].text || '')
        i++
      }
      groups.push({ type: item.type, lines })
    }
  }

  // 第二轮合并：相邻 removed-group + added-group 按行配对为 replaced
  const merged = []
  let gi = 0
  while (gi < groups.length) {
    const g = groups[gi]
    if (g.type === 'removed' && gi + 1 < groups.length && groups[gi + 1].type === 'added') {
      const oldLines = g.lines
      const newLines = groups[gi + 1].lines
      const items = []
      const maxLen = Math.max(oldLines.length, newLines.length)
      for (let k = 0; k < maxLen; k++) {
        const ol = k < oldLines.length ? oldLines[k] : ''
        const nl = k < newLines.length ? newLines[k] : ''
        if (ol && nl && lineSimilarity(ol, nl) >= SIMILARITY_THRESHOLD) {
          items.push({ type: 'replaced', text: nl, oldText: ol })
        } else {
          if (ol) items.push({ type: 'removed', text: ol })
          if (nl) items.push({ type: 'added', text: nl })
        }
      }
      merged.push({ type: 'replaced', items })
      gi += 2
    } else {
      merged.push(g)
      gi++
    }
  }

  return merged
}
