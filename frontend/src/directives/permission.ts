/**
 * v-permission 权限指令
 * 用法：<el-button v-permission="'user:create'">新增</el-button>
 *       <el-button v-permission="['user:create', 'user:update']">操作</el-button>
 */
import type { Directive, DirectiveBinding } from 'vue'
import { usePermissionStore } from '@/store/permission'

const permissionDirective: Directive = {
  mounted(el: HTMLElement, binding: DirectiveBinding) {
    const { value } = binding
    if (!value) return

    const permStore = usePermissionStore()
    const codes = Array.isArray(value) ? value : [value]
    const hasPermission = codes.some((code: string) => permStore.hasPermission(code))

    if (!hasPermission) {
      el.parentNode?.removeChild(el)
    }
  },
}

export default permissionDirective
