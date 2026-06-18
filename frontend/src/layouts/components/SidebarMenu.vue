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
      <template v-for="route in visibleRoutes" :key="route.path">
        <!-- 有子菜单 -->
        <el-sub-menu
          v-if="route.children && route.children.length"
          :index="route.path"
        >
          <template #title>
            <el-icon v-if="route.meta?.icon">
              <component :is="route.meta.icon" />
            </el-icon>
            <span>{{ route.meta?.title }}</span>
          </template>
          <el-menu-item
            v-for="child in visibleChildren(route)"
            :key="child.path"
            :index="resolvePath(route.path, child.path)"
          >
            <el-icon v-if="child.meta?.icon">
              <component :is="child.meta.icon" />
            </el-icon>
            <template #title>{{ child.meta?.title }}</template>
          </el-menu-item>
        </el-sub-menu>

        <!-- 无子菜单（直接叶子节点）-->
        <el-menu-item v-else :index="route.path">
          <el-icon v-if="route.meta?.icon">
            <component :is="route.meta.icon" />
          </el-icon>
          <template #title>{{ route.meta?.title }}</template>
        </el-menu-item>
      </template>
    </el-menu>
  </el-scrollbar>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/store/app'
import { useAuthStore } from '@/store/auth'
import { usePermissionStore } from '@/store/permission'
import { asyncRoutes } from '@/router/index'
import type { RouteRecordRaw } from 'vue-router'

const route = useRoute()
const appStore = useAppStore()
const authStore = useAuthStore()
const permStore = usePermissionStore()

const activeMenu = computed(() => route.path)

// 过滤不显示的顶层路由
const visibleRoutes = computed(() => {
  return asyncRoutes.filter(r => {
    if (r.meta?.hidden) return false
    if (authStore.isSuperplatform) return true
    // 至少有一个子菜单有权限
    if (r.children?.length) {
      return r.children.some(child =>
        !child.meta?.permCode || permStore.hasPermission(child.meta.permCode as string)
      )
    }
    return !r.meta?.permCode || permStore.hasPermission(r.meta.permCode as string)
  })
})

function visibleChildren(route: RouteRecordRaw) {
  return (route.children || []).filter(child => {
    if (child.meta?.hidden) return false
    if (authStore.isSuperplatform) return true
    return !child.meta?.permCode || permStore.hasPermission(child.meta.permCode as string)
  })
}

function resolvePath(parentPath: string, childPath: string) {
  if (childPath.startsWith('/')) return childPath
  return `${parentPath}/${childPath}`
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
