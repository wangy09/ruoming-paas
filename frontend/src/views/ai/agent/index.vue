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
          <div class="agent-card" @click="permStore.hasPermission('ai:agent:update') && openDialog(agent)">
            <div class="agent-card-header">
              <div class="agent-icon" :style="{ background: getSceneBgColor(agent.default_scene) }">
                <img v-if="agent.avatar" :src="agent.avatar" class="agent-avatar" />
                <el-icon v-else :size="28" :color="getSceneIconColor(agent.default_scene)">
                  <component :is="getSceneIcon(agent.default_scene)" />
                </el-icon>
              </div>
              <el-dropdown trigger="click" @click.stop @command="cmd => handleCommand(cmd, agent)">
                <el-icon class="agent-more" @click.stop><MoreFilled /></el-icon>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item v-if="permStore.hasPermission('ai:agent:update')" command="edit">编辑</el-dropdown-item>
                    <el-dropdown-item v-if="permStore.hasPermission('ai:agent:delete')" command="delete" divided>删除</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </div>

            <h3 class="agent-name">{{ agent.name }}</h3>
            <p class="agent-desc">{{ agent.description || '暂无描述' }}</p>

            <div class="agent-info">
              <div class="info-row">
                <el-tag :type="getSceneTagType(agent.default_scene)" size="small">{{ agent.scene_label || '未设置' }}</el-tag>
                <el-tag type="info" size="small">{{ agent.model_name || '默认模型' }}</el-tag>
              </div>
              <div class="info-row">
                <span class="info-item">温度: {{ agent.temperature }}</span>
                <span class="info-item">记忆: {{ agent.memory_label }}</span>
                <span class="info-item">工具: {{ agent.tool_count }}</span>
                <span class="info-item">知识库: {{ agent.kb_count }}</span>
              </div>
            </div>

            <div class="agent-footer">
              <el-tag :type="getStatusTagType(agent.status)" size="small">{{ getStatusLabel(agent.status) }}</el-tag>
            </div>
          </div>
        </el-col>

        <el-col v-if="permStore.hasPermission('ai:agent:create')" :xs="24" :sm="12" :md="8" :lg="6">
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
    <el-dialog v-model="dialogVisible" :title="editId ? '编辑 Agent' : '新建 Agent'" width="720px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-row :gutter="16">
          <el-col :span="16">
            <el-form-item label="Agent 名称" prop="name">
              <el-input v-model="form.name" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="场景类型" prop="default_scene">
              <el-select v-model="form.default_scene" placeholder="默认专业分析" style="width:100%">
                <el-option label="闲聊" value="chitchat" />
                <el-option label="专业分析" value="professional" />
                <el-option label="任务执行" value="task" />
                <el-option label="知识库问答" value="rag" />
                <el-option label="创意写作" value="creative" />
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

        <el-form-item label="记忆类型">
          <el-radio-group v-model="form.memory_type">
            <el-radio-button value="buffer">缓冲记忆</el-radio-button>
            <el-radio-button value="summary">摘要压缩</el-radio-button>
            <el-radio-button value="vector">向量记忆</el-radio-button>
          </el-radio-group>
          <div class="form-hint">
            <template v-if="form.memory_type === 'buffer'">保留完整对话历史，适合短对话</template>
            <template v-else-if="form.memory_type === 'summary'">超长对话自动压缩摘要，节省 Token</template>
            <template v-else>将历史存入向量库，支持超长会话检索</template>
          </div>
        </el-form-item>

        <el-form-item label="绑定工具">
          <el-select v-model="form.tool_ids" multiple placeholder="可选多个工具" style="width:100%" value-key="tool_id">
            <el-option
              v-for="t in toolList"
              :key="t.tool_id"
              :label="t.name"
              :value="t.tool_id"
            >
              <div style="display:flex;flex-direction:column">
                <span>{{ t.name }}</span>
                <span style="font-size:11px;color:#999">{{ t.description }}</span>
              </div>
            </el-option>
          </el-select>
        </el-form-item>

        <el-form-item label="绑定知识库">
          <el-select v-model="form.kb_ids" multiple placeholder="可选多个" style="width:100%">
            <el-option v-for="kb in knowledgeBases" :key="kb.id" :label="kb.name" :value="kb.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="Prompt 模板">
          <el-select v-model="form.prompt_template_id" placeholder="使用系统 Prompt（可选）" clearable style="width:100%">
            <el-option
              v-for="p in promptTemplates.filter(t => t.status === 'published')"
              :key="p.id"
              :label="`${p.name}（v${p.current_version}）`"
              :value="p.id"
            />
          </el-select>
          <div class="form-hint">选择后将覆盖上方手动填写的系统 Prompt</div>
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="最大对话轮次">
              <el-input-number v-model="form.max_rounds" :min="1" :max="50" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="Max Tokens">
              <el-input-number v-model="form.max_tokens" :min="128" :max="131072" :step="256" style="width:100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="推理超时(秒)">
              <el-input-number v-model="form.node_timeout_sec" :min="5" :max="600" :step="5" style="width:100%" />
            </el-form-item>
          </el-col>
        </el-row>
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
import { Plus, MoreFilled, MagicStick, Refresh, Setting, Box, Collection, List } from '@element-plus/icons-vue'
import { agentApi, modelApi, kbApi, toolApi, promptApi } from '@/api/ai'
import { useAgentStatus } from '@/hooks/useDict'
import { usePermissionStore } from '@/store/permission'
import type { AgentInfo, AiModelConfig, KnowledgeBase, ToolInfo, PromptTemplate } from '@/types'

const permStore = usePermissionStore()

// Agent 状态字典
const { tagType: getStatusTagType, label: getStatusLabel } = useAgentStatus()

function getSceneTagType(scene: string | undefined): string {
  const map: Record<string, string> = {
    chitchat: 'warning',
    professional: 'primary',
    task: 'success',
    rag: 'danger',
    creative: 'info',
  }
  return map[scene || ''] || 'default'
}

function getSceneIcon(scene: string | undefined) {
  const map: Record<string, any> = {
    chitchat: Refresh,
    professional: Setting,
    task: Box,
    rag: Collection,
    creative: List,
  }
  return map[scene || ''] || MagicStick
}

function getSceneBgColor(scene: string | undefined): string {
  const map: Record<string, string> = {
    chitchat: 'rgba(250,173,20,0.1)',
    professional: 'rgba(22,119,255,0.1)',
    task: 'rgba(82,196,26,0.1)',
    rag: 'rgba(255,77,79,0.1)',
    creative: 'rgba(144,147,153,0.1)',
  }
  return map[scene || ''] || 'rgba(22,119,255,0.1)'
}

function getSceneIconColor(scene: string | undefined): string {
  const map: Record<string, string> = {
    chitchat: '#faad14',
    professional: '#1677ff',
    task: '#52c41a',
    rag: '#ff4d4f',
    creative: '#909399',
  }
  return map[scene || ''] || '#1677ff'
}

const loading = ref(false)
const tableData = ref<AgentInfo[]>([])
const total = ref(0)
const chatModels = ref<AiModelConfig[]>([])
const knowledgeBases = ref<KnowledgeBase[]>([])
const toolList = ref<ToolInfo[]>([])
const promptTemplates = ref<PromptTemplate[]>([])

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
  name: '', description: '', default_scene: undefined as string | undefined,
  system_prompt: '', model_config_id: undefined as number | undefined,
  temperature: 0.7, max_rounds: 10, max_tokens: 2048, node_timeout_sec: 60,
  memory_type: 'buffer' as string,
  kb_ids: [] as number[],
  tool_ids: [] as string[],
  prompt_template_id: undefined as number | undefined,
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入名称' }],
}

async function openDialog(row?: AgentInfo) {
  editId.value = row?.id ?? null
  Object.assign(form, {
    name: row?.name ?? '', description: row?.description ?? '',
    default_scene: row?.default_scene, system_prompt: row?.system_prompt ?? '',
    model_config_id: row?.model_config_id,
    temperature: row?.temperature ?? 0.7,
    max_rounds: row?.max_rounds ?? 10,
    max_tokens: row?.max_tokens ?? 2048,
    node_timeout_sec: row?.node_timeout_sec ?? 60,
    memory_type: row?.memory_type ?? 'buffer',
    kb_ids: row?.kb_ids ?? [],
    tool_ids: (row?.tool_ids ?? []) as any,
    prompt_template_id: row?.prompt_template_id,
  })

  // 并行预加载依赖数据
  await Promise.all([
    chatModels.value.length ? null : modelApi.list({ model_type: 'chat', page_size: 200 }).then(r => { chatModels.value = r.data.items }),
    knowledgeBases.value.length ? null : kbApi.list({ page_size: 200 }).then(r => { knowledgeBases.value = r.data.items }),
    toolList.value.length ? null : toolApi.list().then(r => { toolList.value = r.data }),
    promptTemplates.value.length ? null : promptApi.list({ page_size: 200 }).then(r => { promptTemplates.value = r.data.items }),
  ])

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
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    overflow: hidden;
    .agent-avatar {
      width: 100%; height: 100%;
      object-fit: cover;
    }
  }

  .agent-more {
    font-size: 18px; color: $text-secondary; cursor: pointer;
    &:hover { color: $primary-color; }
  }

  .agent-name { font-size: 15px; font-weight: 600; color: $text-primary; margin-bottom: 6px; }
  .agent-desc { font-size: 12px; color: $text-secondary; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

  .agent-info {
    margin: 10px 0;
    .info-row {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-bottom: 6px;
    }
    .info-item {
      font-size: 11px;
      color: $text-secondary;
      background: $bg-base;
      padding: 2px 6px;
      border-radius: 4px;
    }
  }

  .agent-footer {
    margin-top: 8px;
    display: flex;
    gap: 6px;
  }
}

.form-hint { font-size: 11px; color: $text-secondary; margin-top: 4px; line-height: 1.4; }
</style>
