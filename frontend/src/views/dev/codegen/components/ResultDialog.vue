<template>
  <el-dialog :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)" title="生成结果" width="760px">
    <el-alert
      title="后端会做路径安全校验。当前 Docker 开发环境只挂载 backend，frontend 文件可能显示为路径不可用。"
      type="info"
      show-icon
      :closable="false"
      class="result-tip"
    />
    <el-table :data="writeResults" border stripe max-height="420">
      <el-table-column prop="path" label="文件路径" min-width="320" show-overflow-tooltip />
      <el-table-column prop="status" label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)">
            {{ statusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="message" label="说明" min-width="220" show-overflow-tooltip />
    </el-table>
    <template #footer>
      <el-button type="primary" @click="emit('update:modelValue', false)">知道了</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import type { GeneratedWriteResult } from '@/api/codegen'

defineProps<{
  modelValue: boolean
  writeResults: GeneratedWriteResult[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

function statusTagType(status: GeneratedWriteResult['status']) {
  const map = {
    created: 'success',
    overwritten: 'warning',
    skipped: 'info',
    unavailable: 'danger',
    error: 'danger',
  } as const
  return map[status] || 'info'
}

function statusText(status: GeneratedWriteResult['status']) {
  const map = {
    created: '已创建',
    overwritten: '已覆盖',
    skipped: '已跳过',
    unavailable: '路径不可用',
    error: '失败',
  }
  return map[status] || status
}
</script>

<style lang="scss" scoped>
.result-tip {
  margin-bottom: 12px;
}
</style>
