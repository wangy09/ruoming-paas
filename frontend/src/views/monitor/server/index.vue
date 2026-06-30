<template>
  <div class="page-container">
    <!-- 顶部工具栏 -->
    <div class="toolbar">
      <span class="page-title">服务监控</span>
      <div class="toolbar-right">
        <el-select v-model="refreshInterval" style="width: 130px" @change="onIntervalChange">
          <el-option label="关闭自动刷新" :value="0" />
          <el-option label="每 5 秒" :value="5" />
          <el-option label="每 10 秒" :value="10" />
          <el-option label="每 30 秒" :value="30" />
          <el-option label="每 60 秒" :value="60" />
        </el-select>
        <el-button :icon="Refresh" :loading="loading" @click="fetchAll">手动刷新</el-button>
      </div>
    </div>

    <!-- 系统基础信息 -->
    <el-card class="info-card mb-3" v-if="sysInfo">
      <template #header><span class="card-title">系统信息</span></template>
      <el-descriptions :column="4" border size="small">
        <el-descriptions-item label="主机名">{{ sysInfo.hostname }}</el-descriptions-item>
        <el-descriptions-item label="操作系统">{{ sysInfo.os }}</el-descriptions-item>
        <el-descriptions-item label="CPU 品牌">{{ sysInfo.cpu_brand }}</el-descriptions-item>
        <el-descriptions-item label="架构">{{ sysInfo.arch }}</el-descriptions-item>
        <el-descriptions-item label="逻辑核数">{{ sysInfo.cpu_count_logical }}</el-descriptions-item>
        <el-descriptions-item label="物理核数">{{ sysInfo.cpu_count_physical }}</el-descriptions-item>
        <el-descriptions-item label="运行时长">{{ sysInfo.uptime }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- CPU / 内存 / Swap 仪表盘 -->
    <el-row :gutter="16" class="mb-3" v-if="metrics">
      <!-- CPU 仪表盘 -->
      <el-col :xs="24" :sm="8">
        <el-card>
          <template #header>
            <span class="card-title">CPU 使用率</span>
            <span class="card-sub">负载 {{ metrics.cpu.load_avg_1m }} / {{ metrics.cpu.load_avg_5m }} / {{ metrics.cpu.load_avg_15m }}</span>
          </template>
          <v-chart class="gauge-chart" :option="cpuGaugeOption" autoresize />
          <div class="gauge-detail">
            <span>频率 {{ metrics.cpu.freq_mhz }} MHz</span>
            <span>逻辑核 {{ metrics.cpu.count_logical }}</span>
          </div>
        </el-card>
      </el-col>

      <!-- 内存仪表盘 -->
      <el-col :xs="24" :sm="8">
        <el-card>
          <template #header>
            <span class="card-title">内存使用率</span>
            <span class="card-sub">{{ metrics.memory.used_gb }} GB / {{ metrics.memory.total_gb }} GB</span>
          </template>
          <v-chart class="gauge-chart" :option="memGaugeOption" autoresize />
          <div class="gauge-detail">
            <span>已用 {{ metrics.memory.used_gb }} GB</span>
            <span>可用 {{ metrics.memory.available_gb }} GB</span>
          </div>
        </el-card>
      </el-col>

      <!-- Swap 仪表盘 -->
      <el-col :xs="24" :sm="8">
        <el-card>
          <template #header>
            <span class="card-title">Swap 使用率</span>
            <span class="card-sub">{{ metrics.swap.used_gb }} GB / {{ metrics.swap.total_gb }} GB</span>
          </template>
          <v-chart class="gauge-chart" :option="swapGaugeOption" autoresize />
          <div class="gauge-detail">
            <span>已用 {{ metrics.swap.used_gb }} GB</span>
            <span>总量 {{ metrics.swap.total_gb }} GB</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 磁盘使用情况 -->
    <el-card class="mb-3" v-if="metrics?.disk?.length">
      <template #header><span class="card-title">磁盘使用情况</span></template>
      <el-table :data="metrics.disk" size="small" stripe>
        <el-table-column prop="mount" label="挂载点" />
        <el-table-column prop="device" label="设备" />
        <el-table-column prop="fstype" label="文件系统" width="100" />
        <el-table-column label="总容量" width="100">
          <template #default="{ row }">{{ row.total_gb }} GB</template>
        </el-table-column>
        <el-table-column label="已使用" width="100">
          <template #default="{ row }">{{ row.used_gb }} GB</template>
        </el-table-column>
        <el-table-column label="可用" width="100">
          <template #default="{ row }">{{ row.free_gb }} GB</template>
        </el-table-column>
        <el-table-column label="使用率" width="200">
          <template #default="{ row }">
            <el-progress
              :percentage="row.percent"
              :color="row.percent > 90 ? '#f56c6c' : row.percent > 70 ? '#e6a23c' : '#67c23a'"
              :stroke-width="10"
            />
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 网络流量趋势 -->
    <el-card>
      <template #header>
        <span class="card-title">网络流量趋势</span>
        <el-select v-model="selectedIface" style="width: 130px; margin-left: 12px" @change="onIfaceChange" size="small">
          <el-option v-for="iface in networkInterfaces" :key="iface" :label="iface" :value="iface" />
        </el-select>
      </template>
      <v-chart class="traffic-chart" :option="networkChartOption" autoresize />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { GaugeChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { monitorApi } from '@/api/monitor'
import { ElMessage } from 'element-plus'

use([CanvasRenderer, GaugeChart, LineChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

// ── 刷新控制 ──────────────────────────────────────────────────
const STORAGE_KEY = 'monitor_refresh_interval'
const refreshInterval = ref<number>(Number(localStorage.getItem(STORAGE_KEY) ?? 30))
let timer: ReturnType<typeof setInterval> | null = null
const loading = ref(false)

function onIntervalChange(val: number) {
  localStorage.setItem(STORAGE_KEY, String(val))
  startTimer()
}

function startTimer() {
  if (timer) clearInterval(timer)
  if (refreshInterval.value > 0) {
    timer = setInterval(fetchMetricsAndNetwork, refreshInterval.value * 1000)
  }
}

// ── 数据 ──────────────────────────────────────────────────────
const sysInfo = ref<any>(null)
const metrics = ref<any>(null)
const networkData = ref<any>(null)
const selectedIface = ref<string>('')

// 网络流量历史（最近 20 个点）
const MAX_POINTS = 20
const networkHistory = ref<{ time: string; send: number; recv: number }[]>([])
let prevNetStats: Record<string, { bytes_sent: number; bytes_recv: number }> = {}
let prevTime = 0

const networkInterfaces = computed<string[]>(() => networkData.value?.interfaces ?? [])

async function fetchAll() {
  loading.value = true
  try {
    const [infoRes, metricsRes, netRes] = await Promise.all([
      !sysInfo.value ? monitorApi.serverInfo() : Promise.resolve(null),
      monitorApi.serverMetrics(),
      monitorApi.serverNetwork(selectedIface.value || undefined),
    ])
    if (infoRes) sysInfo.value = infoRes.data
    metrics.value = metricsRes.data
    handleNetworkData(netRes.data)
  } catch {
    ElMessage.error('获取监控数据失败')
  } finally {
    loading.value = false
  }
}

async function fetchMetricsAndNetwork() {
  try {
    const [metricsRes, netRes] = await Promise.all([
      monitorApi.serverMetrics(),
      monitorApi.serverNetwork(selectedIface.value || undefined),
    ])
    metrics.value = metricsRes.data
    handleNetworkData(netRes.data)
  } catch {
    // 静默失败，避免干扰用户操作
  }
}

function handleNetworkData(data: any) {
  if (!data) return
  networkData.value = data

  // 初始化选中网卡
  if (!selectedIface.value && data.selected) {
    selectedIface.value = data.selected
  }

  const iface = selectedIface.value
  const stats = data.stats?.[iface]
  if (!stats) return

  const now = Date.now()
  const elapsed = prevTime ? (now - prevTime) / 1000 : 1
  prevTime = now

  const prev = prevNetStats[iface]
  const sendKb = prev ? Math.max(0, (stats.bytes_sent - prev.bytes_sent) / 1024 / elapsed) : 0
  const recvKb = prev ? Math.max(0, (stats.bytes_recv - prev.bytes_recv) / 1024 / elapsed) : 0

  prevNetStats[iface] = { bytes_sent: stats.bytes_sent, bytes_recv: stats.bytes_recv }

  const time = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  networkHistory.value.push({ time, send: Math.round(sendKb), recv: Math.round(recvKb) })
  if (networkHistory.value.length > MAX_POINTS) {
    networkHistory.value.shift()
  }
}

function onIfaceChange() {
  prevNetStats = {}
  prevTime = 0
  fetchMetricsAndNetwork()
}

// ── ECharts 配置 ──────────────────────────────────────────────

function makeGaugeOption(percent: number, label: string, color: string) {
  return {
    series: [{
      type: 'gauge',
      startAngle: 210,
      endAngle: -30,
      min: 0,
      max: 100,
      splitNumber: 10,
      radius: '85%',
      axisLine: {
        lineStyle: {
          width: 12,
          color: [[percent / 100, color], [1, '#e8e8e8']],
        },
      },
      pointer: { length: '60%', width: 5 },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      detail: {
        formatter: `{value}%`,
        fontSize: 22,
        fontWeight: 700,
        color: color,
        offsetCenter: [0, '40%'],
      },
      data: [{ value: percent, name: label }],
      title: { fontSize: 13, color: '#666', offsetCenter: [0, '70%'] },
    }],
  }
}

const cpuGaugeOption = computed(() => {
  const p = metrics.value?.cpu?.percent ?? 0
  const color = p > 90 ? '#f56c6c' : p > 70 ? '#e6a23c' : '#409eff'
  return makeGaugeOption(p, 'CPU', color)
})

const memGaugeOption = computed(() => {
  const p = metrics.value?.memory?.percent ?? 0
  const color = p > 90 ? '#f56c6c' : p > 70 ? '#e6a23c' : '#67c23a'
  return makeGaugeOption(p, '内存', color)
})

const swapGaugeOption = computed(() => {
  const p = metrics.value?.swap?.percent ?? 0
  const color = p > 90 ? '#f56c6c' : p > 70 ? '#e6a23c' : '#909399'
  return makeGaugeOption(p, 'Swap', color)
})

const networkChartOption = computed(() => {
  const hist = networkHistory.value
  return {
    tooltip: { trigger: 'axis', formatter: (params: any[]) => {
      return params.map((p: any) => `${p.marker}${p.seriesName}: ${p.value} KB/s`).join('<br/>')
    }},
    legend: { data: ['上行 (KB/s)', '下行 (KB/s)'], bottom: 0 },
    grid: { left: 50, right: 20, top: 20, bottom: 40 },
    xAxis: { type: 'category', data: hist.map(h => h.time), axisLabel: { fontSize: 11 } },
    yAxis: { type: 'value', name: 'KB/s', splitLine: { lineStyle: { type: 'dashed' } } },
    series: [
      {
        name: '上行 (KB/s)',
        type: 'line',
        smooth: true,
        data: hist.map(h => h.send),
        areaStyle: { color: 'rgba(64,158,255,.15)' },
        lineStyle: { color: '#409eff', width: 2 },
        itemStyle: { color: '#409eff' },
      },
      {
        name: '下行 (KB/s)',
        type: 'line',
        smooth: true,
        data: hist.map(h => h.recv),
        areaStyle: { color: 'rgba(103,194,58,.15)' },
        lineStyle: { color: '#67c23a', width: 2 },
        itemStyle: { color: '#67c23a' },
      },
    ],
  }
})

// ── 生命周期 ──────────────────────────────────────────────────
onMounted(() => {
  fetchAll()
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

.mb-3 { margin-bottom: 16px; }

.card-title { font-size: 14px; font-weight: 600; color: $text-primary; }
.card-sub { font-size: 12px; color: $text-secondary; margin-left: 8px; }

.gauge-chart { height: 180px; }
.gauge-detail {
  display: flex;
  justify-content: space-around;
  font-size: 12px;
  color: $text-secondary;
  padding-bottom: 4px;
}

.traffic-chart { height: 280px; }

:deep(.el-card__header) {
  display: flex;
  align-items: center;
  padding: 12px 16px;
}
</style>
