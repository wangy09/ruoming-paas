/**
 * 若茗 PaaS - 增强版 Markdown 渲染器
 * 在 markdown-it 基础上为代码块添加工具栏（语言标签 + 复制 + 下载按钮）
 */
import MarkdownIt from 'markdown-it'
import type { Token, RenderRule } from 'markdown-it'

export function createEnhancedMd(): MarkdownIt {
  const md = new MarkdownIt({
    html: false,
    linkify: true,
    breaks: true,
  })

  // 保存默认的 fence 渲染器
  const rules = md.renderer.rules
  const defaultFence = rules.fence ? (rules.fence as RenderRule).bind(rules) : null

  // 覆盖 fence 渲染规则，注入工具栏
  rules.fence = (tokens: Token[], idx: number, options: any, env: any, self: any): string => {
    const token = tokens[idx]
    const lang = token.info.trim().split(/\s+/)[0] || 'text'
    const code = token.content
    // 用 base64 编码避免 HTML 属性中的引号问题
    const encoded = btoa(unescape(encodeURIComponent(code)))

    // 调用默认渲染器获取原始 HTML
    const rawHtml = defaultFence
      ? defaultFence(tokens, idx, options, env, self)
      : `<pre><code class="language-${lang}">${md.utils.escapeHtml(code)}</code></pre>`

    // 包装一层 div，加工具栏
    return `<div class="code-block-wrapper" data-lang="${lang}" data-code="${encoded}">
      <div class="code-block-toolbar">
        <span class="code-lang">${lang}</span>
        <button class="code-btn code-copy" title="复制代码">复制</button>
        <button class="code-btn code-download" title="下载文件">下载</button>
      </div>
      ${rawHtml}
    </div>`
  }

  return md
}

/**
 * 为指定容器设置代码块按钮的事件委托
 * 在组件 onMounted 中调用
 */
export function setupCodeBlockHandlers(rootSelector: string): void {
  const root = document.querySelector(rootSelector)
  if (!root) return

  root.addEventListener('click', (e) => {
    const target = e.target as HTMLElement
    if (!target.classList.contains('code-btn')) return

    const wrapper = target.closest('.code-block-wrapper') as HTMLElement
    if (!wrapper) return

    const encoded = wrapper.dataset.code || ''
    const lang = wrapper.dataset.lang || 'txt'

    // 解码 base64
    let code = ''
    try {
      code = decodeURIComponent(escape(atob(encoded)))
    } catch {
      code = wrapper.querySelector('code')?.textContent || ''
    }

    if (target.classList.contains('code-copy')) {
      navigator.clipboard
        .writeText(code)
        .then(() => {
          target.textContent = '已复制'
          setTimeout(() => {
            target.textContent = '复制'
          }, 2000)
        })
        .catch(() => {})
    } else if (target.classList.contains('code-download')) {
      // 从代码块第一行注释提取文件名，否则用 code.<ext>
      const extMap: Record<string, string> = {
        python: 'py',
        py: 'py',
        typescript: 'ts',
        ts: 'ts',
        javascript: 'js',
        js: 'js',
        vue: 'vue',
        sql: 'sql',
        shell: 'sh',
        bash: 'sh',
        json: 'json',
        html: 'html',
        css: 'css',
        yaml: 'yml',
        yml: 'yml',
        xml: 'xml',
        java: 'java',
        go: 'go',
      }
      const ext = extMap[lang] || 'txt'

      // 尝试从代码内容中提取文件路径注释
      let filename = `code.${ext}`
      const firstLines = code.split('\n').slice(0, 5)
      for (const line of firstLines) {
        const match = line.match(/#\s*(?:path:\s*)?([\w/]+\.\w+)/) || 
                      line.match(/\/\/\s*(?:path:\s*)?([\w/]+\.\w+)/) ||
                      line.match(/<!--\s*([\w/]+\.\w+)\s*-->/)
        if (match) {
          filename = match[1].split('/').pop() || filename
          break
        }
      }

      const blob = new Blob([code], { type: 'text/plain;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
    }
  })
}
