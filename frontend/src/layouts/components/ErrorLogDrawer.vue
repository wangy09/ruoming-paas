<template>
  <!-- 触发按钮（header 右侧图标） -->
  <el-tooltip content="接口错误记录">
    <div class="error-log-btn" @click="open">
      <el-badge :value="store.unreadCount || undefined" :max="99" type="danger">
        <el-icon class="header-icon" :class="{ 'has-error': store.hasErrors }">
          <Warning />
        </el-icon>
      </el-badge>
    </div>
  </el-tooltip>

  <!-- 抽屉 -->
  <el-drawer
    v-model="visible"
    title="接口错误记录"
    direction="rtl"
    size="600px"
    @open="store.markRead()"
  >
    <template #header>
      <div class="drawer-header">
        <span class="drawer-title">接口错误记录</span>
        <el-tag v-if="store.logs.length" type="danger" size="small">
          {{ store.logs.length }} 条
        </el-tag>
      </div>
    </template>

    <div v-if="store.logs.length === 0" class="empty-tip">
      <el-empty description="暂无错误记录" :image-size="80" />
    </div>

    <div v-else>
      <div class="toolbar">
        <el-button type="danger" plain size="small" :icon="Delete" @click="store.clearLogs()">
          清空记录
        </el-button>
      </div>

      <div
        v-for="log in store.logs"
        :key="log.id"
        class="log-item"
      >
        <!-- 第一行：状态码 + 方法 + URL + 时间 -->
        <div class="log-header">
          <el-tag
            :type="getStatusType(log.status)"
            size="small"
            class="status-tag"
          >
            {{ log.status === 0 ? 'NET' : log.status }}
          </el-tag>
          <span class="method">{{ log.method }}</span>
          <span class="url" :title="log.url">{{ log.url }}</span>
          <span class="time">{{ log.time }}</span>
        </div>

        <!-- 第二行：错误信息 -->
        <div class="log-message">{{ log.message }}</div>

        <!-- 第三行：可选详情 -->
        <div v-if="log.traceId || log.code" class="log-meta">
          <span v-if="log.code" class="meta-item">
            业务码：<code>{{ log.code }}</code>
          </span>
          <span v-if="log.traceId" class="meta-item trace-id">
            TraceID：<code>{{ log.traceId }}</code>
            <el-tooltip content="复制 TraceID 用于后端日志联查">
              <el-icon class="copy-icon" @click="copyTraceId(log.traceId!)"><CopyDocument /></el-icon>
            </el-tooltip>
          </span>
        </div>

        <!-- 响应快照（可折叠） -->
        <el-collapse-transition>
          <div v-if="expandedIds.has(log.id) && log.responseSnippet" class="response-snippet">
            <pre>{{ log.responseSnippet }}</pre>
          </div>
        </el-collapse-transition>

        <div v-if="log.responseSnippet" class="expand-toggle" @click="toggleExpand(log.id)">
          {{ expandedIds.has(log.id) ? '收起响应' : '展开响应' }}
        </div>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Warning, Delete, CopyDocument } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useErrorLogStore } from '@/store/errorLog'

const store = useErrorLogStore()
const visible = ref(false)
const expandedIds = ref(new Set<string>())

function open() {
  visible.value = true
}

function getStatusType(status: number): 'danger' | 'warning' | 'info' | 'success' {
  if (status === 0 || status >= 500) return 'danger'
  if (status >= 400) return 'warning'
  if (status === 200) return 'info'  // 业务错误
  return 'info'
}

function toggleExpand(id: string) {
  if (expandedIds.value.has(id)) {
    expandedIds.value.delete(id)
  } else {
    expandedIds.value.add(id)
  }
}

async function copyTraceId(traceId: string) {
  try {
    await navigator.clipboard.writeText(traceId)
    ElMessage.success('TraceID 已复制')
  } catch {
    ElMessage.error('复制失败，请手动复制')
  }
}
</script>

<style lang="scss" scoped>
.error-log-btn {
  cursor: pointer;
  display: flex;
  align-items: center;

  .header-icon {
    font-size: 18px;
    color: var(--el-text-color-regular);
    transition: color 0.2s;

    &:hover,
    &.has-error {
      color: var(--el-color-danger);
    }
  }
}

.drawer-header {
  display: flex;
  align-items: center;
  gap: 8px;

  .drawer-title {
    font-size: 16px;
    font-weight: 600;
  }
}

.empty-tip {
  padding: 60px 0;
  display: flex;
  justify-content: center;
}

.toolbar {
  margin-bottom: 12px;
  display: flex;
  justify-content: flex-end;
}

.log-item {
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 10px;
  background: var(--el-bg-color);
  font-size: 13px;

  &:hover {
    border-color: var(--el-color-primary-light-5);
  }

  .log-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;

    .status-tag {
      flex-shrink: 0;
      font-family: monospace;
    }

    .method {
      flex-shrink: 0;
      font-weight: 600;
      font-family: monospace;
      color: var(--el-color-primary);
      min-width: 46px;
    }

    .url {
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-family: monospace;
      color: var(--el-text-color-secondary);
      font-size: 12px;
    }

    .time {
      flex-shrink: 0;
      font-size: 11px;
      color: var(--el-text-color-placeholder);
    }
  }

  .log-message {
    color: var(--el-color-danger);
    font-size: 13px;
    margin-bottom: 4px;
    word-break: break-all;
  }

  .log-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-top: 4px;

    .meta-item {
      font-size: 12px;
      color: var(--el-text-color-secondary);

      code {
        background: var(--el-fill-color-light);
        padding: 1px 4px;
        border-radius: 3px;
        font-family: monospace;
        font-size: 11px;
      }
    }

    .trace-id {
      display: flex;
      align-items: center;
      gap: 4px;

      .copy-icon {
        cursor: pointer;
        color: var(--el-color-primary);
        font-size: 13px;

        &:hover {
          opacity: 0.7;
        }
      }
    }
  }

  .response-snippet {
    margin-top: 8px;
    background: var(--el-fill-color-light);
    border-radius: 4px;
    padding: 8px;
    font-size: 11px;
    font-family: monospace;
    overflow-x: auto;
    max-height: 200px;
    overflow-y: auto;
    white-space: pre-wrap;
    word-break: break-all;
    color: var(--el-text-color-secondary);
  }

  .expand-toggle {
    margin-top: 6px;
    font-size: 12px;
    color: var(--el-color-primary);
    cursor: pointer;
    user-select: none;

    &:hover {
      text-decoration: underline;
    }
  }
}
</style>
