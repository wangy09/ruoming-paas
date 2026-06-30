<template>
  <div class="basic-layout" :class="{ 'sidebar-collapsed': appStore.sidebarCollapsed }">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="logo">
        <img :src="appStore.logoUrl" alt="logo" class="logo-img" />
        <span v-show="!appStore.sidebarCollapsed" class="logo-text">{{ appStore.appTitle }}</span>
      </div>
      <SidebarMenu />
    </aside>

    <!-- 主内容区 -->
    <div class="main-wrapper">
      <!-- 顶部 Header -->
      <header class="header">
        <div class="header-left">
          <el-icon class="collapse-btn" @click="appStore.toggleSidebar()">
            <component :is="appStore.sidebarCollapsed ? 'Expand' : 'Fold'" />
          </el-icon>
          <!-- 面包屑 -->
          <el-breadcrumb separator="/">
            <el-breadcrumb-item v-for="item in breadcrumbs" :key="item.path" :to="item.path">
              {{ item.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="header-right">
          <!-- 接口错误记录 -->
          <ErrorLogDrawer />

          <!-- 新消息提醒 -->
          <MessageBell />

          <!-- 暗色模式 -->
          <el-tooltip :content="appStore.isDark ? '切换亮色' : '切换暗色'">
            <el-icon class="header-icon" @click="appStore.toggleDark()">
              <component :is="appStore.isDark ? 'Sunny' : 'Moon'" />
            </el-icon>
          </el-tooltip>

          <!-- 用户头像 -->
          <el-dropdown trigger="click" @command="handleUserCommand">
            <div class="user-avatar">
              <el-avatar :size="32" :src="authStore.userInfo?.avatar">
                {{ authStore.userInfo?.nickname?.charAt(0) || authStore.userInfo?.username?.charAt(0) }}
              </el-avatar>
              <span class="username">{{ authStore.userInfo?.nickname || authStore.userInfo?.username }}</span>
              <el-icon><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人设置</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <!-- 标签页 -->
      <TabsBar />

      <!-- 路由视图 -->
      <main class="content">
        <router-view v-slot="{ Component, route }">
          <keep-alive :include="appStore.cachedViews">
            <component :is="Component" :key="route.path" />
          </keep-alive>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import { useAuthStore } from '@/store/auth'
import { useAppStore } from '@/store/app'
import { usePermissionStore } from '@/store/permission'
import SidebarMenu from './components/SidebarMenu.vue'
import TabsBar from './components/TabsBar.vue'
import ErrorLogDrawer from './components/ErrorLogDrawer.vue'
import MessageBell from './components/MessageBell.vue'
import { resetRouter } from '@/router/guard'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const appStore = useAppStore()
const permStore = usePermissionStore()

onMounted(() => {
  void appStore.loadPublicConfig()
})

// 面包屑
const breadcrumbs = computed(() => {
  return route.matched
    .filter(r => r.meta.title)
    .map(r => ({ path: r.path, title: r.meta.title as string }))
})

async function handleUserCommand(cmd: string) {
  if (cmd === 'logout') {
    await ElMessageBox.confirm('确定退出登录？', '提示', { type: 'warning' })
    await authStore.logout()
    permStore.reset()
    resetRouter()
    router.push('/login')
  } else if (cmd === 'profile') {
    router.push('/profile')
  }
}
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.basic-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

// ── 侧边栏 ────────────────────────────────────────────────────────────────────
.sidebar {
  width: $sidebar-width;
  flex-shrink: 0;
  height: 100vh;
  background: $bg-sidebar;
  display: flex;
  flex-direction: column;
  transition: width 0.25s ease;
  overflow: hidden;

  .logo {
    height: $header-height;
    display: flex;
    align-items: center;
    padding: 0 18px;
    gap: 10px;
    border-bottom: 1px solid rgba(255,255,255,.08);
    flex-shrink: 0;

    .logo-img { width: 28px; height: 28px; flex-shrink: 0; }
    .logo-text {
      color: #fff;
      font-size: 16px;
      font-weight: 700;
      white-space: nowrap;
      overflow: hidden;
    }
  }
}

.basic-layout.sidebar-collapsed .sidebar {
  width: $sidebar-collapsed-width;
}

// ── 主内容区 ──────────────────────────────────────────────────────────────────
.main-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.header {
  height: $header-height;
  background: #fff;
  border-bottom: 1px solid $border-color;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  flex-shrink: 0;
  box-shadow: 0 1px 4px rgba(0,21,41,.08);

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .collapse-btn {
    font-size: 18px;
    cursor: pointer;
    color: $text-regular;
    &:hover { color: $primary-color; }
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .header-icon {
    font-size: 18px;
    cursor: pointer;
    color: $text-regular;
    &:hover { color: $primary-color; }
  }

  .user-avatar {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    padding: 4px 8px;
    border-radius: $border-radius;
    &:hover { background: rgba(0,0,0,.04); }

    .username { font-size: 13px; color: $text-primary; }
  }
}

.content {
  flex: 1;
  overflow: auto;
  background: $bg-base;
}
</style>
