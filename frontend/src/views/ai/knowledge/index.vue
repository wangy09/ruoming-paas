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
                  <div class="kb-item-header">
                <div class="kb-item-title">
                  <el-icon><Collection /></el-icon>
                  {{ kb.name }}
                </div>
                <div class="kb-item-actions" @click.stop>
                  <el-dropdown trigger="click" @command="cmd => handleKbCommand(cmd, kb)">
                    <el-icon class="kb-more"><MoreFilled /></el-icon>
                    <template #dropdown>
                      <el-dropdown-menu>
                        <el-dropdown-item v-if="permStore.hasPermission('ai:kb:update')" command="edit">编辑</el-dropdown-item>
                        <el-dropdown-item v-if="permStore.hasPermission('ai:kb:delete')" command="delete" divided>删除</el-dropdown-item>
                      </el-dropdown-menu>
                    </template>
                  </el-dropdown>
                </div>
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
                <el-dropdown v-permission="'ai:kb:upload'" @command="handleSourceCommand">
                  <el-button :icon="Plus">
                    添加来源<el-icon class="el-icon--right"><ArrowDown /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="url">
                        <el-icon><Link /></el-icon> URL 抓取
                      </el-dropdown-item>
                      <el-dropdown-item command="api">
                        <el-icon><Connection /></el-icon> API 接口
                      </el-dropdown-item>
                      <el-dropdown-item command="database">
                        <el-icon><Grid /></el-icon> 数据库查询
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
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
              <el-table-column prop="name" label="名称" min-width="180" show-overflow-tooltip />
              <el-table-column label="来源" width="100" align="center">
                <template #default="{ row }">
                  <el-tag :type="sourceTagType[row.source_type]" size="small">
                    {{ sourceLabel[row.source_type] || row.source_type }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="file_type" label="类型" width="70" align="center" />
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
                  <el-button link type="danger" size="small" v-permission="'ai:kb:doc:delete'" @click="deleteDoc(row)">删除</el-button>
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

    <el-dialog v-model="kbDialogVisible" :title="kbEditId ? '编辑知识库' : '新建知识库'" width="520px" destroy-on-close>
      <el-form ref="kbFormRef" :model="kbForm" :rules="kbRules" label-width="110px">
        <el-form-item label="知识库名称" prop="name">
          <el-input v-model="kbForm.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="kbForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="向量模型">
          <el-select v-model="kbForm.embed_model_id" placeholder="使用默认向量模型" clearable style="width:100%">
            <el-option
              v-for="m in embedModels"
              :key="m.id"
              :label="`${m.name}（${m.provider}）`"
              :value="m.id"
            />
          </el-select>
          <div class="form-hint">不选则使用系统默认向量模型</div>
        </el-form-item>
        <el-form-item label="排序模型">
          <el-select v-model="kbForm.rerank_model_id" placeholder="不使用重排序" clearable style="width:100%">
            <el-option
              v-for="m in rerankModels"
              :key="m.id"
              :label="`${m.name}（${m.provider}）`"
              :value="m.id"
            />
          </el-select>
          <div class="form-hint">混合检索时对候选结果重排序，提升精度（可选）</div>
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
        <el-button type="primary" :loading="kbSubmitting" @click="submitKb">确定</el-button>
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

    <!-- URL 抓取弹窗 -->
    <el-dialog v-model="urlDialogVisible" title="添加 URL 抓取来源" width="560px" destroy-on-close>
      <el-form ref="urlFormRef" :model="urlForm" :rules="urlRules" label-width="110px">
        <el-form-item label="URL 列表" prop="urls">
          <div style="width:100%">
            <div v-for="(u, i) in urlForm.urlList" :key="i" class="url-row">
              <el-input v-model="urlForm.urlList[i]" placeholder="https://example.com/article" style="flex:1" />
              <el-button link type="danger" :icon="Delete" @click="urlForm.urlList.splice(i, 1)" v-if="urlForm.urlList.length > 1" />
            </div>
            <el-button link :icon="Plus" @click="urlForm.urlList.push('')" :disabled="urlForm.urlList.length >= 20">
              添加 URL（最多 20 条）
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="文档名称">
          <el-input v-model="urlForm.name" placeholder="留空则使用页面标题" />
        </el-form-item>
        <el-form-item label="CSS 选择器">
          <el-input v-model="urlForm.css_selector" placeholder="可选，如 article.main-content" />
          <div class="form-hint">指定 CSS 选择器可精准提取正文，留空自动识别</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="urlDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="sourceSubmitting" @click="submitUrlSource">开始抓取</el-button>
      </template>
    </el-dialog>

    <!-- API/数据库来源弹窗 -->
    <el-dialog v-model="apiDialogVisible" :title="apiForm.source_type === 'database' ? '添加数据库来源' : '添加 API 接口来源'" width="600px" destroy-on-close>
      <el-form ref="apiFormRef" :model="apiForm" :rules="apiRules" label-width="110px">
        <el-form-item label="来源名称" prop="name">
          <el-input v-model="apiForm.name" placeholder="如：产品文档 API" />
        </el-form-item>

        <!-- API 类型 -->
        <template v-if="apiForm.source_type === 'api'">
          <el-form-item label="请求 URL" prop="url">
            <el-input v-model="apiForm.url" placeholder="https://api.example.com/docs" />
          </el-form-item>
          <el-form-item label="请求方法">
            <el-select v-model="apiForm.method" style="width:140px">
              <el-option v-for="m in ['GET','POST','PUT']" :key="m" :label="m" :value="m" />
            </el-select>
          </el-form-item>
          <el-form-item label="请求头">
            <div class="headers-editor">
              <div v-for="(h, i) in apiHeaderRows" :key="i" class="header-row">
                <el-input v-model="h.key" placeholder="Key" style="width:40%" />
                <span class="colon">:</span>
                <el-input v-model="h.value" placeholder="Value" style="width:48%" />
                <el-button link :icon="Delete" type="danger" @click="apiHeaderRows.splice(i, 1)" />
              </div>
              <el-button link :icon="Plus" @click="apiHeaderRows.push({ key: '', value: '' })">添加请求头</el-button>
            </div>
          </el-form-item>
          <el-form-item label="请求体">
            <el-input v-model="apiForm.body" type="textarea" :rows="3" placeholder='{"key":"value"}（POST 时使用）' />
          </el-form-item>
          <el-form-item label="JSONPath">
            <el-input v-model="apiForm.json_path" placeholder="如 $.data.content（留空使用完整响应）" />
            <div class="form-hint">从 JSON 响应中提取指定字段作为文档内容</div>
          </el-form-item>
        </template>

        <!-- 数据库类型 -->
        <template v-if="apiForm.source_type === 'database'">
          <el-form-item label="连接串" prop="db_url">
            <el-input v-model="apiForm.db_url" placeholder="postgresql://user:pass@host:5432/db" />
            <div class="form-hint">支持 PostgreSQL、MySQL（需服务端安装对应驱动）</div>
          </el-form-item>
          <el-form-item label="查询 SQL" prop="sql">
            <el-input v-model="apiForm.sql" type="textarea" :rows="4" placeholder="SELECT title, content FROM articles WHERE status=1" />
            <div class="form-hint">查询结果按列拼接为文本后写入知识库</div>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="apiDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="sourceSubmitting" @click="submitApiSource">提交</el-button>
      </template>
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
import { Plus, Upload, Search, Collection, Refresh, Loading, MoreFilled, Delete, Link, Connection, Grid, ArrowDown } from '@element-plus/icons-vue'
import { kbApi, modelApi } from '@/api/ai'
import { formatDate, formatBytes } from '@/utils/format'
import { usePermissionStore } from '@/store/permission'
import type { KnowledgeBase, KnowledgeDoc, AiModelConfig } from '@/types'

const permStore = usePermissionStore()

const sourceLabel: Record<string, string> = { file: '文件', url: 'URL', text: '文本', api: 'API', database: '数据库' }
const sourceTagType: Record<string, string> = { file: '', url: 'success', text: 'info', api: 'warning', database: 'danger' }

const statusTagMap: Record<string, string> = { ready: 'success', processing: 'warning', error: 'danger' }
const docStatusTagMap: Record<string, string> = { pending: 'info', processing: 'warning', done: 'success', error: 'danger' }
const docStatusLabel: Record<string, string> = { pending: '待处理', processing: '处理中', done: '已完成', error: '失败' }
const taskStatusTagMap: Record<string, string> = { pending: 'info', running: 'warning', completed: 'success', failed: 'danger' }
const taskStatusLabel: Record<string, string> = { pending: '待执行', running: '执行中', completed: '已完成', failed: '失败' }

const kbList = ref<KnowledgeBase[]>([])
const currentKb = ref<KnowledgeBase | null>(null)
const embedModels = ref<AiModelConfig[]>([])
const rerankModels = ref<AiModelConfig[]>([])

async function fetchKbList() {
  const res = await kbApi.list({ page_size: 100 })
  kbList.value = res.data.items
}

async function fetchEmbedModels() {
  const res = await modelApi.list({ model_type: 'embed', page_size: 200 })
  embedModels.value = res.data.items
}

async function fetchRerankModels() {
  const res = await modelApi.list({ model_type: 'rerank', page_size: 200 })
  rerankModels.value = res.data.items
}

function selectKb(kb: KnowledgeBase) {
  currentKb.value = kb
  fetchDocs()
  startStatusPolling()
}

function handleKbCommand(cmd: string, kb: KnowledgeBase) {
  if (cmd === 'edit') openKbDialog(kb)
  if (cmd === 'delete') deleteKb(kb)
}

async function deleteKb(kb: KnowledgeBase) {
  await ElMessageBox.confirm(`确定删除知识库「${kb.name}」及其所有文档和向量数据？此操作不可恢复！`, '警告', { type: 'warning' })
  await kbApi.delete(kb.id)
  ElMessage.success('已删除')
  if (currentKb.value?.id === kb.id) {
    currentKb.value = null
    docList.value = []
  }
  fetchKbList()
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
const kbEditId = ref<number | null>(null)
const kbSubmitting = ref(false)
const kbFormRef = ref<FormInstance>()
const kbForm = reactive<{
  name: string; description: string; chunk_size: number; chunk_overlap: number; embed_model_id: number | undefined; rerank_model_id: number | undefined
}>({ name: '', description: '', chunk_size: 512, chunk_overlap: 64, embed_model_id: undefined, rerank_model_id: undefined })
const kbRules: FormRules = { name: [{ required: true, message: '请输入知识库名称' }] }

function openKbDialog(kb?: KnowledgeBase) {
  kbEditId.value = kb?.id ?? null
  Object.assign(kbForm, {
    name: kb?.name ?? '',
    description: kb?.description ?? '',
    chunk_size: kb?.chunk_size ?? 512,
    chunk_overlap: kb?.chunk_overlap ?? 64,
    embed_model_id: kb?.embed_model_id ?? undefined,
    rerank_model_id: kb?.rerank_model_id ?? undefined,
  })
  kbDialogVisible.value = true
}

async function submitKb() {
  await kbFormRef.value?.validate()
  kbSubmitting.value = true
  try {
    if (kbEditId.value) {
      await kbApi.update(kbEditId.value, kbForm)
      ElMessage.success('更新成功')
      // 同步更新当前选中的KB信息
      if (currentKb.value?.id === kbEditId.value) {
        Object.assign(currentKb.value, kbForm)
      }
    } else {
      await kbApi.create(kbForm)
      ElMessage.success('创建成功')
    }
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

// ── URL 抓取来源 ──────────────────────────────────────────────────────────────
const urlDialogVisible = ref(false)
const urlFormRef = ref<FormInstance>()
const sourceSubmitting = ref(false)
const urlForm = reactive({ urlList: [''], name: '', css_selector: '' })
const urlRules: FormRules = {
  urls: [{ required: true, message: '请至少填写一个 URL' }],
}

// ── API/数据库来源 ────────────────────────────────────────────────────────────
const apiDialogVisible = ref(false)
const apiFormRef = ref<FormInstance>()

interface HeaderRow { key: string; value: string }
const apiHeaderRows = ref<HeaderRow[]>([])

const apiForm = reactive({
  source_type: 'api' as 'api' | 'database',
  name: '',
  url: '',
  method: 'GET',
  body: '',
  json_path: '',
  db_url: '',
  sql: '',
})

const apiRules: FormRules = {
  name: [{ required: true, message: '请填写来源名称', trigger: 'blur' }],
  url: [{ required: true, message: '请填写 API URL', trigger: 'blur' }],
  db_url: [{ required: true, message: '请填写数据库连接串', trigger: 'blur' }],
  sql: [{ required: true, message: '请填写查询 SQL', trigger: 'blur' }],
}

function handleSourceCommand(cmd: 'url' | 'api' | 'database') {
  if (cmd === 'url') {
    Object.assign(urlForm, { urlList: [''], name: '', css_selector: '' })
    urlDialogVisible.value = true
  } else {
    Object.assign(apiForm, { source_type: cmd, name: '', url: '', method: 'GET', body: '', json_path: '', db_url: '', sql: '' })
    apiHeaderRows.value = []
    apiDialogVisible.value = true
  }
}

async function submitUrlSource() {
  const urls = urlForm.urlList.map(u => u.trim()).filter(Boolean)
  if (!urls.length) { ElMessage.warning('请至少填写一个有效 URL'); return }
  if (!currentKb.value) return
  sourceSubmitting.value = true
  try {
    await kbApi.addUrlSource(currentKb.value.id, {
      urls,
      name: urlForm.name || undefined,
      css_selector: urlForm.css_selector || undefined,
    })
    ElMessage.success(`已提交 ${urls.length} 个 URL 抓取任务，正在后台处理...`)
    urlDialogVisible.value = false
    fetchDocs()
    startStatusPolling()
  } finally {
    sourceSubmitting.value = false
  }
}

async function submitApiSource() {
  if (!await apiFormRef.value?.validate().catch(() => false)) return
  if (!currentKb.value) return
  sourceSubmitting.value = true
  try {
    const headers: Record<string, string> = {}
    apiHeaderRows.value.forEach(h => { if (h.key) headers[h.key] = h.value })
    await kbApi.addApiSource(currentKb.value.id, {
      name: apiForm.name,
      source_type: apiForm.source_type,
      url: apiForm.url || undefined,
      method: apiForm.method,
      headers,
      body: apiForm.body || undefined,
      json_path: apiForm.json_path || undefined,
      db_url: apiForm.db_url || undefined,
      sql: apiForm.sql || undefined,
    })
    ElMessage.success('已提交来源任务，正在后台处理...')
    apiDialogVisible.value = false
    fetchDocs()
    startStatusPolling()
  } finally {
    sourceSubmitting.value = false
  }
}

onMounted(() => {
  fetchKbList()
  fetchEmbedModels()
  fetchRerankModels()
})
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
  padding: 10px 14px;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 6px;
  transition: all .15s;

  &:hover { background: #f0f7ff; }
  &.active { background: #e6f4ff; border: 1px solid #91caff; }

  .kb-item-header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 4px;
  }
  .kb-item-title {
    display: flex; align-items: center; gap: 6px;
    font-size: 14px; font-weight: 500; color: $text-primary;
  }
  .kb-item-actions {
    opacity: 0; transition: opacity .15s;
    .kb-more { font-size: 16px; color: $text-secondary; cursor: pointer; padding: 2px 4px;
      &:hover { color: $primary-color; }
    }
  }
  &:hover .kb-item-actions { opacity: 1; }
  .kb-item-meta { font-size: 12px; color: $text-secondary; }
}

.form-hint { font-size: 11px; color: $text-secondary; margin-top: 4px; }

.url-row {
  display: flex; align-items: center; gap: 6px; margin-bottom: 8px;
}

.headers-editor {
  width: 100%;
  .header-row {
    display: flex; align-items: center; gap: 6px; margin-bottom: 8px;
    .colon { color: $text-secondary; font-weight: bold; }
  }
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