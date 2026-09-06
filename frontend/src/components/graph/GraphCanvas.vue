<template>
  <div ref="containerRef" class="graph-canvas" />
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import cytoscape from 'cytoscape'

const props = defineProps({
  // 原始节点：{ id, name, node_type, description, properties }
  nodes: { type: Array, default: () => [] },
  // 原始边：{ id, source_id, target_id, edge_type, description, is_bidirectional }
  edges: { type: Array, default: () => [] },
})

const emit = defineEmits(['nodeClick', 'blankClick'])

const containerRef = ref(null)
let cy = null

// 关系类型 -> 边颜色
const EDGE_COLORS = {
  '朋友': '#22c55e', '恋人': '#ec4899', '配偶': '#f43f5e',
  '父母': '#f59e0b', '子女': '#f59e0b', '兄弟姐妹': '#eab308',
  '师父': '#a855f7', '徒弟': '#c084fc', '敌人': '#ef4444',
  '对手': '#f97316', '导师': '#8b5cf6', '门生': '#a78bfa',
  '盟友': '#06b6d4', '亲属': '#fbbf24', '君主': '#7c3aed',
  '臣子': '#8b5cf6', '其他': '#6b7280', '所属': '#475569',
}
const EDGE_HIGHLIGHT = '#22d3ee'

function buildElements() {
  const degMap = {}
  props.edges.forEach((e) => {
    degMap[e.source_id] = (degMap[e.source_id] || 0) + 1
    degMap[e.target_id] = (degMap[e.target_id] || 0) + 1
  })

  const nodes = props.nodes.map((n) => ({
    group: 'nodes',
    data: {
      id: 'n' + n.id,
      label: n.name,
      ntype: n.node_type,
      desc: n.description,
      props: n.properties,
      deg: degMap[n.id] || 0,
      dbId: n.id,
    },
  }))

  const edges = props.edges.map((e) => ({
    group: 'edges',
    data: {
      id: 'e' + e.id,
      source: 'n' + e.source_id,
      target: 'n' + e.target_id,
      etype: e.edge_type,
      desc: e.description,
      bidir: e.is_bidirectional,
    },
  }))

  return [...nodes, ...edges]
}

function getStyle() {
  const s = [
    {
      selector: 'node[ntype="character"]',
      style: {
        'background-color': '#6366f1', 'border-color': '#818cf8', 'border-width': 2,
        'label': 'data(label)', 'color': '#e0e7ff', 'font-size': '11px',
        'text-valign': 'bottom', 'text-margin-y': 8, 'text-halign': 'center',
        'text-outline-color': '#0f172a', 'text-outline-width': 2.5,
        'text-wrap': 'ellipsis', 'text-max-width': '80px',
        'width': (el) => Math.max(36, Math.min(58, 30 + el.data('deg') * 5)),
        'height': (el) => Math.max(36, Math.min(58, 30 + el.data('deg') * 5)),
      },
    },
    {
      selector: 'node[ntype="faction"]',
      style: {
        'background-color': '#ef4444', 'border-color': '#f87171', 'border-width': 2.5,
        'shape': 'hexagon', 'label': 'data(label)', 'color': '#fecaca',
        'font-size': '12px', 'font-weight': 'bold',
        'text-valign': 'bottom', 'text-margin-y': 10, 'text-halign': 'center',
        'text-outline-color': '#0f172a', 'text-outline-width': 2.5,
        'width': 48, 'height': 48,
      },
    },
    {
      selector: 'edge',
      style: {
        'width': 1.5, 'line-color': '#475569', 'target-arrow-color': '#475569',
        'target-arrow-shape': 'triangle', 'arrow-scale': 0.6,
        'curve-style': 'bezier', 'label': '', 'opacity': 0.6,
        'font-size': '9px', 'color': '#94a3b8', 'text-rotation': 'autorotate',
        'text-margin-y': -10, 'text-outline-color': '#0f172a', 'text-outline-width': 2,
      },
    },
  ]
  Object.keys(EDGE_COLORS).forEach((t) => {
    s.push({
      selector: `edge[etype="${t}"]`,
      style: { 'line-color': EDGE_COLORS[t], 'target-arrow-color': EDGE_COLORS[t] },
    })
  })
  s.push({ selector: 'edge[?bidir]', style: { 'source-arrow-shape': 'triangle', 'source-arrow-color': '#475569' } })
  s.push({ selector: 'edge[etype="所属"]', style: { 'line-style': 'dashed', 'line-dash-pattern': [5, 3], 'opacity': 0.35, 'width': 1 } })
  s.push({ selector: 'node.highlighted', style: { 'border-width': 4, 'border-color': EDGE_HIGHLIGHT, 'z-index': 10 } })
  s.push({
    selector: 'edge.highlighted',
    style: {
      'line-color': EDGE_HIGHLIGHT, 'target-arrow-color': EDGE_HIGHLIGHT,
      'source-arrow-color': EDGE_HIGHLIGHT, 'width': 2.5, 'opacity': 1, 'z-index': 10,
      'label': 'data(etype)', 'font-size': '10px',
    },
  })
  s.push({ selector: '.faded', style: { opacity: 0.1 } })
  s.push({ selector: 'node.search-match', style: { 'border-width': 4, 'border-color': '#fbbf24', 'z-index': 20 } })
  return s
}

function initGraph() {
  if (!containerRef.value) return
  destroyGraph()

  cy = cytoscape({
    container: containerRef.value,
    elements: buildElements(),
    style: getStyle(),
    layout: {
      name: 'cose', animate: false,
      nodeRepulsion: () => 6000,
      idealEdgeLength: (e) => (e.data('etype') === '所属' ? 80 : 140),
      edgeElasticity: () => 100,
      gravity: 0.25, numIter: 300, padding: 50,
      nodeDimensionsIncludeLabels: true,
      initialTemp: 300, coolingFactor: 0.95,
    },
    minZoom: 0.05, maxZoom: 5,
    boxSelectionEnabled: false,
    wheelSensitivity: 0.2,
  })

  cy.on('tap', 'node', (evt) => {
    const node = evt.target
    highlightNode(node)
    emit('nodeClick', { node: node.data(), neighbors: getNeighbors(node) })
  })
  cy.on('tap', (evt) => {
    if (evt.target === cy) {
      clearHighlight()
      emit('blankClick')
    }
  })

  // 平滑滚轮缩放
  containerRef.value.addEventListener('wheel', onWheel, { passive: false })
}

function onWheel(e) {
  if (!cy) return
  e.preventDefault()
  const factor = e.deltaY > 0 ? 0.9 : 1.1
  const pt = { x: e.offsetX, y: e.offsetY }
  const newZoom = Math.max(cy.minZoom(), Math.min(cy.maxZoom(), cy.zoom() * factor))
  cy.zoom({ level: newZoom, renderedPosition: pt })
}

function getNeighbors(node) {
  return node.connectedEdges().map((edge) => {
    const isSrc = edge.data('source') === node.id()
    const otherId = isSrc ? edge.data('target') : edge.data('source')
    const other = cy.getElementById(otherId)
    return {
      direction: isSrc ? 'out' : 'in',
      edgeType: edge.data('etype'),
      node: other.data(),
      cyId: otherId,
    }
  })
}

function highlightNode(node) {
  cy.elements().removeClass('highlighted faded')
  const nb = node.closedNeighborhood()
  cy.elements().addClass('faded')
  nb.removeClass('faded').addClass('highlighted')
}

function highlightByCyId(cyId) {
  const node = cy.getElementById(cyId)
  if (node && node.length) {
    highlightNode(node)
    cy.animate({ center: { eles: node }, duration: 300 })
    return { node: node.data(), neighbors: getNeighbors(node) }
  }
  return null
}

function clearHighlight() {
  if (cy) cy.elements().removeClass('highlighted faded search-match')
}

function focusNeighborhood(cyId) {
  const node = cy.getElementById(cyId)
  if (node && node.length) {
    highlightNode(node)
    cy.animate({ fit: { eles: node.closedNeighborhood(), padding: 80 }, duration: 400 })
  }
}

function searchMatch(query) {
  if (!cy) return 0
  cy.elements().removeClass('search-match highlighted faded')
  if (!query) return 0
  const matches = cy.nodes().filter((n) => (n.data('label') || '').indexOf(query) >= 0)
  if (matches.length) {
    cy.elements().addClass('faded')
    matches.removeClass('faded').addClass('search-match')
    cy.animate({ fit: { eles: matches, padding: 80 }, duration: 400 })
  }
  return matches.length
}

function applyFilters(nodeTypes, edgeTypes) {
  if (!cy) return
  cy.nodes().forEach((n) => {
    n.style('display', nodeTypes.includes(n.data('ntype')) ? 'element' : 'none')
  })
  cy.edges().forEach((e) => {
    const src = cy.getElementById(e.data('source'))
    const tgt = cy.getElementById(e.data('target'))
    const visible =
      src.style('display') !== 'none' &&
      tgt.style('display') !== 'none' &&
      edgeTypes.includes(e.data('etype'))
    e.style('display', visible ? 'element' : 'none')
  })
}

function resize() {
  if (cy) cy.resize()
}

function destroyGraph() {
  if (containerRef.value) {
    containerRef.value.removeEventListener('wheel', onWheel)
  }
  if (cy) {
    cy.destroy()
    cy = null
  }
}

watch(
  () => [props.nodes, props.edges],
  () => initGraph(),
  { deep: true },
)

function onResize() {
  if (cy) cy.resize()
}

onMounted(() => {
  initGraph()
  window.addEventListener('resize', onResize)
})
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  destroyGraph()
})

defineExpose({
  highlightByCyId,
  focusNeighborhood,
  clearHighlight,
  searchMatch,
  applyFilters,
  resize,
})
</script>

<style lang="scss" scoped>
.graph-canvas {
  width: 100%;
  height: 100%;
  flex: 1;
  min-height: 0;
  border-radius: var(--radius-lg);
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid var(--glass-border);
  position: relative;
  overflow: hidden;

  // 确保 canvas 不会被拉伸
  :deep(canvas) {
    display: block;
  }
}
</style>
