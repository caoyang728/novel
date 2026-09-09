<template>
  <AppModal
    :visible="visible"
    :title="isEdit ? '编辑项目' : '创建项目'"
    width="520px"
    @update:visible="$emit('update:visible', $event)"
    @cancel="handleCancel"
  >
    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
      @submit.prevent
    >
      <el-form-item label="项目名称" prop="title">
        <el-input v-model="form.title" placeholder="请输入项目名称" maxlength="100" />
      </el-form-item>
      <el-form-item label="项目描述" prop="description">
        <el-input
          v-model="form.description"
          type="textarea"
          :rows="3"
          placeholder="请输入项目描述（可选）"
          maxlength="500"
        />
      </el-form-item>
      <el-form-item label="题材类型" prop="genre">
        <el-select v-model="form.genre" placeholder="选择题材类型" style="width: 100%">
          <el-option
            v-for="g in GENRE_OPTIONS"
            :key="g.value"
            :label="g.label"
            :value="g.value"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="每章最低字数" prop="min_words_per_chapter">
        <el-input-number
          v-model="form.min_words_per_chapter"
          :min="100"
          :max="10000"
          :step="100"
        />
      </el-form-item>
    </el-form>

    <template #footer>
      <div class="form-actions">
        <AppButton @click="handleCancel">取消</AppButton>
        <AppButton
          variant="accent"
          :loading="submitting"
          @click="handleSubmit"
        >
          {{ isEdit ? '保存' : '创建' }}
        </AppButton>
      </div>
    </template>
  </AppModal>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import AppModal from '@/components/common/AppModal.vue'
import AppButton from '@/components/common/AppButton.vue'
import { showConfirmModal } from '@/utils/modal'

const GENRE_OPTIONS = [
  { value: 'xuanhuan', label: '玄幻/仙侠' },
  { value: 'wuxia', label: '武侠' },
  { value: 'fantasy', label: '西方奇幻' },
  { value: 'scifi', label: '科幻' },
  { value: 'history', label: '历史/架空' },
  { value: 'urban', label: '都市' },
  { value: 'apocalypse', label: '末世/灾变' },
  { value: 'general', label: '通用' },
]

const props = defineProps({
  visible: { type: Boolean, default: false },
  project: { type: Object, default: null },
  submitting: { type: Boolean, default: false },
})

const emit = defineEmits(['update:visible', 'submit'])

const formRef = ref(null)
const isEdit = ref(false)
const originalGenre = ref('')

const form = reactive({
  title: '',
  description: '',
  genre: 'general',
  min_words_per_chapter: 1000,
})

const rules = {
  title: [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
}

watch(() => props.visible, (val) => {
  if (val && props.project) {
    isEdit.value = true
    form.title = props.project.title || ''
    form.description = props.project.description || ''
    form.genre = props.project.genre || 'general'
    originalGenre.value = props.project.genre || 'general'
    form.min_words_per_chapter = props.project.min_words_per_chapter || 1000
  } else if (val) {
    isEdit.value = false
    originalGenre.value = ''
    form.title = ''
    form.description = ''
    form.genre = 'general'
    form.min_words_per_chapter = 1000
  }
})

// 编辑模式下修改题材时弹窗提醒
watch(() => form.genre, (newVal, oldVal) => {
  if (isEdit.value && oldVal && newVal !== oldVal) {
    showConfirmModal({
      title: '修改题材提醒',
      message: '修改题材将影响世界观、大纲等模块的构建指引，是否确认？',
      onConfirm: () => {},
      onCancel: () => {
        form.genre = oldVal
      },
    })
  }
})

function handleCancel() {
  emit('update:visible', false)
}

async function handleSubmit() {
  try {
    await formRef.value?.validate()
    emit('submit', { ...form, isEdit: isEdit.value })
  } catch {
    // validation failed
  }
}
</script>

<style lang="scss" scoped>
.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>
