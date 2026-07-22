<template>
  <el-dialog
    v-model="visible"
    :title="editId ? '编辑{{ page_title }}' : '新增{{ page_title }}'"
    width="800px"
    @close="handleClose"
  >
    <el-form :model="form" label-width="100px">
{% for item in form_items %}      <el-form-item label="{{ item.label }}">
          {{ item.control }}
        </el-form-item>
{% endfor %}

{% if has_sub_tables %}
{% for st in sub_tables %}      <el-form-item label="{{ st.table_comment }}">
        <div class="sub-table-container">
          <el-button size="small" type="primary" @click="add{{ st.entity_name }}Item">+ 新增{{ st.table_comment }}</el-button>
          <el-table :data="form.{{ st.entity_var }}_list" border style="margin-top: 8px">
{% for col in st.table_columns %}            <el-table-column prop="{{ col.prop }}" label="{{ col.label }}"{{ col.width }}>
              <template #default="{ row }">
                <el-input v-model="row.{{ col.prop }}" placeholder="{{ col.label }}" />
              </template>
            </el-table-column>
{% endfor %}            <el-table-column label="操作" width="100">
              <template #default="{ $index }">
                <el-button size="small" type="danger" @click="remove{{ st.entity_name }}Item($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-form-item>
{% endfor %}
{% endif %}
    </el-form>
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" @click="handleSubmit">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'
import type { {{ entity_name }}Info{% if has_sub_tables %}{% for st in sub_tables %}, {{ st.entity_name }}Info{% endfor %}{% endif %} } from '@/api/{{ module_name }}'

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
{% if has_sub_tables %}
{% for st in sub_tables %}  {{ st.entity_var }}_list: [] as {{ st.entity_name }}Info[],
{% endfor %}
{% endif %}
})

{% if has_sub_tables %}
{% for st in sub_tables %}
function add{{ st.entity_name }}Item() {
  const defaultItem: {{ st.entity_name }}Info = {
{% for field in st.form_defaults %}    {{ field.name }}: {{ field.default }},
{% endfor %}
  }
  form.{{ st.entity_var }}_list.push(defaultItem)
}

function remove{{ st.entity_name }}Item(index: number) {
  form.{{ st.entity_var }}_list.splice(index, 1)
}
{% endfor %}
{% endif %}

watch(
  () => props.modelValue,
  (val) => {
    if (val) {
      Object.assign(form, val)
{% if has_sub_tables %}
{% for st in sub_tables %}      if (!form.{{ st.entity_var }}_list) form.{{ st.entity_var }}_list = []
{% endfor %}
{% endif %}
    } else {
      resetForm()
    }
  },
  { immediate: true }
)

function resetForm() {
{% for field in form_defaults %}  form.{{ field.name }} = {{ field.default }}
{% endfor %}
{% if has_sub_tables %}
{% for st in sub_tables %}  form.{{ st.entity_var }}_list = []
{% endfor %}
{% endif %}
}

function handleClose() {
  emit('update:visible', false)
}

function handleSubmit() {
  emit('submit', { ...form })
}
</script>

<style lang="scss" scoped>
.sub-table-container {
  width: 100%;
}
</style>