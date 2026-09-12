<template>
  <div class="markdown-body" :class="{ 'diff-show-background': showDiffBackground }" v-html="parsedHtml" />
</template>

<script setup>
import { computed } from 'vue'
import { safeMarkdownParse } from '@/utils/markdown'
import { computeMarkdownDiffGroups, computeWordDiff, escapeHtml } from '@/utils/diff'
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
 * 词级 diff 渲染：把 computeWordDiff 的结果转成带 <span> 标记的 HTML
 * 每个片段先单独做行内 Markdown 渲染，再用 <span> 包裹。
 * computeWordDiff 已保证 `**粗体**` 等结构是原子 token，不会出现标记被拆半的情况。
 * @param {string} mode 'old' = 只标红删除词，'new' = 只标绿新增词
 */
function renderWordDiffHtml(oldLine, newLine, mode) {
  const { oldPrefix, newPrefix, parts } = computeWordDiff(oldLine, newLine)
  // 块级前缀（如 "### "、"- "）原样展示，旧视图用旧前缀，避免编号被误标为变更
  let html = escapeHtml(mode === 'old' ? oldPrefix : newPrefix)
  for (const part of parts) {
    const text = marked.parseInline(escapeHtml(part.text))
    if (part.type === 'added') {
      if (mode === 'new') html += `<span class="dw-a">${text}</span>`
    } else if (part.type === 'removed') {
      if (mode === 'old') html += `<span class="dw-r">${text}</span>`
    } else {
      html += text
    }
  }
  return html
}

/**
 * 渲染替换组中的单个 item（旧版本视图）
 * replaced → 词级高亮；removed → 整体标红；added → 旧版本中不存在，留空
 */
function renderOldItem(it) {
  if (it.oldText) return renderWordDiffHtml(it.oldText, it.text, 'old')
  if (it.type === 'removed') return `<span class="dw-r">${marked.parseInline(escapeHtml(it.text))}</span>`
  return ''
}

/**
 * 渲染替换组中的单个 item（新版本视图）
 * replaced → 词级高亮；added → 整体标绿；removed → 新版本中不存在，留空
 */
function renderNewItem(it) {
  if (it.oldText) return renderWordDiffHtml(it.oldText, it.text, 'new')
  if (it.type === 'added') return `<span class="dw-a">${marked.parseInline(escapeHtml(it.text))}</span>`
  return ''
}

/**
 * 主函数：Markdown 感知的 diff 渲染
 * diff 计算由 utils/diff.js 负责，本组件只负责把分组结果渲染成 HTML
 */
function renderMarkdownDiff(content, baseline, showRemoved) {
  if (!baseline || !content) return safeMarkdownParse(content)

  const groups = computeMarkdownDiffGroups(baseline, content)

  const htmlParts = []
  for (const g of groups) {
    if (g.type === 'replaced') {
      // 旧版本和新版本合并在同一个 diff-block 中，上下排列
      const parts = []
      if (showRemoved) {
        parts.push(`<p class="dw-old">${g.items.map(renderOldItem).join('<br>')}</p>`)
      }
      parts.push(`<p class="dw-new">${g.items.map(renderNewItem).join('<br>')}</p>`)
      htmlParts.push(`<div class="diff-block diff-replaced">${parts.join('')}</div>`)
    } else {
      const text = g.lines.join('\n')
      if (!text.trim()) continue
      if (g.type === 'added') {
        htmlParts.push(`<div class="diff-block diff-added">${marked.parse(text)}</div>`)
      } else if (g.type === 'removed' && showRemoved) {
        htmlParts.push(`<div class="diff-block diff-removed">${marked.parse(text)}</div>`)
      } else if (g.type === 'equal') {
        htmlParts.push(marked.parse(text))
      }
    }
  }

  return DOMPurify.sanitize(htmlParts.join(''), { ADD_TAGS: ['span'], ADD_ATTR: ['class'] })
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

  // ── Diff 样式 ──────────────────────────────────────────────

  .diff-block {
    padding: 2px 8px;
    border-radius: 3px;
    margin: 2px 0;
    word-break: break-word;

    > h1, > h2, > h3, > h4, > h5, > h6 {
      margin: 0.3em 0;
    }
    > p {
      margin: 0;
    }
  }

  .diff-added {
    color: #34d399;
    border-left: 3px solid #34d399;
  }

  .diff-removed {
    color: #f87171;
    text-decoration: line-through;
    opacity: 0.75;
    border-left: 3px solid #f87171;
  }

  .diff-replaced {
    border-left: 3px solid #fbbf24;
    padding: 4px 8px;

    p.dw-old {
      margin: 0 0 4px 0;
      opacity: 0.75;
      border-bottom: 1px dashed rgba(251, 191, 36, 0.3);
      padding-bottom: 4px;
    }

    p.dw-new {
      margin: 0;
    }

    // 行内新增词（jsdiff diffWords 标记）
    .dw-a {
      color: #34d399;
      background: rgba(52, 211, 153, 0.12);
      border-radius: 2px;
      padding: 0 1px;
    }

    // 行内删除词（jsdiff diffWords 标记）
    .dw-r {
      color: #f87171;
      text-decoration: line-through;
      opacity: 0.75;
      background: rgba(248, 113, 113, 0.08);
      border-radius: 2px;
      padding: 0 1px;
    }
  }

  // 背景模式
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
