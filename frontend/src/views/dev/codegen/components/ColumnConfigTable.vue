<template>
  <el-table v-loading="loading" :data="columnConfigs" border stripe height="360" row-key="column_name">
    <el-table-column prop="column_name" label="字段名" min-width="150" fixed />
    <el-table-column prop="column_comment" label="注释" min-width="160" show-overflow-tooltip />
    <el-table-column prop="data_type" label="数据库类型" min-width="130" />
    <el-table-column prop="python_type" label="Python" width="100" />
    <el-table-column prop="ts_type" label="TypeScript" width="150" />
    <el-table-column label="列表显示" width="90">
      <template #default="{ row }">
        <el-switch v-model="row.is_list" />
      </template>
    </el-table-column>
    <el-table-column label="表单编辑" width="90">
      <template #default="{ row }">
        <el-switch v-model="row.is_form" />
      </template>
    </el-table-column>
    <el-table-column label="搜索条件" width="90">
      <template #default="{ row }">
        <el-switch v-model="(row as CodegenColumn & ColumnConfig).is_search" :disabled="!isSearchable(row as CodegenColumn & ColumnConfig)" />
      </template>
    </el-table-column>
    <el-table-column label="必填" width="80">
      <template #default="{ row }">
        <el-switch v-model="row.is_required" />
      </template>
    </el-table-column>
    <el-table-column prop="form_component" label="表单组件" width="110">
      <template #default="{ row }">
        <el-select v-model="row.form_component" style="width: 100%">
          <el-option label="输入框" value="input" />
          <el-option label="数字框" value="number" />
          <el-option label="文本域" value="textarea" />
          <el-option label="开关" value="switch" />
          <el-option label="日期时间" value="datetime" />
        </el-select>
      </template>
    </el-table-column>
    <el-table-column prop="is_nullable" label="可空" width="80">
      <template #default="{ row }">
        <el-tag :type="row.is_nullable ? 'info' : 'success'" size="small">
          {{ row.is_nullable ? '是' : '否' }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="is_primary_key" label="主键" width="80">
      <template #default="{ row }">
        <el-tag v-if="row.is_primary_key" type="warning" size="small">是</el-tag>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import type { CodegenColumn, ColumnConfig } from '@/api/codegen'

defineProps<{
  loading: boolean
  columnConfigs: (CodegenColumn & ColumnConfig)[]
}>()

function isSearchable(row: CodegenColumn & ColumnConfig) {
  return row.python_type === 'str' || row.data_type === 'text'
}
</script>
