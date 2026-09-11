<template>
  <div ref="chartRef" class="timeline-graph-canvas" />
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  /** 时间线事件列表 [{ id, title, start_year, end_year, event_type, characters, location, ... }] */
  timeline: { type: Array, default: () => [] },
  /** 角色轨迹列表（仅人物视图使用）[{ chapter_number, source, location, ... }] */
  trajectories: { type: Array, default: () => [] },
  /** 视图类型: global | character | location */
  view: { type: String, default: 'global' },
  /** 元数据 { earliest_year, latest_year, era_unit, total_events } */
  meta: { type: Object, default: () => ({}) },
})

const chartRef = ref(null)
let chart = null

// 事件类型配色
const EVENT_TYPE_COLORS = {
  battle: '#ef4444',
  politics: '#6366f1',
  culture: '#f59e0b',
  economy: '#22c55e',
  personal: '#ec4899',
  disaster: '#f97316',
  other: '#6b7280',
}
const DEFAULT_COLOR = '#818cf8'

const EVENT_TYPE_LABELS = {
  battle: '战斗',
  politics: '政治',
  culture: '文化',
  economy: '经济',
  personal: '个人',
  disaster: '灾难',
  other: '其他',
}

function getEventColor(event) {
  return EVENT_TYPE_COLORS[event.event_type] || DEFAULT_COLOR
}

function buildOption() {
  const events = props.timeline || []
  if (events.length === 0) return null

  // 按时间排序并计算时间轴范围
  const sorted = [...events].sort((a, b) => {
    const ya = a.start_year ?? Infinity
    const yb = b.start_year ?? Infinity
    if (ya !== yb) return ya - yb
    return (a.start_month ?? 0) - (b.start_month ?? 0)
  })

  const years = sorted.map((e) => e.start_year).filter((y) => y != null)
  const earliest = props.meta.earliest_year ?? Math.min(...years)
  const latest = props.meta.latest_year ?? Math.max(...years)
  const eraUnit = props.meta.era_unit || ''

  // Y 轴：事件标题
  const yLabels = sorted.map((e) => {
    const timeStr = formatTimeShort(e)
    return `${e.title} (${timeStr})`
  })

  // 为每个事件创建一个 bar 数据
  const barData = sorted.map((e, idx) => {
    const start = e.start_year ?? earliest
    const end = e.end_year ?? start + 1
    return {
      value: [idx, start, end, e.title, e.event_type, e.description, e.location],
      itemStyle: {
        color: getEventColor(e),
        borderRadius: [4, 4, 4, 4],
      },
    }
  })

  // 人物视图：叠加轨迹点
  const trajectoryData = []
  if (props.view === 'character' && props.trajectories.length > 0) {
    props.trajectories.forEach((t, idx) => {
      const year = t.story_year ?? null
      if (year == null) return
      // 找到最近的事件作为 Y 坐标参考
      let yIdx = 0
      for (let i = 0; i < sorted.length; i++) {
        if (sorted[i].start_year != null && sorted[i].start_year <= year) {
          yIdx = i
        }
      }
      trajectoryData.push({
        value: [yIdx, year, year + 0.5, t.summary || t.source || '轨迹', 'trajectory'],
        itemStyle: {
          color: '#22d3ee',
          borderColor: '#fff',
          borderWidth: 1,
        },
        symbol: 'diamond',
        symbolSize: 12,
      })
    })
  }

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: '#4b5563',
      borderWidth: 1,
      textStyle: { color: '#f9fafb', fontSize: 12 },
      formatter: (params) => {
        if (!params.data) return ''
        const d = params.data.value
        const title = d[3] || ''
        const type = d[4] || ''
        const desc = d[5] || ''
        const loc = d[6] || ''
        const typeLabel = EVENT_TYPE_LABELS[type] || type
        let html = `<div style="max-width:320px">`
        html += `<div style="font-weight:600;margin-bottom:4px">${title}</div>`
        if (typeLabel) html += `<div style="color:#9ca3af;font-size:11px">类型: ${typeLabel}</div>`
        if (d[1] !== undefined) {
          html += `<div style="color:#9ca3af;font-size:11px">时间: ${eraUnit}${d[1]}年${d[2] && d[2] !== d[1] ? ' ~ ' + eraUnit + d[2] + '年' : ''}</div>`
        }
        if (loc) html += `<div style="color:#9ca3af;font-size:11px">地点: ${loc}</div>`
        if (desc) html += `<div style="margin-top:6px;color:#d1d5db;font-size:12px;line-height:1.5">${desc.length > 200 ? desc.slice(0, 200) + '...' : desc}</div>`
        html += `</div>`
        return html
      },
    },
    grid: {
      left: 200,
      right: 40,
      top: 20,
      bottom: 40,
    },
    xAxis: {
      type: 'value',
      min: earliest - 1,
      max: latest + 1,
      axisLabel: {
        color: '#9ca3af',
        fontSize: 11,
        formatter: (val) => `${eraUnit}${val}`,
      },
      axisLine: { lineStyle: { color: '#4b5563' } },
      splitLine: { lineStyle: { color: 'rgba(75, 85, 99, 0.3)' } },
    },
    yAxis: {
      type: 'category',
      data: yLabels,
      inverse: true,
      axisLabel: {
        color: '#d1d5db',
        fontSize: 11,
        width: 180,
        overflow: 'truncate',
      },
      axisLine: { lineStyle: { color: '#4b5563' } },
      axisTick: { show: false },
    },
    series: [
      {
        type: 'custom',
        renderItem: (params, api) => {
          const idx = api.value(0)
          const startVal = api.value(1)
          const endVal = api.value(2)
          const start = api.coord([startVal, idx])
          const end = api.coord([endVal, idx])
          const height = api.size([0, 1])[1] * 0.6
          const width = Math.max(end[0] - start[0], 8)
          const rectShape = echarts.graphic.clipRectByRect(
            { x: start[0], y: start[1] - height / 2, width, height },
            { x: params.coordSys.x, y: params.coordSys.y, width: params.coordSys.width, height: params.coordSys.height }
          )
          return rectShape && {
            type: 'rect',
            shape: rectShape,
            style: api.style(),
          }
        },
        encode: { x: [1, 2], y: 0 },
        data: barData,
        z: 2,
      },
      // 事件类型图例
      ...Object.entries(EVENT_TYPE_COLORS).map(([type, color]) => ({
        type: 'scatter',
        name: EVENT_TYPE_LABELS[type] || type,
        data: [],
        itemStyle: { color },
      })),
      // 轨迹点（人物视图）
      ...(trajectoryData.length > 0 ? [{
        type: 'scatter',
        name: '角色轨迹',
        data: trajectoryData,
        symbol: 'diamond',
        symbolSize: 12,
        z: 3,
        tooltip: {
          formatter: (params) => {
            const d = params.data.value
            return `<div style="max-width:280px"><div style="font-weight:600;color:#22d3ee">角色轨迹</div><div style="color:#d1d5db;margin-top:4px">${d[3] || ''}</div></div>`
          },
        },
      }] : []),
    ],
    // 自定义 legend
    legend: {
      show: true,
      bottom: 4,
      textStyle: { color: '#9ca3af', fontSize: 11 },
      itemWidth: 12,
      itemHeight: 8,
      itemGap: 16,
      data: [
        ...Object.entries(EVENT_TYPE_LABELS).map(([type, label]) => ({
          name: label,
          itemStyle: { color: EVENT_TYPE_COLORS[type] },
        })),
        ...(trajectoryData.length > 0 ? [{ name: '角色轨迹' }] : []),
      ],
    },
    dataZoom: [
      {
        type: 'slider',
        xAxisIndex: 0,
        bottom: 24,
        height: 16,
        backgroundColor: 'rgba(30, 41, 59, 0.5)',
        borderColor: '#4b5563',
        fillerColor: 'rgba(99, 102, 241, 0.2)',
        handleStyle: { color: '#6366f1' },
        textStyle: { color: '#9ca3af', fontSize: 10 },
        dataBackground: {
          lineStyle: { color: '#4b5563' },
          areaStyle: { color: 'rgba(99, 102, 241, 0.1)' },
        },
      },
      {
        type: 'inside',
        xAxisIndex: 0,
      },
    ],
  }
  return option
}

function formatTimeShort(event) {
  const era = event.era_unit || ''
  const y = event.start_year
  if (y === null || y === undefined) return ''
  return `${era}${y}年`
}

function initChart() {
  if (!chartRef.value) return
  chart = echarts.init(chartRef.value, null, { renderer: 'canvas' })
  const option = buildOption()
  if (option) chart.setOption(option)
}

function updateChart() {
  if (!chart) return
  const option = buildOption()
  if (option) {
    chart.setOption(option, true)
  } else {
    chart.clear()
  }
}

function handleResize() {
  chart?.resize()
}

onMounted(() => {
  nextTick(() => initChart())
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
  chart = null
})

watch(
  () => [props.timeline, props.trajectories, props.view],
  () => nextTick(() => updateChart()),
  { deep: true }
)
</script>

<style lang="scss" scoped>
.timeline-graph-canvas {
  width: 100%;
  height: 100%;
  min-height: 400px;
}
</style>
