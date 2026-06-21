<template>
  <div class="page-container">
    <!-- 欢迎卡片 -->
    <el-row :gutter="16" class="mb-4">
      <el-col :span="24">
        <div class="welcome-card">
          <div class="welcome-info">
            <el-avatar :size="56" class="welcome-avatar">
              {{ authStore.userInfo?.nickname?.charAt(0) || authStore.userInfo?.username?.charAt(0) }}
            </el-avatar>
            <div>
              <h2 class="welcome-title">你好，{{ authStore.userInfo?.nickname || authStore.userInfo?.username }} 👋</h2>
              <p class="welcome-sub">{{ greeting }}，欢迎使用若茗 PaaS 管理平台</p>
            </div>
          </div>
          <div class="welcome-meta">
            <span class="meta-item">
              <el-icon><Clock /></el-icon>
              {{ currentTime }}
            </span>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="mb-4">
      <el-col v-for="stat in stats" :key="stat.label" :xs="12" :sm="6">
        <div class="stat-card" :style="{ '--accent': stat.color }">
          <div class="stat-icon">
            <el-icon :size="28">
              <component :is="stat.icon" />
            </el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">
              <span v-if="!statsLoading">{{ stat.value }}</span>
              <el-skeleton-item v-else variant="text" style="width: 60px" />
            </div>
            <div class="stat-label">{{ stat.label }}</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 图表区 -->
    <el-row :gutter="16">
      <el-col :xs="24" :md="14">
        <div class="page-card">
          <div class="card-header">
            <span class="card-title">AI 调用趋势（近7天）</span>
          </div>
          <v-chart class="chart" :option="callTrendOption" autoresize />
        </div>
      </el-col>
      <el-col :xs="24" :md="10">
        <div class="page-card">
          <div class="card-header">
            <span class="card-title">Token 消耗分布</span>
          </div>
          <v-chart class="chart" :option="tokenDistOption" autoresize />
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Clock } from '@element-plus/icons-vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { useAuthStore } from '@/store/auth'
import { formatDate } from '@/utils/format'
import { dashboardApi } from '@/api/dashboard'
import dayjs from 'dayjs'

use([CanvasRenderer, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent])

const authStore = useAuthStore()
const statsLoading = ref(true)

const currentTime = ref(formatDate(new Date()))

// 更新时间
setInterval(() => {
  currentTime.value = formatDate(new Date())
}, 60000)

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 6) return '凌晨好'
  if (h < 12) return '上午好'
  if (h < 18) return '下午好'
  return '晚上好'
})

const stats = ref([
  { label: '总用户数', value: '-', icon: 'User', color: '#1677ff' },
  { label: '活跃租户', value: '-', icon: 'OfficeBuilding', color: '#52c41a' },
  { label: '今日 AI 调用', value: '-', icon: 'MagicStick', color: '#faad14' },
  { label: '今日 Token 消耗', value: '-', icon: 'Coin', color: '#ff4d4f' },
])

// 加载统计数据
onMounted(async () => {
  try {
    const { data } = await dashboardApi.stats()
    stats.value[0].value = String(data.total_users || 0)
    stats.value[1].value = String(data.active_tenants || 0)
    stats.value[2].value = String(data.today_calls || 0).replace(/\B(?=(\d{3})+(?!\d))/g, ',')
    stats.value[3].value = formatToken(data.today_tokens || 0)
  } catch {
    // 使用默认值
    stats.value[0].value = '0'
    stats.value[1].value = '0'
    stats.value[2].value = '0'
    stats.value[3].value = '0'
  } finally {
    statsLoading.value = false
  }
})

// 格式化 Token 数量
function formatToken(count: number): string {
  if (count >= 1000000) {
    return (count / 1000000).toFixed(1) + 'M'
  }
  if (count >= 1000) {
    return (count / 1000).toFixed(1) + 'K'
  }
  return String(count)
}

// AI 调用趋势图
const last7Days = Array.from({ length: 7 }, (_, i) =>
  dayjs().subtract(6 - i, 'day').format('MM-DD')
)

// 模拟趋势数据（后续可接入真实数据）
const callTrendOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 40, right: 20, top: 20, bottom: 30 },
  xAxis: { type: 'category', data: last7Days, axisLine: { lineStyle: { color: '#ddd' } } },
  yAxis: { type: 'value', splitLine: { lineStyle: { type: 'dashed' } } },
  series: [{
    name: 'AI调用次数',
    type: 'line',
    smooth: true,
    data: [1200, 980, 1560, 2100, 1800, 2340, 3542],
    areaStyle: { color: 'rgba(22,119,255,.12)' },
    lineStyle: { color: '#1677ff', width: 2 },
    itemStyle: { color: '#1677ff' },
  }],
}))

// Token 分布饼图
const tokenDistOption = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {c} K ({d}%)' },
  legend: { bottom: 10, itemWidth: 12, itemHeight: 12 },
  series: [{
    type: 'pie',
    radius: ['45%', '70%'],
    center: ['50%', '45%'],
    data: [
      { name: '文档理解', value: 68 },
      { name: '对话问答', value: 45 },
      { name: 'RAG 检索', value: 28 },
      { name: '代码生成', value: 15 },
    ],
    itemStyle: { borderRadius: 4, borderWidth: 2, borderColor: '#fff' },
  }],
}))
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.mb-4 { margin-bottom: 16px; }

.welcome-card {
  background: linear-gradient(135deg, #1677ff 0%, #4096ff 100%);
  border-radius: 10px;
  padding: 24px 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #fff;

  .welcome-info {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .welcome-avatar { background: rgba(255,255,255,.3); font-size: 22px; font-weight: 700; }
  .welcome-title { font-size: 20px; font-weight: 600; margin-bottom: 4px; }
  .welcome-sub { font-size: 13px; opacity: .85; }

  .welcome-meta {
    .meta-item {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      opacity: .85;
    }
  }
}

.stat-card {
  background: #fff;
  border-radius: 10px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,.06);
  border-left: 4px solid var(--accent);

  .stat-icon {
    width: 52px;
    height: 52px;
    border-radius: 10px;
    background: color-mix(in srgb, var(--accent) 12%, transparent);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--accent);
    flex-shrink: 0;
  }

  .stat-value { font-size: 24px; font-weight: 700; color: $text-primary; }
  .stat-label { font-size: 12px; color: $text-secondary; margin-top: 4px; }
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  .card-title { font-size: 15px; font-weight: 600; color: $text-primary; }
}

.chart { height: 260px; }
</style>
