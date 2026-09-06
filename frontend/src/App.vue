<template>
  <router-view />
  <!-- 命令式弹窗宿主（showModal / showConfirmModal） -->
  <ModalHost />
</template>

<script setup>
// App 根组件 — 路由视图承载 + 全局命令式弹窗宿主
import ModalHost from '@/components/common/ModalHost.vue'
</script>

<style lang="scss">
// 全局样式已在 main.js 通过 import './styles/index.scss' 引入
</style>
