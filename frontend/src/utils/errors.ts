import axios from 'axios'
import type { ApiErrorBody } from '../types/domain'

function detailMessage(details: unknown): string | null {
  if (typeof details === 'string') return details
  if (Array.isArray(details)) {
    const messages = details.map(detailMessage).filter((message): message is string => Boolean(message))
    return messages.length ? messages.slice(0, 3).join('；') : null
  }
  if (details && typeof details === 'object') {
    const messages = Object.entries(details).flatMap(([field, value]) => {
      if (field === 'record') return []
      const message = detailMessage(value)
      if (!message) return []
      return [field === 'detail' || field === 'non_field_errors' ? message : `${field}: ${message}`]
    })
    return messages.length ? messages.slice(0, 3).join('；') : null
  }
  return null
}

export function errorMessage(error: unknown): string {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    const body = error.response?.data
    if (error.response?.status === 400 || error.response?.status === 409) {
      const detail = detailMessage(body?.details)
      if (detail) return detail
    }
    if (error.response?.status === 503) return '服务暂时不可用，请稍后重试。'
    if (error.response?.status === 409) return '操作冲突，请刷新后重试。'
    if (error.response?.status === 404) return '记录不存在或已变更。'
    if (error.response?.status === 401) return '登录已失效，请重新登录。'
    if (body?.message) return body.message
    if (!error.response) return '无法连接服务，请检查网络后重试。'
  }
  return error instanceof Error ? error.message : '请求失败，请稍后重试。'
}
