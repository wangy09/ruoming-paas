<template>
  <div class="page-container">
    <div class="page-card">
      <div class="card-header">
        <span class="card-title">模型管理</span>
        <el-button type="primary" :icon="Plus" v-permission="'ai:model:create'" @click="openDialog()">
          接入模型
        </el-button>
      </div>

      <!-- 类型筛选 -->
      <el-radio-group v-model="filterType" class="mb-3" @change="fetchList">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="chat">对话</el-radio-button>
        <el-radio-button value="embedding">向量</el-radio-button>
        <el-radio-button value="rerank">Rerank</el-radio-button>
      </el-radio-group>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="name" label="模型名称" min-width="160" />
        <el-table-column prop="provider" label="供应商" width="120" />
        <el-table-column prop="model_id" label="模型标识" min-width="200" show-overflow-tooltip />
        <el-table-column label="类型" width="90" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_embed" size="small">向量</el-tag>
            <el-tag v-else-if="row.is_rerank" size="small">Rerank</el-tag>
            <el-tag v-else size="small">对话</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="默认" width="70" align="center">
          <template #default="{ row }">
            <el-icon v-if="row.is_default" color="#52c41a"><Check /></el-icon>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-switch :model-value="row.status === 1" @change="toggleStatus(row)" />
          </template>
        </el-table-column>
        <el-table-column label="上下文窗口" width="120" align="right">
          <template #default="{ row }">{{ row.context_length?.toLocaleString() }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="testConnect(row)" :loading="testingId === row.id">
              连通测试
            </el-button>
            <el-button link type="primary" v-permission="'ai:model:update'" @click="openDialog(row)">编辑</el-button>
            <el-button link type="danger" v-permission="'ai:model:delete'" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        class="mt-4"
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :total="total"
        layout="total, sizes, prev, pager, next"
        @change="fetchList"
      />
    </div>

    <!-- 新增/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="editId ? '编辑模型' : '接入模型'" width="580px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px" autocomplete="off">
        <el-form-item label="供应商" prop="provider">
          <el-select
            v-model="form.provider"
            style="width:100%"
            filterable
            allow-create
            placeholder="选择或输入供应商标识"
            @change="onProviderChange"
          >
            <el-option-group label="国内">
              <el-option label="追鹿（Zhuilu）" value="zhuilu" />
              <el-option label="阿里云通义（Qwen）" value="qwen" />
              <el-option label="豆包（Doubao）" value="doubao" />
              <el-option label="DeepSeek" value="deepseek" />
              <el-option label="智谱 GLM（Zhipu）" value="zhipu" />
              <el-option label="月之暗面（Moonshot）" value="moonshot" />
              <el-option label="MiniMax" value="minimax" />
              <el-option label="百度千帆（Baidu）" value="baidu" />
            </el-option-group>
            <el-option-group label="国际">
              <el-option label="OpenAI" value="openai" />
              <el-option label="Azure OpenAI" value="azure" />
            </el-option-group>
            <el-option-group label="本地部署">
              <el-option label="Ollama（本地）" value="ollama" />
            </el-option-group>
          </el-select>
        </el-form-item>
        <el-form-item label="模型用途">
          <el-checkbox v-model="form.is_embed">向量嵌入</el-checkbox>
          <el-checkbox v-model="form.is_rerank">Rerank</el-checkbox>
          <span class="text-gray text-sm ml-2">（都不选则为对话模型）</span>
        </el-form-item>
        <el-form-item label="显示名称" prop="name">
          <el-input v-model="form.name" placeholder="自定义显示名称" />
        </el-form-item>
        <el-form-item label="模型标识" prop="model_id">
          <el-input v-model="form.model_id" placeholder="如：gpt-4o / qwen-max" />
        </el-form-item>
        <el-form-item label="API Base URL">
          <el-input v-model="form.base_url" :placeholder="baseUrlPlaceholder" name="base_url" autocomplete="off" />
        </el-form-item>
        <el-form-item label="API Key">
          <template #label>
            API Key
            <el-tag v-if="editId && rowHasApiKey" type="success" size="small" class="ml-2">已配置</el-tag>
          </template>
          <el-input
            v-model="form.api_key"
            type="password"
            show-password
            :placeholder="editId ? '留空则保持原配置' : '请输入 API Key'"
            name="api_key"
            autocomplete="new-password"
          />
          <div v-if="editId && rowHasApiKey" class="text-gray text-xs mt-1">已配置 API Key，如需修改请填写新值</div>
        </el-form-item>
        <el-form-item label="上下文窗口">
          <el-input-number v-model="form.context_length" :min="512" :max="131072" :step="512" />
        </el-form-item>
        <el-form-item label="Max Tokens">
          <el-input-number v-model="form.max_tokens" :min="128" :max="131072" :step="256" />
        </el-form-item>
        <el-form-item label="状态">
          <el-radio-group v-model="form.status">
            <el-radio :value="1">启用</el-radio>
            <el-radio :value="0">禁用</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="form.is_default" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Check } from '@element-plus/icons-vue'
import { modelApi } from '@/api/ai'
import type { AiModelConfig } from '@/types'

const loading = ref(false)
const tableData = ref<AiModelConfig[]>([])
const total = ref(0)
const filterType = ref('')
const testingId = ref<number | null>(null)

const query = reactive({ page: 1, page_size: 10, model_type: '' })

async function fetchList() {
  loading.value = true
  try {
    const res = await modelApi.list({ ...query, model_type: filterType.value || undefined })
    tableData.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

async function toggleStatus(row: AiModelConfig) {
  await modelApi.update(row.id, { status: row.status === 1 ? 0 : 1 })
}

async function testConnect(row: AiModelConfig) {
  testingId.value = row.id
  try {
    const res = await modelApi.test(row.id)
    ElMessage.success(`连通成功，延迟 ${res.data.latency_ms}ms`)
  } catch {
    ElMessage.error('连通失败，请检查配置')
  } finally {
    testingId.value = null
  }
}

async function handleDelete(row: AiModelConfig) {
  await ElMessageBox.confirm(`确定删除模型「${row.name}」？`, '警告', { type: 'warning' })
  await modelApi.delete(row.id)
  ElMessage.success('已删除')
  fetchList()
}

// 表单
const dialogVisible = ref(false)
const editId = ref<number | null>(null)
const submitting = ref(false)
const rowHasApiKey = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  provider: 'zhuilu',
  is_embed: false,
  is_rerank: false,
  name: '',
  model_id: '',
  base_url: '',
  api_key: '',
  context_length: 8192,
  max_tokens: 4096,
  status: 1,
  is_default: false,
})
const rules: FormRules = {
  provider: [{ required: true }],
  name: [{ required: true, message: '请输入显示名称' }],
  model_id: [{ required: true, message: '请输入模型标识' }],
}

// 内置厂商预设（base_url + 默认 model_id）
const VENDOR_PRESETS: Record<string, { url: string; model: string }> = {
  zhuilu:   { url: 'https://api.zhuilu.ai/v1',                                      model: 'qwen-max' },
  openai:   { url: 'https://api.openai.com/v1',                                     model: 'gpt-4o' },
  azure:    { url: 'https://<resource>.openai.azure.com/openai/deployments/<deploy>', model: 'gpt-4o' },
  ollama:   { url: 'http://localhost:11434',                                          model: 'llama3' },
  qwen:     { url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',              model: 'qwen-max' },
  doubao:   { url: 'https://ark.cn-beijing.volces.com/api/v3',                       model: 'ep-xxxxxxxx' },
  deepseek: { url: 'https://api.deepseek.com/v1',                                   model: 'deepseek-chat' },
  zhipu:    { url: 'https://open.bigmodel.cn/api/paas/v4',                           model: 'glm-4' },
  moonshot: { url: 'https://api.moonshot.cn/v1',                                    model: 'moonshot-v1-8k' },
  minimax:  { url: 'https://api.minimax.chat/v1',                                   model: 'abab6.5s-chat' },
  baidu:    { url: 'https://qianfan.baidubce.com/v2',                               model: 'ernie-4.0-8k' },
}

const baseUrlPlaceholder = computed(() => VENDOR_PRESETS[form.provider]?.url || 'https://your-api.example.com/v1')

function onProviderChange(val: string) {
  const preset = VENDOR_PRESETS[val]
  if (preset) {
    // 只在用户未手动填写时才回填预设值
    if (!form.base_url) form.base_url = preset.url
    if (!form.model_id) form.model_id = preset.model
  }
}

function openDialog(row?: AiModelConfig) {
  editId.value = row?.id ?? null
  rowHasApiKey.value = row?.has_api_key ?? false
  Object.assign(form, {
    provider: row?.provider ?? 'zhuilu',
    is_embed: row?.is_embed ?? false,
    is_rerank: row?.is_rerank ?? false,
    name: row?.name ?? '',
    model_id: row?.model_id ?? '',
    base_url: row?.base_url ?? '',
    api_key: '',
    context_length: row?.context_length ?? 8192,
    max_tokens: row?.max_tokens ?? 4096,
    status: row?.status ?? 1,
    is_default: row?.is_default ?? false,
  })
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    if (editId.value) {
      await modelApi.update(editId.value, form)
      ElMessage.success('更新成功')
    } else {
      await modelApi.create(form)
      ElMessage.success('接入成功')
    }
    dialogVisible.value = false
    fetchList()
  } finally {
    submitting.value = false
  }
}

onMounted(fetchList)
</script>

<style lang="scss" scoped>
.card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.card-title { font-size: 15px; font-weight: 600; }
.mb-3 { margin-bottom: 12px; }
.mt-4 { margin-top: 16px; }
.text-gray { color: #909399; }
.text-sm { font-size: 12px; }
.ml-2 { margin-left: 8px; }
</style>
