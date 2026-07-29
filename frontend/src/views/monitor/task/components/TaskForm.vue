<template>
  <el-dialog
    v-model="visible"
    :title="isEdit ? '编辑计划任务' : '新建计划任务'"
    width="580px"
    :close-on-click-modal="false"
    @closed="handleClosed"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" label-position="right">
      <el-form-item label="任务名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入任务名称" maxlength="64" show-word-limit />
      </el-form-item>

      <el-form-item label="任务类型" prop="task_type">
        <el-radio-group v-model="form.task_type">
          <el-radio value="cron">周期（Cron 表达式）</el-radio>
          <el-radio value="interval">间隔执行</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item v-if="form.task_type === 'cron'" label="Cron 表达式" prop="cron_expr">
        <el-input v-model="form.cron_expr" placeholder="如：0 2 * * *（每天凌晨2点）">
          <template #append>
            <el-button @click="openCronGenerator">生成器</el-button>
          </template>
        </el-input>
        <div class="form-tip">格式：分 时 日 月 周，如 <code>0 */6 * * *</code> 表示每6小时</div>
      </el-form-item>

      <el-form-item v-if="form.task_type === 'interval'" label="执行间隔" prop="interval_value">
        <div class="interval-input">
          <el-input-number
            v-model="form.interval_value"
            :min="1"
            :max="9999"
            controls-position="right"
            style="width: 160px"
          />
          <el-select v-model="form.interval_unit" style="width: 110px">
            <el-option
              v-for="unit in intervalUnits"
              :key="unit.value"
              :label="unit.label"
              :value="unit.value"
            />
          </el-select>
        </div>
        <span class="form-tip-inline">最小 10 秒</span>
      </el-form-item>

      <el-form-item label="执行方法" prop="func_name">
        <el-select
          v-model="form.func_name"
          filterable
          placeholder="请选择 Celery Task"
          style="width: 100%"
          :loading="functionsLoading"
        >
          <el-option
            v-for="fn in functions"
            :key="fn.value"
            :label="`${fn.label}（${fn.value}）`"
            :value="fn.value"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="是否一次性">
        <el-switch v-model="form.is_once" active-text="是（执行完自动停用）" />
      </el-form-item>

      <el-form-item label="状态">
        <el-radio-group v-model="form.status">
          <el-radio :value="1">启用</el-radio>
          <el-radio :value="0">停用</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="备注">
        <el-input v-model="form.remark" type="textarea" :rows="2" maxlength="255" show-word-limit />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>

  <el-dialog
    v-model="cronGeneratorVisible"
    title="Cron 表达式生成器"
    width="560px"
    append-to-body
    :close-on-click-modal="false"
  >
    <el-form label-width="110px">
      <el-form-item label="执行频率">
        <el-radio-group v-model="cronForm.mode">
          <el-radio-button value="minute">每 N 分钟</el-radio-button>
          <el-radio-button value="hour">每 N 小时</el-radio-button>
          <el-radio-button value="daily">每天</el-radio-button>
          <el-radio-button value="weekly">每周</el-radio-button>
          <el-radio-button value="monthly">每月</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-form-item v-if="cronForm.mode === 'minute'" label="间隔分钟">
        <el-input-number v-model="cronForm.minuteStep" :min="1" :max="59" controls-position="right" />
      </el-form-item>

      <el-form-item v-if="cronForm.mode === 'hour'" label="间隔小时">
        <div class="cron-row">
          <el-input-number v-model="cronForm.hourStep" :min="1" :max="23" controls-position="right" />
          <span class="form-unit">第</span>
          <el-input-number v-model="cronForm.minute" :min="0" :max="59" controls-position="right" />
          <span class="form-unit">分钟执行</span>
        </div>
      </el-form-item>

      <el-form-item v-if="cronForm.mode === 'daily'" label="执行时间">
        <div class="cron-row">
          <el-input-number v-model="cronForm.hour" :min="0" :max="23" controls-position="right" />
          <span class="form-unit">时</span>
          <el-input-number v-model="cronForm.minute" :min="0" :max="59" controls-position="right" />
          <span class="form-unit">分</span>
        </div>
      </el-form-item>

      <template v-if="cronForm.mode === 'weekly'">
        <el-form-item label="星期">
          <el-checkbox-group v-model="cronForm.weekdays">
            <el-checkbox-button v-for="day in weekOptions" :key="day.value" :value="day.value">
              {{ day.label }}
            </el-checkbox-button>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="执行时间">
          <div class="cron-row">
            <el-input-number v-model="cronForm.hour" :min="0" :max="23" controls-position="right" />
            <span class="form-unit">时</span>
            <el-input-number v-model="cronForm.minute" :min="0" :max="59" controls-position="right" />
            <span class="form-unit">分</span>
          </div>
        </el-form-item>
      </template>

      <template v-if="cronForm.mode === 'monthly'">
        <el-form-item label="每月日期">
          <el-input-number v-model="cronForm.monthDay" :min="1" :max="31" controls-position="right" />
          <span class="form-tip-inline">部分月份没有 29-31 日，请谨慎选择</span>
        </el-form-item>
        <el-form-item label="执行时间">
          <div class="cron-row">
            <el-input-number v-model="cronForm.hour" :min="0" :max="23" controls-position="right" />
            <span class="form-unit">时</span>
            <el-input-number v-model="cronForm.minute" :min="0" :max="59" controls-position="right" />
            <span class="form-unit">分</span>
          </div>
        </el-form-item>
      </template>

      <el-form-item label="生成结果">
        <el-input :model-value="generatedCron" readonly>
          <template #append>
            <el-button @click="copyGeneratedCron">复制</el-button>
          </template>
        </el-input>
        <div class="form-tip">{{ cronDescription }}</div>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="cronGeneratorVisible = false">取消</el-button>
      <el-button type="primary" @click="applyGeneratedCron">使用此表达式</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { taskApi } from '@/api/monitor'
import type { ScheduledTaskInfo } from '@/types'

interface FunctionOption { value: string; label: string }
type IntervalUnit = 'day' | 'hour' | 'minute' | 'second'
type CronMode = 'minute' | 'hour' | 'daily' | 'weekly' | 'monthly'

const intervalUnits: Array<{ label: string; value: IntervalUnit; seconds: number }> = [
  { label: '天', value: 'day', seconds: 86400 },
  { label: '小时', value: 'hour', seconds: 3600 },
  { label: '分钟', value: 'minute', seconds: 60 },
  { label: '秒', value: 'second', seconds: 1 },
]
const weekOptions = [
  { label: '周一', value: 1 },
  { label: '周二', value: 2 },
  { label: '周三', value: 3 },
  { label: '周四', value: 4 },
  { label: '周五', value: 5 },
  { label: '周六', value: 6 },
  { label: '周日', value: 0 },
]

const props = defineProps<{
  modelValue: boolean
  editData?: ScheduledTaskInfo | null
}>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'success'): void
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})
const isEdit = computed(() => !!props.editData?.id)

const formRef = ref<FormInstance>()
const submitting = ref(false)
const functions = ref<FunctionOption[]>([])
const functionsLoading = ref(false)
const cronGeneratorVisible = ref(false)
const cronForm = ref({
  mode: 'daily' as CronMode,
  minuteStep: 5,
  hourStep: 1,
  minute: 0,
  hour: 2,
  weekdays: [1],
  monthDay: 1,
})

const generatedCron = computed(() => {
  const minute = clampNumber(cronForm.value.minute, 0, 59)
  const hour = clampNumber(cronForm.value.hour, 0, 23)

  switch (cronForm.value.mode) {
    case 'minute':
      return `*/${clampNumber(cronForm.value.minuteStep, 1, 59)} * * * *`
    case 'hour':
      return `${minute} */${clampNumber(cronForm.value.hourStep, 1, 23)} * * *`
    case 'weekly': {
      const weekdays = [...cronForm.value.weekdays].sort((a, b) => a - b)
      return `${minute} ${hour} * * ${weekdays.length ? weekdays.join(',') : '*'}`
    }
    case 'monthly':
      return `${minute} ${hour} ${clampNumber(cronForm.value.monthDay, 1, 31)} * *`
    case 'daily':
    default:
      return `${minute} ${hour} * * *`
  }
})

const cronDescription = computed(() => {
  const minute = padNumber(clampNumber(cronForm.value.minute, 0, 59))
  const hour = padNumber(clampNumber(cronForm.value.hour, 0, 23))

  switch (cronForm.value.mode) {
    case 'minute':
      return `每 ${clampNumber(cronForm.value.minuteStep, 1, 59)} 分钟执行一次`
    case 'hour':
      return `每 ${clampNumber(cronForm.value.hourStep, 1, 23)} 小时的第 ${minute} 分钟执行`
    case 'weekly': {
      const dayNames = weekOptions
        .filter((day) => cronForm.value.weekdays.includes(day.value))
        .map((day) => day.label)
      return `${dayNames.length ? dayNames.join('、') : '每周每天'} ${hour}:${minute} 执行`
    }
    case 'monthly':
      return `每月 ${clampNumber(cronForm.value.monthDay, 1, 31)} 日 ${hour}:${minute} 执行`
    case 'daily':
    default:
      return `每天 ${hour}:${minute} 执行`
  }
})

const defaultForm = () => ({
  name: '',
  task_type: 'interval' as 'cron' | 'interval',
  func_name: '',
  cron_expr: '',
  interval_seconds: 300,
  interval_value: 5,
  interval_unit: 'minute' as IntervalUnit,
  is_once: false,
  status: 1,
  remark: '',
})

const form = ref(defaultForm())

const rules: FormRules = {
  name: [{ required: true, message: '请输入任务名称', trigger: 'blur' }],
  task_type: [{ required: true, message: '请选择任务类型', trigger: 'change' }],
  func_name: [{ required: true, message: '请选择执行方法', trigger: 'change' }],
  cron_expr: [{ required: true, message: '请输入 Cron 表达式', trigger: 'blur' }],
  interval_value: [
    { required: true, message: '请输入执行间隔', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        const seconds = toIntervalSeconds(Number(value), form.value.interval_unit)
        if (form.value.task_type === 'interval' && seconds < 10) {
          callback(new Error('执行间隔不能小于 10 秒'))
          return
        }
        callback()
      },
      trigger: 'change',
    },
  ],
}

watch(visible, async (v) => {
  if (!v) return
  // 加载 task 列表
  functionsLoading.value = true
  try {
    const res = await taskApi.getFunctions()
    functions.value = res.data ?? []
  } finally {
    functionsLoading.value = false
  }
  // 填充编辑数据
  if (props.editData?.id) {
    const nextForm = { ...defaultForm(), ...props.editData }
    const interval = splitIntervalSeconds(Number(props.editData.interval_seconds || nextForm.interval_seconds))
    nextForm.interval_value = interval.value
    nextForm.interval_unit = interval.unit
    form.value = nextForm
  } else {
    form.value = defaultForm()
  }
})

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    const payload: Record<string, any> = { ...form.value }
    // 清理不相关字段
    if (payload.task_type === 'cron') {
      delete payload.interval_seconds
    } else {
      payload.interval_seconds = toIntervalSeconds(payload.interval_value, payload.interval_unit)
      delete payload.cron_expr
    }
    delete payload.interval_value
    delete payload.interval_unit

    if (isEdit.value) {
      await taskApi.update(props.editData!.id, payload)
      ElMessage.success('更新成功')
    } else {
      await taskApi.create(payload)
      ElMessage.success('创建成功')
    }
    visible.value = false
    emit('success')
  } catch (e: unknown) {
    const err = e as { response?: { data?: { message?: string } } }
    ElMessage.error(err.response?.data?.message || '操作失败')
  } finally {
    submitting.value = false
  }
}

function handleClosed() {
  formRef.value?.resetFields()
  form.value = defaultForm()
}

function toIntervalSeconds(value: number, unit: IntervalUnit) {
  const unitConfig = intervalUnits.find((item) => item.value === unit)
  return Math.round(Number(value || 0) * (unitConfig?.seconds ?? 1))
}

function splitIntervalSeconds(seconds: number): { value: number; unit: IntervalUnit } {
  const normalized = Number(seconds || 300)
  for (const unit of intervalUnits) {
    if (normalized >= unit.seconds && normalized % unit.seconds === 0) {
      return { value: normalized / unit.seconds, unit: unit.value }
    }
  }
  return { value: normalized, unit: 'second' }
}

function openCronGenerator() {
  cronGeneratorVisible.value = true
}

function applyGeneratedCron() {
  form.value.cron_expr = generatedCron.value
  cronGeneratorVisible.value = false
}

async function copyGeneratedCron() {
  try {
    await navigator.clipboard.writeText(generatedCron.value)
    ElMessage.success('已复制 Cron 表达式')
  } catch {
    ElMessage.warning('复制失败，请手动复制')
  }
}

function clampNumber(value: number, min: number, max: number) {
  const normalized = Number(value)
  if (Number.isNaN(normalized)) return min
  return Math.min(Math.max(Math.trunc(normalized), min), max)
}

function padNumber(value: number) {
  return String(value).padStart(2, '0')
}
</script>

<style lang="scss" scoped>
.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  code { background: #f5f7fa; padding: 1px 4px; border-radius: 3px; }
}
.form-unit { margin-left: 8px; color: #606266; font-size: 13px; }
.form-tip-inline { margin-left: 8px; font-size: 12px; color: #909399; }
.interval-input { display: inline-flex; gap: 8px; align-items: center; }
.cron-row { display: inline-flex; gap: 8px; align-items: center; }
</style>
