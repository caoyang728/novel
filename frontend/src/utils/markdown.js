/**
 * Markdown 解析 — marked + DOMPurify
 */
import { marked } from 'marked'
import DOMPurify from 'dompurify'

// 配置 marked
marked.setOptions({
  breaks: true,
  gfm: true,
})

/**
 * 安全解析 Markdown 为 HTML
 * @param {string} markdown - Markdown 文本
 * @returns {string} 消毒后的 HTML
 */
export function safeMarkdownParse(markdown) {
  if (!markdown) return ''
  try {
    const rawHtml = marked.parse(markdown)
    return DOMPurify.sanitize(rawHtml, {
      ADD_TAGS: ['iframe'],
      ADD_ATTR: ['target', 'allow', 'allowfullscreen', 'frameborder', 'scrolling'],
    })
  } catch (err) {
    console.error('Markdown parse error:', err)
    return DOMPurify.sanitize(markdown)
  }
}

/**
 * 增量解析（流式场景：逐块追加后整体重新解析）
 * @param {string} text - 累积文本
 * @returns {string} 消毒后的 HTML
 */
export function incrementalMarkdownParse(text) {
  return safeMarkdownParse(text)
}
