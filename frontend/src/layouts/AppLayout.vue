<script setup lang="ts">
import { computed, ref, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Clock, Expand, Fold, FolderOpened, House, MagicStick,
  Menu, Setting, SwitchButton, VideoCamera, View,
} from '@element-plus/icons-vue'
import { api, messageOf } from '../api'
import { administrator, setAdministrator } from '../session'

const route = useRoute(); const router = useRouter(); const collapsed = ref(false)
const pageTitle = computed(() => String(route.meta.title || '系统'))
const items:{ path:string; label:string; icon:Component }[] = [
  { path:'/', label:'系统首页', icon:House },
  { path:'/children', label:'儿童档案', icon:FolderOpened },
  { path:'/analysis', label:'视频分析', icon:VideoCamera },
  { path:'/observations', label:'行为观察', icon:View },
  { path:'/activities', label:'家庭互动', icon:MagicStick },
  { path:'/history', label:'综合历史', icon:Clock },
  { path:'/settings', label:'系统设置', icon:Setting },
]
function isActive(path:string){ return route.path===path || (path!=='/' && route.path.startsWith(`${path}/`)) }
async function logout() {
  try { await api.post('/auth/logout'); setAdministrator(null); await router.replace('/login') }
  catch (error) { ElMessage.error(messageOf(error)) }
}
</script>
<template>
  <div class="shell" :class="{ collapsed }">
    <aside>
      <div class="brand"><span class="brand-icon"><img src="/app-icon.png" alt="儿童行为观察系统图标"/></span><div><b>儿童行为观察</b><small>本地管理系统</small></div></div>
      <nav><button v-for="item in items" :key="item.path" :class="{ active: isActive(item.path) }" :title="collapsed ? item.label : undefined" @click="router.push(item.path)"><i><component :is="item.icon"/></i><em>{{ item.label }}</em></button></nav>
      <button class="collapse" :title="collapsed ? '展开导航' : '收起导航'" @click="collapsed = !collapsed"><i><component :is="collapsed ? Expand : Fold"/></i><span>{{ collapsed ? '展开导航' : '收起导航' }}</span></button>
    </aside>
    <section class="workspace">
      <header><div class="header-title"><button class="mobile-toggle" title="切换导航" @click="collapsed = !collapsed"><Menu/></button><span>基于深度学习的自闭症筛查与干预系统</span><i></i><b>{{ pageTitle }}</b></div><div class="account"><span>管理员：{{ administrator?.username }}</span><el-button text @click="logout"><el-icon><SwitchButton/></el-icon><span>退出登录</span></el-button></div></header>
      <main><router-view /></main>
    </section>
  </div>
</template>
<style scoped>
.shell{--side:224px;min-height:100vh}.shell.collapsed{--side:76px}aside{position:fixed;z-index:10;inset:0 auto 0 0;width:var(--side);box-sizing:border-box;background:linear-gradient(180deg,#17474a 0%,#133c3f 62%,#103639 100%);border-right:1px solid rgba(255,255,255,.06);color:white;padding:22px 14px;display:flex;flex-direction:column;transition:width .22s ease;box-shadow:8px 0 28px rgba(12,47,49,.08)}.brand{display:flex;align-items:center;gap:12px;padding:0 8px 26px;white-space:nowrap;overflow:hidden}.brand-icon{flex:0 0 42px;height:42px;display:grid;place-items:center;background:linear-gradient(145deg,#f1fbf9,#cce9e5);color:#176f73;border-radius:12px;overflow:hidden;box-shadow:0 7px 18px rgba(4,36,38,.2),inset 0 0 0 1px rgba(255,255,255,.65)}.brand-icon img{width:100%;height:100%;object-fit:cover}.brand b,.brand small{display:block}.brand b{font-size:15px;letter-spacing:.02em}.brand small{font-size:12px;color:#a9c8c7;margin-top:5px}nav{display:grid;gap:6px}nav button,.collapse{border:0;background:transparent;color:#c9dfde;border-radius:10px;cursor:pointer}nav button{position:relative;height:48px;display:flex;align-items:center;gap:12px;padding:0 10px;white-space:nowrap;overflow:hidden;text-align:left;transition:background .18s ease,color .18s ease,transform .18s ease}nav button:hover{color:white;background:rgba(112,184,180,.13);transform:translateX(2px)}nav button.active{color:white;background:linear-gradient(90deg,rgba(78,151,150,.42),rgba(72,139,140,.28));box-shadow:inset 0 0 0 1px rgba(173,222,218,.08)}nav button.active::before{content:'';position:absolute;left:0;width:3px;height:24px;border-radius:0 4px 4px 0;background:#8dd5cd;box-shadow:0 0 10px rgba(141,213,205,.55)}nav i,.collapse i{font-style:normal;flex:0 0 30px;height:30px;display:grid;place-items:center;border-radius:8px;color:#b9d8d6;transition:background .18s ease,color .18s ease,box-shadow .18s ease}nav i svg,.collapse i svg{width:18px;height:18px}nav button:hover i{color:#e8f7f5;background:rgba(255,255,255,.06)}nav button.active i{color:#176f73;background:#dff2ef;box-shadow:0 4px 12px rgba(5,46,48,.22)}nav em{font-style:normal;font-size:14px;letter-spacing:.01em}.collapse{margin-top:auto;height:42px;padding:0 10px;display:flex;align-items:center;gap:12px;text-align:left;color:#91b5b3;transition:color .18s ease,background .18s ease}.collapse:hover{color:#e5f4f2;background:rgba(255,255,255,.05)}.collapse span{font-size:13px}.collapsed .brand{padding-inline:3px}.collapsed .brand div,.collapsed nav em,.collapsed .collapse span{display:none}.collapsed nav button,.collapsed .collapse{justify-content:center;padding-inline:0}.collapsed nav button:hover{transform:none}.workspace{margin-left:var(--side);transition:margin .22s ease;min-width:0}.workspace header{height:62px;background:white;border-bottom:1px solid #e5ebed;display:flex;align-items:center;justify-content:space-between;padding:0 28px;color:#465a63}.workspace main{padding:28px 30px;max-width:1440px;margin:auto}.header-title{display:flex;align-items:center;min-width:0;white-space:nowrap}.header-title span{font-size:13px;color:#718087;overflow:hidden;text-overflow:ellipsis}.header-title>i{height:14px;border-left:1px solid #d5dddf;margin:0 12px}.header-title b{font-size:14px}.account{display:flex;align-items:center;gap:14px;font-size:13px}.account :deep(.el-button)>span{display:flex;align-items:center;gap:6px}.mobile-toggle{display:none;width:34px;height:34px;padding:7px;border:0;border-radius:8px;background:transparent;color:#35595d;margin-right:8px}.mobile-toggle:hover{background:#eef6f5}.mobile-toggle svg{width:20px;height:20px}@media(max-width:720px){.shell{--side:76px}.brand{padding-inline:3px}.brand div,nav em{display:none}nav button{justify-content:center;padding-inline:0}.collapse{display:none}.workspace header{padding:0 14px}.account>span,.header-title>span,.header-title>i{display:none}.workspace main{padding:18px}.mobile-toggle{display:inline-grid;place-items:center}}
</style>
