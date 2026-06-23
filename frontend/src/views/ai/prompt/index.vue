<template>
  <div class="page-container">
    <div class="page-card">
      <div class="card-header">
        <span class="card-title">Prompt 模板管理</span>
        <el-button type="primary" :icon="Plus" v-permission="'ai:prompt:create'" @click="openDialog()">
          新建模板
        </el-button>
      </div>

      <el-table v-loading="loading" :data="tableData" border stripe>
        <el-table-column prop="name" label="模板名称" min-width="160" />
        <el-table-column prop="category" label="分类" width="120" />
        <el-table-column label="变量" min-width="200">
          <template #default="{ row }">
            <el-tag v-for="v in row.variables" :key="v" size="small" type="info" class="mr-1" v-text="`{{${v}}}`"></el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="statusTagMap[row.status]" size="small">{{ statusLabelMap[row.status] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="current_version" label="版本" width="70" align="center" />
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-button
              v-if="row.status === 0"
              link type="success"
              v-permission="'ai:prompt:publish'"
              @click="handlePublish(row)"
            >发布</el-button>
            <el-button link type="warning" @click="openPreview(row)">预览</el-button>
            <el-button link type="info" @click="openVersions(row)">版本</el-button>
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

    <!-- 新增/编辑 -->
    <el-dialog v-model="dialogVisible" :title="editId ? '编辑模板' : '新建模板'" width="700px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-row :gutter="16">
          <el-col :span="14">
            <el-form-item label="模板名称" prop="name">
              <el-input v-model="form.name" />
            </el-form-item>
          </el-col>
          <el-col :span="10">
            <el-form-item label="分类">
              <el-input v-model="form.category" placeholder="如：客服、翻译、摘要" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="模板内容" prop="content">
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="12"
            placeholder="使用 {{variable}} 定义变量，如：请将以下内容翻译为{{language}}：{{content}}"
            @input="extractVariables"
          />
        </el-form-item>
        <el-form-item label="识别变量">
          <div class="flex gap-2 flex-wrap">
            <el-tag v-for="v in detectedVars" :key="v" type="info" v-text="`{{${v}}}`"></el-tag>
            <span v-if="!detectedVars.length" class="text-gray text-sm">在模板中使用 {{'{'}}{{'{'}}variable{{'}'}}{{'}'}}</span>
          </div>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">保存草稿</el-button>
      </template>
    </el-dialog>

    <!-- 渲染预览 -->
    <el-dialog v-model="previewVisible" title="渲染预览" width="640px" destroy-on-close>
      <div class="preview-vars">
        <div v-for="v in previewTemplate?.variables" :key="v" class="preview-var-item">
          <el-input v-model="previewVars[v]" :placeholder="v" style="flex:1">
            <template #prepend>{{ v }}</template>
          </el-input>
        </div>
      </div>
      <el-button type="primary" class="mt-3" @click="doPreview" :loading="previewing" style="width:100%">
        渲染预览
      </el-button>
      <div v-if="previewResult" class="preview-result mt-3">
        <pre>{{ previewResult }}</pre>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { promptApi } from '@/api/ai'
import { formatDate } from '@/utils/format'
import type { PromptTemplate } from '@/types'

const statusTagMap: Record<number, string> = { 0: 'info', 1: 'success', 2: 'warning' }
const statusLabelMap: Record<number, string> = { 0: '草稿', 1: '已发布', 2: '归档' }

const loading = ref(false)
const tableData = ref<PromptTemplate[]>([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10 })

async function fetchList() {
  loading.value = true
  try {
    const res = await promptApi.list(query)
    tableData.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

async function handlePublish(row: PromptTemplate) {
  await ElMessageBox.confirm(`发布模板「${row.name}」？发布后将生成版本快照。`, '确认', { type: 'info' })
  await promptApi.publish(row.id)
  ElMessage.success('发布成功')
  fetchList()
}

function openVersions(_row: PromptTemplate) {
  ElMessage.info('版本历史功能开发中...')
}

// 编辑
const dialogVisible = ref(false)
const editId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const detectedVars = ref<string[]>([])
const form = reactive({
  name: '', category: '', content: '', description: '', variables: [] as string[],
})
const rules: FormRules = {
  name: [{ required: true, message: '请输入名称' }],
  content: [{ required: true, message: '请输入模板内容' }],
}

function extractVariables() {
  const matches = form.content.match(/\{\{(\w+)\}\}/g) ?? []
  const vars = [...new Set(matches.map(m => m.replace(/\{\{|\}\}/g, '')))]
  detectedVars.value = vars
  form.variables = vars
}

function openDialog(row?: PromptTemplate) {
  editId.value = row?.id ?? null
  Object.assign(form, {
    name: row?.name ?? '', category: row?.category ?? '',
    content: row?.content ?? '', description: row?.description ?? '',
    variables: row?.variables ?? [],
  })
  detectedVars.value = form.variables
  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    if (editId.value) {
      await promptApi.update(editId.value, form)
      ElMessage.success('更新成功')
    } else {
      await promptApi.create(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchList()
  } finally {
    submitting.value = false
  }
}

// 预览
const previewVisible = ref(false)
const previewTemplate = ref<PromptTemplate | null>(null)
const previewVars = ref<Record<string, string>>({})
const previewing = ref(false)
const previewResult = ref('')

function openPreview(row: PromptTemplate) {
  previewTemplate.value = row
  previewVars.value = Object.fromEntries((row.variables || []).map(v => [v, '']))
  previewResult.value = ''
  previewVisible.value = true
}

async function doPreview() {
  if (!previewTemplate.value) return
  previewing.value = true
  try {
    const res = await promptApi.preview(previewTemplate.value.id, previewVars.value)
    previewResult.value = res.data.rendered
  } finally {
    previewing.value = false
  }
}

onMounted(fetchList)
</script>

<style lang="scss" scoped>
.card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.card-title { font-size: 15px; font-weight: 600; }
.mt-4 { margin-top: 16px; }
.mt-3 { margin-top: 12px; }
.mr-1 { margin-right: 4px; }
.flex { display: flex; }
.flex-wrap { flex-wrap: wrap; }
.gap-2 { gap: 8px; }

.preview-vars { display: flex; flex-direction: column; gap: 8px; }
.preview-var-item { display: flex; align-items: center; }

.preview-result {
  background: #f6f6f6;
  border-radius: 6px;
  padding: 12px;
  max-height: 300px;
  overflow: auto;
  pre { font-size: 13px; line-height: 1.6; white-space: pre-wrap; }
}
</style>
