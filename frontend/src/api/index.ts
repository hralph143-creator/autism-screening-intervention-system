import axios from 'axios'

export const api = axios.create({ baseURL: '/api', timeout: 10_000, withCredentials: true })

export function messageOf(error: any): string {
  if (!error.response) return '无法连接后端服务，请确认系统已启动'
  return error.response.data?.detail || `请求失败（${error.response.status}）`
}

