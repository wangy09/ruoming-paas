<template>
  <div class="page-container">
    <div class="page-card">
      <div class="card-header">
        <div class="header-left">
          <span class="card-title">Prompt 模板管理</span>
          <el-input
            v-model="query.category"
            placeholder="按分类筛选"
            clearable
            style="width:160px;margin-left:12px"
            @clear="fetchList"
            @keyup.enter="fetchList"
          />
        </div>
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
        <el-table-column label="操作" width="260" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
            <el-button
              v-if="row.status !== 'published'"
              link type="success"
              v-permission="'ai:prompt:publish'"
              @click="handlePublish(row)"
            >发布</el-button>
            <el-button link type="warning" @click="openPreview(row)">预览</el-button>
            <el-button link type="info" v-permission="'ai:prompt:version'" @click="openVersions(row)">版本</el-button>
            <el-button link type="danger" v-permission="'ai:prompt:delete'" @click="handleDelete(row)">删除</el-button>
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

    <!-- 版本历史 -->
    <el-dialog v-model="versionsVisible" :title="`版本历史 — ${currentTemplate?.name}`" width="680px" destroy-on-close>
      <div class="version-toolbar">
        <el-button type="primary" size="small" :icon="Plus" @click="openAddVersion">提交新版本</el-button>
      </div>
      <el-table v-loading="versionsLoading" :data="versionList" border stripe class="mt-3">
        <el-table-column prop="version" label="版本" width="70" align="center" />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_published ? 'success' : 'info'" size="small">
              {{ row.is_published ? '已发布' : '草稿' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="changelog" label="变更说明" min-width="180" show-overflow-tooltip />
        <el-table-column label="时间" width="160">
          <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="previewVersion(row)">预览</el-button>
            <el-button
              v-if="!row.is_published"
              link type="success"
              @click="publishOneVersion(row)"
            >发布</el-button>
            <el-button
              v-if="!row.is_published"
              link type="warning"
              @click="rollbackToVersion(row)"
            >回滚</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 新版本内容预览区 -->
      <el-dialog v-model="versionContentVisible" title="版本内容预览" width="580px" append-to-body destroy-on-close>
        <pre class="version-content-pre">{{ versionContentPreview }}</pre>
      </el-dialog>

      <!-- 提交新版本 -->
      <el-dialog v-model="addVersionVisible" title="提交新版本" width="660px" append-to-body destroy-on-close>
        <el-form ref="addVersionFormRef" :model="addVersionForm" label-width="90px">
          <el-form-item label="版本内容" prop="content" :rules="[{ required: true, message: '请输入内容' }]">
            <el-input
              v-model="addVersionForm.content"
              type="textarea"
              :rows="10"
              placeholder="输入新版本的模板内容..."
              @input="extractAddVersionVars"
            />
          </el-form-item>
          <el-form-item label="变更说明">
            <el-input v-model="addVersionForm.changelog" placeholder="描述本次修改内容..." />
          </el-form-item>
          <el-form-item label="识别变量">
            <div class="flex gap-2 flex-wrap">
              <el-tag v-for="v in addVersionVars" :key="v" type="info" size="small" v-text="`{{${v}}}`" />
              <span v-if="!addVersionVars.length" class="text-gray text-sm">暂未识别到变量</span>
            </div>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="addVersionVisible = false">取消</el-button>
          <el-button type="primary" :loading="addVersionSubmitting" @click="submitNewVersion">提交</el-button>
        </template>
      </el-dialog>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { promptApi } from '@/api/ai'
import { formatDate } from '@/utils/format'
import type { PromptTemplate, PromptVersion } from '@/types'

const statusTagMap: Record<string, string> = { draft: 'info', published: 'success', archived: 'warning' }
const statusLabelMap: Record<string, string> = { draft: '草稿', published: '已发布', archived: '归档' }

const loading = ref(false)
const tableData = ref<PromptTemplate[]>([])
const total = ref(0)
const query = reactive({ page: 1, page_size: 10, category: '' })

async function fetchList() {
  loading.value = true
  try {
    const res = await promptApi.list({ ...query, category: query.category || undefined })
    tableData.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

async function handlePublish(row: PromptTemplate) {
  await ElMessageBox.confirm(`发布模板「${row.name}」v${row.current_version}？`, '确认', { type: 'info' })
  await promptApi.publishVersion(row.id, row.current_version)
  ElMessage.success('发布成功')
  fetchList()
}

async function handleDelete(row: PromptTemplate) {
  await ElMessageBox.confirm(`确定删除模板「${row.name}」？`, '警告', { type: 'warning' })
  await promptApi.delete(row.id)
  ElMessage.success('已删除')
  fetchList()
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

// 渲染预览
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

// 版本管理
const versionsVisible = ref(false)
const versionsLoading = ref(false)
const currentTemplate = ref<PromptTemplate | null>(null)
const versionList = ref<PromptVersion[]>([])
const versionContentVisible = ref(false)
const versionContentPreview = ref('')

async function openVersions(row: PromptTemplate) {
  currentTemplate.value = row
  versionsVisible.value = true
  versionsLoading.value = true
  try {
    const res = await promptApi.versions(row.id)
    versionList.value = res.data
  } finally {
    versionsLoading.value = false
  }
}

function previewVersion(row: PromptVersion) {
  versionContentPreview.value = row.content
  versionContentVisible.value = true
}

async function publishOneVersion(row: PromptVersion) {
  if (!currentTemplate.value) return
  await ElMessageBox.confirm(`发布版本 v${row.version}？`, '确认', { type: 'info' })
  await promptApi.publishVersion(currentTemplate.value.id, row.version)
  ElMessage.success('发布成功')
  // 刷新版本列表和模板列表
  const res = await promptApi.versions(currentTemplate.value.id)
  versionList.value = res.data
  fetchList()
}

async function rollbackToVersion(row: PromptVersion) {
  if (!currentTemplate.value) return
  await ElMessageBox.confirm(`回滚到版本 v${row.version}？当前内容将被覆盖。`, '确认', { type: 'warning' })
  await promptApi.rollbackVersion(currentTemplate.value.id, row.version)
  ElMessage.success('已回滚')
  versionsVisible.value = false
  fetchList()
}

// 提交新版本
const addVersionVisible = ref(false)
const addVersionSubmitting = ref(false)
const addVersionFormRef = ref<FormInstance>()
const addVersionVars = ref<string[]>([])
const addVersionForm = reactive({ content: '', changelog: '', variables: [] as string[] })

function openAddVersion() {
  Object.assign(addVersionForm, { content: currentTemplate.value?.content ?? '', changelog: '', variables: [] })
  addVersionVars.value = currentTemplate.value?.variables ?? []
  addVersionVisible.value = true
}

function extractAddVersionVars() {
  const matches = addVersionForm.content.match(/\{\{(\w+)\}\}/g) ?? []
  const vars = [...new Set(matches.map(m => m.replace(/\{\{|\}\}/g, '')))]
  addVersionVars.value = vars
  addVersionForm.variables = vars
}

async function submitNewVersion() {
  if (!currentTemplate.value) return
  await addVersionFormRef.value?.validate()
  addVersionSubmitting.value = true
  try {
    await promptApi.addVersion(currentTemplate.value.id, {
      content: addVersionForm.content,
      variables: addVersionForm.variables,
      changelog: addVersionForm.changelog,
    })
    ElMessage.success('新版本已提交')
    addVersionVisible.value = false
    const res = await promptApi.versions(currentTemplate.value.id)
    versionList.value = res.data
    fetchList()
  } finally {
    addVersionSubmitting.value = false
  }
}

onMounted(fetchList)
</script>

<style lang="scss" scoped>
.card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.header-left { display: flex; align-items: center; }
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

.version-toolbar { display: flex; justify-content: flex-end; }
.version-content-pre { font-size: 13px; line-height: 1.6; white-space: pre-wrap; background: #f6f6f6; border-radius: 6px; padding: 12px; max-height: 400px; overflow: auto; }
</style>
