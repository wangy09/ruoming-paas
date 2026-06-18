<template>
  <div class="login-page">
    <div class="login-bg" />
    <div class="login-card">
      <div class="login-header">
        <img src="/logo.svg" alt="logo" class="login-logo" />
        <h1 class="login-title">若茗 PaaS</h1>
        <p class="login-subtitle">企业级 AI 应用开发底座</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        class="login-form"
        @keyup.enter="handleLogin"
      >
        <el-form-item prop="tenant_code">
          <el-input
            v-model="form.tenant_code"
            placeholder="租户代码（超管可留空）"
            :prefix-icon="Office"
            clearable
          />
        </el-form-item>

        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            placeholder="用户名"
            :prefix-icon="User"
            clearable
          />
        </el-form-item>

        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="密码"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>

        <el-button
          type="primary"
          class="login-btn"
          :loading="loading"
          @click="handleLogin"
        >
          登 录
        </el-button>
      </el-form>

      <div class="login-footer">
        <span>默认账号：admin / ruoming@2024</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock, OfficeBuilding as Office } from '@element-plus/icons-vue'
import { useAuthStore } from '@/store/auth'
import { usePermissionStore } from '@/store/permission'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const permStore = usePermissionStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  tenant_code: '',
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }, { min: 6, message: '密码至少6位', trigger: 'blur' }],
}

async function handleLogin() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await authStore.login({
      username: form.username,
      password: form.password,
      tenant_code: form.tenant_code || undefined,
    })

    // 加载权限
    await permStore.loadPermissions()

    ElMessage.success('登录成功')
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.replace(redirect)
  } catch (e: unknown) {
    // 错误已由 request 拦截器统一处理
    console.error(e)
  } finally {
    loading.value = false
  }
}
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.login-page {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #001529 0%, #003a8c 50%, #1677ff 100%);
}

.login-bg {
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(circle at 20% 80%, rgba(22,119,255,.15) 0%, transparent 50%),
    radial-gradient(circle at 80% 20%, rgba(82,196,26,.1) 0%, transparent 50%);
}

.login-card {
  position: relative;
  width: 420px;
  background: rgba(255,255,255,.96);
  border-radius: 12px;
  padding: 48px 40px 36px;
  box-shadow: 0 24px 64px rgba(0,0,0,.25);
}

.login-header {
  text-align: center;
  margin-bottom: 36px;

  .login-logo { width: 56px; height: 56px; margin-bottom: 12px; }
  .login-title { font-size: 24px; font-weight: 700; color: $text-primary; }
  .login-subtitle { font-size: 13px; color: $text-secondary; margin-top: 4px; }
}

.login-form {
  :deep(.el-form-item) { margin-bottom: 20px; }
  :deep(.el-input__inner) { height: 42px; }
}

.login-btn {
  width: 100%;
  height: 42px;
  font-size: 15px;
  letter-spacing: 2px;
  margin-top: 8px;
}

.login-footer {
  text-align: center;
  margin-top: 24px;
  font-size: 12px;
  color: $text-secondary;
}
</style>
