<template>
  <el-dialog :model-value="visible" @update:model-value="emit('update:visible', $event)" title="分配角色" width="480px" destroy-on-close>
    <el-checkbox-group v-model="selectedRoleIds">
      <div v-for="role in allRoles" :key="role.id" class="role-item">
        <el-checkbox :label="role.id" :value="role.id">
          <div>
            <span class="font-bold">{{ role.name }}</span>
            <span class="text-gray text-sm ml-2">{{ role.code }}</span>
          </div>
        </el-checkbox>
      </div>
    </el-checkbox-group>
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import type { UserListItem, RoleInfo } from '@/types'

const props = defineProps<{
  visible: boolean
  modelValue?: UserListItem | null
  allRoles: RoleInfo[]
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'submit', userId: number, roleIds: number[]): void
}>()

const submitting = ref(false)
const selectedRoleIds = ref<number[]>([])

watch(
  () => props.modelValue,
  (val) => {
    if (val) {
      selectedRoleIds.value = (val.roles || []).map((r: { id: number }) => r.id)
    } else {
      selectedRoleIds.value = []
    }
  },
  { immediate: true }
)

function handleClose() {
  emit('update:visible', false)
}

async function handleSubmit() {
  if (!props.modelValue?.id) return
  submitting.value = true
  try {
    emit('submit', props.modelValue.id, [...selectedRoleIds.value])
  } finally {
    submitting.value = false
  }
}
</script>

<style lang="scss" scoped>
.role-item {
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
  &:last-child { border-bottom: none; }
}
.font-bold { font-weight: 600; }
.text-gray { color: var(--el-text-color-secondary); }
.text-sm { font-size: 12px; }
.ml-2 { margin-left: 8px; }
</style>