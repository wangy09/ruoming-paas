<template>
  <div class="page-container file-center-page">
    <el-card class="filter-card" shadow="never">
      <div class="toolbar">
        <div class="filters">
          <el-input
            v-model="query.keyword"
            placeholder="搜索文件名 / 备注"
            clearable
            class="filter-input"
            @keyup.enter="reload"
            @clear="reload"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-select v-model="query.status" placeholder="状态" clearable class="filter-select" @change="reload">
            <el-option label="正常" :value="1" />
            <el-option label="已归档" :value="2" />
          </el-select>
          <el-input v-model="query.biz_type" placeholder="业务类型" clearable class="filter-select" @keyup.enter="reload" @clear="reload" />
          <el-input v-model="query.category" placeholder="分类" clearable class="filter-select" @keyup.enter="reload" @clear="reload" />
          <el-button :icon="Search" type="primary" @click="reload">查询</el-button>
          <el-button :icon="Refresh" @click="resetQuery">重置</el-button>
        </div>
        <div class="actions">
          <el-tag v-if="storageConfig" type="info" effect="plain">
            {{ storageConfig.backend }} / {{ storageConfig.max_upload_size_mb }}MB
          </el-tag>
          <el-button type="primary" :icon="Upload" v-permission="'system:file:upload'" @click="openUpload">
            上传文件
          </el-button>
        </div>
      </div>
    </el-card>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="files" border stripe>
        <el-table-column label="文件名" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="file-name-cell">
              <el-icon class="file-icon"><Document /></el-icon>
              <div>
                <div class="file-name">{{ row.original_name }}</div>
                <div class="file-meta">{{ row.mime_type || '-' }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="100">
          <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column label="存储" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.storage_backend }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="biz_type" label="业务类型" width="130" show-overflow-tooltip />
        <el-table-column prop="category" label="分类" width="120" show-overflow-tooltip />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'warning'" size="small">
              {{ row.status === 1 ? '正常' : '已归档' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="下载" width="80" align="center" prop="download_count" />
        <el-table-column label="上传时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="260" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" v-permission="'system:file:preview'" @click="handlePreview(row)">预览</el-button>
            <el-button link type="primary" v-permission="'system:file:download'" @click="handleDownload(row)">下载</el-button>
            <el-button link type="primary" v-permission="'system:file:update'" @click="openEdit(row)">编辑</el-button>
            <el-button
              v-if="row.status === 1"
              link
              type="warning"
              v-permission="'system:file:archive'"
              @click="handleArchive(row)"
            >
              归档
            </el-button>
            <el-button
              v-else
              link
              type="success"
              v-permission="'system:file:archive'"
              @click="handleRestore(row)"
            >
              恢复
            </el-button>
            <el-button link type="danger" v-permission="'system:file:delete'" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @current-change="reload"
        @size-change="reload"
      />
    </el-card>

    <el-dialog v-model="uploadVisible" title="上传文件" width="560px">
      <el-form label-width="90px">
        <el-form-item label="选择文件" required>
          <el-upload
            ref="uploadRef"
            drag
            :auto-upload="false"
            :limit="1"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽文件到这里，或 <em>点击选择</em></div>
            <template #tip>
              <div class="el-upload__tip">
                最大 {{ storageConfig?.max_upload_size_mb || 50 }}MB；支持 {{ storageConfig?.allowed_extensions.join(', ') }}
              </div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item label="业务类型">
          <el-input v-model="uploadForm.biz_type" placeholder="例如 contract / order / user" />
        </el-form-item>
        <el-form-item label="业务ID">
          <el-input v-model="uploadForm.biz_id" placeholder="业务数据 ID，可选" />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="uploadForm.category" placeholder="例如 附件 / 合同 / 发票" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="uploadForm.remark" type="textarea" :rows="3" maxlength="255" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitUpload">上传</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="编辑文件信息" width="520px">
      <el-form label-width="90px">
        <el-form-item label="业务类型">
          <el-input v-model="editForm.biz_type" />
        </el-form-item>
        <el-form-item label="业务ID">
          <el-input v-model="editForm.biz_id" />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="editForm.category" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.remark" type="textarea" :rows="3" maxlength="255" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="previewVisible"
      :title="previewTitle"
      width="820px"
      class="file-preview-dialog"
      :fullscreen="previewFullscreen"
      @closed="clearPreview"
    >
      <div v-loading="previewLoading" class="preview-body" :class="{ fullscreen: previewFullscreen }">
        <img v-if="previewKind === 'image'" :src="previewUrl" class="preview-image" />
        <iframe v-else-if="previewKind === 'iframe'" :src="previewUrl" class="preview-frame" />
        <pre v-else-if="previewKind === 'text'" class="preview-text">{{ previewText }}</pre>
        <el-empty v-else description="该文件类型暂不支持在线预览，请下载后查看" />
      </div>
      <template #footer>
        <el-button @click="previewFullscreen = !previewFullscreen">
          {{ previewFullscreen ? '退出全屏' : '全屏预览' }}
        </el-button>
        <el-button @click="previewVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type UploadFile, type UploadInstance } from 'element-plus'
import { Document, Refresh, Search, Upload, UploadFilled } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import { fileApi } from '@/api/file'
import type { FileInfo, StorageConfigInfo } from '@/types'

const loading = ref(false)
const uploading = ref(false)
const saving = ref(false)
const previewLoading = ref(false)
const files = ref<FileInfo[]>([])
const storageConfig = ref<StorageConfigInfo | null>(null)
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)

const query = reactive({
  keyword: '',
  status: undefined as number | undefined,
  biz_type: '',
  category: '',
})

const uploadVisible = ref(false)
const uploadRef = ref<UploadInstance>()
const selectedFile = ref<File | null>(null)
const uploadForm = reactive({
  biz_type: '',
  biz_id: '',
  category: '',
  remark: '',
})

const editVisible = ref(false)
const currentFile = ref<FileInfo | null>(null)
const editForm = reactive({
  biz_type: '',
  biz_id: '',
  category: '',
  remark: '',
})

const previewVisible = ref(false)
const previewTitle = ref('')
const previewUrl = ref('')
const previewText = ref('')
const previewKind = ref<'image' | 'iframe' | 'text' | 'unsupported'>('unsupported')
const previewFullscreen = ref(false)

async function reload() {
  loading.value = true
  try {
    const res = await fileApi.list({
      page: page.value,
      page_size: pageSize.value,
      keyword: query.keyword || undefined,
      status: query.status,
      biz_type: query.biz_type || undefined,
      category: query.category || undefined,
    })
    files.value = res.data?.items ?? []
    total.value = res.data?.total ?? 0
  } finally {
    loading.value = false
  }
}

async function fetchStorageConfig() {
  const res = await fileApi.config()
  storageConfig.value = res.data
}

function resetQuery() {
  query.keyword = ''
  query.status = undefined
  query.biz_type = ''
  query.category = ''
  page.value = 1
  reload()
}

function openUpload() {
  selectedFile.value = null
  Object.assign(uploadForm, { biz_type: '', biz_id: '', category: '', remark: '' })
  uploadRef.value?.clearFiles()
  uploadVisible.value = true
}

function handleFileChange(uploadFile: UploadFile) {
  selectedFile.value = uploadFile.raw ?? null
}

function handleFileRemove() {
  selectedFile.value = null
}

async function submitUpload() {
  if (!selectedFile.value) {
    ElMessage.warning('请选择文件')
    return
  }
  uploading.value = true
  try {
    await fileApi.upload({ file: selectedFile.value, ...uploadForm })
    ElMessage.success('上传成功')
    uploadVisible.value = false
    reload()
  } finally {
    uploading.value = false
  }
}

function openEdit(row: any) {
  currentFile.value = row
  Object.assign(editForm, {
    biz_type: row.biz_type || '',
    biz_id: row.biz_id || '',
    category: row.category || '',
    remark: row.remark || '',
  })
  editVisible.value = true
}

async function submitEdit() {
  if (!currentFile.value) return
  saving.value = true
  try {
    await fileApi.update(currentFile.value.id, editForm)
    ElMessage.success('保存成功')
    editVisible.value = false
    reload()
  } finally {
    saving.value = false
  }
}

async function handlePreview(row: any) {
  previewTitle.value = row.original_name
  previewVisible.value = true
  previewLoading.value = true
  previewKind.value = resolvePreviewKind(row)
  previewText.value = ''
  try {
    if (previewKind.value === 'unsupported') return
    const blob = await fileApi.previewBlob(row.id)
    previewUrl.value = URL.createObjectURL(blob)
    if (previewKind.value === 'text') {
      previewText.value = await blob.text()
    }
  } catch (error) {
    previewKind.value = 'unsupported'
    ElMessage.error(`预览失败：${getErrorMessage(error)}`)
  } finally {
    previewLoading.value = false
  }
}

async function handleDownload(row: any) {
  const blob = await fileApi.downloadBlob(row.id)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = row.original_name
  link.click()
  URL.revokeObjectURL(url)
  reload()
}

async function handleArchive(row: any) {
  const { value } = await ElMessageBox.prompt(`请输入「${row.original_name}」的归档原因`, '归档文件', {
    inputType: 'textarea',
    confirmButtonText: '归档',
    cancelButtonText: '取消',
  })
  await fileApi.archive(row.id, value)
  ElMessage.success('归档成功')
  reload()
}

async function handleRestore(row: any) {
  await fileApi.restore(row.id)
  ElMessage.success('恢复成功')
  reload()
}

async function handleDelete(row: any) {
  await ElMessageBox.confirm(`确定删除文件记录「${row.original_name}」？物理文件会保留在存储中。`, '提示', { type: 'warning' })
  await fileApi.remove(row.id)
  ElMessage.success('删除成功')
  reload()
}

function resolvePreviewKind(row: FileInfo) {
  const mime = row.mime_type || ''
  if (mime.startsWith('image/')) return 'image'
  if (mime.startsWith('text/') || ['application/json', 'application/xml'].includes(mime)) return 'text'
  if (mime === 'application/pdf' || mime.startsWith('audio/') || mime.startsWith('video/')) return 'iframe'
  return 'unsupported'
}

function clearPreview() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
  }
  previewUrl.value = ''
  previewText.value = ''
  previewKind.value = 'unsupported'
  previewFullscreen.value = false
}

function formatSize(size: number) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`
  return `${(size / 1024 / 1024 / 1024).toFixed(1)} GB`
}

function formatTime(value?: string | null) {
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '-'
}

function getErrorMessage(error: unknown) {
  if (error instanceof Error) return error.message
  if (typeof error === 'string') return error
  return '请查看接口错误详情'
}

onMounted(() => {
  fetchStorageConfig()
  reload()
})
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.file-center-page {
  .filter-card {
    margin-bottom: 16px;
  }
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.filters,
.actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.filter-input {
  width: 240px;
}

.filter-select {
  width: 140px;
}

.file-name-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.file-icon {
  color: var(--el-color-primary);
  font-size: 22px;
}

.file-name {
  font-weight: 500;
  color: $text-primary;
}

.file-meta {
  margin-top: 2px;
  color: $text-secondary;
  font-size: 12px;
}

.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}

.preview-body {
  min-height: 360px;

  &.fullscreen {
    min-height: calc(100vh - 150px);

    .preview-image {
      max-height: calc(100vh - 170px);
    }

    .preview-frame,
    .preview-text {
      height: calc(100vh - 170px);
      max-height: calc(100vh - 170px);
    }
  }
}

.preview-image {
  display: block;
  max-width: 100%;
  max-height: 620px;
  margin: 0 auto;
}

.preview-frame {
  width: 100%;
  height: 620px;
  border: 1px solid $border-color;
  border-radius: 6px;
}

.preview-text {
  max-height: 620px;
  overflow: auto;
  padding: 14px;
  border: 1px solid $border-color;
  border-radius: 6px;
  background: $bg-base;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
