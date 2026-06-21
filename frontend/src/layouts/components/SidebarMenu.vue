<template>
  <el-scrollbar class="sidebar-scrollbar">
    <el-menu
      :collapse="appStore.sidebarCollapsed"
      :default-active="activeMenu"
      :unique-opened="true"
      router
      background-color="#001529"
      text-color="rgba(255,255,255,0.65)"
      active-text-color="#ffffff"
      class="sidebar-menu"
    >
      <template v-for="menu in menuTree" :key="menu.id">
        <!-- 有子菜单 -->
        <el-sub-menu
          v-if="menu.children && menu.children.length"
          :index="menu.path || '/' + menu.id"
        >
          <template #title>
            <el-icon v-if="menu.icon">
              <component :is="getIconComponent(menu.icon)" />
            </el-icon>
            <span>{{ menu.title }}</span>
          </template>
          <el-menu-item
            v-for="child in menu.children"
            :key="child.id"
            :index="child.path || '/' + child.id"
          >
            <el-icon v-if="child.icon">
              <component :is="getIconComponent(child.icon)" />
            </el-icon>
            <template #title>{{ child.title }}</template>
          </el-menu-item>
        </el-sub-menu>

        <!-- 无子菜单（直接叶子节点）-->
        <el-menu-item v-else :index="menu.path || '/' + menu.id">
          <el-icon v-if="menu.icon">
            <component :is="getIconComponent(menu.icon)" />
          </el-icon>
          <template #title>{{ menu.title }}</template>
        </el-menu-item>
      </template>
    </el-menu>
  </el-scrollbar>
</template>

<script setup lang="ts">
import { computed, markRaw } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/store/app'
import { usePermissionStore } from '@/store/permission'
import * as ElIcons from '@element-plus/icons-vue'
import type { MenuPermission } from '@/types'

const route = useRoute()
const appStore = useAppStore()
const permStore = usePermissionStore()

const activeMenu = computed(() => route.path)

const menuTree = computed(() => permStore.menuTree)

function getIconComponent(iconName: string | undefined) {
  if (!iconName) return null
  const icon = (ElIcons as Record<string, unknown>)[iconName]
  return icon ? markRaw(icon) : null
}
</script>

<style lang="scss" scoped>
.sidebar-scrollbar {
  flex: 1;
  overflow: hidden;
}

.sidebar-menu {
  border-right: none !important;
  width: 100%;

  :deep(.el-sub-menu__title:hover),
  :deep(.el-menu-item:hover) {
    background-color: rgba(255, 255, 255, 0.08) !important;
  }

  :deep(.el-menu-item.is-active) {
    background-color: var(--el-color-primary) !important;
    color: #ffffff !important;
  }

  &.el-menu--collapse {
    :deep(.el-sub-menu__title span),
    :deep(.el-menu-item span) {
      display: none;
    }
  }
}
</style>
