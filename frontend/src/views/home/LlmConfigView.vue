<template>
  <div class="llm-config-view">
    <div v-loading="loading" class="config-sections">
      <el-tabs v-model="activeTab" class="config-tabs">
        <!-- 模型配置 -->
        <el-tab-pane label="模型配置" name="models">
          <template #label>
            <span class="tab-label"><el-icon><Box /></el-icon> 模型配置</span>
          </template>
          <section class="config-section">
            <div class="service-block glass-surface">
              <div class="service-header">
                <div>
                  <div class="service-title">模型配置</div>
                  <div class="service-desc">管理 LLM 模型配置，设置 API 密钥、参数和价格</div>
                </div>
                <AppButton variant="accent" size="small" @click="openConfigModal">
                  <el-icon><Plus /></el-icon> 添加配置
                </AppButton>
              </div>
              <EmptyState v-if="configs.length === 0" icon="Box" text="暂无 LLM 配置，请添加" />
              <div v-else class="config-list">
                <div
                  v-for="config in configs"
                  :key="config.id"
                  class="config-card"
                  :class="{ default: config.is_default, disabled: !config.is_active }"
                >
                <div class="config-main">
                  <el-icon class="config-icon"><Box /></el-icon>
                  <div class="config-info">
                    <div class="config-name-row">
                      <span class="config-name">{{ config.name }}</span>
                      <el-tag v-if="config.is_default" type="success" size="small">默认</el-tag>
                      <el-tag v-if="!config.is_active" type="info" size="small">已停用</el-tag>
                    </div>
                    <div class="config-provider">{{ providerName(config.provider) }} · {{ config.model_name }}</div>
                  </div>
                </div>

                <div class="config-status">
                  <span v-if="connStatus[config.id] === 'testing'" class="status testing">
                    <el-icon class="is-loading"><Loading /></el-icon> 连接中
                  </span>
                  <span v-else-if="connStatus[config.id] === 'success'" class="status success">
                    <el-icon><CircleCheck /></el-icon> 已连接
                  </span>
                  <span v-else-if="connStatus[config.id] === 'fail'" class="status fail" :title="connStatus[config.id + '_msg']">
                    <el-icon><CircleClose /></el-icon> {{ connStatus[config.id + '_msg'] || '连接失败' }}
                  </span>
                </div>

                <div class="config-actions">
                  <AppButton size="small" @click="testConnection(config.id)">
                    <el-icon><Connection /></el-icon>
                  </AppButton>
                  <AppButton size="small" @click="openConfigModal(config.id)">
                    <el-icon><Edit /></el-icon>
                  </AppButton>
                  <AppButton size="small" variant="danger" @click="deleteConfig(config.id)">
                    <el-icon><Delete /></el-icon>
                  </AppButton>
                  <el-switch
                    :model-value="config.is_active"
                    @change="(val) => toggleActive(config.id, val)"
                  />
                </div>
              </div>
            </div>
            </div>
          </section>
        </el-tab-pane>

        <!-- 场景配置 -->
        <el-tab-pane label="场景配置" name="scenes">
          <template #label>
            <span class="tab-label"><el-icon><Operation /></el-icon> 场景配置</span>
          </template>
          <section class="config-section">
            <div class="service-block glass-surface">
              <div class="service-header">
                <div>
                  <div class="service-title">场景配置</div>
                  <div class="service-desc">为不同写作场景分配模型配置，自定义温度和 Token 参数</div>
                </div>
              </div>
              <div v-for="group in orderedGroups" :key="group.key" class="task-group">
                <div class="task-group-title">{{ group.name }}</div>
                <div class="task-group-items">
                  <div v-for="scene in group.scenes" :key="scene.key" class="task-item">
                  <div class="task-left">
                    <div class="task-name">{{ scene.name }}</div>
                    <div v-if="scene.key !== 'default'" class="task-defaults">
                      默认: 温度 {{ scene.default_temperature }} · Token {{ scene.default_max_tokens }}
                    </div>
                    <div
                      v-if="taskOverride(scene.key, 'temperature') != null && taskOverride(scene.key, 'temperature') !== scene.default_temperature"
                      class="task-override"
                    >
                      自定义温度: {{ taskOverride(scene.key, 'temperature') }}
                    </div>
                    <div
                      v-if="taskOverride(scene.key, 'max_tokens') != null && taskOverride(scene.key, 'max_tokens') !== scene.default_max_tokens"
                      class="task-override"
                    >
                      自定义 Token: {{ taskOverride(scene.key, 'max_tokens') }}
                    </div>
                  </div>
                  <div class="task-right">
                    <el-tag v-if="taskConfigInfo(scene.key)" type="primary" size="small">
                      {{ taskConfigInfo(scene.key).name }}
                    </el-tag>
                    <span v-else class="task-unconfigured">未配置</span>
                    <AppButton size="small" @click="openTaskModal(scene.key)">
                      <el-icon><Edit /></el-icon>
                    </AppButton>
                  </div>
                </div>
              </div>
            </div>
            </div>
          </section>
        </el-tab-pane>

        <!-- 向量 & Rerank 配置 -->
        <el-tab-pane label="向量 & Rerank" name="embedding">
          <template #label>
            <span class="tab-label"><el-icon><Connection /></el-icon> 向量 & Rerank</span>
          </template>
          <section class="config-section embedding-section">
            <!-- Embedding 配置 -->
            <div class="service-block glass-surface">
              <div class="service-header">
                <div>
                  <div class="service-title">Embedding 向量化</div>
                  <div class="service-desc">将文本转换为向量，用于语义检索</div>
                </div>
              </div>
              <el-form label-position="top" class="embedding-form">
                <el-form-item label="运行模式">
                  <el-select v-model="embedConfig.embedding_mode" style="width: 100%">
                    <el-option label="仅云API" value="api_only" />
                    <el-option label="仅Docker" value="docker_only" />
                    <el-option label="API优先，Docker兜底" value="api_first" />
                    <el-option label="Docker优先，API兜底" value="docker_first" />
                    <el-option label="关闭" value="disabled" />
                  </el-select>
                </el-form-item>
                <template v-if="embedConfig.embedding_mode !== 'disabled'">
                  <template v-if="showEmbedApi">
                    <div class="section-label">云API 配置</div>
                    <el-form-item label="API 密钥">
                      <el-input
                        v-model="embedConfig.embedding_api_key"
                        type="password"
                        show-password
                        :placeholder="embedConfig.has_embedding_api_key ? '已设置，留空则不修改' : 'sk-...'"
                      />
                    </el-form-item>
                    <div class="form-row">
                      <el-form-item label="API 地址">
                        <el-input v-model="embedConfig.embedding_api_base_url" placeholder="https://api.example.com/v1/" />
                      </el-form-item>
                      <el-form-item label="模型名称">
                        <el-input v-model="embedConfig.embedding_api_model" placeholder="embedding-2" />
                      </el-form-item>
                    </div>
                  </template>
                  <template v-if="showEmbedDocker">
                    <div class="section-label">Docker 配置</div>
                    <div class="form-row">
                      <el-form-item label="服务地址">
                        <el-input v-model="embedConfig.embedding_docker_url" placeholder="http://embedding:8000/embed" />
                      </el-form-item>
                      <el-form-item label="超时(秒)">
                        <el-input-number v-model="embedConfig.embedding_docker_timeout" :min="5" :max="120" style="width: 100%" />
                      </el-form-item>
                    </div>
                  </template>
                  <div class="form-actions">
                    <AppButton size="small" :loading="embedTesting" @click="testEmbedding">
                      <el-icon><Connection /></el-icon> 测试连接
                    </AppButton>
                    <span v-if="embedTestResult" :class="['test-result', embedTestResult.success ? 'success' : 'fail']">
                      {{ embedTestResult.message }}
                    </span>
                  </div>
                </template>
              </el-form>
            </div>

            <!-- Rerank 配置 -->
            <div class="service-block glass-surface">
              <div class="service-header">
                <div>
                  <div class="service-title">Rerank 重排序</div>
                  <div class="service-desc">对检索结果进行语义重排序，提升相关性</div>
                </div>
              </div>
              <el-form label-position="top" class="embedding-form">
                <el-form-item label="运行模式">
                  <el-select v-model="embedConfig.rerank_mode" style="width: 100%">
                    <el-option label="仅云API" value="api_only" />
                    <el-option label="仅Docker" value="docker_only" />
                    <el-option label="API优先，Docker兜底" value="api_first" />
                    <el-option label="Docker优先，API兜底" value="docker_first" />
                    <el-option label="关闭" value="disabled" />
                  </el-select>
                </el-form-item>
                <template v-if="embedConfig.rerank_mode !== 'disabled'">
                  <template v-if="showRerankApi">
                    <div class="section-label">云API 配置</div>
                    <el-form-item label="API 密钥">
                      <el-input
                        v-model="embedConfig.rerank_api_key"
                        type="password"
                        show-password
                        :placeholder="embedConfig.has_rerank_api_key ? '已设置，留空则不修改' : 'sk-...'"
                      />
                    </el-form-item>
                    <div class="form-row">
                      <el-form-item label="API 地址">
                        <el-input v-model="embedConfig.rerank_api_base_url" placeholder="https://api.example.com/v1/" />
                      </el-form-item>
                      <el-form-item label="模型名称">
                        <el-input v-model="embedConfig.rerank_api_model" placeholder="rerank-v1" />
                      </el-form-item>
                    </div>
                  </template>
                  <template v-if="showRerankDocker">
                    <div class="section-label">Docker 配置</div>
                    <div class="form-row">
                      <el-form-item label="服务地址">
                        <el-input v-model="embedConfig.rerank_docker_url" placeholder="http://rerank:8000/rerank" />
                      </el-form-item>
                      <el-form-item label="超时(秒)">
                        <el-input-number v-model="embedConfig.rerank_docker_timeout" :min="5" :max="120" style="width: 100%" />
                      </el-form-item>
                    </div>
                  </template>
                  <div class="form-actions">
                    <AppButton size="small" :loading="rerankTesting" @click="testRerank">
                      <el-icon><Connection /></el-icon> 测试连接
                    </AppButton>
                    <span v-if="rerankTestResult" :class="['test-result', rerankTestResult.success ? 'success' : 'fail']">
                      {{ rerankTestResult.message }}
                    </span>
                  </div>
                </template>
              </el-form>
            </div>

            <div class="embedding-save-bar">
              <AppButton variant="accent" :loading="embedSaving" @click="saveEmbedConfig">
                保存配置
              </AppButton>
            </div>
          </section>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 新增/编辑配置弹窗 -->
    <AppModal
      v-model:visible="configModal.visible"
      :title="configModal.id ? '编辑 LLM 配置' : '添加 LLM 配置'"
      width="640px"
    >
      <el-form label-position="top" class="config-form">
        <el-form-item label="配置名称" required>
          <el-input v-model="configModal.name" placeholder="例如：DeepSeek 主力" />
        </el-form-item>
        <div class="form-row">
          <el-form-item label="服务商">
            <el-select v-model="configModal.provider" style="width: 100%" @change="onProviderChange">
              <el-option
                v-for="(preset, key) in providerPresets"
                :key="key"
                :label="preset.name || key"
                :value="key"
              />
              <el-option label="自定义" value="custom" />
            </el-select>
          </el-form-item>
          <el-form-item label="API 密钥" :required="!configModal.id">
            <el-input
              v-model="configModal.apiKey"
              type="password"
              show-password
              :placeholder="configModal.id ? '留空则不修改密钥' : 'sk-...'"
            />
          </el-form-item>
        </div>
        <el-form-item label="API 地址">
          <el-input v-model="configModal.baseUrl" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="模型" required>
          <el-select
            v-if="presetModels.length > 0 && !configModal.customModel"
            v-model="configModal.modelName"
            style="width: 100%"
            @change="onModelChange"
          >
            <el-option v-for="m in presetModels" :key="m.name" :label="`${m.label} (${m.name})`" :value="m.name" />
            <el-option label="自定义输入..." value="__custom__" />
          </el-select>
          <el-input
            v-else
            v-model="configModal.modelName"
            placeholder="模型名称"
          >
            <template #append>
              <AppButton v-if="presetModels.length > 0" size="small" @click="configModal.customModel = false">选择预设</AppButton>
            </template>
          </el-input>
        </el-form-item>
        <div class="form-row">
          <el-form-item label="温度">
            <el-input-number v-model="configModal.temperature" :min="0" :max="2" :step="0.1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="最大 Token">
            <el-input-number v-model="configModal.maxTokens" :min="256" :max="200000" :step="256" style="width: 100%" />
          </el-form-item>
        </div>
        <div class="form-row">
          <el-form-item label="输入价格 / 百万 Token">
            <el-input-number v-model="configModal.inputPrice" :min="0" :step="0.1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="输出价格 / 百万 Token">
            <el-input-number v-model="configModal.outputPrice" :min="0" :step="0.1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="缓存命中价格">
            <el-input-number v-model="configModal.cacheHitPrice" :min="0" :step="0.1" style="width: 100%" />
          </el-form-item>
        </div>
        <el-form-item>
          <el-checkbox v-model="configModal.isDefault">设为默认配置</el-checkbox>
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="modal-footer">
          <AppButton :loading="testing" @click="testFromModal">
            <el-icon><Connection /></el-icon> 测试连接
          </AppButton>
          <div>
            <AppButton @click="configModal.visible = false">取消</AppButton>
            <AppButton variant="accent" :loading="saving" @click="saveConfig">保存</AppButton>
          </div>
        </div>
      </template>
    </AppModal>

    <!-- 场景配置弹窗 -->
    <AppModal
      v-model:visible="taskModal.visible"
      :title="`编辑场景配置 - ${taskModal.sceneName}`"
      width="520px"
    >
      <el-form label-position="top">
        <el-form-item label="使用模型配置">
          <el-select v-model="taskModal.configId" style="width: 100%" placeholder="选择模型配置">
            <el-option v-for="c in configs" :key="c.id" :label="`${c.name} (${providerName(c.provider)})`" :value="c.id" />
          </el-select>
        </el-form-item>
        <template v-if="taskModal.taskType !== 'default'">
          <el-form-item label="温度（留空使用场景默认值）">
            <el-input
              v-model="taskModal.temperature"
              type="number"
              :placeholder="taskModal.defaultTemp ? `默认值: ${taskModal.defaultTemp}` : '留空使用场景默认值'"
            />
          </el-form-item>
          <el-form-item label="最大 Token（留空使用场景默认值）">
            <el-input
              v-model="taskModal.maxTokens"
              type="number"
              :placeholder="taskModal.defaultTokens ? `默认值: ${taskModal.defaultTokens}` : '留空使用场景默认值'"
            />
          </el-form-item>
        </template>
      </el-form>

      <template #footer>
        <AppButton @click="taskModal.visible = false">取消</AppButton>
        <AppButton variant="accent" :loading="saving" @click="saveTaskConfig">保存</AppButton>
      </template>
    </AppModal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import {
  Plus, Box, Edit, Delete, Loading, CircleCheck, CircleClose,
  Connection, Operation, Setting,
} from '@element-plus/icons-vue'
import EmptyState from '@/components/common/EmptyState.vue'
import AppButton from '@/components/common/AppButton.vue'
import AppModal from '@/components/common/AppModal.vue'
import { llmConfigApi, embeddingConfigApi } from '@/api/llmConfig'
import { showSuccess, showError } from '@/utils/notify'
import { showConfirmModal } from '@/utils/modal'
import { rsaEncrypt } from '@/utils/crypto'
import { useUiStore } from '@/stores/ui'

const GROUP_ORDER = ['default', 'worldview', 'character', 'timeline', 'outline', 'volume', 'chapter', 'note']

const uiStore = useUiStore()

onUnmounted(() => {
  uiStore.clearHeaderActions()
})

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const activeTab = ref('models')
const configs = ref([])
const taskConfigs = ref([])
const groupedScenes = ref({})
const providerPresets = ref({})
const connStatus = reactive({})

const configModal = reactive({
  visible: false,
  id: null,
  name: '',
  provider: 'deepseek',
  apiKey: '',
  baseUrl: '',
  modelName: '',
  customModel: false,
  temperature: 0.7,
  maxTokens: 4096,
  inputPrice: 0,
  outputPrice: 0,
  cacheHitPrice: 0,
  isDefault: false,
})

const taskModal = reactive({
  visible: false,
  taskType: '',
  sceneName: '',
  configId: null,
  temperature: '',
  maxTokens: '',
  defaultTemp: '',
  defaultTokens: '',
})

// Embedding / Rerank 配置状态
const embedConfig = reactive({
  embedding_mode: 'api_only',
  embedding_api_key: '',
  embedding_api_base_url: '',
  embedding_api_model: '',
  embedding_docker_url: '',
  embedding_docker_timeout: 30,
  has_embedding_api_key: false,
  rerank_mode: 'disabled',
  rerank_api_key: '',
  rerank_api_base_url: '',
  rerank_api_model: '',
  rerank_docker_url: '',
  rerank_docker_timeout: 30,
  has_rerank_api_key: false,
})
const embedSaving = ref(false)
const embedTesting = ref(false)
const embedTestResult = ref(null)
const rerankTesting = ref(false)
const rerankTestResult = ref(null)

const showEmbedApi = computed(() =>
  ['api_only', 'api_first', 'docker_first'].includes(embedConfig.embedding_mode)
)
const showEmbedDocker = computed(() =>
  ['docker_only', 'docker_first', 'api_first'].includes(embedConfig.embedding_mode)
)
const showRerankApi = computed(() =>
  ['api_only', 'api_first', 'docker_first'].includes(embedConfig.rerank_mode)
)
const showRerankDocker = computed(() =>
  ['docker_only', 'docker_first', 'api_first'].includes(embedConfig.rerank_mode)
)

const orderedGroups = computed(() =>
  GROUP_ORDER.filter((k) => groupedScenes.value[k]).map((k) => ({ key: k, ...groupedScenes.value[k] })),
)

const presetModels = computed(() => providerPresets.value[configModal.provider]?.models || [])

function providerName(provider) {
  return providerPresets.value[provider]?.name || provider
}

function taskConfig(sceneKey) {
  return taskConfigs.value.find((t) => t.task_type === sceneKey)
}

function taskConfigInfo(sceneKey) {
  const tc = taskConfig(sceneKey)
  if (!tc) return null
  return configs.value.find((c) => c.id === tc.llm_config_id)
}

function taskOverride(sceneKey, field) {
  return taskConfig(sceneKey)?.[field] ?? null
}

async function loadProviderPresets() {
  try {
    const res = await fetch('/static/data/llm_providers.json')
    if (res.ok) providerPresets.value = await res.json()
  } catch (e) {
    console.error('加载服务商预设失败:', e)
  }
}

async function loadConfigs(testAll = false) {
  loading.value = true
  try {
    const data = await llmConfigApi.getAll()
    if (data.success) {
      configs.value = data.configs || []
      taskConfigs.value = data.task_configs || []
      groupedScenes.value = data.grouped_scenes || {}
      if (testAll) testAllConnections()
    }
  } catch {
    // 统一提示
  } finally {
    loading.value = false
  }
}

async function testAllConnections() {
  await Promise.allSettled(configs.value.filter((c) => c.is_active).map((c) => testConnection(c.id, true)))
}

async function testConnection(configId, silent = false) {
  connStatus[configId] = 'testing'
  try {
    const data = await llmConfigApi.test(configId)
    if (data.success) {
      connStatus[configId] = 'success'
      connStatus[configId + '_msg'] = data.message || '连接成功'
      if (!silent) showSuccess(data.message || '连接成功')
    } else {
      connStatus[configId] = 'fail'
      connStatus[configId + '_msg'] = data.message || '连接失败'
      if (!silent) showError(data.message || '连接失败')
    }
  } catch {
    connStatus[configId] = 'fail'
    connStatus[configId + '_msg'] = '请求异常'
  }
}

function onProviderChange() {
  const preset = providerPresets.value[configModal.provider]
  if (preset?.base_url) configModal.baseUrl = preset.base_url
  configModal.customModel = false
  configModal.modelName = preset?.models?.[0]?.name || ''
  onModelChange()
}

function onModelChange() {
  if (configModal.modelName === '__custom__') {
    configModal.modelName = ''
    configModal.customModel = true
    return
  }
  const model = presetModels.value.find((m) => m.name === configModal.modelName)
  if (model) {
    configModal.inputPrice = model.input_price || 0
    configModal.outputPrice = model.output_price || 0
    configModal.cacheHitPrice = model.cache_hit_price || 0
  }
}

function openConfigModal(configId = null) {
  Object.assign(configModal, {
    visible: true,
    id: configId,
    name: '',
    provider: 'deepseek',
    apiKey: '',
    baseUrl: '',
    modelName: '',
    customModel: false,
    temperature: 0.7,
    maxTokens: 4096,
    inputPrice: 0,
    outputPrice: 0,
    cacheHitPrice: 0,
    isDefault: false,
  })

  if (configId) {
    const config = configs.value.find((c) => c.id === configId)
    if (config) {
      Object.assign(configModal, {
        name: config.name,
        provider: config.provider,
        baseUrl: config.base_url || '',
        modelName: config.model_name || '',
        temperature: config.temperature ?? 0.7,
        maxTokens: config.max_tokens ?? 4096,
        inputPrice: config.input_price || 0,
        outputPrice: config.output_price || 0,
        cacheHitPrice: config.cache_hit_price || 0,
        isDefault: !!config.is_default,
        customModel: !providerPresets.value[config.provider]?.models?.some((m) => m.name === config.model_name),
      })
    }
  } else {
    onProviderChange()
  }
}

async function saveConfig() {
  if (!configModal.name.trim() || !configModal.modelName.trim()) {
    showError('请填写配置名称和模型')
    return
  }
  saving.value = true
  const payload = {
    name: configModal.name.trim(),
    provider: configModal.provider,
    api_key: configModal.apiKey || undefined,
    base_url: configModal.baseUrl.trim(),
    model_name: configModal.modelName.trim(),
    temperature: Number(configModal.temperature),
    max_tokens: Number(configModal.maxTokens),
    input_price: Number(configModal.inputPrice) || 0,
    output_price: Number(configModal.outputPrice) || 0,
    cache_hit_price: Number(configModal.cacheHitPrice) || 0,
    is_default: configModal.isDefault,
  }
  try {
    const data = configModal.id
      ? await llmConfigApi.update({ config_id: configModal.id, ...payload })
      : await llmConfigApi.create(payload)
    if (data.success) {
      configModal.visible = false
      await loadConfigs(false)
      showSuccess('保存成功')
      const savedId = data.config_id || configModal.id
      if (savedId) testConnection(savedId, true)
    }
  } catch {
    // 统一提示
  } finally {
    saving.value = false
  }
}

async function testFromModal() {
  if (!configModal.modelName.trim()) {
    showError('请先填写模型名称')
    return
  }
  testing.value = true
  try {
    let data
    if (configModal.apiKey) {
      data = await llmConfigApi.testParams({
        api_key: configModal.apiKey,
        base_url: configModal.baseUrl.trim(),
        model_name: configModal.modelName.trim(),
      })
    } else if (configModal.id) {
      data = await llmConfigApi.test(configModal.id)
    } else {
      showError('请填写 API 密钥')
      return
    }
    if (data.success) {
      showSuccess(data.message || '连接成功')
      if (configModal.id) {
        connStatus[configModal.id] = 'success'
        connStatus[configModal.id + '_msg'] = data.message || '连接成功'
      }
    } else {
      showError(data.message || '连接失败')
      if (configModal.id) {
        connStatus[configModal.id] = 'fail'
        connStatus[configModal.id + '_msg'] = data.message || '连接失败'
      }
    }
  } catch {
    showError('测试请求失败，请重试')
  } finally {
    testing.value = false
  }
}

function deleteConfig(configId) {
  showConfirmModal({
    title: '删除配置',
    message: '确定要删除这个 LLM 配置吗？',
    danger: true,
    confirmText: '删除',
    onConfirm: async (close) => {
      try {
        const data = await llmConfigApi.delete(configId)
        if (data.success) {
          close()
          await loadConfigs(false)
          showSuccess('删除成功')
        }
      } catch {
        // 统一提示
      }
    },
  })
}

async function toggleActive(configId, isActive) {
  try {
    const data = await llmConfigApi.toggleActive(configId, isActive)
    if (data.success) {
      const config = configs.value.find((c) => c.id === configId)
      if (config) config.is_active = isActive
      showSuccess(isActive ? '已启用' : '已停用')
    }
  } catch {
    // 统一提示（request.js 已报错）
  }
}

function openTaskModal(taskType) {
  let sceneName = taskType
  let defaultTemp = ''
  let defaultTokens = ''
  for (const group of orderedGroups.value) {
    const scene = group.scenes.find((s) => s.key === taskType)
    if (scene) {
      sceneName = scene.name
      defaultTemp = scene.default_temperature
      defaultTokens = scene.default_max_tokens
      break
    }
  }
  const tc = taskConfig(taskType)
  Object.assign(taskModal, {
    visible: true,
    taskType,
    sceneName,
    configId: tc?.llm_config_id ?? null,
    temperature: tc?.temperature ?? '',
    maxTokens: tc?.max_tokens ?? '',
    defaultTemp,
    defaultTokens,
  })
}

async function saveTaskConfig() {
  saving.value = true
  try {
    const data = await llmConfigApi.setTask({
      task_type: taskModal.taskType,
      config_id: taskModal.configId,
      temperature: taskModal.temperature ? Number(taskModal.temperature) : null,
      max_tokens: taskModal.maxTokens ? Number(taskModal.maxTokens) : null,
    })
    if (data.success) {
      taskModal.visible = false
      await loadConfigs(false)
      showSuccess('保存成功')
    }
  } catch {
    // 统一提示
  } finally {
    saving.value = false
  }
}

async function loadEmbedConfig() {
  try {
    const data = await embeddingConfigApi.get()
    if (data.success && data.config) {
      Object.assign(embedConfig, data.config)
      // 清空密码字段（不从后端获取明文）
      embedConfig.embedding_api_key = ''
      embedConfig.rerank_api_key = ''
    }
  } catch {
    // 静默失败
  }
}

async function saveEmbedConfig() {
  embedSaving.value = true
  try {
    const payload = { ...embedConfig }
    // 清理空密码字段
    if (!payload.embedding_api_key) delete payload.embedding_api_key
    if (!payload.rerank_api_key) delete payload.rerank_api_key
    delete payload.has_embedding_api_key
    delete payload.has_rerank_api_key
    // RSA 加密 API key
    if (payload.embedding_api_key) {
      payload.embedding_api_key_encrypted = await rsaEncrypt(payload.embedding_api_key)
      delete payload.embedding_api_key
    }
    if (payload.rerank_api_key) {
      payload.rerank_api_key_encrypted = await rsaEncrypt(payload.rerank_api_key)
      delete payload.rerank_api_key
    }
    const data = await embeddingConfigApi.save(payload)
    if (data.success) {
      showSuccess('保存成功')
      // 重新加载以更新 has_*_api_key 状态
      await loadEmbedConfig()
    }
  } catch {
    // 统一提示
  } finally {
    embedSaving.value = false
  }
}

async function testEmbedding() {
  embedTesting.value = true
  embedTestResult.value = null
  try {
    const payload = { test_type: 'embedding', embedding_mode: embedConfig.embedding_mode }
    if (embedConfig.embedding_api_key) {
      payload.embedding_api_key_encrypted = await rsaEncrypt(embedConfig.embedding_api_key)
    }
    if (embedConfig.embedding_api_base_url) payload.embedding_api_base_url = embedConfig.embedding_api_base_url
    if (embedConfig.embedding_api_model) payload.embedding_api_model = embedConfig.embedding_api_model
    if (embedConfig.embedding_docker_url) payload.embedding_docker_url = embedConfig.embedding_docker_url
    payload.embedding_docker_timeout = embedConfig.embedding_docker_timeout
    const data = await embeddingConfigApi.test(payload)
    embedTestResult.value = data.results || data
  } catch {
    embedTestResult.value = { success: false, message: '测试请求失败' }
  } finally {
    embedTesting.value = false
  }
}

async function testRerank() {
  rerankTesting.value = true
  rerankTestResult.value = null
  try {
    const payload = { test_type: 'rerank', rerank_mode: embedConfig.rerank_mode }
    if (embedConfig.rerank_api_key) {
      payload.rerank_api_key_encrypted = await rsaEncrypt(embedConfig.rerank_api_key)
    }
    if (embedConfig.rerank_api_base_url) payload.rerank_api_base_url = embedConfig.rerank_api_base_url
    if (embedConfig.rerank_api_model) payload.rerank_api_model = embedConfig.rerank_api_model
    if (embedConfig.rerank_docker_url) payload.rerank_docker_url = embedConfig.rerank_docker_url
    payload.rerank_docker_timeout = embedConfig.rerank_docker_timeout
    const data = await embeddingConfigApi.test(payload)
    rerankTestResult.value = data.results || data
  } catch {
    rerankTestResult.value = { success: false, message: '测试请求失败' }
  } finally {
    rerankTesting.value = false
  }
}

onMounted(async () => {
  await loadProviderPresets()
  await loadConfigs(true)
  await loadEmbedConfig()
})
</script>

<style lang="scss" scoped>
.llm-config-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: var(--surface);
  border-radius: var(--radius-lg);
}

.config-sections {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.config-tabs {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;

  :deep(.el-tabs__header) {
    margin-bottom: 0;
    flex-shrink: 0;
  }
  :deep(.el-tabs__nav-wrap::after) {
    display: none;
  }
  :deep(.el-tabs__content) {
    flex: 1;
    overflow-y: auto;
    min-height: 0;
    padding: 0 4px 16px;
  }
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.config-section {
  padding: 20px 0;
}

.config-list {
  display: flex;
  flex-direction: column;
}

.config-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 0;
  border-bottom: 1px solid var(--glass-border);
  transition: background var(--transition-normal);

  &:last-child {
    border-bottom: none;
  }

  &:hover {
    background: rgba(255, 255, 255, 0.02);
  }

  &.default {
    background: rgba(34, 197, 94, 0.03);
  }

  &.disabled {
    opacity: 0.5;
  }
}

.config-main {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.config-icon {
  font-size: 22px;
  color: var(--primary);
}

.config-info {
  min-width: 0;
}

.config-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 3px;
}

.config-name {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 14px;
}

.config-provider {
  font-size: 12px;
  color: var(--text-muted);
}

.config-status {
  min-width: 120px;
  font-size: 12px;

  .status {
    display: inline-flex;
    align-items: center;
    gap: 4px;

    &.success { color: #22c55e; }
    &.fail { color: #ef4444; }
    &.testing { color: var(--text-muted); }
  }
}

.config-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

// 场景配置
.task-group {
  margin-bottom: 20px;

  &:last-child {
    margin-bottom: 0;
  }
}

.task-group-items {
  display: flex;
  flex-direction: column;
}

.task-group-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-top: 16px;
  margin-bottom: 8px;

  &:first-child {
    margin-top: 0;
  }
}

.task-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 0;
  border-bottom: 1px solid var(--glass-border);
  transition: background var(--transition-normal);

  &:last-child {
    border-bottom: none;
  }

  &:hover {
    background: rgba(255, 255, 255, 0.02);
  }
}

.task-name {
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
}

.task-defaults {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 3px;
}

.task-override {
  font-size: 12px;
  color: var(--primary);
  margin-top: 3px;
}

.task-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.task-unconfigured {
  font-size: 12px;
  color: var(--text-muted);
  font-style: italic;
}

// 弹窗表单
.config-form {
  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0 16px;
  }
  .form-row:has(.el-form-item:nth-child(3)) {
    grid-template-columns: 1fr 1fr 1fr;
  }
}

.modal-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

// Embedding / Rerank 配置
.embedding-section {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.service-block {
  padding: 20px;
}

.service-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}

.service-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.service-desc {
  font-size: 12px;
  color: var(--text-muted);
}

.embedding-form {
  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0 16px;
  }
}

.section-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 12px 0 4px;
  padding-top: 8px;
  border-top: 1px solid var(--glass-border);
}

.form-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
}

.test-result {
  font-size: 12px;

  &.success { color: #22c55e; }
  &.fail { color: #ef4444; }
}

.embedding-save-bar {
  display: flex;
  justify-content: flex-end;
  padding-top: 4px;
}

@media (max-width: 768px) {
  .btn-text {
    display: none;
  }
  .config-status {
    display: none;
  }
  .config-form .form-row {
    grid-template-columns: 1fr !important;
  }
  .embedding-form .form-row {
    grid-template-columns: 1fr !important;
  }
}
</style>
