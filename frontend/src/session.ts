import { ref } from 'vue'
import { api } from './api'

export interface Administrator { id: number; username: string }
export const administrator = ref<Administrator | null>(null)
let checked = false

export async function checkSession(force = false): Promise<boolean> {
  if (checked && !force) return administrator.value !== null
  try {
    administrator.value = (await api.get('/auth/me')).data
  } catch {
    administrator.value = null
  }
  checked = true
  return administrator.value !== null
}

export function setAdministrator(value: Administrator | null) {
  administrator.value = value
  checked = true
}

