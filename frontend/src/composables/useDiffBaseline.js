/**
 * Diff 基线管理 — content / baseline 双状态
 *
 * 用途：Markdown 预览时对比"当前内容"与"上次保存的快照"，高亮未保存的变更。
 * 配合 MarkdownRenderer 的 highlight-new / baseline / show-removed 三个 props 使用。
 *
 * 核心设计：
 *   - content  = 当前文档内容（AI 流式返回或用户手动编辑都会更新）
 *   - baseline = 上次保存/加载时的快照
 *   - 二者不等时 hasUnsavedChanges() 为 true → MarkdownRenderer 以 diff 方式展示变更
 *
 * baseline 同步时机（仅以下三处）：
 *   1. 加载版本 / 初始化 → loadSnapshot(saved)   // content 与 baseline 同时设为已保存内容
 *   2. 保存当前版本      → commit()             // baseline 追上 content，diff 消失
 *   3. 另存新版本        → commit()             // 同上
 *
 * baseline 不同步的时机（diff 持续显示）：
 *   - AI 流式返回：content 更新，baseline 不变
 *   - 用户手动编辑：content 更新，baseline 不变
 *
 * 用法：
 *   const { content, baseline, hasUnsavedChanges, reset, loadSnapshot, commit, revert } = useDiffBaseline()
 */
import { ref } from 'vue'

export function useDiffBaseline() {
  const content = ref('')
  const baseline = ref('')

  /** 是否存在未保存的变更 */
  function hasUnsavedChanges() {
    return content.value !== baseline.value
  }

  /** 清空状态（无版本 / 删除当前版本时） */
  function reset() {
    content.value = ''
    baseline.value = ''
  }

  /** 加载版本或初始化：content 与 baseline 同时设为已保存内容，diff 消失 */
  function loadSnapshot(value) {
    const v = value || ''
    content.value = v
    baseline.value = v
  }

  /** 保存 / 另存后：baseline 追上 content，diff 消失 */
  function commit() {
    baseline.value = content.value
  }

  /** 回滚：content 恢复为 baseline（如流式生成失败时） */
  function revert() {
    content.value = baseline.value
  }

  return { content, baseline, hasUnsavedChanges, reset, loadSnapshot, commit, revert }
}
