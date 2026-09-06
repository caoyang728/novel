/**
 * 命令式弹窗 API — showModal / showConfirmModal
 *
 * 命令式弹窗（如 showConfirmModal）若脱离 Vue 应用树直接 createVNode+render
 * 到 body，el-dialog 在初始即为 visible=true 的情况下不会触发打开过渡
 * （overlay 停留在 display:none），且缺少 appContext。
 *
 * 因此这里只维护一个响应式「弹窗描述符栈」 modalStack，真正的声明式渲染由
 * 挂载在 App 根组件内的 <ModalHost /> 完成——与页面中其它 AppModal 完全
 * 同一套机制，弹窗推入栈时 visible=false，下一帧翻转为 true，可靠地经历
 * false→true 的打开过程。
 */
import { reactive, nextTick, h } from 'vue'
import DOMPurify from 'dompurify'

// 由 ModalHost.vue 渲染的命令式弹窗描述符栈
export const modalStack = reactive([])
let modalSeq = 0

const CLOSE_DELAY = 320 // 等待关闭过渡结束后再移除节点

function pushModal(descriptor) {
  const id = ++modalSeq
  const item = { id, visible: false, ...descriptor }
  modalStack.push(item)
  // 挂载后下一帧打开：声明式 el-dialog 需要 false→true 才触发进入过渡
  // 必须通过 modalStack 访问获取 reactive 代理对象再赋值，直接对原始 item
  // 赋值不会被 Vue 响应式系统追踪，导致 visible 变更不触发重新渲染
  nextTick(() => {
    const target = modalStack.find((m) => m.id === id)
    if (target) target.visible = true
  })
  return item
}

function closeModal(item) {
  if (!item || item._dismissing) return
  // 通过 modalStack 获取 reactive 代理对象，确保属性变更被 Vue 追踪
  const target = modalStack.find((m) => m.id === item.id)
  if (!target || target._dismissing) return
  target._dismissing = true
  target.visible = false
  setTimeout(() => {
    const i = modalStack.findIndex((m) => m.id === item.id)
    if (i !== -1) modalStack.splice(i, 1)
  }, CLOSE_DELAY)
}

function bodyToVnode(body) {
  if (body == null) return h('span')
  if (typeof body === 'string') {
    return h('span', { innerHTML: DOMPurify.sanitize(body) })
  }
  // 已是 VNode 或可渲染对象，直接返回
  return body
}

/**
 * 显示通用弹窗
 * @param {object} options title/body(string|VNode)/footer(VNode)/width/height/minHeight/onCancel
 * @returns {{ close: Function }}
 */
export function showModal(options = {}) {
  const {
    title = '',
    body = '',
    footer = null,
    width = '520px',
    height = 'auto',
    minHeight,
    showClose = true,
    closeOnClickModal = false,
    closeOnPressEscape = true,
    onCancel,
  } = options

  const item = pushModal({
    kind: 'modal',
    props: {
      title,
      width,
      height,
      minHeight,
      showClose,
      closeOnClickModal,
      closeOnPressEscape,
    },
    bodyVnode: bodyToVnode(body),
    footerVnode: footer || null,
    onCancel,
  })

  return {
    close: () => closeModal(item),
  }
}

/**
 * 显示确认弹窗
 * @param {object} options title/message/confirmText/cancelText/danger/onConfirm(close)/onCancel
 */
export function showConfirmModal(options = {}) {
  const {
    title = '确认',
    message = '',
    confirmText = '确认',
    cancelText = '取消',
    danger = false,
    onConfirm,
    onCancel,
  } = options

  const item = pushModal({
    kind: 'confirm',
    props: { title, message, confirmText, cancelText, danger },
    onConfirm,
    onCancel,
  })

  const close = () => closeModal(item)

  return { close }
}
