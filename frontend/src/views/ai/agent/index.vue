<template>
  <div class="page-container">
    <div class="page-card">
      <div class="card-header">
        <span class="card-title">Agent 管理</span>
        <el-button type="primary" :icon="Plus" v-permission="'ai:agent:create'" @click="openDialog()">
          新建 Agent
        </el-button>
      </div>

      <!-- Agent 卡片列表 -->
      <el-row :gutter="16" v-loading="loading">
        <el-col
          v-for="agent in tableData"
          :key="agent.id"
          :xs="24" :sm="12" :md="8" :lg="6"
        >
          <div class="agent-card" @click="openDialog(agent)">
            <div class="agent-card-header">
              <div class="agent-icon">
                <el-icon :size="28"><Robot /></el-icon>
              </div>
              <el-dropdown trigger="click" @click.stop @command="cmd => handleCommand(cmd, agent)">
                <el-icon class="agent-more" @click.stop><MoreFilled /></el-icon>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="edit">编辑</el-dropdown-item>
                    <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>

            <h3 class="agent-name">{{ agent.name }}</h3>
            <p class="agent-desc">{{ agent.description || '暂无描述' }}</p>

            <div class="agent-footer">
              <el-tag :type="statusTagMap[agent.status]" size="small">{{ statusLabelMap[agent.status] }}</el-tag>
              <el-tag type="info" size="small">{{ typeLabelMap[agent.type] }}</el-tag>
            </div>
          </div>
        </el-col>

        <el-col :xs="24" :sm="12" :md="8" :lg="6">
          <div class="agent-card agent-add-card" @click="openDialog()">
            <el-icon :size="36" color="#c0c4cc"><Plus /></el-icon>
            <span>新建 Agent</span>
          </div>
        </el-col>
      </el-row>

      <el-pagination
        class="mt-4"
        v-model:current-page="query.page"
        v-model:page-size="query.page_size"
        :total="total"
        layout="total, prev, pager, next"
        @change="fetchList"
      />
    </div>

    <!-- 编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="editId ? '编辑 Agent' : '新建 Agent'" width="680px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="16">
          <el-col :span="16">
            <el-form-item label="Agent 名称" prop="name">
              <el-input v-model="form.name" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="类型" prop="type">
              <el-select v-model="form.type" style="width:100%">
                <el-option label="普通对话" value="chat" />
                <el-option label="RAG 问答" value="rag" />
                <el-option label="工具调用" value="tool" />
                <el-option label="工作流" value="workflow" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>

        <el-form-item label="系统 Prompt">
          <el-input
            v-model="form.system_prompt"
            type="textarea"
            :rows="5"
            placeholder="定义 Agent 的角色、能力范围和行为规则..."
          />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="14">
            <el-form-item label="绑定模型">
              <el-select v-model="form.model_config_id" placeholder="使用默认模型" clearable style="width:100%">
                <el-option
                  v-for="m in chatModels"
                  :key="m.id"
                  :label="`${m.name}（${m.provider}）`"
                  :value="m.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="10">
            <el-form-item label="Temperature">
              <el-input-number v-model="form.temperature" :min="0" :max="2" :step="0.1" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="绑定知识库" v-if="['rag', 'tool', 'workflow'].includes(form.type)">
          <el-select v-model="form.knowledge_base_ids" multiple placeholder="可选多个" style="width:100%">
            <el-option v-for="kb in knowledgeBases" :key="kb.id" :label="kb.name" :value="kb.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="最大迭代次数">
          <el-input-number v-model="form.max_iterations" :min="1" :max="20" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, MoreFilled, Robot } from '@element-plus/icons-vue'
import { agentApi, modelApi, kbApi } from '@/api/ai'
import type { AgentInfo, AiModelConfig, KnowledgeBase } from '@/types'

const statusTagMap: Record<string, string> = { draft: 'info', active: 'success', archived: '' }
const statusLabelMap: Record<string, string> = { draft: '草稿', active: '启用', archived: '归档' }
const typeLabelMap: Record<string, string> = { chat: '对话', rag: 'RAG', tool: '工具', workflow: '工作流' }

const loading = ref(false)
const tableData = ref<AgentInfo[]>([])
const total = ref(0)
const chatModels = ref<AiModelConfig[]>([])
const knowledgeBases = ref<KnowledgeBase[]>([])

const query = reactive({ page: 1, page_size: 20 })

async function fetchList() {
  loading.value = true
  try {
    const res = await agentApi.list(query)
    tableData.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function handleCommand(cmd: string, agent: AgentInfo) {
  if (cmd === 'edit') openDialog(agent)
  if (cmd === 'delete') handleDelete(agent)
}

async function handleDelete(agent: AgentInfo) {
  await ElMessageBox.confirm(`确定删除 Agent「${agent.name}」？`, '警告', { type: 'warning' })
  await agentApi.delete(agent.id)
  ElMessage.success('已删除')
  fetchList()
}

const dialogVisible = ref(false)
const editId = ref<number | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  name: '', description: '', type: 'chat' as AgentInfo['type'],
  system_prompt: '', model_config_id: undefined as number | undefined,
  temperature: 0.7, max_iterations: 5,
  knowledge_base_ids: [] as number[],
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入名称' }],
  type: [{ required: true }],
}

async function openDialog(row?: AgentInfo) {
  editId.value = row?.id ?? null
  Object.assign(form, {
    name: row?.name ?? '', description: row?.description ?? '',
    type: row?.type ?? 'chat', system_prompt: row?.system_prompt ?? '',
    model_config_id: row?.model_config_id,
    temperature: row?.temperature ?? 0.7,
    max_iterations: row?.max_iterations ?? 5,
    knowledge_base_ids: row?.knowledge_base_ids ?? [],
  })

  // 预加载模型和知识库列表
  if (!chatModels.value.length) {
    const res = await modelApi.list({ model_type: 'chat', page_size: 200 })
    chatModels.value = res.data.items
  }
  if (!knowledgeBases.value.length) {
    const res = await kbApi.list({ page_size: 200 })
    knowledgeBases.value = res.data.items
  }

  dialogVisible.value = true
}

async function handleSubmit() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    if (editId.value) {
      await agentApi.update(editId.value, form)
      ElMessage.success('更新成功')
    } else {
      await agentApi.create(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchList()
  } finally {
    submitting.value = false
  }
}

onMounted(fetchList)
</script>

<style lang="scss" scoped>
@use '@/styles/variables.scss' as *;

.card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.card-title { font-size: 15px; font-weight: 600; }
.mt-4 { margin-top: 16px; }

.agent-card {
  background: $bg-white;
  border: 1px solid $border-color;
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 16px;
  cursor: pointer;
  transition: all .2s;
  min-height: 160px;

  &:hover {
    border-color: $primary-color;
    box-shadow: 0 4px 12px rgba(22,119,255,.12);
    transform: translateY(-2px);
  }

  &.agent-add-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    border-style: dashed;
    color: $text-secondary;
    font-size: 13px;
    &:hover { border-color: $primary-color; color: $primary-color; }
  }

  .agent-card-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 12px;
  }

  .agent-icon {
    width: 48px; height: 48px;
    background: rgba(22,119,255,.1);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    color: $primary-color;
  }

  .agent-more {
    font-size: 18px; color: $text-secondary; cursor: pointer;
    &:hover { color: $primary-color; }
  }

  .agent-name { font-size: 15px; font-weight: 600; color: $text-primary; margin-bottom: 6px; }
  .agent-desc { font-size: 12px; color: $text-secondary; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  .agent-footer {
    margin-top: 14px;
    display: flex;
    gap: 6px;
  }
}
</style>
