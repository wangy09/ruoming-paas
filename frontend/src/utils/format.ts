import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'
import 'dayjs/locale/zh-cn'

dayjs.extend(relativeTime)
dayjs.locale('zh-cn')

export const formatDate = (date: string | Date | undefined, fmt = 'YYYY-MM-DD HH:mm:ss') => {
  if (!date) return '-'
  return dayjs(date).format(fmt)
}

export const fromNow = (date: string | Date) => dayjs(date).fromNow()

export const formatBytes = (bytes: number) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

export const formatNumber = (num: number) =>
  num >= 10000 ? (num / 10000).toFixed(1) + 'w' : num.toString()

/** 脱敏：手机号 138****1234 */
export const maskPhone = (phone: string) =>
  phone?.replace(/(\d{3})\d{4}(\d{4})/, '$1****$2') ?? ''

/** 脱敏：邮箱 ab***@gmail.com */
export const maskEmail = (email: string) => {
  if (!email) return ''
  const [local, domain] = email.split('@')
  return local.slice(0, 2) + '***@' + domain
}
