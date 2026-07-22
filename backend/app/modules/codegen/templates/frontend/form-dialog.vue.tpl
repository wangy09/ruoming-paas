<template>
  <el-dialog
    v-model="visible"
    :title="editId ? '编辑{{ page_title }}' : '新增{{ page_title }}'"
    width="640px"
    @close="handleClose"
  >
    <el-form :model="form" label-width="100px">
{% for item in form_items %}      <el-form-item label="{{ item.label }}">
          {{ item.control }}
        </el-form-item>
{% endfor %}    </el-form>
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'
import type { {{ entity_name }}Info } from '@/api/{{ module_name }}'

const props = defineProps<{
  visible: boolean
  modelValue?: {{ entity_name }}Info | null
}>()

const emit = defineEmits<{
  (e: 'update:visible', value: boolean): void
  (e: 'submit', form: typeof form): void
}>()

const editId = defineModel<number | null>({ default: null })

const form = reactive({
{% for field in form_defaults %}  {{ field.name }}: {{ field.default }},
{% endfor %}
})

watch(
  () => props.modelValue,
  (val) => {
    if (val) {
      Object.assign(form, val)
    } else {
      resetForm()
    }
  },
  { immediate: true }
)

function resetForm() {
{% for field in form_defaults %}  form.{{ field.name }} = {{ field.default }}
{% endfor %}
}

function handleClose() {
  emit('update:visible', false)
}

function handleSubmit() {
  emit('submit', { ...form })
}
</script>