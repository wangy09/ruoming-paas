<template>
  <div class="page-container manual-page">
    <div class="manual-hero">
      <div>
        <el-tag effect="dark" round>帮助中心</el-tag>
        <h1>若茗 PaaS 开发底座用户手册</h1>
        <p>先说明如何启动服务和开发业务模块，再介绍账号、权限、配置、集成、AI、消息、审计和监控等内置基础能力。</p>
      </div>
      <div class="hero-actions">
        <el-button :icon="Printer" @click="printManual">打印 / 另存为 PDF</el-button>
        <el-button type="primary" :icon="Reading" @click="scrollToTop">返回顶部</el-button>
      </div>
    </div>

    <div class="manual-layout">
      <aside class="manual-sidebar">
        <el-input
          v-model="keyword"
          placeholder="搜索手册章节"
          clearable
          class="manual-search"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>

        <div class="toc-title">目录</div>
        <div class="toc-list">
          <button
            v-for="heading in filteredHeadings"
            :key="heading.id"
            class="toc-item"
            :class="[`level-${heading.level}`, { active: activeHeading === heading.id }]"
            @click="scrollToHeading(heading.id)"
          >
            {{ heading.title }}
          </button>
          <el-empty v-if="!filteredHeadings.length" description="没有匹配章节" :image-size="72" />
        </div>
      </aside>

      <main class="manual-content-card">
        <div class="manual-meta">
          <span>文档版本：2026-07</span>
          <span>来源：当前代码菜单与功能实现</span>
          <span>仓库文档：docs/用户手册.md</span>
        </div>
        <article ref="articleRef" class="manual-content" v-html="renderedManual" />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import MarkdownIt from 'markdown-it'
import { Printer, Reading, Search } from '@element-plus/icons-vue'
import manualContent from './content.md?raw'

interface ManualHeading {
  id: string
  title: string
  level: number
}

const keyword = ref('')
const activeHeading = ref('')
const articleRef = ref<HTMLElement>()

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: false,
})

const headings = computed<ManualHeading[]>(() => {
  const result: ManualHeading[] = []
  const lines = manualContent.split('\n')

  for (const line of lines) {
    const matched = /^(#{2,3})\s+(.+)$/.exec(line)
    if (!matched) continue

    const title = matched[2].trim()
    result.push({
      id: headingId(title),
      title,
      level: matched[1].length,
    })
  }

  return result
})

const filteredHeadings = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  if (!text) return headings.value
  return headings.value.filter(item => item.title.toLowerCase().includes(text))
})

const renderedManual = computed(() => {
  let html = md.render(manualContent)
  for (const heading of headings.value) {
    const escapedTitle = escapeRegExp(heading.title)
    const pattern = new RegExp(`<h${heading.level}>${escapedTitle}</h${heading.level}>`, 'g')
    html = html.replace(pattern, `<h${heading.level} id="${heading.id}">${heading.title}</h${heading.level}>`)
  }
  return html
})

function headingId(title: string) {
  return `manual-${Array.from(title)
    .map(char => char.charCodeAt(0).toString(16))
    .join('-')}`
}

function escapeRegExp(text: string) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function scrollToHeading(id: string) {
  const element = document.getElementById(id)
  if (!element) return
  activeHeading.value = id
  element.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function scrollToTop() {
  articleRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function printManual() {
  window.print()
}

function handleScroll() {
  const visible = headings.value
    .map(item => ({ ...item, el: document.getElementById(item.id) }))
    .filter((item): item is ManualHeading & { el: HTMLElement } => Boolean(item.el))
    .filter(item => item.el.getBoundingClientRect().top <= 140)
    .pop()

  if (visible) activeHeading.value = visible.id
}

onMounted(() => {
  window.addEventListener('scroll', handleScroll, { passive: true })
  handleScroll()
})

onBeforeUnmount(() => {
  window.removeEventListener('scroll', handleScroll)
})
</script>

<style lang="scss" scoped>
.manual-page {
  background:
    radial-gradient(circle at 12% 0%, rgba(22, 119, 255, 0.12), transparent 26%),
    radial-gradient(circle at 88% 6%, rgba(82, 196, 26, 0.10), transparent 24%);
}

.manual-hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 28px;
  margin-bottom: 16px;
  color: #fff;
  background: linear-gradient(135deg, #102a58 0%, #1677ff 100%);
  border-radius: 14px;
  box-shadow: 0 16px 36px rgba(22, 119, 255, 0.22);

  h1 {
    margin: 16px 0 10px;
    font-size: 30px;
    line-height: 1.2;
  }

  p {
    max-width: 760px;
    color: rgba(255, 255, 255, 0.82);
    line-height: 1.7;
  }
}

.hero-actions {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  flex-shrink: 0;
}

.manual-layout {
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 16px;
}

.manual-sidebar,
.manual-content-card {
  background: var(--app-bg-card);
  border: 1px solid var(--app-border-color);
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.manual-sidebar {
  position: sticky;
  top: 16px;
  align-self: start;
  max-height: calc(100vh - 32px);
  padding: 16px;
  overflow: hidden;
}

.manual-search {
  margin-bottom: 16px;
}

.toc-title {
  margin-bottom: 10px;
  color: var(--app-text-primary);
  font-weight: 600;
}

.toc-list {
  max-height: calc(100vh - 128px);
  overflow-y: auto;
}

.toc-item {
  display: block;
  width: 100%;
  padding: 8px 10px;
  color: var(--app-text-regular);
  line-height: 1.4;
  text-align: left;
  cursor: pointer;
  background: transparent;
  border: none;
  border-radius: 8px;

  &:hover,
  &.active {
    color: var(--el-color-primary);
    background: rgba(22, 119, 255, 0.10);
  }

  &.level-3 {
    padding-left: 24px;
    font-size: 13px;
  }
}

.manual-content-card {
  min-width: 0;
  padding: 28px 34px;
}

.manual-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  padding-bottom: 18px;
  margin-bottom: 24px;
  color: var(--app-text-secondary);
  border-bottom: 1px solid var(--app-border-color);
}

.manual-content {
  color: var(--app-text-primary);
  line-height: 1.85;

  :deep(h1) {
    margin: 0 0 20px;
    font-size: 30px;
  }

  :deep(h2) {
    padding-top: 16px;
    margin: 30px 0 14px;
    font-size: 22px;
    border-top: 1px solid var(--app-border-color);
    scroll-margin-top: 24px;
  }

  :deep(h3) {
    margin: 22px 0 10px;
    font-size: 17px;
    scroll-margin-top: 24px;
  }

  :deep(p),
  :deep(li) {
    color: var(--app-text-regular);
  }

  :deep(ul),
  :deep(ol) {
    padding-left: 22px;
    margin: 10px 0 16px;
  }

  :deep(code) {
    padding: 2px 6px;
    color: #d4380d;
    background: rgba(250, 140, 22, 0.10);
    border-radius: 4px;
  }
}

@media (max-width: 960px) {
  .manual-hero,
  .manual-layout {
    display: block;
  }

  .hero-actions {
    margin-top: 18px;
  }

  .manual-sidebar {
    position: static;
    max-height: none;
    margin-bottom: 16px;
  }

  .toc-list {
    max-height: 260px;
  }
}

@media print {
  .manual-hero,
  .manual-sidebar {
    display: none;
  }

  .manual-layout {
    display: block;
  }

  .manual-content-card {
    padding: 0;
    border: none;
    box-shadow: none;
  }
}
</style>
