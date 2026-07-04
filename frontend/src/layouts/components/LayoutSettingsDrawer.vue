<template>
  <el-drawer
    v-model="drawerVisible"
    title="布局设置"
    size="320px"
    append-to-body
    destroy-on-close
  >
    <div class="settings-panel">
      <section class="settings-section">
        <div class="section-title">主题配置</div>
        <div class="setting-item">
          <div>
            <div class="setting-label">主题色</div>
            <div class="setting-tip">同步 Element Plus 主色</div>
          </div>
          <el-color-picker v-model="primaryColor" :predefine="PRESET_COLORS" @change="handlePrimaryColorChange" />
        </div>
        <div class="color-presets">
          <button
            v-for="preset in THEME_PRESETS"
            :key="preset.color"
            class="color-preset"
            :class="{ active: primaryColor === preset.color }"
            :style="{ backgroundColor: preset.color }"
            :aria-label="`切换皮肤 ${preset.name}`"
            @click="handlePrimaryColorChange(preset.color)"
          >
            <span class="preset-name">{{ preset.name }}</span>
          </button>
        </div>
        <div class="setting-item">
          <div>
            <div class="setting-label">暗色模式</div>
            <div class="setting-tip">切换页面明暗主题</div>
          </div>
          <el-switch v-model="darkMode" />
        </div>
      </section>

      <section class="settings-section">
        <div class="section-title">视觉辅助</div>
        <div class="setting-item">
          <div>
            <div class="setting-label">灰色模式</div>
            <div class="setting-tip">页面整体置灰，适合特殊展示场景</div>
          </div>
          <el-switch
            :model-value="appStore.visualSettings.grayMode"
            @change="appStore.setGrayMode(Boolean($event))"
          />
        </div>
        <div class="setting-item">
          <div>
            <div class="setting-label">色弱模式</div>
            <div class="setting-tip">降低颜色辨识压力，辅助区分状态色</div>
          </div>
          <el-switch
            :model-value="appStore.visualSettings.colorWeakMode"
            @change="appStore.setColorWeakMode(Boolean($event))"
          />
        </div>
      </section>

      <section class="settings-section">
        <div class="section-title">布局显示</div>
        <div class="setting-item">
          <div>
            <div class="setting-label">显示标签栏</div>
            <div class="setting-tip">控制 TabsBar 是否展示</div>
          </div>
          <el-switch
            :model-value="appStore.layoutSettings.showTabsBar"
            @change="appStore.setShowTabsBar(Boolean($event))"
          />
        </div>
        <div class="setting-item">
          <div>
            <div class="setting-label">显示面包屑</div>
            <div class="setting-tip">控制 Header 左侧路径导航</div>
          </div>
          <el-switch
            :model-value="appStore.layoutSettings.showBreadcrumb"
            @change="appStore.setShowBreadcrumb(Boolean($event))"
          />
        </div>
        <div class="setting-item">
          <div>
            <div class="setting-label">固定 Header</div>
            <div class="setting-tip">关闭后 Header 随内容滚动</div>
          </div>
          <el-switch
            :model-value="appStore.layoutSettings.fixedHeader"
            @change="appStore.setFixedHeader(Boolean($event))"
          />
        </div>
      </section>

      <section class="settings-section">
        <div class="section-title">缓存与重置</div>
        <div class="action-list">
          <el-button class="action-btn" @click="handleResetLayout">
            恢复默认布局
          </el-button>
          <el-button class="action-btn" @click="handleClearPageCache">
            清理页面缓存
          </el-button>
          <el-button class="action-btn" type="danger" plain @click="handleClearPreferenceCache">
            清理前端偏好
          </el-button>
        </div>
        <div class="setting-tip">
          清理前端偏好会重置标签页、页面缓存、布局和主题偏好，不会退出登录。
        </div>
      </section>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAppStore } from '@/store/app'

const THEME_PRESETS = [
  { name: '若茗蓝', color: '#1677ff' },
  { name: '经典蓝', color: '#409eff' },
  { name: '极客紫', color: '#722ed1' },
  { name: '湖青', color: '#13c2c2' },
  { name: '松石绿', color: '#52c41a' },
  { name: '暖橙', color: '#faad14' },
  { name: '薄暮红', color: '#ff4d4f' },
]
const PRESET_COLORS = THEME_PRESETS.map(item => item.color)

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: boolean): void
}>()

const appStore = useAppStore()
const primaryColor = ref(appStore.primaryColor)

const drawerVisible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const darkMode = computed({
  get: () => appStore.isDark,
  set: (value: boolean) => {
    // VueUse 暗色状态由 toggleDark 统一维护，避免本地状态与 HTML class 不一致
    if (value !== appStore.isDark) appStore.toggleDark()
  },
})

watch(
  () => appStore.primaryColor,
  (color) => {
    primaryColor.value = color
  },
)

function handlePrimaryColorChange(color: string | null) {
  if (!color) return
  primaryColor.value = color
  appStore.setPrimaryColor(color)
}

function handleResetLayout() {
  appStore.resetLayoutSettings()
  appStore.resetVisualSettings()
  ElMessage.success('已恢复默认布局')
}

function handleClearPageCache() {
  appStore.clearPageCache()
  ElMessage.success('页面缓存已清理')
}

async function handleClearPreferenceCache() {
  try {
    await ElMessageBox.confirm(
      '将清理主题色、布局设置、视觉模式、标签页和页面缓存，不会清理登录状态。确定继续？',
      '清理前端偏好',
      { type: 'warning' },
    )
  } catch {
    return
  }
  appStore.clearPreferenceCache()
  primaryColor.value = appStore.primaryColor
  ElMessage.success('前端偏好已清理')
}
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.settings-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.settings-section {
  padding-bottom: 18px;
  border-bottom: 1px solid $border-color;

  &:last-child {
    border-bottom: 0;
  }
}

.section-title {
  margin-bottom: 14px;
  color: $text-primary;
  font-size: 15px;
  font-weight: 600;
}

.setting-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 48px;
}

.setting-label {
  color: $text-primary;
  font-size: 14px;
}

.setting-tip {
  margin-top: 4px;
  color: $text-secondary;
  font-size: 12px;
}

.color-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 8px 0 14px;
}

.color-preset {
  position: relative;
  width: 68px;
  height: 30px;
  border: 2px solid transparent;
  border-radius: 15px;
  color: #fff;
  cursor: pointer;
  transition: transform 0.15s, border-color 0.15s;
  overflow: hidden;

  &:hover {
    transform: translateY(-1px);
  }

  &.active {
    border-color: $text-primary;
  }
}

.preset-name {
  position: relative;
  z-index: 1;
  font-size: 12px;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.28);
}

.action-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 10px;
}

.action-btn {
  width: 100%;
  margin-left: 0;
}
</style>
