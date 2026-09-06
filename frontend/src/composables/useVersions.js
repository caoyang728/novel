/**
 * 版本管理 composable — 版本列表/加载/定稿/删除
 */
import { ref } from 'vue'
import { showConfirmModal } from '@/utils/modal'
import { showSuccess, showError } from '@/utils/notify'

export function useVersions(options = {}) {
  const {
    fetchVersions,
    fetchVersionDetail,
    deleteVersionApi,
    finalizeVersionApi,
    onDeleteSuccess,
    onFinalizeSuccess,
  } = options

  // ---- State ----
  const versions = ref([])
  const currentVersion = ref(null)
  const loading = ref(false)
  const detailLoading = ref(false)

  // ---- Methods ----

  /**
   * 加载版本列表
   */
  async function loadVersions() {
    if (!fetchVersions) return
    loading.value = true
    try {
      const data = await fetchVersions()
      // 后端可能返回 { versions: [...] } 或直接是数组
      const list = Array.isArray(data) ? data : data.versions || data.results || []
      versions.value = list
    } catch (err) {
      showError('加载版本列表失败')
    } finally {
      loading.value = false
    }
  }

  /**
   * 加载版本详情
   */
  async function loadVersionDetail(versionId) {
    if (!fetchVersionDetail) return
    detailLoading.value = true
    try {
      const data = await fetchVersionDetail(versionId)
      // 后端可能返回 { version: {...} } 或直接是对象
      currentVersion.value = data.version || data
      return currentVersion.value
    } catch (err) {
      showError('加载版本详情失败')
    } finally {
      detailLoading.value = false
    }
  }

  /**
   * 选择版本
   */
  function selectVersion(version) {
    currentVersion.value = version
  }

  /**
   * 删除版本（带确认弹窗）
   */
  function confirmDeleteVersion(version) {
    showConfirmModal({
      title: '删除版本',
      message: `确定要删除版本 "${version.version_number || version.name}" 吗？此操作不可撤销。`,
      danger: true,
      confirmText: '删除',
      onConfirm: async (close) => {
        try {
          await deleteVersionApi(version.id)
          showSuccess('版本已删除')
          close()
          await loadVersions()
          onDeleteSuccess?.(version)
        } catch (err) {
          showError('删除失败')
        }
      },
    })
  }

  /**
   * 定稿版本（带确认弹窗）
   */
  function confirmFinalizeVersion(version) {
    showConfirmModal({
      title: '定稿版本',
      message: `确定要定稿版本 "${version.version_number || version.name}" 吗？定稿后将不可修改。`,
      confirmText: '定稿',
      onConfirm: async (close) => {
        try {
          await finalizeVersionApi(version.id)
          showSuccess('版本已定稿')
          close()
          await loadVersions()
          onFinalizeSuccess?.(version)
        } catch (err) {
          showError('定稿失败')
        }
      },
    })
  }

  return {
    // State
    versions,
    currentVersion,
    loading,
    detailLoading,
    // Methods
    loadVersions,
    loadVersionDetail,
    selectVersion,
    confirmDeleteVersion,
    confirmFinalizeVersion,
  }
}
