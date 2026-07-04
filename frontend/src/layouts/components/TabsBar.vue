<template>
  <div class="tabs-bar" v-if="visitedViews.length">
    <el-scrollbar class="tabs-scrollbar">
      <div class="tabs-container">
        <span
          v-for="tab in visitedViews"
          :key="tab.path"
          class="tab-item"
          :class="{ active: isActive(tab.path) }"
          @click="router.push(tab.path)"
          @contextmenu.prevent.stop="openContextMenu($event, tab)"
        >
          {{ tab.title }}
          <el-icon
            v-if="!tab.affix"
            class="tab-close"
            @click.stop="closeTab(tab.path)"
          >
            <Close />
          </el-icon>
        </span>
      </div>
    </el-scrollbar>

    <!-- 右侧操作 -->
    <el-dropdown trigger="click" @command="handleTabCommand">
      <el-button link class="tabs-action-btn">
        <el-icon><ArrowDown /></el-icon>
      </el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="refresh">刷新当前</el-dropdown-item>
          <el-dropdown-item command="close-left">关闭左侧</el-dropdown-item>
          <el-dropdown-item command="close-right">关闭右侧</el-dropdown-item>
          <el-dropdown-item command="close-others">关闭其他</el-dropdown-item>
          <el-dropdown-item command="close-all">关闭全部</el-dropdown-item>
          <el-dropdown-item divided command="maximize">
            {{ appStore.contentMaximized ? '退出最大化' : '最大化当前' }}
          </el-dropdown-item>
          <el-dropdown-item command="open-new">新窗口打开</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>

    <!-- 右键菜单 -->
    <teleport to="body">
      <transition name="fade">
        <div
          v-if="contextMenuVisible"
          class="context-menu"
          :style="{ left: menuLeft + 'px', top: menuTop + 'px' }"
          @click.stop
        >
          <div class="context-menu-item" @click="handleContextCommand('refresh')">
            <el-icon><Refresh /></el-icon>
            <span>刷新</span>
          </div>
          <div class="context-menu-item" @click="handleContextCommand('close')">
            <el-icon><Close /></el-icon>
            <span>关闭</span>
          </div>
          <div class="context-menu-item" @click="handleContextCommand('close-others')">
            <el-icon><Remove /></el-icon>
            <span>关闭其他</span>
          </div>
          <div class="context-menu-item" @click="handleContextCommand('close-left')">
            <el-icon><ArrowLeft /></el-icon>
            <span>关闭左边</span>
          </div>
          <div class="context-menu-item" @click="handleContextCommand('close-right')">
            <el-icon><ArrowRight /></el-icon>
            <span>关闭右边</span>
          </div>
          <div class="context-menu-divider" />
          <div class="context-menu-item" @click="handleContextCommand('maximize')">
            <el-icon><FullScreen /></el-icon>
            <span>{{ appStore.contentMaximized ? '退出最大化' : '最大化' }}</span>
          </div>
          <div class="context-menu-item" @click="handleContextCommand('open-new')">
            <el-icon><TopRight /></el-icon>
            <span>新窗口打开</span>
          </div>
        </div>
      </transition>
      <!-- 点击空白处关闭菜单 -->
      <div
        v-if="contextMenuVisible"
        class="context-menu-overlay"
        @click="closeContextMenu"
        @contextmenu.prevent.stop="closeContextMenu"
      />
    </teleport>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { ArrowDown, ArrowLeft, ArrowRight, Close, FullScreen, Refresh, Remove, TopRight } from '@element-plus/icons-vue'
import { useAppStore } from '@/store/app'

interface TabItem {
  path: string
  title: string
  affix?: boolean
}

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()

const { visitedViews } = storeToRefs(appStore)

const isActive = (path: string) => route.path === path

// 右键菜单状态
const contextMenuVisible = ref(false)
const menuLeft = ref(0)
const menuTop = ref(0)
const currentTab = ref<TabItem | null>(null)

function closeTab(path: string) {
  const idx = visitedViews.value.findIndex(v => v.path === path)
  appStore.removeVisitedView(path)
  // 如果关闭的是当前页，跳转到前一个
  if (isActive(path) && visitedViews.value.length) {
    const target = visitedViews.value[Math.min(idx, visitedViews.value.length - 1)]
    router.push(target.path)
  } else if (isActive(path)) {
    router.push('/dashboard')
  }
}

function handleTabCommand(cmd: string) {
  executeTabCommand(cmd, route.path)
}

// 右键菜单
function openContextMenu(e: MouseEvent, tab: TabItem) {
  currentTab.value = tab
  // 计算菜单位置，确保不超出屏幕
  const menuWidth = 160
  const menuHeight = 280
  let left = e.clientX
  let top = e.clientY

  if (left + menuWidth > window.innerWidth) {
    left = window.innerWidth - menuWidth - 10
  }
  if (top + menuHeight > window.innerHeight) {
    top = window.innerHeight - menuHeight - 10
  }

  menuLeft.value = left
  menuTop.value = top
  contextMenuVisible.value = true
}

function closeContextMenu() {
  contextMenuVisible.value = false
  currentTab.value = null
}

function handleContextCommand(cmd: string) {
  if (!currentTab.value) return

  executeTabCommand(cmd, currentTab.value.path)
  closeContextMenu()
}

function executeTabCommand(cmd: string, tabPath: string) {
  switch (cmd) {
    case 'refresh':
      // 刷新当前标签页
      if (isActive(tabPath)) {
        router.go(0)
      } else {
        // 先跳转到该页再刷新
        router.push(tabPath).then(() => router.go(0))
      }
      break

    case 'close':
      closeTab(tabPath)
      break

    case 'close-others':
      appStore.closeOtherViews(tabPath)
      ensureActiveTabVisible(tabPath)
      break

    case 'close-left':
      appStore.closeLeftViews(tabPath)
      ensureActiveTabVisible(tabPath)
      break

    case 'close-right':
      appStore.closeRightViews(tabPath)
      ensureActiveTabVisible(tabPath)
      break

    case 'close-all':
      appStore.closeAllViews()
      if (!visitedViews.value.some(v => v.path === route.path)) {
        router.push(visitedViews.value[0]?.path || '/dashboard')
      }
      break

    case 'maximize':
      appStore.toggleContentMaximized()
      break

    case 'open-new':
      // 新窗口打开
      window.open(window.location.origin + tabPath, '_blank')
      break
  }
}

function ensureActiveTabVisible(fallbackPath: string) {
  if (visitedViews.value.some(v => v.path === route.path)) return
  if (visitedViews.value.some(v => v.path === fallbackPath)) {
    router.push(fallbackPath)
    return
  }
  router.push(visitedViews.value[0]?.path || '/dashboard')
}
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.tabs-bar {
  height: $tabbar-height;
  background: #fff;
  border-bottom: 1px solid $border-color;
  display: flex;
  align-items: center;
  padding: 0 8px;
  flex-shrink: 0;
  gap: 4px;
}

.tabs-scrollbar {
  flex: 1;
  :deep(.el-scrollbar__wrap) { overflow-x: auto; overflow-y: hidden; }
}

.tabs-container {
  display: flex;
  align-items: center;
  height: $tabbar-height;
  gap: 4px;
  padding: 4px 0;
  white-space: nowrap;
}

.tab-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  height: 28px;
  padding: 0 10px;
  border: 1px solid $border-color;
  border-radius: 4px;
  font-size: 12px;
  color: $text-regular;
  cursor: pointer;
  user-select: none;
  transition: all .15s;

  &:hover { color: $primary-color; border-color: $primary-color; }

  &.active {
    background: $primary-color;
    border-color: $primary-color;
    color: #fff;
  }

  .tab-close {
    font-size: 12px;
    border-radius: 50%;
    &:hover { background: rgba(0,0,0,.15); }
  }
}

.tabs-action-btn {
  flex-shrink: 0;
  color: $text-regular;
  &:hover { color: $primary-color; }
}
</style>

<style lang="scss">
// 右键菜单样式（不受 scoped 影响）
.context-menu-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 999;
}

.context-menu {
  position: fixed;
  z-index: 1000;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  padding: 4px 0;
  min-width: 140px;
}

.context-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  font-size: 13px;
  color: #606266;
  cursor: pointer;
  transition: all 0.15s;

  .el-icon {
    font-size: 14px;
    color: #909399;
  }

  &:hover {
    background: #f5f7fa;
    color: #409eff;
    
    .el-icon {
      color: #409eff;
    }
  }
}

.context-menu-divider {
  height: 1px;
  background: #e4e7ed;
  margin: 4px 0;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s, transform 0.15s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: scale(0.95);
}
</style>
