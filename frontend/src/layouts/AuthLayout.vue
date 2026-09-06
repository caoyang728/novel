<template>
  <div class="auth-layout">
    <!-- 左侧品牌区 -->
    <div class="auth-brand">
      <div class="auth-brand-content">
        <div class="brand-glow" />
        <h1 class="brand-title">Novel Agent</h1>
        <p class="brand-subtitle">AI 驱动的小说创作助手</p>
        <div class="brand-features">
          <div class="brand-feature">
            <el-icon><EditPen /></el-icon>
            <span>智能大纲生成</span>
          </div>
          <div class="brand-feature">
            <el-icon><ChatDotRound /></el-icon>
            <span>对话式创作</span>
          </div>
          <div class="brand-feature">
            <el-icon><DataAnalysis /></el-icon>
            <span>世界观管理</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧表单区 -->
    <div class="auth-form-area">
      <div class="auth-form-card glass-panel">
        <router-view />
      </div>
    </div>
  </div>
</template>

<script setup>
import { EditPen, ChatDotRound, DataAnalysis } from '@element-plus/icons-vue'
</script>

<style lang="scss" scoped>
.auth-layout {
  display: flex;
  min-height: 100vh;
}

// 左侧品牌区
.auth-brand {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  padding: 48px;
}

.auth-brand-content {
  position: relative;
  z-index: 1;
  text-align: center;
}

.brand-glow {
  position: absolute;
  width: 300px;
  height: 300px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(129, 140, 248, 0.3), transparent 70%);
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 0;
  filter: blur(60px);
}

.brand-title {
  font-size: 42px;
  font-weight: 800;
  background: linear-gradient(135deg, #818cf8, #c084fc);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin: 0 0 12px;
  position: relative;
  z-index: 1;
}

.brand-subtitle {
  font-size: 18px;
  color: var(--text-secondary);
  margin: 0 0 40px;
  position: relative;
  z-index: 1;
}

.brand-features {
  display: flex;
  flex-direction: column;
  gap: 16px;
  position: relative;
  z-index: 1;
}

.brand-feature {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--text-regular);
  font-size: 15px;
  justify-content: center;

  .el-icon {
    font-size: 20px;
    color: var(--primary);
  }
}

// 右侧表单区
.auth-form-area {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
}

.auth-form-card {
  width: 100%;
  max-width: 420px;
  padding: 40px;
}

// 响应式：窄屏单栏
@media (max-width: 768px) {
  .auth-layout {
    flex-direction: column;
  }

  .auth-brand {
    padding: 32px 24px;
    min-height: auto;
  }

  .brand-title {
    font-size: 28px;
  }

  .brand-subtitle {
    font-size: 15px;
    margin-bottom: 24px;
  }

  .brand-features {
    display: none;
  }

  .auth-form-area {
    padding: 24px;
  }

  .auth-form-card {
    padding: 24px;
  }
}
</style>
