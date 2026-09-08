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
 * 标记型 diff：逐行用 marked 解析，通过标记文本识别 diff 类型。
 * 流程：标记行 → marked 逐行解析 → DOMPurify → 识别标记 → 包裹 diff class → 清除标记
 */
function renderMarkdownDiff(content, baseline, showRemoved) {
  const MA = '%%DA%%'   // added marker
  const MR = '%%DR%%'   // removed marker
  // 匹配标记文本（可能被 DOMPurify 保留或去掉 * 包裹）
  const markerRe = /\*?%%D[AR]%%\*?\s*/

  const diffResult = computeLcsDiff(baseline, content)

  // 用 marked 逐行解析（带标记前缀）
  const rendered = diffResult.map(item => {
    const line = item.text || ''
    if (item.type === 'added') {
      return { type: 'added', html: marked.parse(`*${MA}* ${line}`) }
    }
    if (item.type === 'removed' && showRemoved) {
      return { type: 'removed', html: marked.parse(`*${MR}* ${line}`) }
    }
    return { type: 'equal', html: marked.parse(line) }
  })

  // DOMPurify 消毒
  const fullHtml = rendered.map(r => r.html).join('')
  const cleanHtml = DOMPurify.sanitize(fullHtml)

  // 解析 DOM，识别标记行，直接清除标记文本（不再二次解析，避免多余 <p> 嵌套）
  const doc = new DOMParser().parseFromString(`<div id="dr">${cleanHtml}</div>`, 'text/html')
  const root = doc.getElementById('dr')
  const output = []

  for (const node of Array.from(root.childNodes)) {
    if (node.nodeType !== Node.ELEMENT_NODE) {
      output.push(node.textContent || '')
      continue
    }

    const text = node.textContent || ''
    const isAdded = text.includes(MA)
    const isRemoved = text.includes(MR)

    if (isAdded || isRemoved) {
      const cls = isAdded ? 'diff-added' : 'diff-removed'
      // 直接从 outerHTML 中清除标记，避免二次解析
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
