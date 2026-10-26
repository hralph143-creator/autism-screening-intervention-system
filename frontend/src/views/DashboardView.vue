<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRight } from '@element-plus/icons-vue'
import { api, messageOf } from '../api'

const router = useRouter(); const loading = ref(true); const error = ref('')
const health = ref<any>(null); const info = ref<any>(null); const stats = ref<any>({ total_children: 0, added_this_month: 0, recent_children: [] })
const entries = [
  ['/children','儿童档案'],
  ['/analysis','视频分析'],
  ['/observations','行为观察'],
  ['/activities','家庭互动'],
  ['/history','综合历史'],
]
async function load() {
  loading.value = true; error.value = ''
  try {
    [health.value, info.value, stats.value] = await Promise.all([api.get('/health'), api.get('/system/info'), api.get('/dashboard/stats')]).then(values => values.map(value => value.data))
  } catch (reason) { error.value = messageOf(reason) } finally { loading.value = false }
}
function formatDate(value: string) { return new Date(value).toLocaleDateString('zh-CN') }
onMounted(load)
</script>
<template>
  <div class="page-head"><h1>系统首页</h1><el-button :loading="loading" @click="load">刷新数据</el-button></div>
  <el-alert v-if="error" :title="error" type="error" show-icon :closable="false"/>
  <template v-else>
    <div class="summary-grid" v-loading="loading"><div class="metric panel"><span>儿童档案总数</span><b>{{ stats.total_children }}</b></div><div class="metric panel"><span>本月新增档案</span><b>{{ stats.added_this_month }}</b></div><div class="service panel"><div><i :class="{ ok: health?.status==='ok' }"></i><span><b>后端服务</b><small>{{ health?.status==='ok'?'运行正常':'状态异常' }}</small></span></div><div><i :class="{ ok: health?.database==='connected' }"></i><span><b>SQLite 数据库</b><small>{{ health?.database==='connected'?'连接正常':'连接异常' }}</small></span></div></div></div>
    <div class="content-grid">
      <section class="panel recent"><div class="section-head"><h2>最近创建的档案</h2><el-button link type="primary" @click="router.push('/children')">查看全部</el-button></div><el-table v-if="stats.recent_children.length" :data="stats.recent_children"><el-table-column prop="child_code" label="儿童编号" min-width="180"/><el-table-column prop="nickname" label="档案昵称"/><el-table-column prop="age_text" label="年龄" width="120"/><el-table-column label="建档日期" width="120"><template #default="scope">{{ formatDate(scope.row.created_at) }}</template></el-table-column></el-table><div v-else class="empty">暂无儿童档案<br/><el-button link type="primary" @click="router.push('/children')">创建第一份档案</el-button></div></section>
      <section class="panel navigation"><h2>功能导航</h2><button v-for="entry in entries" :key="entry[0]" @click="router.push(entry[0])"><b>{{ entry[1] }}</b><ArrowRight/></button></section>
    </div>
  </template>
</template>
<style scoped>.summary-grid{display:grid;grid-template-columns:230px 230px 1fr;gap:14px}.metric span,.metric b{display:block}.metric span{color:#5d6e75}.metric b{font-size:32px;color:#176f73;margin-top:12px}.service{display:grid;grid-template-columns:1fr 1fr;align-items:center}.service>div{display:flex;align-items:center;gap:13px;padding:10px 18px}.service i{width:10px;height:10px;background:#b9c3c5;border-radius:50%;box-shadow:0 0 0 5px #f0f2f3}.service i.ok{background:#2d9080;box-shadow:0 0 0 5px #e6f4f1}.service b,.service small{display:block}.service small{color:#7f8d92;margin-top:6px}.content-grid{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:14px;margin-top:14px}.section-head{display:flex;justify-content:space-between;align-items:center}.section-head h2,.navigation h2{font-size:17px}.empty{text-align:center;color:#849197;padding:55px 20px;line-height:2}.navigation button{border:0;border-top:1px solid #edf0f1;background:white;width:100%;display:flex;justify-content:space-between;align-items:center;text-align:left;padding:15px 4px;cursor:pointer}.navigation button:hover{color:#167c80}.navigation button svg{width:16px;color:#8ba0a3}@media(max-width:1000px){.summary-grid{grid-template-columns:1fr 1fr}.service{grid-column:1/-1}.content-grid{grid-template-columns:1fr}}@media(max-width:650px){.summary-grid{grid-template-columns:1fr}.service{grid-column:auto;grid-template-columns:1fr}.content-grid{grid-template-columns:1fr}}</style>

