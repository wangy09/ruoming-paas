<template>
  <el-dialog :model-value="visible" @update:model-value="emit('update:visible', $event)" :title="dialogTitle" width="920px" destroy-on-close>
    <el-alert
      v-if="isEncryptedEdit"
      class="encrypted-tip"
      type="warning"
      show-icon
      :closable="false"
      title="该配置为加密字段，编辑时配置值留空将不覆盖原密文。"
    />

    <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="作用域" prop="scope">
            <el-select v-model="form.scope" class="w-full" @change="handleScopeChange">
              <el-option v-for="item in scopeOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="配置键" prop="config_key">
            <el-input v-model="form.config_key" :disabled="Boolean(editId)" placeholder="如：site.title" maxlength="128" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="分类">
            <el-input v-model="form.category" placeholder="如：基础配置 / 安全配置" maxlength="64" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="名称">
            <el-input v-model="form.label" placeholder="配置展示名称" maxlength="128" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="值类型" prop="val_type">
            <el-select v-model="form.val_type" class="w-full" @change="handleValueTypeChange">
              <el-option v-for="item in valueTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="控件类型" prop="config_type">
            <el-select v-model="form.config_type" class="w-full">
              <el-option v-for="item in formTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="必填">
            <el-switch v-model="form.required" active-text="是" inactive-text="否" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="状态">
            <el-radio-group v-model="form.status">
              <el-radio-button :value="1">启用</el-radio-button>
              <el-radio-button :value="0">停用</el-radio-button>
            </el-radio-group>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="公开访问">
            <el-switch v-model="form.is_public" active-text="公开" inactive-text="私有" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="加密存储">
            <el-switch v-model="form.is_encrypted" active-text="加密" inactive-text="明文" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="应用标识" :required="form.scope === 'app'">
            <el-input
              v-model="form.app_key"
              :disabled="form.scope !== 'app' && form.scope !== 'user'"
              placeholder="scope 为 app/user 时可填写"
              maxlength="64"
            />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="用户ID" :required="form.scope === 'user'">
            <el-input-number
              v-model="form.user_id"
              :disabled="form.scope !== 'user'"
              :min="1"
              :precision="0"
              class="w-full"
              placeholder="scope 为 user 时填写"
            />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="配置值" prop="config_val">
        <el-switch
          v-if="form.config_type === 'switch'"
          v-model="form.config_val"
          active-value="true"
          inactive-value="false"
          active-text="true"
          inactive-text="false"
        />
        <el-select
          v-else-if="form.config_type === 'select'"
          v-model="form.config_val"
          filterable
          clearable
          placeholder="请选择配置值"
          class="w-full"
        >
          <el-option
            v-for="option in parsedSelectOptions"
            :key="String(option.value)"
            :label="option.label"
            :value="String(option.value)"
          />
        </el-select>
        <el-input
          v-else-if="isMultiLineValue"
          v-model="form.config_val"
          type="textarea"
          :rows="5"
          :placeholder="configValuePlaceholder"
        />
        <el-input-number
          v-else-if="form.config_type === 'number'"
          :model-value="numberConfigValue"
          :min="form.min_value"
          :max="form.max_value"
          :precision="form.val_type === 'int' ? 0 : undefined"
          class="w-full"
          @update:model-value="handleNumberConfigValueChange"
        />
        <el-input
          v-else
          v-model="form.config_val"
          :type="form.config_type === 'password' || form.is_encrypted ? 'password' : 'text'"
          :show-password="form.config_type === 'password' || form.is_encrypted"
          :placeholder="configValuePlaceholder"
        />
      </el-form-item>

      <el-row :gutter="16">
        <el-col :span="12">
          <el-form-item label="默认值">
            <el-input v-model="form.default_value" placeholder="可选默认值" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="排序">
            <el-input-number v-model="form.sort" :min="0" :max="999999" :precision="0" class="w-full" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item v-if="form.config_type === 'select'" label="选项配置" prop="optionsText">
        <el-input
          v-model="form.optionsText"
          type="textarea"
          :rows="5"
          placeholder='JSON 数组，例如：[{"label":"启用","value":"1"},{"label":"停用","value":"0"}]'
        />
      </el-form-item>

      <el-row :gutter="16">
        <el-col :span="8">
          <el-form-item label="正则校验">
            <el-input v-model="form.regex" placeholder="可选，如：^\w+$" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="最小值">
            <el-input-number v-model="form.min_value" :disabled="!showNumberLimit" class="w-full" />
          </el-form-item>
        </el-col>
        <el-col :span="8">
          <el-form-item label="最大值">
            <el-input-number v-model="form.max_value" :disabled="!showNumberLimit" class="w-full" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="3" maxlength="255" show-word-limit />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { type FormInstance, type FormRules } from 'element-plus'
import type {
  ConfigFormType,
  ConfigInfo,
  ConfigOption,
  ConfigScope,
  ConfigValueType,
} from '@/types'

interface ConfigFormState {
  scope: ConfigScope
  config_key: string
  config_val: string
  val_type: ConfigValueType
  is_encrypted: boolean
  category: string
  config_type: ConfigFormType
  default_value: string
  optionsText: string
  required: boolean
  regex: string
  min_value?: number
  max_value?: number
  sort: number
  status: 0 | 1
  label: string
  description: string
  is_public: boolean
  app_key: string
  user_id?: number
}

const scopeOptions: Array<{ label: string; value: ConfigScope }> = [
  { label: '全局', value: 'global' },
  { label: '租户', value: 'tenant' },
  { label: '应用', value: 'app' },
  { label: '用户', value: 'user' },
]

const valueTypeOptions: Array<{ label: string; value: ConfigValueType }> = [
  { label: '字符串', value: 'string' },
  { label: '整数', value: 'int' },
  { label: '数字', value: 'number' },
  { label: '布尔', value: 'bool' },
  { label: 'JSON', value: 'json' },
]

const formTypeOptions: Array<{ label: string; value: ConfigFormType }> = [
  { label: '输入框', value: 'input' },
  { label: '多行文本', value: 'textarea' },
  { label: '开关', value: 'switch' },
  { label: '下拉框', value: 'select' },
  { label: 'JSON', value: 'json' },
  { label: '密码框', value: 'password' },
  { label: '数字输入', value: 'number' },
]

const props = defineProps<{
  visible: boolean
  editId: number | null
  editingRow: ConfigInfo | null
  initialForm: ConfigFormState
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'submit', form: ConfigFormState): void
}>()

const formRef = ref<FormInstance>()
const submitting = ref(false)

const form = reactive<ConfigFormState>({ ...props.initialForm })

const dialogTitle = computed(() => (props.editId ? '编辑配置' : '新增配置'))

const showNumberLimit = computed(() => ['int', 'number'].includes(form.val_type) || form.config_type === 'number')
const isMultiLineValue = computed(() => form.config_type === 'textarea' || form.config_type === 'json' || form.val_type === 'json')
const isEncryptedEdit = computed(() => Boolean(props.editId && props.editingRow?.is_encrypted))

const numberConfigValue = computed(() => {
  if (!form.config_val) return undefined
  const value = Number(form.config_val)
  return Number.isFinite(value) ? value : undefined
})

const configValuePlaceholder = computed(() => {
  if (isEncryptedEdit.value) return '留空不覆盖原密文'
  if (form.val_type === 'json') return '请输入合法 JSON'
  return '请输入配置值'
})

const parsedSelectOptions = computed<ConfigOption[]>(() => {
  const parsed = parseOptionsText(form.optionsText, false)
  return Array.isArray(parsed) ? parsed : []
})

const rules: FormRules<ConfigFormState> = {
  scope: [{ required: true, message: '请选择作用域', trigger: 'change' }],
  config_key: [{ required: true, message: '请输入配置键', trigger: 'blur' }],
  val_type: [{ required: true, message: '请选择值类型', trigger: 'change' }],
  config_type: [{ required: true, message: '请选择控件类型', trigger: 'change' }],
  config_val: [{ validator: validateConfigValue, trigger: 'blur' }],
  optionsText: [{ validator: validateOptionsText, trigger: 'blur' }],
}

watch(
  () => props.initialForm,
  (val) => {
    Object.assign(form, val)
  },
  { deep: true }
)

function handleScopeChange() {
  if (form.scope !== 'app' && form.scope !== 'user') {
    form.app_key = ''
    form.user_id = undefined
  }
}

function handleValueTypeChange() {
  if (form.val_type === 'bool') {
    form.config_type = 'switch'
  }
}

function handleNumberConfigValueChange(value: number | undefined) {
  form.config_val = value === undefined ? '' : String(value)
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    emit('submit', { ...form })
  } finally {
    submitting.value = false
  }
}

function parseOptionsText(text: string, strict: boolean): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return strict ? [] : []
  }
}

function validateConfigValue(rule: unknown, value: string, callback: (error?: Error) => void) {
  if (form.required && !value.trim()) {
    callback(new Error('该配置为必填项'))
    return
  }
  if (form.val_type === 'json') {
    try {
      JSON.parse(value)
    } catch {
      callback(new Error('请输入合法 JSON'))
      return
    }
  }
  callback()
}

function validateOptionsText(rule: unknown, value: string, callback: (error?: Error) => void) {
  if (!value.trim()) {
    callback()
    return
  }
  try {
    const parsed = JSON.parse(value)
    if (!Array.isArray(parsed)) {
      callback(new Error('选项必须是 JSON 数组'))
      return
    }
    for (const item of parsed) {
      if (!item || typeof item !== 'object' || !('label' in item) || !('value' in item)) {
        callback(new Error('选项格式不正确，应为 {label, value} 对象数组'))
        return
      }
    }
  } catch {
    callback(new Error('请输入合法 JSON'))
    return
  }
  callback()
}
</script>

<style lang="scss" scoped>
.encrypted-tip { margin-bottom: 16px; }
.w-full { width: 100%; }
</style>