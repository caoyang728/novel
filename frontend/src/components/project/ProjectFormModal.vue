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

const props = defineProps({
  visible: { type: Boolean, default: false },
  project: { type: Object, default: null },
  submitting: { type: Boolean, default: false },
})

const emit = defineEmits(['update:visible', 'submit'])

const formRef = ref(null)
const isEdit = ref(false)

const form = reactive({
  title: '',
  description: '',
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
    form.min_words_per_chapter = props.project.min_words_per_chapter || 1000
  } else if (val) {
    isEdit.value = false
    form.title = ''
    form.description = ''
    form.min_words_per_chapter = 1000
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
