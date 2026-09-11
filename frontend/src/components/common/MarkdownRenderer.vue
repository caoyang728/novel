<template>
  <div class="markdown-body" :class="{ 'diff-show-background': showDiffBackground }" v-html="parsedHtml" />
</template>

<script setup>
import { computed } from 'vue'
import { safeMarkdownParse } from '@/utils/markdown'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps({
  content: { type: String, default: '' },
  highlightNew: { type: Boolean, default: false },
  baseline: { type: String, default: '' },
  showRemoved: { type: Boolean, default: false },
  showDiffBackground: { type: Boolean, default: false },
})

/**
 * LCS 行级 diff：对比 baseline 和 content，返回 diff 结果数组
 * 每项: { type: 'equal' | 'added' | 'removed', text: string }
 */
function computeLcsDiff(oldText, newText) {
  const oldLines = oldText.split('\n')
  const newLines = newText.split('\n')
  const m = oldLines.length
  const n = newLines.length

  // LCS 动态规划
  const dp = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0))
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] = oldLines[i - 1] === newLines[j - 1]
        ? dp[i - 1][j - 1] + 1
        : Math.max(dp[i - 1][j], dp[i][j - 1])
    }
  }

  // 回溯
  const result = []
  let i = m, j = n
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldLines[i - 1] === newLines[j - 1]) {
      result.unshift({ type: 'equal', text: newLines[j - 1] })
      i--; j--
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.unshift({ type: 'added', text: newLines[j - 1] })
      j--
    } else {
      result.unshift({ type: 'removed', text: oldLines[i - 1] })
      i--
    }
  }
  return result
}

/**
 * 标记型 diff：将连续相同 diff 类型的行分组后逐组用 marked 解析，
 * 保留标题、列表等块级 Markdown 结构。
 * 流程：行级 LCS diff → 按类型分组 → 每组整体解析 → DOMPurify → 识别标记 → 包裹 diff class → 清除标记
 */
function renderMarkdownDiff(content, baseline, showRemoved) {
  const MA = '%%DA%%'   // added marker
  const MR = '%%DR%%'   // removed marker
  const markerRe = /\*?%%D[AR]%%\*?\s*/

  const diffResult = computeLcsDiff(baseline, content)

  // 将连续相同 diff 类型的行合并为组，避免逐行解析破坏块级 Markdown 结构
  const groups = []
  let currentGroup = null
  for (const item of diffResult) {
    const line = item.text || ''
    if (currentGroup && currentGroup.type === item.type) {
      currentGroup.lines.push(line)
    } else {
      currentGroup = { type: item.type, lines: [line] }
      groups.push(currentGroup)
    }
  }

  // 每组作为一个完整 Markdown 块解析
  const rendered = groups.map(group => {
    const fullText = group.lines.join('\n')
    if (group.type === 'added') {
      return { type: 'added', html: marked.parse(`*${MA}* ${fullText}`) }
    }
    if (group.type === 'removed' && showRemoved) {
      return { type: 'removed', html: marked.parse(`*${MR}* ${fullText}`) }
    }
    return { type: 'equal', html: marked.parse(fullText) }
  })

  // DOMPurify 消毒并插入分隔符：<span class="ds"> 标记每个 added/removed 组的起始，
  // DOMPurify 会保留 <span> 元素，遍历时用它追踪 diff 组边界
  const SEP = 'ds'  // diff-separator class
  const allParts = []
  for (const r of rendered) {
    const clean = DOMPurify.sanitize(r.html)
    if (r.type === 'added') {
      allParts.push(`<span class="${SEP}" data-diff="a"></span>${clean}`)
    } else if (r.type === 'removed') {
      allParts.push(`<span class="${SEP}" data-diff="r"></span>${clean}`)
    } else {
      allParts.push(clean)
    }
  }
  const finalHtml = allParts.join('')

  // 解析 DOM，识别分隔符 span，清除标记文本，包裹 diff class
  const doc = new DOMParser().parseFromString(`<div id="dr">${finalHtml}</div>`, 'text/html')
  const root = doc.getElementById('dr')
  const output = []
  let currentDiffType = null

  for (const node of Array.from(root.childNodes)) {
    // 分隔符 span：更新当前组类型并跳过
    if (node.nodeType === Node.ELEMENT_NODE && node.classList.contains(SEP)) {
      const d = node.getAttribute('data-diff')
      currentDiffType = d === 'a' ? 'added' : d === 'r' ? 'removed' : null
      continue
    }

    if (node.nodeType !== Node.ELEMENT_NODE) {
      output.push(node.textContent || '')
      continue
    }

    if (currentDiffType) {
      const cls = currentDiffType === 'added' ? 'diff-added' : 'diff-removed'
      const cleaned = node.outerHTML.replace(markerRe, '')
      output.push(`<div class="diff-block ${cls}">${cleaned}</div>`)
    } else {
      output.push(node.outerHTML)
    }
  }

  return output.join('')
}

const parsedHtml = computed(() => {
  if (props.highlightNew && props.baseline) {
    return renderMarkdownDiff(props.content, props.baseline, props.showRemoved)
  }
  return safeMarkdownParse(props.content)
})
</script>

<style lang="scss">
.markdown-body {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-regular);

  h1, h2, h3, h4, h5, h6 {
    color: var(--text-primary);
    margin: 1em 0 0.5em;
    font-weight: 600;
  }

  h1 { font-size: 1.6em; }
  h2 { font-size: 1.4em; }
  h3 { font-size: 1.2em; }

  p {
    margin: 0.5em 0;
  }

  ul, ol {
    padding-left: 1.5em;
    margin: 0.5em 0;
  }

  li {
    margin: 0.25em 0;
  }

  blockquote {
    border-left: 3px solid var(--primary);
    padding-left: 1em;
    margin: 0.8em 0;
    color: var(--text-secondary);
    background: rgba(129, 140, 248, 0.05);
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    padding: 8px 12px;
  }

  code {
    background: rgba(255, 255, 255, 0.08);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 0.9em;
    color: var(--primary);
  }

  pre {
    background: rgba(0, 0, 0, 0.3);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-sm);
    padding: 12px 16px;
    overflow-x: auto;
    margin: 0.8em 0;

    code {
      background: none;
      padding: 0;
      color: var(--text-regular);
    }
  }

  table {
    width: 100%;
    border-collapse: collapse;
    margin: 0.8em 0;

    th, td {
      border: 1px solid var(--glass-border);
      padding: 8px 12px;
      text-align: left;
    }

    th {
      background: rgba(255, 255, 255, 0.04);
      color: var(--text-secondary);
      font-weight: 600;
    }
  }

  hr {
    border: none;
    border-top: 1px solid var(--glass-border);
    margin: 1em 0;
  }

  a {
    color: var(--primary);
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
  }

  img {
    max-width: 100%;
    border-radius: var(--radius-sm);
  }

  // diff 分隔符（仅用于 DOM 追踪，不显示）
  .ds {
    display: none;
  }

  // Diff 区块样式（文字颜色模式）
  .diff-block {
    padding: 2px 8px;
    border-radius: 3px;
    margin: 2px 0;
    word-break: break-word;

    // 保留内部块级元素的原有样式
    > h1, > h2, > h3, > h4, > h5, > h6 {
      margin: 0.3em 0;
    }
    > p {
      margin: 0;
    }
  }

  // 新增内容：绿色文字 + 左边框
  .diff-added {
    color: #34d399;
    border-left: 3px solid #34d399;
  }

  // 删除内容：红色文字 + 删除线 + 左边框
  .diff-removed {
    color: #f87171;
    text-decoration: line-through;
    opacity: 0.75;
    border-left: 3px solid #f87171;
  }

  // 开启背景模式时，覆盖为带背景色的样式
  &.diff-show-background {
    .diff-added {
      background: rgba(16, 185, 129, 0.12);
      color: #6ee7b7;
    }
    .diff-removed {
      background: rgba(239, 68, 68, 0.1);
      color: #f87171;
    }
  }

}
</style>
