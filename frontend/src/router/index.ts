import { createRouter, createWebHistory } from 'vue-router'
import { checkSession } from '../session'
import AppLayout from '../layouts/AppLayout.vue'
import LoginView from '../views/LoginView.vue'
import DashboardView from '../views/DashboardView.vue'
import ChildrenView from '../views/ChildrenView.vue'
import SettingsView from '../views/SettingsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView, meta: { title: '管理员登录' } },
    {
      path: '/', component: AppLayout, meta: { auth: true }, children: [
        { path: '', component: DashboardView, meta: { title: '系统首页' } },
        { path: 'children', component: ChildrenView, meta: { title: '儿童档案' } },
        { path: 'analysis', component: () => import('../views/VideoAnalysisView.vue'), meta: { title: '视频分析' } },
        { path: 'observations', component: () => import('../views/ObservationsView.vue'), meta: { title: '行为观察' } },
        { path: 'activities', component: () => import('../views/ActivitiesView.vue'), meta: { title: '家庭互动活动' } },
        { path: 'history', component: () => import('../views/HistoryView.vue'), meta: { title: '综合历史' } },
        { path: 'history/report/:childId', component: () => import('../views/ReportView.vue'), meta: { title: '报告预览' } },
        { path: 'settings', component: SettingsView, meta: { title: '系统设置' } },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async to => {
  if (to.meta.auth && !(await checkSession())) return { path: '/login', query: { redirect: to.fullPath } }
  if (to.path === '/login' && await checkSession()) return '/'
  return true
})

export default router
