<template>
  <div class="reset-password-view">
    <h2 class="form-title">重置密码</h2>
    <p class="form-subtitle">输入您的用户名和新密码</p>

    <el-form
      ref="formRef"
      :model="form"
      :rules="rules"
      label-position="top"
      @submit.prevent="handleReset"
    >
      <el-form-item label="用户名" prop="username">
        <el-input
          v-model="form.username"
          placeholder="请输入用户名"
          :prefix-icon="User"
          size="large"
        />
      </el-form-item>

      <el-form-item label="邮箱" prop="email">
        <el-input
          v-model="form.email"
          placeholder="请输入注册时的邮箱"
          :prefix-icon="Message"
          size="large"
        />
      </el-form-item>

      <el-form-item label="新密码" prop="password">
        <el-input
          v-model="form.password"
          type="password"
          placeholder="请输入新密码"
          :prefix-icon="Lock"
          size="large"
          show-password
        />
      </el-form-item>

      <el-form-item label="确认新密码" prop="confirmPassword">
        <el-input
          v-model="form.confirmPassword"
          type="password"
          placeholder="请再次输入新密码"
          :prefix-icon="Lock"
          size="large"
          show-password
          @keyup.enter="handleReset"
        />
      </el-form-item>

      <el-form-item>
        <el-button
          type="primary"
          size="large"
          :loading="loading"
          class="reset-btn"
          @click="handleReset"
        >
          重置密码
        </el-button>
      </el-form-item>
    </el-form>

    <div class="form-links">
      <router-link to="/login" class="form-link">返回登录</router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { User, Lock, Message } from '@element-plus/icons-vue'
import { authApi } from '@/api/auth'
import { showSuccess, showError } from '@/utils/notify'

const router = useRouter()

const formRef = ref(null)
const loading = ref(false)

const form = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
})

const validateConfirmPassword = (rule, value, callback) => {
  if (value !== form.password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度不少于 6 个字符', trigger: 'blur' },
  ],
  confirmPassword: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    { validator: validateConfirmPassword, trigger: 'blur' },
  ],
}

async function handleReset() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }

  loading.value = true
  try {
    await authApi.resetPassword({
      username: form.username,
      email: form.email,
      password: form.password,
      password_confirm: form.confirmPassword,
    })
    showSuccess('密码重置成功，请登录')
    router.push('/login')
  } catch (err) {
    showError(err.message || '重置失败')
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
.reset-password-view {
  width: 100%;
}

.form-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 8px;
}

.form-subtitle {
  font-size: 14px;
  color: var(--text-muted);
  margin: 0 0 32px;
}

.reset-btn {
  width: 100%;
}

.form-links {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}

.form-link {
  font-size: 13px;
  color: var(--primary);
  text-decoration: none;

  &:hover {
    text-decoration: underline;
  }
}
</style>
