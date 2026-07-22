<template>
  <div>
    <el-empty v-if="files.length === 0" description="请选择数据表并生成预览" />
    <el-tabs v-else v-model="activeFile" tab-position="left" class="file-tabs">
      <el-tab-pane v-for="file in files" :key="file.path" :label="shortPath(file.path)" :name="file.path">
        <div class="code-header">
          <span>{{ file.path }}</span>
          <el-button size="small" type="primary" plain @click="copyCode(file.content)">复制</el-button>
        </div>
        <pre class="code-block"><code>{{ file.content }}</code></pre>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { GeneratedFile } from '@/api/codegen'

defineProps<{
  files: GeneratedFile[]
}>()

const activeFile = ref('')

async function copyCode(content: string) {
  await navigator.clipboard.writeText(content)
  ElMessage.success('已复制')
}

function shortPath(path: string) {
  const parts = path.split('/')
  return parts.slice(-2).join('/')
}
</script>

<style lang="scss" scoped>
.file-tabs {
  height: 100%;

  :deep(.el-tabs__content) {
    height: 100%;
  }
}

.code-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 0 10px;
  font-size: 13px;
  color: $text-secondary;
}

.code-block {
  height: calc(100% - 42px);
  margin: 0;
  padding: 14px;
  overflow: auto;
  border-radius: 8px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 13px;
  line-height: 1.55;
}
</style>
