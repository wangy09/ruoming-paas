<template>
  <div class="page-container">
    <div class="search-bar">
      <el-input
        v-model="query.keyword"
        placeholder="搜索"
        clearable
        @keyup.enter="fetchList"
        @clear="fetchList"
      />
      <el-button
        type="primary"
        @click="openDialog()"
        v-permission="'{{ module_name }}:create'"
      >
        新增{{ page_title }}
      </el-button>
    </div>

    <el-table v-loading="loading" :data="items" border stripe>
{% for col in table_columns %}      <el-table-column prop="{{ col.prop }}" label="{{ col.label }}"{{ col.width }} show-overflow-tooltip />
{% endfor %}      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDialog(row)" v-permission="'{{ module_name }}:update'">编辑</el-button>
          <el-button link type="danger" @click="handleDelete(row)" v-permission="'{{ module_name }}:delete'">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      v-model:current-page="query.page"
      v-model:page-size="query.page_size"
      :total="total"
      layout="total, sizes, prev, pager, next"
      style="margin-top: 16px; justify-content: flex-end"
      @current-change="fetchList"
      @size-change="fetchList"
    />

    <FormDialog
      v-model:visible="dialogVisible"
      v-model:model-value="editRow"
      @submit="handleSubmit"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { {{ module_name }}Api, type {{ entity_name }}Info } from '@/api/{{ module_name }}'
import FormDialog from './components/FormDialog.vue'

const loading = ref(false)
const items = ref<{{ entity_name }}Info[]>([])
const total = ref(0)
const dialogVisible = ref(false)
const editRow = ref<{{ entity_name }}Info | null>(null)
const query = reactive({ page: 1, page_size: 10, keyword: '' })

async function fetchList() {
  loading.value = true
  try {
    const res = await {{ module_name }}Api.list(query)
    items.value = res.data?.items ?? []
    total.value = res.data?.total ?? 0
  } finally {
    loading.value = false
  }
}

function openDialog(row?: {{ entity_name }}Info) {
  editRow.value = row ?? null
  dialogVisible.value = true
}

async function handleSubmit(form: Record<string, unknown>) {
  if (editRow.value?.id) {
    await {{ module_name }}Api.update(editRow.value.id, form)
  } else {
    await {{ module_name }}Api.create(form)
  }
  ElMessage.success('保存成功')
  dialogVisible.value = false
  fetchList()
}

async function handleDelete(row: {{ entity_name }}Info) {
  await ElMessageBox.confirm('确定删除该数据？', '提示', { type: 'warning' })
  await {{ module_name }}Api.remove(row.id)
  ElMessage.success('删除成功')
  fetchList()
}

onMounted(fetchList)
</script>

<style lang="scss" scoped>
.search-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
</style>