<template>
  <div class="error-page">
    <div class="error-content">
      <div class="error-code">404</div>
      <div class="error-title">页面不存在</div>
      <div class="error-desc">抱歉，您访问的页面不存在或已被移除</div>
      <el-button type="primary" @click="router.push('/dashboard')">返回工作台</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
const router = useRouter()
</script>

<style lang="scss" scoped>
.error-page {
  display: flex; align-items: center; justify-content: center;
  height: 100vh; background: #f0f2f5;
}
.error-content { text-align: center; }
.error-code { font-size: 100px; font-weight: 900; color: #e8e8e8; line-height: 1; }
.error-title { font-size: 24px; font-weight: 600; color: #303133; margin: 12px 0; }
.error-desc { color: #909399; margin-bottom: 24px; }
</style>
