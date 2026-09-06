<template>
  <div class="markdown-body" v-html="parsedHtml" />
</template>

<script setup>
import { computed } from 'vue'
import { safeMarkdownParse } from '@/utils/markdown'

const props = defineProps({
  content: { type: String, default: '' },
  highlightNew: { type: Boolean, default: false },
  baseline: { type: String, default: '' },
})

function escapeHtml(text) {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function highlightNewContent(html, baseline) {
  if (!baseline || !html) return html
  
  // 将 baseline 转换为纯文本行用于对比
  const baselineLines = baseline.split('\n').filter(line => line.trim())
  
  // 在HTML中找到文本内容并标记新增的段落
  // 简单方案：对每个主要块级元素检查是否包含新增内容
  const parser = new DOMParser()
  const doc = parser.parseFromString(html, 'text/html')
  const body = doc.body
  
  // 递归处理节点
  function processNode(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      const text = node.textContent.trim()
      if (text && !baselineLines.some(line => line.includes(text) || text.includes(line))) {
        // 这段文本在 baseline 中不存在，标记为新增
        const span = doc.createElement('span')
        span.className = 'diff-added'
        // 移除"【本轮更新】"标记
        let content = node.textContent.replace(/【本轮更新】[：:]?\s*/g, '')
        span.textContent = content
        node.parentNode.replaceChild(span, node)
      }
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      // 跳过代码块和特定元素
      if (['PRE', 'CODE'].includes(node.tagName)) return
      Array.from(node.childNodes).forEach(child => processNode(child))
    }
  }
  
  processNode(body)
  return body.innerHTML
}

const parsedHtml = computed(() => {
  const html = safeMarkdownParse(props.content)
  if (props.highlightNew && props.baseline) {
    return highlightNewContent(html, props.baseline)
  }
  return html
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

  // 新增内容高亮
  .diff-added {
    background: rgba(16, 185, 129, 0.15);
    color: #6ee7b7;
    border-radius: 3px;
    padding: 1px 4px;
  }
}
</style>
