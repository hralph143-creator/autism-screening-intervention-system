<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { Calendar, Clock, VideoCamera, View, MagicStick } from '@element-plus/icons-vue'
import { api, messageOf } from '../api'

interface Child { id:number; child_code:string; nickname:string }
interface TimelineItem { record_type:string; record_type_label:string; record_id:number; business_date:string; date_meaning:string; title:string; status:string; status_label:string; detail_path:string }
const route=useRoute(); const router=useRouter()
const children=ref<Child[]>([]); const childId=ref<number|null>(null); const overview=ref<any>(null)
const rows=ref<TimelineItem[]>([]); const total=ref(0); const page=ref(1); const pageSize=ref(10)
const recordType=ref(''); const dateRange=ref<[string,string]|null>(null); const sortOrder=ref('desc')
const loading=ref(false); const error=ref(''); const chartEl=ref<HTMLDivElement>(); let chart:echarts.ECharts|null=null
const reportTypes=ref(['VIDEO','OBSERVATION','ACTIVITY'])
const icons:Record<string,any>={VIDEO:VideoCamera,OBSERVATION:View,ACTIVITY:MagicStick}
const tagTypes:Record<string,string>={VIDEO:'primary',OBSERVATION:'warning',ACTIVITY:'success'}

async function loadChildren(){ children.value=(await api.get('/children',{params:{page_size:100}})).data.items }
async function loadAll(){
  if(!childId.value){overview.value=null;rows.value=[];total.value=0;chart?.dispose();chart=null;return}
  loading.value=true;error.value=''
  try{
    const params={record_type:recordType.value||undefined,start_date:dateRange.value?.[0],end_date:dateRange.value?.[1],sort_order:sortOrder.value,page:page.value,page_size:pageSize.value}
    const [overviewResponse,timelineResponse]=await Promise.all([api.get(`/children/${childId.value}/overview`),api.get(`/children/${childId.value}/timeline`,{params})])
    overview.value=overviewResponse.data;rows.value=timelineResponse.data.items;total.value=timelineResponse.data.total
    await nextTick();drawChart()
  }catch(reason:any){
    error.value=reason?.response?.status===404
      ? '综合历史接口尚未加载，请关闭旧后端窗口后重新运行 run.bat'
      : messageOf(reason)
  }finally{loading.value=false}
}
function refresh(){page.value=1;void loadAll()}
function drawChart(){
  if(!chartEl.value||!overview.value)return
  chart?.dispose();chart=echarts.init(chartEl.value)
  const data=overview.value.monthly_counts
  chart.setOption({
    color:['#3b8f91','#d59545','#6a8f7d'],
    tooltip:{trigger:'axis',confine:true},
    legend:{data:['视频分析','行为观察','家庭互动'],top:0,left:'center',itemWidth:16,itemHeight:9,itemGap:22},
    grid:{left:24,right:24,top:50,bottom:18,containLabel:true},
    xAxis:{type:'category',data:data.map((x:any)=>x.month),axisLabel:{margin:14}},
    yAxis:{type:'value',minInterval:1},
    series:[
      {name:'视频分析',type:'bar',stack:'count',barMaxWidth:120,data:data.map((x:any)=>x.VIDEO)},
      {name:'行为观察',type:'bar',stack:'count',barMaxWidth:120,data:data.map((x:any)=>x.OBSERVATION)},
      {name:'家庭互动',type:'bar',stack:'count',barMaxWidth:120,data:data.map((x:any)=>x.ACTIVITY)},
    ],
  })
}
function openDetail(item:TimelineItem){
  const query=item.record_type==='VIDEO'?{task:String(item.record_id),child:String(childId.value)}:{record:String(item.record_id),child:String(childId.value)}
  void router.push({path:item.detail_path,query})
}
function generateReport(){
  if(!childId.value||!reportTypes.value.length)return
  void router.push({path:`/history/report/${childId.value}`,query:{start:dateRange.value?.[0],end:dateRange.value?.[1],types:reportTypes.value.join(',')}})
}
function resize(){chart?.resize()}
onMounted(async()=>{try{await loadChildren();const queryChild=Number(route.query.child);if(Number.isInteger(queryChild)&&children.value.some(x=>x.id===queryChild))childId.value=queryChild;else if(children.value.length)childId.value=children.value[0].id;await loadAll();window.addEventListener('resize',resize)}catch(reason){error.value=messageOf(reason)}})
onBeforeUnmount(()=>{chart?.dispose();window.removeEventListener('resize',resize)})
</script>

<template>
  <div class="page-head"><h1>综合历史</h1><el-button :loading="loading" @click="loadAll">刷新</el-button></div>
  <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="notice"><template #default><el-button link type="primary" @click="loadAll">重新加载</el-button></template></el-alert>
  <section class="panel selector"><label>儿童档案<el-select v-model="childId" filterable placeholder="请选择儿童编号或昵称" @change="refresh"><el-option v-for="child in children" :key="child.id" :value="child.id" :label="`${child.child_code} · ${child.nickname}`"/></el-select></label><div v-if="!children.length" class="no-child">暂无儿童档案，请先创建档案。</div></section>

  <template v-if="overview">
    <section class="profile panel"><div><span>儿童编号</span><b>{{ overview.child.child_code }}</b></div><div><span>档案昵称</span><b>{{ overview.child.nickname }}</b></div><div><span>年龄</span><b>{{ overview.child.age_text }}</b></div><div><span>性别</span><b>{{ overview.child.gender||'未填写' }}</b></div><div><span>建档日期</span><b>{{ overview.child.created_at.slice(0,10) }}</b></div></section>
    <div class="overview-grid"><article class="panel"><VideoCamera/><span>视频分析</span><b>{{ overview.counts.video }}</b></article><article class="panel"><View/><span>行为观察</span><b>{{ overview.counts.observation }}</b></article><article class="panel"><MagicStick/><span>家庭互动</span><b>{{ overview.counts.activity }}</b></article><article class="panel"><Calendar/><span>最近记录</span><b class="date">{{ overview.latest_record_date||'暂无' }}</b></article></div>
    <section class="panel trend"><div class="section-title"><h2>记录数量变化</h2></div><div v-if="overview.monthly_counts.length" ref="chartEl" class="chart"></div><div v-else class="empty">暂无可统计记录</div></section>

    <section class="panel history-panel" v-loading="loading">
      <div class="section-title"><h2>综合时间线</h2><span>共 {{ total }} 条</span></div>
      <div class="filters"><el-select v-model="recordType" clearable placeholder="全部记录类型" @change="refresh"><el-option label="视频分析" value="VIDEO"/><el-option label="行为观察" value="OBSERVATION"/><el-option label="家庭互动" value="ACTIVITY"/></el-select><el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" range-separator="至" @change="refresh"/><el-select v-model="sortOrder" @change="refresh"><el-option label="日期从新到旧" value="desc"/><el-option label="日期从旧到新" value="asc"/></el-select></div>
      <el-timeline v-if="rows.length"><el-timeline-item v-for="item in rows" :key="`${item.record_type}-${item.record_id}`" :timestamp="`${item.business_date} · ${item.date_meaning}`" placement="top"><div class="timeline-card"><i><component :is="icons[item.record_type]"/></i><div><div><el-tag :type="tagTypes[item.record_type] as any" effect="plain">{{ item.record_type_label }}</el-tag><el-tag effect="plain">{{ item.status_label }}</el-tag></div><b>{{ item.title }}</b><small>记录 #{{ item.record_id }} · {{ overview.child.child_code }}</small></div><el-button link type="primary" @click="openDetail(item)">查看详情</el-button></div></el-timeline-item></el-timeline><div v-else class="empty">所选条件下暂无历史记录</div>
      <div class="pagination"><span>第 {{ page }} 页</span><el-pagination v-model:current-page="page" v-model:page-size="pageSize" layout="prev,pager,next,sizes" :page-sizes="[10,20,50]" :total="total" @current-change="loadAll" @size-change="refresh"/></div>
    </section>

    <section class="panel report-box"><div><h2>生成综合报告</h2><el-checkbox-group v-model="reportTypes"><el-checkbox value="VIDEO">视频分析</el-checkbox><el-checkbox value="OBSERVATION">行为观察</el-checkbox><el-checkbox value="ACTIVITY">家庭互动</el-checkbox></el-checkbox-group></div><el-button type="primary" :disabled="!reportTypes.length" @click="generateReport">预览报告</el-button></section>
  </template>
</template>

<style scoped>
.notice{margin-bottom:16px}.selector{margin-bottom:14px}.selector label{display:grid;grid-template-columns:90px minmax(260px,520px);gap:10px;align-items:center;font-size:13px;font-weight:600}.no-child{color:#839297}.profile{display:grid;grid-template-columns:repeat(5,1fr);gap:18px;margin-bottom:14px}.profile span,.profile b{display:block}.profile span{font-size:12px;color:#7b8c91}.profile b{margin-top:7px;color:#324e54}.overview-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:14px}.overview-grid article{display:grid;grid-template-columns:34px 1fr;align-items:center}.overview-grid svg{grid-row:1/3;width:23px;color:#338083}.overview-grid span{font-size:12px;color:#75888d}.overview-grid b{font-size:25px;color:#255f63}.overview-grid .date{font-size:16px}.trend,.history-panel{margin-bottom:14px}.section-title{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:15px}.section-title h2,.report-box h2{font-size:17px;margin:0}.section-title>span{font-size:12px;color:#819095}.chart{height:260px}.filters{display:flex;gap:10px;margin-bottom:24px}.filters .el-select{width:190px}.timeline-card{display:grid;grid-template-columns:38px 1fr auto;gap:12px;align-items:center;border:1px solid #e4ebec;border-radius:10px;padding:13px 15px;background:#fff}.timeline-card>i{width:36px;height:36px;display:grid;place-items:center;border-radius:9px;background:#e9f5f3;color:#28777a}.timeline-card svg{width:19px}.timeline-card .el-tag{margin-right:6px}.timeline-card b,.timeline-card small{display:block}.timeline-card b{margin:8px 0 5px}.timeline-card small{color:#859399}.empty{text-align:center;color:#8a979b;padding:36px}.pagination{display:flex;justify-content:space-between;align-items:center;margin-top:18px;color:#7d8b90;font-size:12px}.report-box{display:flex;justify-content:space-between;align-items:center;margin-bottom:28px}.report-box .el-checkbox-group{margin-top:13px}.report-box .el-button{min-width:120px}@media(max-width:900px){.profile{grid-template-columns:repeat(2,1fr)}.overview-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:680px){.selector label{grid-template-columns:1fr}.profile,.overview-grid{grid-template-columns:1fr}.filters,.report-box{align-items:stretch;flex-direction:column}.filters .el-select,.filters .el-date-editor{width:100%!important}.timeline-card{grid-template-columns:38px 1fr}.timeline-card>.el-button{grid-column:2}.pagination{align-items:flex-start;flex-direction:column}}
</style>
