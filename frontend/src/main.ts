import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import './style.css'
import App from './App.vue'
import router from './router'
import { api } from './api'
import { setAdministrator } from './session'

api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401 && router.currentRoute.value.path !== '/login') {
      setAdministrator(null)
      void router.replace({ path: '/login', query: { redirect: router.currentRoute.value.fullPath } })
    }
    return Promise.reject(error)
  },
)

createApp(App).use(ElementPlus).use(router).mount('#app')
