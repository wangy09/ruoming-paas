<template>
  <el-dialog :model-value="modelValue" @update:model-value="emit('update:modelValue', $event)" title="批量生成" width="500px">
    <el-form :model="form" label-width="100px">
      <el-form-item label="选择配置">
        <el-checkbox-group v-model="form.config_ids">
          <el-checkbox
            v-for="config in configList"
            :key="config.id"
            :label="config.id"
          >
            {{ config.table_name }} ({{ config.module_name }})
          </el-checkbox>
        </el-checkbox-group>
      </el-form-item>
      <el-form-item label="写入策略">
        <el-switch
          v-model="form.overwrite"
          active-text="覆盖已存在文件"
          inactive-text="已存在则跳过"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleBatchGenerate">批量生成</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { codegenApi, type BatchGenerateParams, type GenTableResponse } from '@/api/codegen'

defineProps<{
  modelValue: boolean
  configList: GenTableResponse[]
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'batchGenerated'): void
}>()

const loading = ref(false)

const form = reactive({
  config_ids: [] as number[],
  overwrite: false,
})

async function handleBatchGenerate() {
  if (form.config_ids.length === 0) {
    ElMessage.warning('请选择至少一个配置')
    return
  }

  try {
    await ElMessageBox.confirm(
      form.overwrite
        ? `将批量生成 ${form.config_ids.length} 个配置的代码并覆盖已存在文件，确定继续？`
        : `将批量生成 ${form.config_ids.length} 个配置的代码，已存在文件会自动跳过，确定继续？`,
      '批量生成确认',
      { type: form.overwrite ? 'warning' : 'info' }
    )
  } catch {
    return
  }

  loading.value = true
  try {
    await codegenApi.batchGenerate({
      config_ids: form.config_ids,
      overwrite: form.overwrite,
    } as BatchGenerateParams)
    emit('update:modelValue', false)
    emit('batchGenerated')
    ElMessage.success('批量生成完成')
  } catch {
    ElMessage.error('批量生成失败')
  } finally {
    loading.value = false
    form.config_ids = []
  }
}
</script>
