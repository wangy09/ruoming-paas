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
            v-for="color in PRESET_COLORS"
            :key="color"
            class="color-preset"
            :class="{ active: primaryColor === color }"
            :style="{ backgroundColor: color }"
            :aria-label="`切换主题色 ${color}`"
            @click="handlePrimaryColorChange(color)"
          />
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
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useAppStore } from '@/store/app'

const PRESET_COLORS = ['#1677ff', '#409eff', '#722ed1', '#13c2c2', '#52c41a', '#faad14', '#ff4d4f']

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
  gap: 10px;
  margin: 8px 0 14px;
}

.color-preset {
  width: 24px;
  height: 24px;
  border: 2px solid transparent;
  border-radius: 50%;
  cursor: pointer;
  transition: transform 0.15s, border-color 0.15s;

  &:hover {
    transform: scale(1.08);
  }

  &.active {
    border-color: $text-primary;
  }
}
</style>
