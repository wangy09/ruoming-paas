<template>
  <div class="page-container">
    <div class="toolbar">
      <span class="page-title">熔断器监控</span>
      <div class="toolbar-right">
        <el-select v-model="filterType" style="width: 130px" placeholder="全部类型">
          <el-option label="全部" value="" />
          <el-option label="AI 模型" :value="circuitTypeLabels.llm" />
          <el-option label="第三方集成" :value="circuitTypeLabels.integration" />
          <el-option label="网页搜索" :value="circuitTypeLabels.websearch" />
          <el-option label="代码生成" :value="circuitTypeLabels.codegen" />
        </el-select>
        <el-select v-model="refreshInterval" style="width: 130px" @change="onIntervalChange">
          <el-option label="关闭自动刷新" :value="0" />
          <el-option label="每 5 秒" :value="5" />
          <el-option label="每 10 秒" :value="10" />
          <el-option label="每 30 秒" :value="30" />
        </el-select>
        <el-button :icon="Refresh" :loading="loading" @click="fetchData">手动刷新</el-button>
      </div>
    </div>

    <el-card v-if="filteredBreakers.length === 0" class="empty-card">
      <div class="empty-state">
        <el-icon class="empty-icon"><Box /></el-icon>
        <p class="empty-text">暂无熔断器数据</p>
        <p class="empty-hint">触发外部服务调用后会自动创建熔断器</p>
      </div>
    </el-card>

    <el-row :gutter="16" v-else>
      <el-col :xs="24" :sm="12" :lg="8" v-for="breaker in filteredBreakers" :key="breaker.service_id">
        <el-card :class="`breaker-card ${breaker.state.toLowerCase()}`">
          <template #header>
            <div class="card-header">
              <div class="card-header-left">
                <span class="card-title">{{ getBreakerName(breaker) }}</span>
                <span class="card-subtitle">{{ getBreakerSubtitle(breaker) }}</span>
              </div>
              <div class="card-header-right">
                <el-tag size="small" style="margin-right: 8px">
                  {{ circuitTypeLabels[breaker.circuit_type] }}
                </el-tag>
                <el-tag :type="getStateTagType(breaker.state)" size="small">
                  {{ getStateLabel(breaker.state) }}
                </el-tag>
              </div>
            </div>
          </template>

          <div class="state-icon-wrapper">
            <el-icon :class="`state-icon ${breaker.state.toLowerCase()}`">
              <component :is="getStateIcon(breaker.state)" />
            </el-icon>
          </div>

          <el-descriptions :column="2" border size="small" class="desc">
            <el-descriptions-item label="失败次数">
              <span :class="{ 'text-danger': breaker.fail_count >= breaker.fail_threshold }">
                {{ breaker.fail_count }} / {{ breaker.fail_threshold }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="熔断超时">
              {{ breaker.open_timeout }} 秒
            </el-descriptions-item>
            <el-descriptions-item label="已熔断时长" v-if="breaker.elapsed_seconds !== undefined">
              {{ breaker.elapsed_seconds }} 秒
            </el-descriptions-item>
            <el-descriptions-item label="剩余恢复时间" v-if="breaker.remaining_seconds !== undefined">
              <span :class="{ 'text-danger': breaker.remaining_seconds <= 10 }">
                {{ breaker.remaining_seconds }} 秒
              </span>
            </el-descriptions-item>
          </el-descriptions>

          <div class="fail-progress" v-if="breaker.state !== 'OPEN'">
            <el-progress
              :percentage="Math.round((breaker.fail_count / breaker.fail_threshold) * 100)"
              :color="getProgressColor(breaker)"
              :stroke-width="6"
              :text-inside="true"
              :show-text="false"
            />
            <span class="progress-label">失败进度 {{ breaker.fail_count }}/{{ breaker.fail_threshold }}</span>
          </div>

          <div class="actions" v-if="breaker.state === 'CLOSED' && permissionStore.hasPermission('monitor:circuit:trip')">
            <el-button size="small" type="danger" :icon="Delete" @click="handleTrip(breaker)">
              触发熔断
            </el-button>
          </div>
          <div class="actions" v-else-if="breaker.state !== 'CLOSED' && permissionStore.hasPermission('monitor:circuit:reset')">
            <el-button size="small" type="primary" :icon="Refresh" @click="handleReset(breaker)">
              重置熔断器
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="legend-card" v-if="filteredBreakers.length > 0">
      <template #header><span class="card-title">状态说明</span></template>
      <el-descriptions :column="3" size="small">
        <el-descriptions-item label="CLOSED（关闭）">
          <span class="legend-item closed">
            <span class="dot"></span>
            正常状态，所有请求正常通过
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="OPEN（打开）">
          <span class="legend-item open">
            <span class="dot"></span>
            熔断中，自动切换到备用或返回错误
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="HALF_OPEN（半开）">
          <span class="legend-item half-open">
            <span class="dot"></span>
            尝试恢复，允许少量请求通过
          </span>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, type Component } from 'vue'
import { Refresh, Box, Check, Warning, Delete } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { circuitBreakerApi, type CircuitBreakerState } from '@/api/monitor'
import { usePermissionStore } from '@/store/permission'

const permissionStore = usePermissionStore()

const circuitTypeLabels: Record<string, string> = {
  llm: 'AI 模型',
  integration: '第三方集成',
  websearch: '网页搜索',
  codegen: '代码生成',
}

const STORAGE_KEY = 'circuit_refresh_interval'
const refreshInterval = ref<number>(Number(localStorage.getItem(STORAGE_KEY) ?? 30))
const filterType = ref('')
let timer: ReturnType<typeof setInterval> | null = null
const loading = ref(false)

const breakers = ref<CircuitBreakerState[]>([])

const filteredBreakers = computed(() => {
  if (!filterType.value) return breakers.value
  return breakers.value.filter(b => circuitTypeLabels[b.circuit_type] === filterType.value)
})

function onIntervalChange(val: number) {
  localStorage.setItem(STORAGE_KEY, String(val))
  startTimer()
}

function startTimer() {
  if (timer) clearInterval(timer)
  if (refreshInterval.value > 0) {
    timer = setInterval(fetchData, refreshInterval.value * 1000)
  }
}

async function fetchData() {
  loading.value = true
  try {
    const res = await circuitBreakerApi.list()
    breakers.value = (res as any).data || []
  } catch {
    ElMessage.error('获取熔断器状态失败')
  } finally {
    loading.value = false
  }
}

async function handleReset(breaker: CircuitBreakerState) {
  try {
    await circuitBreakerApi.reset(breaker.circuit_type, breaker.service_id)
    ElMessage.success('熔断器已重置')
    await fetchData()
  } catch {
    ElMessage.error('重置失败')
  }
}

async function handleTrip(breaker: CircuitBreakerState) {
  try {
    await circuitBreakerApi.trip(breaker.circuit_type, breaker.service_id)
    ElMessage.success('熔断器已触发')
    await fetchData()
  } catch {
    ElMessage.error('触发失败')
  }
}

function getBreakerName(breaker: CircuitBreakerState): string {
  if (breaker.model_name) return breaker.model_name
  if (breaker.provider) return breaker.provider
  return `${circuitTypeLabels[breaker.circuit_type]} #${breaker.service_id}`
}

function getBreakerSubtitle(breaker: CircuitBreakerState): string {
  if (breaker.model_config_id !== undefined) {
    return `ID: ${breaker.model_config_id}`
  }
  return `类型: ${circuitTypeLabels[breaker.circuit_type]}`
}

function getStateLabel(state: string): string {
  const map: Record<string, string> = {
    CLOSED: '正常',
    OPEN: '熔断中',
    HALF_OPEN: '恢复中',
  }
  return map[state] || state
}

function getStateTagType(state: string): 'success' | 'danger' | 'warning' | 'info' {
  const map: Record<string, 'success' | 'danger' | 'warning' | 'info'> = {
    CLOSED: 'success',
    OPEN: 'danger',
    HALF_OPEN: 'warning',
  }
  return map[state] || 'info'
}

function getStateIcon(state: string): Component {
  const map: Record<string, Component> = {
    CLOSED: Check,
    OPEN: Delete,
    HALF_OPEN: Warning,
  }
  return map[state] || Box
}

function getProgressColor(breaker: CircuitBreakerState): string {
  const ratio = breaker.fail_count / breaker.fail_threshold
  if (ratio >= 0.8) return '#f56c6c'
  if (ratio >= 0.5) return '#e6a23c'
  return '#67c23a'
}

onMounted(() => {
  fetchData()
  startTimer()
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;

  .page-title { font-size: 18px; font-weight: 600; color: $text-primary; }
  .toolbar-right { display: flex; align-items: center; gap: 10px; }
}

.empty-card {
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 40px 0;

    .empty-icon {
      font-size: 48px;
      color: #c0c4cc;
      margin-bottom: 16px;
    }

    .empty-text {
      font-size: 16px;
      color: $text-primary;
      margin-bottom: 8px;
    }

    .empty-hint {
      font-size: 13px;
      color: $text-secondary;
    }
  }
}

.breaker-card {
  transition: all 0.3s ease;

  &.closed {
    border-color: #e8f5e9;
    .state-icon-wrapper { background: #e8f5e9; }
    .state-icon { color: #67c23a; }
  }

  &.open {
    border-color: #fee2e2;
    .state-icon-wrapper { background: #fee2e2; }
    .state-icon { color: #f56c6c; }
  }

  &.half-open {
    border-color: #fef3c7;
    .state-icon-wrapper { background: #fef3c7; }
    .state-icon { color: #e6a23c; }
  }

  .card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
  }

  .card-header-left {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .card-title { font-size: 14px; font-weight: 600; color: $text-primary; }
  .card-subtitle { font-size: 12px; color: $text-secondary; }

  .state-icon-wrapper {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 80px;
    height: 80px;
    border-radius: 50%;
    margin: 16px auto;
  }

  .state-icon {
    font-size: 40px;
  }

  .desc {
    margin-bottom: 12px;
  }

  .fail-progress {
    margin-bottom: 12px;
    .progress-label {
      font-size: 12px;
      color: $text-secondary;
      display: block;
      text-align: center;
      margin-top: 4px;
    }
  }

  .actions {
    display: flex;
    justify-content: center;
  }
}

.legend-card {
  margin-top: 16px;

  .card-title { font-size: 14px; font-weight: 600; color: $text-primary; }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: $text-secondary;

    .dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }

    &.closed .dot { background: #67c23a; }
    &.open .dot { background: #f56c6c; }
    &.half-open .dot { background: #e6a23c; }
  }
}

.text-danger { color: #f56c6c; }

:deep(.el-card__header) {
  padding: 12px 16px;
}
</style>