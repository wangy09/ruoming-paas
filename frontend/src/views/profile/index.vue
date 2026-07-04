<template>
  <div class="profile-page">
    <el-row :gutter="20">
      <!-- 左侧：个人信息 -->
      <el-col :span="12">
        <el-card class="card">
          <template #header>
            <div class="card-header">
              <span>个人信息</span>
            </div>
          </template>
          <el-form :model="profileForm" label-width="80px" label-position="left">
            <el-form-item label="用户名">
              <el-input :model-value="authStore.userInfo?.username" disabled />
            </el-form-item>
            <el-form-item label="昵称">
              <el-input v-model="profileForm.nickname" placeholder="请输入昵称" />
            </el-form-item>
            <el-form-item label="邮箱">
              <el-input v-model="profileForm.email" placeholder="请输入邮箱" />
            </el-form-item>
            <el-form-item label="手机号">
              <el-input v-model="profileForm.phone" placeholder="请输入手机号" />
            </el-form-item>
            <el-form-item label="所属租户">
              <el-input :model-value="authStore.userInfo?.tenant_code || '平台级'" disabled />
            </el-form-item>
            <el-form-item label="角色">
              <el-tag v-for="role in authStore.userInfo?.roles" :key="role.id" size="small" class="mr-1">
                {{ role.name }}
              </el-tag>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="profileLoading" @click="handleUpdateProfile">
                保存修改
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <!-- 右侧：修改密码 -->
      <el-col :span="12">
        <el-card class="card">
          <template #header>
            <div class="card-header">
              <span>修改密码</span>
            </div>
          </template>
          <el-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-width="100px" label-position="left">
            <el-form-item label="原密码" prop="old_password">
              <el-input v-model="pwdForm.old_password" type="password" show-password placeholder="请输入原密码" />
            </el-form-item>
            <el-form-item label="新密码" prop="new_password">
              <el-input v-model="pwdForm.new_password" type="password" show-password placeholder="请输入新密码" />
            </el-form-item>
            <el-form-item label="确认密码" prop="confirm_password">
              <el-input v-model="pwdForm.confirm_password" type="password" show-password placeholder="请确认新密码" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="pwdLoading" @click="handleChangePassword">
                修改密码
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="24">
        <el-card class="card preference-card">
          <template #header>
            <div class="card-header">
              <span>系统偏好</span>
              <el-tag size="small" effect="plain">仅当前浏览器生效</el-tag>
            </div>
          </template>
          <div class="preference-grid">
            <div class="preference-item">
              <div>
                <div class="preference-label">主题色</div>
                <div class="preference-tip">{{ appStore.primaryColor }}</div>
              </div>
              <span class="color-dot" :style="{ backgroundColor: appStore.primaryColor }" />
            </div>
            <div class="preference-item">
              <div>
                <div class="preference-label">暗色模式</div>
                <div class="preference-tip">切换页面明暗主题</div>
              </div>
              <el-switch v-model="darkMode" />
            </div>
            <div class="preference-item">
              <div>
                <div class="preference-label">灰色模式</div>
                <div class="preference-tip">页面整体置灰</div>
              </div>
              <el-switch
                :model-value="appStore.visualSettings.grayMode"
                @change="appStore.setGrayMode(Boolean($event))"
              />
            </div>
            <div class="preference-item">
              <div>
                <div class="preference-label">色弱模式</div>
                <div class="preference-tip">辅助状态色区分</div>
              </div>
              <el-switch
                :model-value="appStore.visualSettings.colorWeakMode"
                @change="appStore.setColorWeakMode(Boolean($event))"
              />
            </div>
            <div class="preference-item">
              <div>
                <div class="preference-label">布局显示</div>
                <div class="preference-tip">标签栏 / 面包屑 / 固定 Header</div>
              </div>
              <div class="preference-tags">
                <el-tag :type="appStore.layoutSettings.showTabsBar ? 'success' : 'info'" size="small">
                  标签栏
                </el-tag>
                <el-tag :type="appStore.layoutSettings.showBreadcrumb ? 'success' : 'info'" size="small">
                  面包屑
                </el-tag>
                <el-tag :type="appStore.layoutSettings.fixedHeader ? 'success' : 'info'" size="small">
                  固定 Header
                </el-tag>
              </div>
            </div>
            <div class="preference-actions">
              <el-button @click="handleResetLayout">恢复默认布局</el-button>
              <el-button @click="handleClearPageCache">清理页面缓存</el-button>
              <el-button type="danger" plain @click="handleClearPreferenceCache">
                清理前端偏好
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { useAuthStore } from '@/store/auth'
import { useAppStore } from '@/store/app'
import { userApi } from '@/api/user'
import { authApi } from '@/api/auth'

const authStore = useAuthStore()
const appStore = useAppStore()

const darkMode = computed({
  get: () => appStore.isDark,
  set: (value: boolean) => {
    if (value !== appStore.isDark) appStore.toggleDark()
  },
})

// 个人信息
const profileLoading = ref(false)
const profileForm = reactive({
  nickname: '',
  email: '',
  phone: '',
})

// 修改密码
const pwdFormRef = ref<FormInstance>()
const pwdLoading = ref(false)
const pwdForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

const validateConfirm = (rule: unknown, value: string, callback: (error?: Error) => void) => {
  if (value !== pwdForm.new_password) {
    callback(new Error('两次输入的密码不一致'))
  } else {
    callback()
  }
}

const pwdRules: FormRules = {
  old_password: [
    { required: true, message: '请输入原密码', trigger: 'blur' },
  ],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '密码长度不能少于6位', trigger: 'blur' },
  ],
  confirm_password: [
    { required: true, message: '请确认新密码', trigger: 'blur' },
    { validator: validateConfirm, trigger: 'blur' },
  ],
}

async function handleUpdateProfile() {
  profileLoading.value = true
  try {
    await userApi.update(authStore.userInfo!.id, {
      nickname: profileForm.nickname || undefined,
      email: profileForm.email || undefined,
      phone: profileForm.phone || undefined,
    })
    // 更新本地用户信息
    if (authStore.userInfo) {
      authStore.userInfo.nickname = profileForm.nickname
      authStore.userInfo.email = profileForm.email
      authStore.userInfo.phone = profileForm.phone
    }
    ElMessage.success('个人信息已更新')
  } catch {
    // 错误已在请求拦截器处理
  } finally {
    profileLoading.value = false
  }
}

async function handleChangePassword() {
  await pwdFormRef.value?.validate()
  pwdLoading.value = true
  try {
    await authApi.updatePassword({
      old_password: pwdForm.old_password,
      new_password: pwdForm.new_password,
    })
    ElMessage.success('密码修改成功，请重新登录')
    // 清空密码表单
    pwdForm.old_password = ''
    pwdForm.new_password = ''
    pwdForm.confirm_password = ''
  } catch {
    // 错误已在请求拦截器处理
  } finally {
    pwdLoading.value = false
  }
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
  ElMessage.success('前端偏好已清理')
}

onMounted(() => {
  // 填充当前用户信息
  if (authStore.userInfo) {
    profileForm.nickname = authStore.userInfo.nickname || ''
    profileForm.email = authStore.userInfo.email || ''
    profileForm.phone = authStore.userInfo.phone || ''
  }
})
</script>

<style scoped lang="scss">
.profile-page {
  padding: 20px;
}

.card {
  border-radius: 8px;

  :deep(.el-card__header) {
    padding: 12px 20px;
    border-bottom: 1px solid var(--el-border-color-lighter);
  }
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.mr-1 {
  margin-right: 6px;
}

:deep(.el-form-item) {
  margin-bottom: 18px;
}

.preference-card {
  margin-top: 20px;
}

.preference-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.preference-item,
.preference-actions {
  min-height: 64px;
  padding: 14px 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
}

.preference-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.preference-label {
  color: var(--el-text-color-primary);
  font-size: 14px;
  font-weight: 500;
}

.preference-tip {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.color-dot {
  width: 24px;
  height: 24px;
  border: 2px solid var(--el-border-color);
  border-radius: 50%;
  flex-shrink: 0;
}

.preference-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.preference-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 1200px) {
  .preference-grid {
    grid-template-columns: 1fr;
  }

  .preference-actions {
    justify-content: flex-start;
  }
}
</style>
