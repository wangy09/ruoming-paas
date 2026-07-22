<template>
  <el-dialog :model-value="visible" @update:model-value="emit('update:visible', $event)" :title="editId ? '编辑用户' : '新增用户'" width="500px" destroy-on-close>
    <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
      <el-form-item label="用户名" prop="username">
        <el-input v-model="form.username" :disabled="!!editId" placeholder="登录用户名" />
      </el-form-item>
      <el-form-item label="用户姓名" prop="nickname">
        <el-input v-model="form.nickname" placeholder="用户真实姓名或显示名称" />
      </el-form-item>
      <el-form-item label="部门">
        <el-tree-select
          v-model="form.dept_id"
          :data="deptOptions"
          :props="{ label: 'name', children: 'children' }"
          node-key="id"
          value-key="id"
          check-strictly
          placeholder="请选择部门（可选）"
          clearable
          style="width: 100%"
        />
      </el-form-item>
      <el-form-item label="邮箱" prop="email">
        <el-input v-model="form.email" placeholder="email@example.com" />
      </el-form-item>
      <el-form-item label="手机号" prop="phone">
        <el-input v-model="form.phone" placeholder="选填" />
      </el-form-item>
      <el-form-item v-if="!editId" label="密码" prop="password">
        <el-input v-model="form.password" type="password" show-password placeholder="至少6位" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, watch, computed } from 'vue'
import { type FormInstance, type FormRules } from 'element-plus'
import type { UserListItem, DeptInfo } from '@/types'

const props = defineProps<{
  visible: boolean
  modelValue?: UserListItem | null
  deptOptions: DeptInfo[]
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'submit', form: typeof form): void
}>()

const formRef = ref<FormInstance>()
const submitting = ref(false)

const editId = computed(() => props.modelValue?.id ?? null)

const form = reactive({
  username: '',
  nickname: '',
  email: '',
  phone: '',
  password: '',
  dept_id: undefined as number | undefined,
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名' }],
  password: [{ required: true, message: '请输入密码' }, { min: 6, message: '至少6位' }],
  email: [{ type: 'email', message: '邮箱格式不正确', trigger: 'blur' }],
}

watch(
  () => props.modelValue,
  (val) => {
    if (val) {
      Object.assign(form, {
        username: val.username ?? '',
        nickname: val.nickname ?? '',
        email: val.email ?? '',
        phone: val.phone ?? '',
        password: '',
        dept_id: (val as any)?.dept_id,
      })
    } else {
      resetForm()
    }
  },
  { immediate: true }
)

function resetForm() {
  form.username = ''
  form.nickname = ''
  form.email = ''
  form.phone = ''
  form.password = ''
  form.dept_id = undefined
}

function handleClose() {
  emit('update:visible', false)
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    emit('submit', { ...form })
  } finally {
    submitting.value = false
  }
}
</script>