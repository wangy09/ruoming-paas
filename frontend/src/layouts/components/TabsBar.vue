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
          @contextmenu.prevent="openContextMenu($event, tab)"
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
          <el-dropdown-item command="close-others">关闭其他</el-dropdown-item>
          <el-dropdown-item command="close-all">关闭全部</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Close, ArrowDown } from '@element-plus/icons-vue'
import { useAppStore } from '@/store/app'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()

const visitedViews = computed(() => appStore.visitedViews)

const isActive = (path: string) => route.path === path

function closeTab(path: string) {
  const idx = visitedViews.value.findIndex(v => v.path === path)
  appStore.removeVisitedView(path)
  // 如果关闭的是当前页，跳转到前一个
  if (isActive(path) && visitedViews.value.length) {
    const target = visitedViews.value[Math.min(idx, visitedViews.value.length - 1)]
    router.push(target.path)
  }
}

function handleTabCommand(cmd: string) {
  if (cmd === 'refresh') {
    router.go(0)
  } else if (cmd === 'close-others') {
    appStore.closeOtherViews(route.path)
  } else if (cmd === 'close-all') {
    appStore.closeAllViews()
    router.push('/dashboard')
  }
}

function openContextMenu(_e: MouseEvent, _tab: { path: string }) {
  // 简化实现：可扩展为真正的右键菜单
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
