<template>
  <el-dialog :model-value="modelValue" @update:model-value="$emit('update:modelValue', $event)" title="配置变更历史" width="820px">
    <div class="history-title">
      <span>{{ configKey }}</span>
      <el-button :icon="Refresh" :loading="loading" @click="$emit('refresh')">刷新</el-button>
    </div>
    <el-table v-loading="loading" :data="rows" border stripe>
      <el-table-column label="变更时间" width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ formatChangedAt(row.changed_at) }}</template>
      </el-table-column>
      <el-table-column prop="old_value" label="旧值" min-width="180" show-overflow-tooltip />
      <el-table-column prop="new_value" label="新值" min-width="180" show-overflow-tooltip />
      <el-table-column label="操作人" width="130" align="center" show-overflow-tooltip>
        <template #default="{ row }">{{ row.changed_by_name || row.changed_by || '-' }}</template>
      </el-table-column>
    </el-table>
    <el-pagination
      :current-page="page"
      :page-size="pageSize"
      :total="total"
      :page-sizes="[10, 20, 50]"
      layout="total, sizes, prev, pager, next"
      class="pagination"
      @current-change="$emit('page-change')"
      @size-change="$emit('page-size-change')"
    />
  </el-dialog>
</template>

<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import type { ConfigHistoryInfo } from '@/types'

defineProps<{
  modelValue: boolean
  configKey: string
  loading: boolean
  rows: ConfigHistoryInfo[]
  total: number
  page: number
  pageSize: number
}>()

defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'refresh'): void
  (e: 'page-change'): void
  (e: 'page-size-change'): void
}>()

function formatChangedAt(date: string | Date | undefined) {
  if (!date) return '-'
  return new Date(date).toLocaleString('zh-CN')
}
</script>

<style lang="scss" scoped>
.history-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
</style>
