<template>
  <div class="page-container">
    <el-row :gutter="16" style="height:calc(100vh - 168px)">
      <!-- 左：知识库列表 -->
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

      <!-- 右：文档列表 -->
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
                <el-button :icon="Search" @click="openSearchDialog">检索测试</el-button>
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
                    {{ docStatusLabel[row.status] }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="chunk_count" label="分块数" width="80" align="center" />
              <el-table-column label="上传时间" width="170">
                <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="80" align="center" fixed="right">
                <template #default="{ row }">
                  <el-button link type="danger" @click="deleteDoc(row)">删除</el-button>
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

    <!-- 新建知识库 -->
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

    <!-- 检索测试 -->
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
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Upload, Search, Collection } from '@element-plus/icons-vue'
import { kbApi } from '@/api/ai'
import { formatDate, formatBytes } from '@/utils/format'
import type { KnowledgeBase, KnowledgeDoc } from '@/types'

const statusTagMap: Record<string, string> = { ready: 'success', processing: 'warning', error: 'danger' }
const docStatusTagMap: Record<string, string> = { pending: 'info', processing: 'warning', indexed: 'success', failed: 'danger' }
const docStatusLabel: Record<string, string> = { pending: '待处理', processing: '处理中', indexed: '已索引', failed: '失败' }

// ── 知识库 ────────────────────────────────────────────────────────────────────
const kbList = ref<KnowledgeBase[]>([])
const currentKb = ref<KnowledgeBase | null>(null)

async function fetchKbList() {
  const res = await kbApi.list({ page_size: 100 })
  kbList.value = res.data.items
}

function selectKb(kb: KnowledgeBase) {
  currentKb.value = kb
  fetchDocs()
}

// ── 文档 ──────────────────────────────────────────────────────────────────────
const docLoading = ref(false)
const docList = ref<KnowledgeDoc[]>([])
const docTotal = ref(0)
const docQuery = reactive({ page: 1, page_size: 20 })
const uploading = ref(false)
const fileInput = ref<HTMLInputElement>()

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
  try {
    await kbApi.uploadDoc(currentKb.value.id, file)
    ElMessage.success('上传成功，正在后台处理...')
    fetchDocs()
  } finally {
    uploading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}

async function deleteDoc(row: KnowledgeDoc) {
  if (!currentKb.value) return
  await ElMessageBox.confirm(`确定删除文档「${row.name}」并清除向量？`, '警告', { type: 'warning' })
  await kbApi.deleteDoc(currentKb.value.id, row.id)
  ElMessage.success('删除成功')
  fetchDocs()
}

// ── 新建知识库 ────────────────────────────────────────────────────────────────
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

// ── 检索测试 ──────────────────────────────────────────────────────────────────
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
</style>
