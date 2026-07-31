declare module 'markdown-it' {
  export interface MarkdownItOptions {
    html?: boolean
    xhtmlOut?: boolean
    breaks?: boolean
    langPrefix?: string
    linkify?: boolean
    typographer?: boolean
    quotes?: string | string[]
    highlight?: (str: string, lang: string) => string
  }

  export interface Token {
    type: string
    tag: string
    attrs: [string, string][] | null
    map: [number, number] | null
    nesting: number
    level: number
    children: Token[] | null
    content: string
    markup: string
    info: string
    meta: any
    block: boolean
    hidden: boolean
  }

  export type RenderRule = (
    tokens: Token[],
    idx: number,
    options: MarkdownItOptions,
    env: any,
    self: Renderer
  ) => string

  export interface Renderer {
    rules: Record<string, RenderRule | undefined>
    [key: string]: any
  }

  export interface Utils {
    escapeHtml: (str: string) => string
    assign: (target: any, ...sources: any[]) => any
    isString: (obj: any) => obj is string
    [key: string]: any
  }

  export default class MarkdownIt {
    constructor(options?: MarkdownItOptions)
    render(src: string): string
    renderInline(src: string): string
    parse(src: string, env: any): Token[]
    options: MarkdownItOptions
    renderer: Renderer
    utils: Utils
    ruler: any
    [key: string]: any
  }
}
