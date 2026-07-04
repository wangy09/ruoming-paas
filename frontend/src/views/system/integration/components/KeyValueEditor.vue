<template>
  <div class="key-value-editor">
    <el-alert
      v-if="secret && editMode && configured"
      class="secret-tip"
      type="info"
      :closable="false"
      show-icon
      title="敏感配置已加密保存，编辑时不会回显；留空表示不更新该字段。"
    />

    <div v-if="!rows.length" class="empty-line">
      暂无字段，点击“添加字段”补充配置
    </div>

    <div v-for="(row, index) in rows" :key="row.id" class="kv-row">
      <el-input
        v-model="row.key"
        class="kv-key"
        :disabled="row.fixed"
        placeholder="字段名"
        @input="emitValue"
      />
      <el-input
        v-model="row.value"
        class="kv-value"
        :type="secret ? 'password' : 'text'"
        :show-password="secret"
        :placeholder="secret && editMode ? '留空保持原值，填写则更新' : '字段值'"
        autocomplete="new-password"
        @input="emitValue"
      />
      <el-button
        link
        type="danger"
        :icon="Delete"
        :disabled="row.fixed"
        @click="removeRow(index)"
      />
    </div>

    <el-button link type="primary" :icon="Plus" @click="addRow">添加字段</el-button>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { Delete, Plus } from '@element-plus/icons-vue'

interface KeyValueRow {
  id: string
  key: string
  value: string
  fixed: boolean
}

const props = withDefaults(defineProps<{
  modelValue: Record<string, unknown>
  fields?: string[]
  secret?: boolean
  editMode?: boolean
  configured?: boolean
}>(), {
  fields: () => [],
  secret: false,
  editMode: false,
  configured: false,
})

const emit = defineEmits<{
  'update:modelValue': [value: Record<string, string>]
}>()

const rows = ref<KeyValueRow[]>([])
const internalUpdating = ref(false)

// 根据平台字段和当前值重建编辑行，固定字段不可删除，避免误删平台必需键。
function buildRows() {
  const fieldSet = new Set(props.fields)
  const nextRows: KeyValueRow[] = props.fields.map(field => ({
    id: `field_${field}`,
    key: field,
    value: String(props.modelValue?.[field] ?? ''),
    fixed: true,
  }))

  Object.entries(props.modelValue || {}).forEach(([key, value]) => {
    if (fieldSet.has(key)) return
    nextRows.push({
      id: `extra_${key}_${Math.random().toString(36).slice(2)}`,
      key,
      value: String(value ?? ''),
      fixed: false,
    })
  })

  rows.value = nextRows
}

function emitValue() {
  const record: Record<string, string> = {}
  rows.value.forEach((row) => {
    const key = row.key.trim()
    if (!key) return
    // 敏感字段留空不提交，确保后端原加密值保持不变。
    if (props.secret && props.editMode && row.value === '') return
    record[key] = row.value
  })
  internalUpdating.value = true
  emit('update:modelValue', record)
  nextTick(() => {
    internalUpdating.value = false
  })
}

function addRow() {
  rows.value.push({
    id: `new_${Date.now()}_${Math.random().toString(36).slice(2)}`,
    key: '',
    value: '',
    fixed: false,
  })
}

function removeRow(index: number) {
  rows.value.splice(index, 1)
  emitValue()
}

watch(
  () => [props.modelValue, props.fields, props.editMode],
  () => {
    if (!internalUpdating.value) buildRows()
  },
  { immediate: true, deep: true },
)
</script>

<style lang="scss" scoped>
.key-value-editor {
  width: 100%;
}

.secret-tip {
  margin-bottom: 10px;
}

.empty-line {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-bottom: 8px;
}

.kv-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.kv-key {
  width: 34%;
}

.kv-value {
  flex: 1;
}
</style>
