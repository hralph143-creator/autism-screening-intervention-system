import { ref } from 'vue'
import { api } from './api'

export interface Administrator { id: number; username: string }
export const administrator = ref<Administrator | null>(null)
let checked = false
const rememberedAccountsKey = 'autism-system:remembered-accounts'

export function getRememberedAccounts(): string[] {
  try {
    const value = JSON.parse(localStorage.getItem(rememberedAccountsKey) || '[]')
    return Array.isArray(value) ? value.filter(item => typeof item === 'string' && item.trim()).slice(0, 5) : []
  } catch {
    return []
  }
}

export function rememberAccount(username: string) {
  const normalized = username.trim()
  if (!normalized) return
  const accounts = [normalized, ...getRememberedAccounts().filter(item => item !== normalized)].slice(0, 5)
  try { localStorage.setItem(rememberedAccountsKey, JSON.stringify(accounts)) } catch { /* 登录不依赖本地存储 */ }
}

export async function checkSession(force = false): Promise<boolean> {
  if (checked && !force) return administrator.value !== null
  try {
    administrator.value = (await api.get('/auth/me')).data
    rememberAccount(administrator.value!.username)
  } catch {
    administrator.value = null
  }
  checked = true
  return administrator.value !== null
}

export function setAdministrator(value: Administrator | null) {
  administrator.value = value
  if (value) rememberAccount(value.username)
  checked = true
}

