<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, messageOf } from '../api'
import { administrator, setAdministrator } from '../session'

const route = useRoute(); const router = useRouter(); const collapsed = ref(false)
const pageTitle = computed(() => String(route.meta.title || '系统'))
const items = [
  ['/', '系统首页', '首'], ['/children', '儿童档案', '档'], ['/analysis', '视频分析', '视'],
  ['/observations', '行为观察', '观'], ['/activities', '家庭训练', '训'], ['/history', '历史记录', '历'],
  ['/settings', '系统设置', '设'],
]
async function logout() {
  try { await api.post('/auth/logout'); setAdministrator(null); await router.replace('/login') }
  catch (error) { ElMessage.error(messageOf(error)) }
}
</script>
<template>
  <div class="shell" :class="{ collapsed }">
    <aside>
      <div class="brand"><span>观</span><div><b>儿童行为观察</b><small>本地管理系统</small></div></div>
      <nav><button v-for="item in items" :key="item[0]" :class="{ active: route.path === item[0] }" @click="router.push(item[0])"><i>{{ item[2] }}</i><em>{{ item[1] }}</em></button></nav>
      <button class="collapse" @click="collapsed = !collapsed">{{ collapsed ? '展开导航' : '收起导航' }}</button>
    </aside>
    <section class="workspace">
      <header><div class="header-title"><button class="mobile-toggle" @click="collapsed = !collapsed">☰</button><span>基于深度学习的自闭症筛查与干预系统</span><i></i><b>{{ pageTitle }}</b></div><div class="account"><span>管理员：{{ administrator?.username }}</span><el-button text @click="logout">退出登录</el-button></div></header>
      <main><router-view /></main>
    </section>
  </div>
</template>
<style scoped>
.shell{--side:224px;min-height:100vh}.shell.collapsed{--side:76px}aside{position:fixed;inset:0 auto 0 0;width:var(--side);background:#173f42;color:white;padding:22px 14px;display:flex;flex-direction:column;transition:width .2s}.brand{display:flex;align-items:center;gap:11px;padding:0 8px 24px;white-space:nowrap;overflow:hidden}.brand>span{flex:0 0 38px;height:38px;display:grid;place-items:center;background:#d9eeeb;color:#176f73;border-radius:9px;font-weight:bold}.brand b,.brand small{display:block}.brand b{font-size:15px}.brand small{font-size:12px;color:#a6c4c3;margin-top:4px}nav{display:grid;gap:5px}nav button,.collapse{border:0;background:transparent;color:#cde0df;border-radius:8px;cursor:pointer}nav button{height:44px;display:flex;align-items:center;gap:12px;padding:0 12px;white-space:nowrap;overflow:hidden;text-align:left}nav button:hover,nav button.active{color:white;background:#28595b}nav i{font-style:normal;flex:0 0 24px;height:24px;display:grid;place-items:center;border:1px solid #79a09f;border-radius:6px;font-size:12px}nav em{font-style:normal;font-size:14px}.collapse{margin-top:auto;padding:10px;color:#9dbab9}.collapsed .brand div,.collapsed nav em{display:none}.collapsed .collapse{font-size:0}.collapsed .collapse::after{content:'展开';font-size:12px}.workspace{margin-left:var(--side);transition:margin .2s;min-width:0}.workspace header{height:62px;background:white;border-bottom:1px solid #e5ebed;display:flex;align-items:center;justify-content:space-between;padding:0 28px;color:#465a63}.workspace main{padding:28px 30px;max-width:1440px;margin:auto}.header-title{display:flex;align-items:center;min-width:0;white-space:nowrap}.header-title span{font-size:13px;color:#718087;overflow:hidden;text-overflow:ellipsis}.header-title i{height:14px;border-left:1px solid #d5dddf;margin:0 12px}.header-title b{font-size:14px}.account{display:flex;align-items:center;gap:14px;font-size:13px}.mobile-toggle{display:none;border:0;background:none;font-size:19px;margin-right:10px}@media(max-width:720px){.shell{--side:76px}.brand div,nav em{display:none}.collapse{display:none}.workspace header{padding:0 14px}.account>span,.header-title span,.header-title i{display:none}.workspace main{padding:18px}.mobile-toggle{display:inline-block}}
</style>
