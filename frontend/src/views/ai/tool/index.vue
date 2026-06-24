<template>
  <div class="page-container">
    <div class="page-card">
      <div class="card-header">
        <div class="header-left">
          <span class="card-title">工具管理</span>
          <el-tag type="info" size="small" style="margin-left:10px">共 {{ toolList.length }} 个</el-tag>
        </div>
        <el-button type="primary" :icon="Plus" v-permission="'ai:tool:create'" @click="openDialog()">新建工具</el-button>
      </div>

      <div v-loading="loading">
        <el-empty v-if="!toolList.length && !loading" description="暂无可用工具" />

        <!-- 内置工具 -->
        <div v-if="builtinTools.length" class="section-title">
          <el-icon><Lock /></el-icon> 内置工具（只读）
        </div>
        <el-row :gutter="16">
          <el-col v-for="tool in builtinTools" :key="tool.tool_id" :xs="24" :sm="12" :md="8">
            <div class="tool-card builtin">
              <div class="tool-card-header">
                <div class="tool-icon builtin-icon">
                  <el-icon :size="22"><component :is="getToolIcon(tool.tool_id)" /></el-icon>
                </div>
                <div class="tool-meta">
                  <div class="tool-name">{{ tool.name }}</div>
                  <el-tag type="info" size="small">内置</el-tag>
                </div>
              </div>
              <div class="tool-desc">{{ tool.description }}</div>
              <div class="tool-id">ID: {{ tool.tool_id }}</div>
            </div>
          </el-col>
        </el-row>

        <!-- 自定义工具 -->
        <div v-if="customTools.length" class="section-title" :style="builtinTools.length ? 'margin-top:24px' : ''">
          <el-icon><Connection /></el-icon> 自定义工具（API 调用）
        </div>
        <el-row :gutter="16">
          <el-col v-for="tool in customTools" :key="tool.tool_id" :xs="24" :sm="12" :md="8">
            <div class="tool-card custom" :class="{ disabled: tool.status === 0 }">
              <div class="tool-card-header">
                <div class="tool-icon custom-icon">
                  <el-icon :size="22"><Connection /></el-icon>
                </div>
                <div class="tool-meta">
                  <div class="tool-name">{{ tool.name }}</div>
                  <el-tag :type="tool.status === 1 ? 'success' : 'info'" size="small">
                    {{ tool.status === 1 ? '启用' : '停用' }}
                  </el-tag>
                </div>
                <div class="tool-actions">
                  <el-button link :icon="Edit" v-permission="'ai:tool:update'" @click="openDialog(tool)" />
                  <el-button link :icon="Delete" type="danger" v-permission="'ai:tool:delete'" @click="handleDelete(tool)" />
                </div>
              </div>
              <div class="tool-desc">{{ tool.description || '暂无描述' }}</div>
              <div class="tool-id" :title="tool.url ?? ''">{{ tool.url ? tool.url : 'ID: ' + tool.tool_id }}</div>
            </div>
          </el-col>
        </el-row>
      </div>

      <div class="tool-tip">
        <el-alert type="info" :closable="false" show-icon>
          <template #title>使用说明</template>
          <template #default>
            在 <strong>Agent 管理</strong> 中编辑 Agent，可在「绑定工具」字段为 Agent 选择工具。自定义工具通过配置的 API URL 进行调用。
          </template>
        </el-alert>
      </div>
    </div>

    <!-- 新建/编辑 自定义工具 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editTool ? '编辑工具' : '新建自定义工具'"
      width="580px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="工具名称" prop="name">
          <el-input v-model="form.name" placeholder="如：天气查询、翻译接口" />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input
            v-model="form.description"
            type="textarea"
            :rows="2"
            placeholder="描述工具的功能，让 Agent 知道何时调用它"
          />
        </el-form-item>
        <el-form-item label="请求 URL" prop="url">
          <el-input v-model="form.url" placeholder="https://api.example.com/v1/action" />
        </el-form-item>
        <el-form-item label="请求方法" prop="method">
          <el-select v-model="form.method" style="width:160px">
            <el-option v-for="m in HTTP_METHODS" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item label="请求头">
          <div class="headers-editor">
            <div v-for="(h, i) in headerRows" :key="i" class="header-row">
              <el-input v-model="h.key" placeholder="Key" style="width:40%" />
              <span class="colon">:</span>
              <el-input v-model="h.value" placeholder="Value" style="width:48%" />
              <el-button link :icon="Delete" type="danger" @click="headerRows.splice(i, 1)" />
            </div>
            <el-button link :icon="Plus" @click="headerRows.push({ key: '', value: '' })">添加请求头</el-button>
          </div>
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">启用</el-radio>
            <el-radio :value="0">停用</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Delete, Edit, Search, Connection, Lock } from '@element-plus/icons-vue'
import { toolApi } from '@/api/ai'
import type { ToolInfo } from '@/types'

const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const toolList = ref<ToolInfo[]>([])
const editTool = ref<ToolInfo | null>(null)

const HTTP_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']

const builtinTools = computed(() => toolList.value.filter(t => !t.tool_type || t.tool_type === 'builtin'))
const customTools = computed(() => toolList.value.filter(t => t.tool_type && t.tool_type !== 'builtin'))

interface HeaderRow { key: string; value: string }
const headerRows = ref<HeaderRow[]>([])

const form = ref({
  name: '',
  description: '',
  url: '',
  method: 'POST',
  status: 1,
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入工具名称', trigger: 'blur' }],
  url: [{ required: true, message: '请输入请求 URL', trigger: 'blur' }],
  method: [{ required: true, message: '请选择请求方法', trigger: 'change' }],
}

const toolIconMap: Record<string, any> = {
  'builtin:web_search': Search,
  'builtin:http_request': Connection,
}

function getToolIcon(toolId: string) {
  return toolIconMap[toolId] || Connection
}

async function fetchTools() {
  loading.value = true
  try {
    const res = await toolApi.list()
    toolList.value = res.data || []
  } finally {
    loading.value = false
  }
}

function openDialog(tool?: ToolInfo) {
  editTool.value = tool ?? null
  if (tool) {
    form.value = {
      name: tool.name,
      description: tool.description,
      url: tool.url ?? '',
      method: tool.method ?? 'POST',
      status: tool.status ?? 1,
    }
    headerRows.value = Object.entries(tool.headers ?? {}).map(([key, value]) => ({ key, value }))
  } else {
    form.value = { name: '', description: '', url: '', method: 'POST', status: 1 }
    headerRows.value = []
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!await formRef.value?.validate().catch(() => false)) return
  submitting.value = true
  try {
    const headers: Record<string, string> = {}
    headerRows.value.forEach(h => { if (h.key) headers[h.key] = h.value })

    if (editTool.value?.db_id) {
      await toolApi.update(editTool.value.db_id, {
        name: form.value.name,
        description: form.value.description,
        url: form.value.url || undefined,
        method: form.value.method,
        headers,
        status: form.value.status,
      })
      ElMessage.success('更新成功')
    } else {
      await toolApi.create({
        name: form.value.name,
        description: form.value.description,
        url: form.value.url,
        method: form.value.method,
        headers,
      })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchTools()
  } finally {
    submitting.value = false
  }
}

async function handleDelete(tool: ToolInfo) {
  if (!tool.db_id) return
  await ElMessageBox.confirm(`确定删除工具「${tool.name}」？已绑定该工具的 Agent 将无法使用它。`, '删除确认', {
    type: 'warning',
    confirmButtonText: '确认删除',
    confirmButtonClass: 'el-button--danger',
  })
  await toolApi.remove(tool.db_id)
  ElMessage.success('删除成功')
  fetchTools()
}

onMounted(fetchTools)
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.card-header {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;
  .header-left { display: flex; align-items: center; }
}
.card-title { font-size: 15px; font-weight: 600; }

.section-title {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; font-weight: 600; color: $text-secondary;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid $border-color;
}

.tool-card {
  border: 1px solid $border-color;
  border-radius: 10px;
  padding: 16px 18px;
  margin-bottom: 16px;
  transition: all .2s;
  background: $bg-white;

  &.builtin { background: #fafafa; }
  &.disabled { opacity: .55; }

  &:not(.builtin):hover {
    border-color: $primary-color;
    box-shadow: 0 4px 12px rgba(22,119,255,.1);
  }

  .tool-card-header {
    display: flex; align-items: center; gap: 10px; margin-bottom: 10px;
  }

  .tool-icon {
    width: 40px; height: 40px; border-radius: 10px;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
    &.builtin-icon { background: rgba(22,119,255,.08); color: #1677ff; }
    &.custom-icon { background: rgba(103,194,58,.1); color: #67c23a; }
  }

  .tool-meta {
    display: flex; flex-direction: column; gap: 4px; flex: 1;
    .tool-name { font-size: 14px; font-weight: 600; color: $text-primary; }
  }

  .tool-actions { display: flex; gap: 2px; margin-left: auto; }

  .tool-desc {
    font-size: 13px; color: $text-regular; line-height: 1.6; margin-bottom: 8px;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
  }

  .tool-id {
    font-size: 11px; color: $text-secondary; font-family: monospace;
    background: $bg-base; padding: 2px 8px; border-radius: 4px; display: inline-block;
  }
}

.tool-tip { margin-top: 24px; }

.headers-editor {
  width: 100%;
  .header-row {
    display: flex; align-items: center; gap: 6px; margin-bottom: 8px;
    .colon { color: $text-secondary; font-weight: bold; }
  }
}
</style>
