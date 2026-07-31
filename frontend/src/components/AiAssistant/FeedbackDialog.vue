<template>
  <el-dialog
    v-model="dialogVisible"
    title="问题反馈"
    width="520px"
    :close-on-click-modal="false"
    append-to-body
  >
    <el-form
      ref="formRef"
      :model="formData"
      :rules="formRules"
      label-position="top"
    >
      <!-- 反馈标题 -->
      <el-form-item label="反馈标题" prop="title">
        <el-input
          v-model="formData.title"
          placeholder="简要描述您反馈的问题（5-200字）"
          maxlength="200"
          show-word-limit
        />
      </el-form-item>

      <!-- 反馈分类 -->
      <el-form-item label="反馈分类" prop="category">
        <el-radio-group v-model="formData.category">
          <el-radio value="bug">🐛 Bug 报告</el-radio>
          <el-radio value="feature">💡 功能建议</el-radio>
          <el-radio value="usage">❓ 使用问题</el-radio>
          <el-radio value="other">📝 其他</el-radio>
        </el-radio-group>
      </el-form-item>

      <!-- 严重程度（可选，Bug 时建议选择） -->
      <el-form-item v-if="formData.category === 'bug'" label="严重程度">
        <el-select
          v-model="formData.severity"
          placeholder="请选择严重程度（可选）"
          clearable
          style="width: 100%"
        >
          <el-option value="low" label="🟢 轻微 - 不影响使用" />
          <el-option value="medium" label="🟡 一般 - 影响部分功能" />
          <el-option value="high" label="🟠 严重 - 影响主要功能" />
          <el-option value="critical" label="🔴 致命 - 系统不可用" />
        </el-select>
      </el-form-item>

      <!-- 详细内容 -->
      <el-form-item label="详细描述" prop="content">
        <el-input
          v-model="formData.content"
          type="textarea"
          :rows="5"
          :maxlength="5000"
          show-word-limit
          resize="none"
          placeholder="请详细描述您遇到的问题、期望的功能或使用上的疑问（10-5000字）"
        />
      </el-form-item>

      <!-- 标签（可选） -->
      <el-form-item label="标签" v-if="tagOptions.length > 0">
        <div class="tags-wrapper">
          <el-check-tag
            v-for="tag in tagOptions"
            :key="tag"
            :checked="formData.tags?.includes(tag)"
            @change="toggleTag(tag)"
          >
            {{ tag }}
          </el-check-tag>
        </div>
      </el-form-item>

      <!-- 关联信息（可选） -->
      <el-form-item v-if="messageId" label="关联 AI 消息">
        <div class="related-info">
          <el-tag type="info">消息 ID: {{ messageId }}</el-tag>
          <span class="info-tip">此反馈将关联到您刚才与 AI 的对话</span>
        </div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleConfirm">
        提交反馈
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { feedbackApi } from '@/api/ai'
import type { FeedbackInfo } from '@/types'

const props = defineProps<{
  /** 弹窗显隐，支持 v-model:visible */
  visible: boolean
  /** 关联的 AI 消息 ID（可选） */
  messageId?: number
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'success', data: FeedbackInfo): void
}>()

// 弹窗显隐双向绑定
const dialogVisible = computed({
  get: () => props.visible,
  set: (val: boolean) => emit('update:visible', val),
})

// Bug 分类的标签选项
const tagOptions = ['页面显示异常', '功能无法使用', '数据错误', '加载缓慢', '其他']

// 表单引用
const formRef = ref<FormInstance>()

// 表单数据
const formData = reactive({
  title: '',
  category: 'bug' as 'bug' | 'feature' | 'usage' | 'other',
  content: '',
  severity: '' as '' | 'low' | 'medium' | 'high' | 'critical',
  tags: [] as string[],
})

// 表单验证规则
const formRules: FormRules = {
  title: [
    { required: true, message: '请输入反馈标题', trigger: 'blur' },
    { min: 5, max: 200, message: '标题长度为 5-200 个字符', trigger: 'blur' },
  ],
  category: [
    { required: true, message: '请选择反馈分类', trigger: 'change' },
  ],
  content: [
    { required: true, message: '请输入详细描述', trigger: 'blur' },
    { min: 10, max: 5000, message: '描述长度为 10-5000 个字符', trigger: 'blur' },
  ],
}

const submitting = ref(false)

// 弹窗打开时重置表单
watch(
  () => props.visible,
  (val) => {
    if (val) {
      formRef.value?.resetFields()
      formData.title = ''
      formData.category = 'bug'
      formData.content = ''
      formData.severity = ''
      formData.tags = []
      submitting.value = false
    }
  },
)

// 切换标签
function toggleTag(tag: string) {
  const idx = formData.tags.indexOf(tag)
  if (idx === -1) {
    formData.tags.push(tag)
  } else {
    formData.tags.splice(idx, 1)
  }
}

function handleCancel() {
  dialogVisible.value = false
}

// 确认提交反馈
async function handleConfirm() {
  if (!formRef.value) return
  
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  
  submitting.value = true
  try {
    const res = await feedbackApi.create({
      title: formData.title.trim(),
      category: formData.category,
      content: formData.content.trim(),
      severity: formData.severity || undefined,
      message_id: props.messageId ?? undefined,
      tags: formData.tags.length ? formData.tags : undefined,
    })
    ElMessage.success('感谢您的反馈！我们会尽快处理。')
    emit('success', res.data)
    dialogVisible.value = false
  } catch (err: any) {
    ElMessage.error(err?.message || '反馈提交失败，请稍后重试')
  } finally {
    submitting.value = false
  }
}
</script>

<style lang="scss" scoped>
.tags-wrapper {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.related-info {
  display: flex;
  align-items: center;
  gap: 8px;
  
  .info-tip {
    font-size: 12px;
    color: #909399;
  }
}

:deep(.el-radio) {
  margin-right: 16px;
  margin-bottom: 8px;
}
</style>
