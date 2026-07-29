<template>
  <div class="page-container">
    <section class="hero-card" :style="{ '--hero-accent': dashboardProfile.color }">
      <div class="hero-main">
        <el-avatar :size="64" class="hero-avatar">
          {{ avatarText }}
        </el-avatar>
        <div class="hero-copy">
          <div class="hero-kicker">{{ greeting }}，{{ displayName }}</div>
          <h2 class="hero-title">{{ dashboardProfile.title }}</h2>
          <p class="hero-desc">{{ dashboardProfile.description }}</p>
          <div class="hero-tags">
            <el-tag effect="dark" round>{{ dashboardProfile.label }}</el-tag>
            <el-tag v-if="tenantLabel" effect="plain" round>{{ tenantLabel }}</el-tag>
            <el-tag v-for="role in roleLabels" :key="role" effect="plain" round>{{ role }}</el-tag>
          </div>
        </div>
      </div>
      <div class="hero-side">
        <div class="time-card">
          <div class="time-label">当前时间</div>
          <div class="time-value">{{ currentTime }}</div>
        </div>
        <div class="hero-actions">
          <el-button type="primary" plain @click="refreshDashboard">
            刷新首页
          </el-button>
          <el-button plain @click="openPreferenceDialog">
            首页设置
          </el-button>
        </div>
      </div>
    </section>

    <el-row v-if="isWidgetVisible('stats')" :gutter="16" class="section-row">
      <el-col v-for="stat in visibleStats" :key="stat.label" :xs="12" :sm="6">
        <div class="stat-card" :style="{ '--accent': stat.color }">
          <div class="stat-icon">
            <el-icon :size="26">
              <component :is="stat.icon" />
            </el-icon>
          </div>
          <div class="stat-content">
            <div class="stat-value">
              <span v-if="!statsLoading">{{ stat.value }}</span>
              <el-skeleton-item v-else variant="text" style="width: 64px" />
            </div>
            <div class="stat-label">{{ stat.label }}</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row v-if="isWidgetVisible('quick_entries') || isWidgetVisible('todos')" :gutter="16" class="section-row">
      <el-col v-if="isWidgetVisible('quick_entries')" :xs="24" :lg="isWidgetVisible('todos') ? 16 : 24">
        <div class="page-card">
          <div class="card-header">
            <div>
              <span class="card-title">常用入口</span>
              <span class="card-subtitle">我的常用入口优先展示，并按权限过滤</span>
            </div>
            <el-button link type="primary" @click="openPreferenceDialog">管理入口</el-button>
          </div>
          <div class="quick-grid">
            <button
              v-for="entry in availableQuickEntries"
              :key="entry.path"
              class="quick-entry"
              :style="{ '--entry-color': entry.color }"
              @click="router.push(entry.path)"
            >
              <span class="quick-icon">
                <el-icon><component :is="entry.icon" /></el-icon>
              </span>
              <span class="quick-title">{{ entry.title }}</span>
              <span class="quick-desc">{{ entry.desc }}</span>
            </button>
          </div>
          <el-empty v-if="!availableQuickEntries.length" description="暂无可用快捷入口" :image-size="80" />
        </div>
      </el-col>

      <el-col v-if="isWidgetVisible('todos')" :xs="24" :lg="isWidgetVisible('quick_entries') ? 8 : 24">
        <div class="page-card todo-card">
          <div class="card-header">
            <div>
              <span class="card-title">今日关注</span>
              <span class="card-subtitle">优先处理消息和基础配置</span>
            </div>
          </div>
          <div class="todo-list">
            <div v-for="todo in todos" :key="todo.title" class="todo-item" @click="router.push(todo.path)">
              <div class="todo-dot" :style="{ backgroundColor: todo.color }" />
              <div class="todo-content">
                <div class="todo-title">{{ todo.title }}</div>
                <div class="todo-desc">{{ todo.desc }}</div>
              </div>
              <el-tag size="small" :type="todo.type">{{ todo.value }}</el-tag>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-row
      v-if="isWidgetVisible('messages') || isWidgetVisible('notices') || isWidgetVisible('workbench')"
      :gutter="16"
      class="section-row"
    >
      <el-col v-if="isWidgetVisible('messages')" :xs="24" :lg="8">
        <div class="page-card">
          <div class="card-header">
            <div>
              <span class="card-title">我的消息</span>
              <span class="card-subtitle">最近收到的站内消息</span>
            </div>
            <el-button link type="primary" @click="router.push('/message/inbox')">查看全部</el-button>
          </div>
          <div v-if="messages.length" class="list-panel">
            <div v-for="msg in messages" :key="msg.id" class="list-item">
              <div class="list-title">
                <span class="text-ellipsis">{{ msg.title }}</span>
                <el-tag v-if="!msg.is_read" size="small" type="danger">未读</el-tag>
              </div>
              <div class="list-meta">{{ formatDateTime(msg.created_at) }}</div>
            </div>
          </div>
          <el-empty v-else description="暂无消息" :image-size="80" />
        </div>
      </el-col>

      <el-col v-if="isWidgetVisible('notices')" :xs="24" :lg="8">
        <div class="page-card">
          <div class="card-header">
            <div>
              <span class="card-title">平台公告</span>
              <span class="card-subtitle">已发布的最新公告</span>
            </div>
            <el-button link type="primary" @click="router.push('/message/notices')">查看公告</el-button>
          </div>
          <div v-if="notices.length" class="list-panel">
            <div v-for="notice in notices" :key="notice.id" class="list-item">
              <div class="list-title">
                <span class="text-ellipsis">{{ notice.title }}</span>
                <el-tag size="small" effect="plain">{{ noticeTargetLabel(notice.target_type) }}</el-tag>
              </div>
              <div class="list-meta">{{ formatDateTime(notice.published_at || notice.created_at) }}</div>
            </div>
          </div>
          <el-empty v-else description="暂无公告" :image-size="80" />
        </div>
      </el-col>

      <el-col v-if="isWidgetVisible('workbench')" :xs="24" :lg="8">
        <div class="page-card">
          <div class="card-header">
            <div>
              <span class="card-title">{{ workbenchTitle }}</span>
              <span class="card-subtitle">{{ workbenchSubtitle }}</span>
            </div>
          </div>
          <div class="workbench-list">
            <div v-for="item in workbenchItems" :key="item.label" class="workbench-item">
              <span class="workbench-label">{{ item.label }}</span>
              <span class="workbench-value">{{ item.value }}</span>
            </div>
          </div>
          <div class="workbench-footer">
            <el-button
              v-for="action in workbenchActions"
              :key="action.path"
              size="small"
              @click="router.push(action.path)"
            >
              {{ action.label }}
            </el-button>
          </div>
        </div>
      </el-col>
    </el-row>

    <el-dialog
      v-model="preferenceDialogVisible"
      title="首页设置"
      width="720px"
      append-to-body
    >
      <div class="preference-panel">
        <div class="preference-section">
          <div class="preference-title">首页模板</div>
          <div class="preference-tip">
            自动模式会优先使用角色默认首页，再按当前用户身份兜底判断；手动选择后只影响当前账号。
            当前来源：{{ preferenceSource === 'user' ? '个人偏好' : '系统默认' }}
          </div>
          <el-radio-group v-model="preferenceForm.template_type" class="template-radio-group">
            <el-radio-button v-for="item in templateOptions" :key="item.value" :label="item.value">
              {{ item.label }}
            </el-radio-button>
          </el-radio-group>
        </div>

        <div class="preference-section">
          <div class="preference-title">组件显示</div>
          <div class="widget-options">
            <el-checkbox
              v-for="widget in widgetOptions"
              :key="widget.key"
              v-model="preferenceForm.widgets[widget.key]"
            >
              <span class="widget-label">{{ widget.label }}</span>
              <span class="widget-desc">{{ widget.desc }}</span>
            </el-checkbox>
          </div>
        </div>

        <div class="preference-section">
          <div class="preference-title">我的常用入口</div>
          <div class="preference-tip">
            只能从当前账号有权限访问的菜单中选择，首页会优先展示这些入口。
          </div>
          <el-select
            v-model="selectedQuickEntryPaths"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="选择要加入首页的菜单"
            class="quick-entry-select"
          >
            <el-option
              v-for="item in availableMenuOptions"
              :key="item.path"
              :label="item.title"
              :value="item.path"
            >
              <span class="menu-option-title">{{ item.title }}</span>
              <span class="menu-option-path">{{ item.path }}</span>
            </el-option>
          </el-select>

          <div v-if="preferenceForm.quick_entries.length" class="quick-entry-config-list">
            <div v-for="(entry, index) in preferenceForm.quick_entries" :key="entry.path" class="quick-entry-config-item">
              <div class="quick-entry-config-main">
                <el-icon><component :is="entry.icon || 'Menu'" /></el-icon>
                <div>
                  <div class="quick-entry-config-title">{{ entry.title }}</div>
                  <div class="quick-entry-config-path">{{ entry.path }}</div>
                </div>
              </div>
              <div class="quick-entry-config-actions">
                <el-button link :disabled="index === 0" @click="moveQuickEntry(index, -1)">上移</el-button>
                <el-button link :disabled="index === preferenceForm.quick_entries.length - 1" @click="moveQuickEntry(index, 1)">下移</el-button>
                <el-button link type="danger" @click="removeQuickEntry(index)">移除</el-button>
              </div>
            </div>
          </div>
          <el-empty v-else description="还没有自定义常用入口" :image-size="72" />
        </div>
      </div>
      <template #footer>
        <el-button @click="resetPreferences">恢复默认</el-button>
        <el-button @click="preferenceDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="preferenceSaving" @click="savePreferences">
          保存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onBeforeUnmount, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { formatDate } from '@/utils/format'
import { useDashboardPreference } from './composables/useDashboardPreference'
import { useDashboardData } from './composables/useDashboardData'

const router = useRouter()
const currentTime = ref(formatDate(new Date()))
let timer: number | undefined

// 使用偏好设置 composable
const {
  preferenceDialogVisible,
  preferenceSaving,
  preferenceSource,
  preferenceForm,
  templateOptions,
  widgetOptions,
  greeting,
  displayName,
  avatarText,
  roleLabels,
  tenantLabel,
  dashboardProfile,
  availableMenuOptions,
  selectedQuickEntryPaths,
  availableQuickEntries,
  isWidgetVisible,
  moveQuickEntry,
  removeQuickEntry,
  loadPreferences,
  openPreferenceDialog,
  savePreferences,
  resetPreferences,
  formatDateTime,
  noticeTargetLabel,
} = useDashboardPreference()

// 使用数据 composable
const {
  statsLoading,
  messages,
  notices,
  baseStats,
  visibleStats,
  loadStats,
  loadWorkbenchData,
  refreshDashboard,
  getTodos,
  getWorkbenchTitle,
  getWorkbenchSubtitle,
  getWorkbenchItems,
  getWorkbenchActions,
} = useDashboardData()

// 计算属性 - 依赖 dashboardProfile 的动态内容
const todos = computed(() => getTodos(dashboardProfile.value.type))
const workbenchTitle = computed(() => getWorkbenchTitle(dashboardProfile.value.type))
const workbenchSubtitle = computed(() => getWorkbenchSubtitle(dashboardProfile.value.type))
const workbenchItems = computed(() => getWorkbenchItems(dashboardProfile.value.type))
const workbenchActions = computed(() => getWorkbenchActions(dashboardProfile.value.type))

onMounted(() => {
  void loadPreferences()
  void refreshDashboard()
  timer = window.setInterval(() => {
    currentTime.value = formatDate(new Date())
  }, 60000)
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.section-row { margin-top: 16px; }

.hero-card {
  position: relative;
  overflow: hidden;
  min-height: 188px;
  border-radius: 16px;
  padding: 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  color: #fff;
  background:
    radial-gradient(circle at 88% 16%, rgba(255, 255, 255, 0.2), transparent 26%),
    linear-gradient(135deg, color-mix(in srgb, var(--hero-accent) 82%, #0f172a), color-mix(in srgb, var(--hero-accent) 48%, #0f172a));
  box-shadow: 0 16px 42px color-mix(in srgb, var(--hero-accent) 16%, transparent);

  &::after {
    content: '';
    position: absolute;
    right: -70px;
    bottom: -90px;
    width: 260px;
    height: 260px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.12);
  }
}

.hero-main {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 18px;
}

.hero-avatar {
  background: rgba(255, 255, 255, 0.26);
  color: #fff;
  font-size: 26px;
  font-weight: 700;
  border: 1px solid rgba(255, 255, 255, 0.34);
}

.hero-kicker {
  font-size: 14px;
  opacity: 0.86;
}

.hero-title {
  margin: 8px 0 8px;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.hero-desc {
  max-width: 680px;
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  opacity: 0.9;
}

.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.hero-side {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 12px;
  min-width: 210px;
}

.hero-actions {
  display: flex;
  gap: 8px;
}

.time-card {
  width: 210px;
  padding: 14px 16px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.22);
  backdrop-filter: blur(8px);
}

.time-label {
  font-size: 12px;
  opacity: 0.78;
}

.time-value {
  margin-top: 6px;
  font-size: 15px;
  font-weight: 600;
}

.stat-card {
  height: 104px;
  background: var(--app-bg-card);
  border-radius: 14px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
  border-left: 4px solid var(--accent);

  .stat-icon {
    width: 50px;
    height: 50px;
    border-radius: 14px;
    background: color-mix(in srgb, var(--accent) 12%, transparent);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--accent);
    flex-shrink: 0;
  }

  .stat-value { font-size: 24px; font-weight: 700; color: var(--app-text-primary); }
  .stat-label { font-size: 12px; color: var(--app-text-secondary); margin-top: 4px; }
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;

  .card-title {
    display: block;
    font-size: 15px;
    font-weight: 600;
    color: var(--app-text-primary);
  }

  .card-subtitle {
    display: block;
    margin-top: 4px;
    color: var(--app-text-secondary);
    font-size: 12px;
  }
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.quick-entry {
  min-height: 118px;
  padding: 16px;
  border: 1px solid var(--app-border-color);
  border-radius: 14px;
  background: var(--app-bg-card);
  text-align: left;
  cursor: pointer;
  transition: transform 0.18s, box-shadow 0.18s, border-color 0.18s;

  &:hover {
    transform: translateY(-2px);
    border-color: color-mix(in srgb, var(--entry-color) 42%, var(--app-border-color));
    box-shadow: 0 12px 28px color-mix(in srgb, var(--entry-color) 12%, transparent);
  }
}

.quick-icon {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--entry-color);
  background: color-mix(in srgb, var(--entry-color) 12%, transparent);
}

.quick-title {
  display: block;
  margin-top: 12px;
  color: var(--app-text-primary);
  font-weight: 600;
}

.quick-desc {
  display: block;
  margin-top: 6px;
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.todo-card {
  height: 100%;
}

.todo-list,
.list-panel,
.workbench-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.todo-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px 0;
  border-bottom: 1px solid var(--app-border-color);
  cursor: pointer;

  &:last-child {
    border-bottom: none;
  }
}

.todo-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.todo-content {
  flex: 1;
  min-width: 0;
}

.todo-title {
  color: var(--app-text-primary);
  font-weight: 600;
}

.todo-desc {
  margin-top: 4px;
  color: var(--app-text-secondary);
  font-size: 12px;
}

.list-item {
  padding: 12px 0;
  border-bottom: 1px solid var(--app-border-color);

  &:last-child {
    border-bottom: none;
  }
}

.list-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  color: var(--app-text-primary);
  font-weight: 500;
}

.list-meta {
  margin-top: 6px;
  color: var(--app-text-secondary);
  font-size: 12px;
}

.text-ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workbench-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-radius: 12px;
  background: var(--app-bg-page);
}

.workbench-label {
  color: var(--app-text-secondary);
}

.workbench-value {
  max-width: 150px;
  overflow: hidden;
  color: var(--app-text-primary);
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workbench-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.preference-panel {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.preference-section {
  padding-bottom: 18px;
  border-bottom: 1px solid var(--app-border-color);

  &:last-child {
    padding-bottom: 0;
    border-bottom: none;
  }
}

.preference-title {
  color: var(--app-text-primary);
  font-weight: 600;
}

.preference-tip {
  margin-top: 6px;
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.template-radio-group {
  margin-top: 14px;
}

.widget-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;

  :deep(.el-checkbox) {
    height: auto;
    align-items: flex-start;
    margin-right: 0;
    padding: 12px;
    border: 1px solid var(--app-border-color);
    border-radius: 10px;
  }
}

.widget-label {
  display: block;
  color: var(--app-text-primary);
  font-weight: 500;
}

.widget-desc {
  display: block;
  margin-top: 4px;
  color: var(--app-text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.quick-entry-select {
  width: 100%;
  margin-top: 14px;
}

.menu-option-title {
  font-weight: 500;
}

.menu-option-path {
  float: right;
  margin-left: 16px;
  color: var(--app-text-secondary);
  font-size: 12px;
}

.quick-entry-config-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 14px;
}

.quick-entry-config-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid var(--app-border-color);
  border-radius: 12px;
  background: var(--app-bg-page);
}

.quick-entry-config-main {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 10px;
  color: var(--app-text-primary);
}

.quick-entry-config-title {
  font-weight: 500;
}

.quick-entry-config-path {
  margin-top: 3px;
  color: var(--app-text-secondary);
  font-size: 12px;
}

.quick-entry-config-actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  gap: 6px;
}

@media (max-width: 1280px) {
  .quick-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .hero-card,
  .hero-main {
    align-items: flex-start;
    flex-direction: column;
  }

  .hero-side,
  .time-card {
    width: 100%;
    min-width: 0;
    align-items: stretch;
  }

  .quick-grid {
    grid-template-columns: 1fr;
  }

  .hero-actions,
  .widget-options {
    flex-direction: column;
    grid-template-columns: 1fr;
  }

  .quick-entry-config-item,
  .quick-entry-config-actions {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
