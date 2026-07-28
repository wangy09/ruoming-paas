import type { Directive, DirectiveBinding } from 'vue'
import { useAppStore } from '@/store/app'

const demoDirective: Directive = {
  mounted(el: HTMLElement, binding: DirectiveBinding) {
    const appStore = useAppStore()
    if (!appStore.isDemoMode) return

    const disabled = binding.value !== false

    if (disabled) {
      el.classList.add('demo-disabled')
      if ('disabled' in el) {
        ;(el as HTMLButtonElement).disabled = true
      }
    }
  },

  updated(el: HTMLElement, binding: DirectiveBinding) {
    const appStore = useAppStore()

    if (!appStore.isDemoMode) {
      el.classList.remove('demo-disabled')
      if ('disabled' in el) {
        ;(el as HTMLButtonElement).disabled = false
      }
      return
    }

    const disabled = binding.value !== false

    if (disabled) {
      el.classList.add('demo-disabled')
      if ('disabled' in el) {
        ;(el as HTMLButtonElement).disabled = true
      }
    } else {
      el.classList.remove('demo-disabled')
      if ('disabled' in el) {
        ;(el as HTMLButtonElement).disabled = false
      }
    }
  },
}

export default demoDirective