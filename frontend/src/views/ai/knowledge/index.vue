<template>
  <div class="page-container">
    <el-row :gutter="16" style="height:calc(100vh - 168px)">
      <el-col :span="7" style="height:100%">
        <div class="page-card h-full flex flex-col">
          <div class="card-header">
            <span class="card-title">知识库</span>
            <el-button type="primary" size="small" :icon="Plus" v-permission="'ai:kb:create'" @click="openKbDialog()">
              新建
            </el-button>
          </div>
          <el-scrollbar flex-1>
            <div
              v-for="kb in kbList"
              :key="kb.id"
              class="kb-item"
              :class="{ active: currentKb?.id === kb.id }"
              @click="selectKb(kb)"
            >
              <div class="kb-item-title">
                <el-icon><Collection /></el-icon>
                {{ kb.name }}
              </div>
              <div class="kb-item-meta">
                {{ kb.doc_count }} 个文档 · {{ kb.chunk_count }} 个分块
                <el-tag
                  :type="statusTagMap[kb.status]"
                  size="small"
                  style="margin-left:6px"
                >{{ kb.status }}</el-tag>
              </div>
            </div>
          </el-scrollbar>
        </div>
      </el-col>

      <el-col :span="17" style="height:100%">
        <div class="page-card h-full flex flex-col">
          <div v-if="!currentKb" class="empty-state">
            <el-empty description="选择知识库查看文档" />
          </div>

          <template v-else>
            <div class="card-header">
              <span class="card-title">{{ currentKb.name }} — 文档列表</span>
              <div class="flex gap-2">
                <el-button
                  type="primary"
                  :icon="Upload"
                  v-permission="'ai:kb:upload'"
                  @click="triggerUpload"
                  :loading="uploading"
                >
                  上传文档
                </el-button>
                <input ref="fileInput" type="file" accept=".txt,.md,.pdf,.docx,.html" hidden @change="handleUpload" />
                <div v-if="uploading" class="w-full mt-2">
                  <div class="flex justify-between text-xs text-gray-500 mb-1">
                    <span>{{ uploadFileName }}</span>
                    <span>{{ uploadProgress }}%</span>
                  </div>
                  <el-progress :percentage="uploadProgress" :stroke-width="6" status="success" />
                </div>
                <el-button :icon="Search" @click="openSearchDialog">检索测试</el-button>
                <el-button
                  :icon="Refresh"
                  @click="reindexAll"
                  :loading="reindexing"
                  v-permission="'ai:kb:upload'"
                >
                  重新索引全部
                </el-button>
              </div>
            </div>

            <el-table v-loading="docLoading" :data="docList" border stripe style="flex:1">
              <el-table-column prop="name" label="文件名" min-width="200" show-overflow-tooltip />
              <el-table-column prop="file_type" label="类型" width="80" align="center" />
              <el-table-column label="大小" width="90" align="right">
                <template #default="{ row }">{{ formatBytes(row.file_size) }}</template>
              </el-table-column>
              <el-table-column label="状态" width="110" align="center">
                <template #default="{ row }">
                  <el-tag :type="docStatusTagMap[row.status]" size="small">
                    <span v-if="row.status === 'processing'" class="flex items-center gap-1">
                      <el-icon :size="12"><Loading /></el-icon>
                      {{ docStatusLabel[row.status] }}
                    </span>
                    <template v-else>{{ docStatusLabel[row.status] }}</template>
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="chunk_count" label="分块数" width="80" align="center" />
              <el-table-column label="上传时间" width="170">
                <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="140" align="center" fixed="right">
                <template #default="{ row }">
                  <el-button
                    link
                    type="primary"
                    size="small"
                    v-if="row.status === 'error'"
                    @click="reindexOne(row)"
                  >重试</el-button>
                  <el-button
                    link
                    type="primary"
                    size="small"
                    v-if="row.status === 'done'"
                    @click="reindexOne(row)"
                  >重新索引</el-button>
                  <el-button link type="danger" size="small" @click="deleteDoc(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>

            <el-pagination
              class="mt-3"
              v-model:current-page="docQuery.page"
              :total="docTotal"
              layout="total, prev, pager, next"
              @change="fetchDocs"
            />
          </template>
        </div>
      </el-col>
    </el-row>

    <el-dialog v-model="kbDialogVisible" title="新建知识库" width="480px" destroy-on-close>
      <el-form ref="kbFormRef" :model="kbForm" :rules="kbRules" label-width="100px">
        <el-form-item label="知识库名称" prop="name">
          <el-input v-model="kbForm.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="kbForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="分块大小">
          <el-input-number v-model="kbForm.chunk_size" :min="128" :max="4096" :step="128" />
          <span class="text-gray text-sm ml-2">字符数</span>
        </el-form-item>
        <el-form-item label="分块重叠">
          <el-input-number v-model="kbForm.chunk_overlap" :min="0" :max="512" :step="32" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="kbDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="kbSubmitting" @click="createKb">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="searchDialogVisible" title="检索测试" width="640px" destroy-on-close>
      <el-input v-model="searchQuery" placeholder="输入检索关键词..." :prefix-icon="Search">
        <template #append>
          <el-button type="primary" @click="doSearch" :loading="searching">检索</el-button>
        </template>
      </el-input>
      <div class="search-results mt-3">
        <div v-for="(item, i) in searchResults" :key="i" class="search-result-item">
          <div class="result-score">相关度 {{ (item.score * 100).toFixed(1) }}%</div>
          <div class="result-content">{{ item.content }}</div>
        </div>
        <el-empty v-if="!searchResults.length && !searching" description="暂无结果" />
      </div>
    </el-dialog>

    <el-dialog v-model="progressDialogVisible" title="重新索引进度" width="500px" :close-on-click-modal="false" destroy-on-close>
      <div v-if="taskStatus" class="progress-content">
        <div class="progress-row">
          <span class="progress-label">当前状态</span>
          <el-tag :type="taskStatusTagMap[taskStatus.status]">{{ taskStatusLabel[taskStatus.status] }}</el-tag>
        </div>
        <div class="progress-row">
          <span class="progress-label">进度</span>
          <span>{{ taskStatus.completed }} / {{ taskStatus.total }}</span>
        </div>
        <el-progress :percentage="taskStatus.progress" :stroke-width="12" :status="taskStatus.status === 'completed' ? 'success' : taskStatus.status === 'failed' ? 'exception' : ''" />
        <div v-if="taskStatus.current_doc" class="progress-row">
          <span class="progress-label">正在处理</span>
          <span class="current-doc">{{ taskStatus.current_doc }}</span>
        </div>
        <div v-if="taskStatus.result" class="progress-result">
          <div class="result-row">
            <span class="result-label">成功</span>
            <span class="result-value success">{{ taskStatus.result.success || 0 }}</span>
          </div>
          <div class="result-row">
            <span class="result-label">失败</span>
            <span class="result-value failed">{{ taskStatus.result.failed || 0 }}</span>
          </div>
          <div v-if="taskStatus.result.failed_docs && taskStatus.result.failed_docs.length > 0" class="failed-docs">
            <div class="result-label">失败文档</div>
            <div v-for="doc in taskStatus.result.failed_docs.slice(0, 5)" :key="doc.doc_id" class="failed-doc-item">
              <span>{{ doc.name }}</span>
              <span class="failed-reason">{{ doc.error }}</span>
            </div>
          </div>
        </div>
        <div v-if="taskStatus.error_msg" class="error-msg">
          {{ taskStatus.error_msg }}
        </div>
      </div>
      <template #footer>
        <el-button @click="closeProgress">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Upload, Search, Collection, Refresh, Loading } from '@element-plus/icons-vue'
import { kbApi } from '@/api/ai'
import { formatDate, formatBytes } from '@/utils/format'
import type { KnowledgeBase, KnowledgeDoc } from '@/types'

const statusTagMap: Record<string, string> = { ready: 'success', processing: 'warning', error: 'danger' }
const docStatusTagMap: Record<string, string> = { pending: 'info', processing: 'warning', done: 'success', error: 'danger' }
const docStatusLabel: Record<string, string> = { pending: '待处理', processing: '处理中', done: '已完成', error: '失败' }
const taskStatusTagMap: Record<string, string> = { pending: 'info', running: 'warning', completed: 'success', failed: 'danger' }
const taskStatusLabel: Record<string, string> = { pending: '待执行', running: '执行中', completed: '已完成', failed: '失败' }

const kbList = ref<KnowledgeBase[]>([])
const currentKb = ref<KnowledgeBase | null>(null)

async function fetchKbList() {
  const res = await kbApi.list({ page_size: 100 })
  kbList.value = res.data.items
}

function selectKb(kb: KnowledgeBase) {
  currentKb.value = kb
  fetchDocs()
  startStatusPolling()
}

const docLoading = ref(false)
const docList = ref<KnowledgeDoc[]>([])
const docTotal = ref(0)
const docQuery = reactive({ page: 1, page_size: 20 })
const uploading = ref(false)
const fileInput = ref<HTMLInputElement>()
const uploadProgress = ref(0)
const uploadFileName = ref('')
const reindexing = ref(false)
const progressDialogVisible = ref(false)
const taskStatus = ref<any>(null)
let taskStatusTimer: ReturnType<typeof setInterval> | null = null

let pollTimer: ReturnType<typeof setInterval> | null = null

function startStatusPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(() => {
    if (currentKb.value && hasProcessingDocs()) {
      fetchDocs()
    }
  }, 3000)
}

function hasProcessingDocs() {
  return docList.value.some(d => d.status === 'processing')
}

function stopStatusPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function fetchDocs() {
  if (!currentKb.value) return
  docLoading.value = true
  try {
    const res = await kbApi.docs(currentKb.value.id, docQuery)
    docList.value = res.data.items
    docTotal.value = res.data.total
  } finally {
    docLoading.value = false
  }
}

function triggerUpload() {
  fileInput.value?.click()
}

async function handleUpload(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file || !currentKb.value) return
  
  uploading.value = true
  uploadFileName.value = file.name
  uploadProgress.value = 0
  
  try {
    if (file.size <= CHUNK_SIZE) {
      await kbApi.uploadDoc(currentKb.value.id, file)
      ElMessage.success('上传成功，正在后台处理...')
    } else {
      await uploadLargeFile(currentKb.value.id, file)
    }
    await fetchDocs()
    startStatusPolling()
  } finally {
    uploading.value = false
    uploadProgress.value = 0
    uploadFileName.value = ''
    if (fileInput.value) fileInput.value.value = ''
  }
}

const CHUNK_SIZE = 5 * 1024 * 1024

async function calculateHash(file: File): Promise<string> {
  const chunkCount = Math.ceil(file.size / CHUNK_SIZE)
  const hashes: string[] = []
  
  for (let i = 0; i < chunkCount; i++) {
    const start = i * CHUNK_SIZE
    const end = Math.min(start + CHUNK_SIZE, file.size)
    const chunk = file.slice(start, end)
    const buffer = await chunk.arrayBuffer()
    const hashBuffer = await crypto.subtle.digest('SHA-256', buffer)
    const hashArray = Array.from(new Uint8Array(hashBuffer))
    hashes.push(hashArray.map(b => b.toString(16).padStart(2, '0')).join(''))
  }
  
  const combined = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(hashes.join('')))
  return Array.from(new Uint8Array(combined)).map(b => b.toString(16).padStart(2, '0')).join('')
}

async function uploadLargeFile(kbId: number, file: File) {
  uploadProgress.value = 5
  const fileHash = await calculateHash(file)
  
  const chunkCount = Math.ceil(file.size / CHUNK_SIZE)
  const initRes = await kbApi.uploadInit(kbId, {
    filename: file.name,
    file_size: file.size,
    file_hash: fileHash,
    part_count: chunkCount,
  })
  
  const uploadId = initRes.data.upload_id
  const uploadedParts = new Set(initRes.data.uploaded_parts)
  const partHashes: string[] = []
  
  for (let i = 0; i < chunkCount; i++) {
    const partNumber = i + 1
    
    if (uploadedParts.has(partNumber)) {
      partHashes.push('')
      uploadProgress.value = 10 + ((i + 1) / chunkCount) * 80
      continue
    }
    
    const start = i * CHUNK_SIZE
    const end = Math.min(start + CHUNK_SIZE, file.size)
    const chunk = file.slice(start, end)
    
    const hashBuffer = await crypto.subtle.digest('SHA-256', await chunk.arrayBuffer())
    const partHash = Array.from(new Uint8Array(hashBuffer)).map(b => b.toString(16).padStart(2, '0')).join('')
    partHashes.push(partHash)
    
    await kbApi.uploadPart(kbId, {
      upload_id: uploadId,
      part_number: partNumber,
      part_hash: partHash,
      file: chunk,
    })
    
    uploadProgress.value = 10 + ((i + 1) / chunkCount) * 80
  }
  
  uploadProgress.value = 95
  await kbApi.uploadComplete(kbId, {
    upload_id: uploadId,
    part_hashes: partHashes,
  })
  
  uploadProgress.value = 100
  ElMessage.success('上传成功，正在后台处理...')
}

async function deleteDoc(row: KnowledgeDoc) {
  if (!currentKb.value) return
  await ElMessageBox.confirm(`确定删除文档「${row.name}」并清除向量？`, '警告', { type: 'warning' })
  await kbApi.deleteDoc(currentKb.value.id, row.id)
  ElMessage.success('删除成功')
  fetchDocs()
}

async function reindexOne(row: KnowledgeDoc) {
  if (!currentKb.value) return
  await ElMessageBox.confirm(`确定重新索引文档「${row.name}」？`, '确认', { type: 'info' })
  try {
    const res = await kbApi.reindexDoc(currentKb.value.id, row.id)
    ElMessage.success('重新索引任务已提交')
    if (res.data.task_id) {
      await openProgressDialog(res.data.task_id)
    }
    fetchDocs()
    startStatusPolling()
  } catch {
    ElMessage.error('重新索引失败')
  }
}

async function reindexAll() {
  if (!currentKb.value) return
  await ElMessageBox.confirm(`确定重新索引知识库「${currentKb.value.name}」中的所有文档？`, '确认', { type: 'info' })
  reindexing.value = true
  try {
    const res = await kbApi.reindexAll(currentKb.value.id)
    reindexing.value = false
    ElMessage.success('重新索引任务已提交')
    if (res.data.task_id) {
      await openProgressDialog(res.data.task_id)
    }
    fetchDocs()
    startStatusPolling()
  } catch {
    reindexing.value = false
    ElMessage.error('重新索引失败')
  }
}

async function openProgressDialog(taskId: string) {
  progressDialogVisible.value = true
  taskStatus.value = null
  
  if (taskStatusTimer) clearInterval(taskStatusTimer)
  
  async function pollTaskStatus() {
    if (!currentKb.value) return
    try {
      const res = await kbApi.getTaskStatus(currentKb.value.id, taskId)
      taskStatus.value = res.data
      
      if (taskStatus.value.status === 'completed' || taskStatus.value.status === 'failed') {
        if (taskStatusTimer) {
          clearInterval(taskStatusTimer)
          taskStatusTimer = null
        }
        fetchDocs()
      }
    } catch {
      if (taskStatusTimer) {
        clearInterval(taskStatusTimer)
        taskStatusTimer = null
      }
    }
  }
  
  await pollTaskStatus()
  taskStatusTimer = setInterval(pollTaskStatus, 2000)
}

function closeProgress() {
  progressDialogVisible.value = false
  if (taskStatusTimer) {
    clearInterval(taskStatusTimer)
    taskStatusTimer = null
  }
}

const kbDialogVisible = ref(false)
const kbSubmitting = ref(false)
const kbFormRef = ref<FormInstance>()
const kbForm = reactive({ name: '', description: '', chunk_size: 512, chunk_overlap: 64 })
const kbRules: FormRules = { name: [{ required: true, message: '请输入知识库名称' }] }

function openKbDialog() { kbDialogVisible.value = true }

async function createKb() {
  await kbFormRef.value?.validate()
  kbSubmitting.value = true
  try {
    await kbApi.create(kbForm)
    ElMessage.success('创建成功')
    kbDialogVisible.value = false
    fetchKbList()
  } finally {
    kbSubmitting.value = false
  }
}

const searchDialogVisible = ref(false)
const searchQuery = ref('')
const searchResults = ref<Array<{ content: string; score: number }>>([])
const searching = ref(false)

function openSearchDialog() { searchDialogVisible.value = true; searchResults.value = [] }

async function doSearch() {
  if (!currentKb.value || !searchQuery.value.trim()) return
  searching.value = true
  try {
    const res = await kbApi.search(currentKb.value.id, searchQuery.value)
    searchResults.value = res.data
  } finally {
    searching.value = false
  }
}

onMounted(fetchKbList)
onUnmounted(() => {
  stopStatusPolling()
  closeProgress()
})
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.h-full { height: 100%; overflow: hidden; }
.flex { display: flex; }
.flex-col { flex-direction: column; }
.flex-1 { flex: 1; overflow: hidden; }
.gap-2 { gap: 8px; }
.mt-3 { margin-top: 12px; }
.mt-4 { margin-top: 16px; }
.ml-2 { margin-left: 8px; }
.card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; flex-shrink: 0; }
.card-title { font-size: 15px; font-weight: 600; }

.empty-state { display: flex; align-items: center; justify-content: center; flex: 1; }

.kb-item {
  padding: 12px 14px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 6px;
  transition: all .15s;

  &:hover { background: #f0f7ff; }
  &.active { background: #e6f4ff; border: 1px solid #91caff; }

  .kb-item-title {
    display: flex; align-items: center; gap: 6px;
    font-size: 14px; font-weight: 500; color: $text-primary;
    margin-bottom: 4px;
  }
  .kb-item-meta { font-size: 12px; color: $text-secondary; }
}

.search-results { max-height: 400px; overflow: auto; }
.search-result-item {
  padding: 12px;
  border: 1px solid $border-color;
  border-radius: 6px;
  margin-bottom: 8px;

  .result-score { font-size: 12px; color: $primary-color; font-weight: 600; margin-bottom: 6px; }
  .result-content { font-size: 13px; color: $text-regular; line-height: 1.6; }
}

.progress-content { padding: 8px 0; }
.progress-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.progress-label { font-size: 13px; color: $text-secondary; }
.current-doc { font-size: 13px; color: $primary-color; font-weight: 500; }
.progress-result { margin-top: 16px; padding-top: 16px; border-top: 1px solid $border-color; }
.result-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.result-label { font-size: 13px; color: $text-secondary; }
.result-value { font-size: 13px; font-weight: 600; }
.result-value.success { color: #67c23a; }
.result-value.failed { color: #f56c6c; }
.failed-docs { margin-top: 8px; }
.failed-doc-item { display: flex; flex-direction: column; padding: 6px 10px; background: #fef0f0; border-radius: 4px; margin-bottom: 4px; font-size: 12px; }
.failed-reason { color: #f56c6c; font-size: 11px; margin-top: 2px; }
.error-msg { margin-top: 12px; padding: 10px; background: #fef0f0; border-radius: 4px; font-size: 12px; color: #f56c6c; }
</style>