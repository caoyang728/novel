<template>
  <div class="character-graph" v-loading="loading" element-loading-text="加载关系图谱...">
    <EmptyState
      v-if="!loading && loadError"
      icon="Warning"
      :text="loadError"
    >
      <AppButton variant="default" size="small" @click="loadGraph" style="margin-top: 12px">重试</AppButton>
    </EmptyState>
    <EmptyState
      v-else-if="!loading && !loadError && !nodes.length"
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
import AppButton from '@/components/common/AppButton.vue'
import { graphApi } from '@/api/graph'
import { showError } from '@/utils/notify'

const props = defineProps({
  projectId: { type: [String, Number], required: true },
  characterId: { type: [String, Number], required: true },
  characterName: { type: String, default: '' },
})

const loading = ref(false)
const loadError = ref('')
const nodes = ref([])
const edges = ref([])
const canvasRef = ref(null)

async function loadGraph() {
  if (!props.projectId || !props.characterName) return
  
  loading.value = true
  loadError.value = ''
  try {
    const res = await graphApi.getSubgraph(props.projectId, {
      name: props.characterName,
      hops: 1,
    })
    nodes.value = res.data?.nodes || []
    edges.value = res.data?.edges || []
  } catch (err) {
    console.error('加载关系图谱失败:', err)
    loadError.value = '加载关系图谱失败，请重试'
    showError('加载关系图谱失败')
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