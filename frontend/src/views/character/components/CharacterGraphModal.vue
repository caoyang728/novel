<template>
  <div class="character-graph" v-loading="loading" element-loading-text="加载关系图谱...">
    <EmptyState
      v-if="!loading && !nodes.length"
      icon="Share"
      text="暂无关系数据"
    />
    <GraphCanvas
      v-else
      ref="canvasRef"
      :nodes="nodes"
      :edges="edges"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import GraphCanvas from '@/components/graph/GraphCanvas.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { graphApi } from '@/api/graph'

const props = defineProps({
  projectId: { type: String, required: true },
  characterId: { type: [String, Number], required: true },
  characterName: { type: String, default: '' },
})

const loading = ref(false)
const nodes = ref([])
const edges = ref([])
const canvasRef = ref(null)

async function loadGraph() {
  if (!props.projectId || !props.characterName) return
  
  loading.value = true
  try {
    const res = await graphApi.getSubgraph(props.projectId, {
      name: props.characterName,
      hops: 1,
    })
    nodes.value = res.data?.nodes || []
    edges.value = res.data?.edges || []
  } catch (err) {
    console.error('加载关系图谱失败:', err)
  } finally {
    loading.value = false
  }
}

watch(() => props.characterName, () => {
  loadGraph()
})

onMounted(() => {
  loadGraph()
})
</script>

<style scoped>
.character-graph {
  flex: 1;
  min-height: 400px;
  display: flex;
  flex-direction: column;
}

:deep(.graph-canvas) {
  flex: 1;
  min-height: 0;
}
</style>