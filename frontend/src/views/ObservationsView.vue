<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api, messageOf } from '../api'

interface Child { id:number; child_code:string; nickname:string }
interface Option { value:string; label:string }
interface Question { key:string; label:string }
interface Dimension { key:string; label:string; items:Question[] }
interface Definition { dimensions:Dimension[]; options:Option[]; scenes:string[]; observer_roles:string[]; disclaimer:string }
interface Video { id:number; original_filename:string; status:string; created_at:string; sampled_frames:number|null }
interface Observation { id:number; child_id:number; child_code:string; child_nickname:string; video_analysis_id:number|null; linked_video:Video|null; observation_date:string; observation_scene:string; observer_role:string; observation_data:Record<string,string>; observation_items:any[]; summary_notes:string|null; auxiliary_summary:string; data_completeness:any; disclaimer:string; created_at:string; updated_at:string }

const route = useRoute(); const router = useRouter()
const definition = ref<Definition|null>(null); const children = ref<Child[]>([]); const videos = ref<Video[]>([])
const rows = ref<Observation[]>([]); const total = ref(0); const loading = ref(false); const error = ref('')
const page = ref(1); const pageSize = ref(10); const filterChild = ref<number|null>(null); const dateRange = ref<[string,string]|null>(null)
const dialogOpen = ref(false); const detailOpen = ref(false); const submitting = ref(false); const editingId = ref<number|null>(null); const detail = ref<Observation|null>(null)
const answers = ref<Record<string,string>>({})
const form = reactive({ child_id:null as number|null, observation_date:'', observation_scene:'', observer_role:'', video_analysis_id:null as number|null, summary_notes:'' })
const videoStatus:Record<string,string> = { PENDING:'等待中', RUNNING:'分析中', COMPLETED:'已完成', FAILED:'失败', INTERRUPTED:'已中断' }

const groupedDetail = computed(()=>{
  if (!detail.value || !definition.value) return []
  return definition.value.dimensions.map(dimension=>({ ...dimension, items:detail.value!.observation_items.filter(item=>item.dimension_key===dimension.key) })).filter(group=>group.items.length)
})

function today(){ const now=new Date(); const offset=now.getTimezoneOffset()*60000; return new Date(now.getTime()-offset).toISOString().slice(0,10) }
async function loadDefinition(){ definition.value=(await api.get('/observations/form-definition')).data }
async function loadChildren(){ children.value=(await api.get('/children',{params:{page_size:100}})).data.items }
async function loadVideos(childId:number|null, selected:number|null=null){
  videos.value=[]
  if(!childId) return
  try { videos.value=(await api.get('/video-analyses',{params:{child_id:childId,page_size:100}})).data.items; form.video_analysis_id=selected && videos.value.some(item=>item.id===selected) ? selected : null }
  catch(reason){ ElMessage.error(messageOf(reason)) }
}
async function load(){
  loading.value=true; error.value=''
  try { const {data}=await api.get('/observations',{params:{child_id:filterChild.value||undefined,date_from:dateRange.value?.[0],date_to:dateRange.value?.[1],page:page.value,page_size:pageSize.value}}); rows.value=data.items; total.value=data.total }
  catch(reason){ error.value=messageOf(reason) } finally { loading.value=false }
}
function refresh(){ page.value=1; void load() }
function resetForm(){ Object.assign(form,{child_id:null,observation_date:today(),observation_scene:'',observer_role:'',video_analysis_id:null,summary_notes:''}); answers.value={}; videos.value=[] }
function createRecord(){ editingId.value=null; resetForm(); if(filterChild.value){ form.child_id=filterChild.value; void loadVideos(form.child_id) } dialogOpen.value=true }
async function editRecord(row:Observation){
  try { const {data}=await api.get(`/observations/${row.id}`); editingId.value=row.id; Object.assign(form,{child_id:data.child_id,observation_date:data.observation_date,observation_scene:data.observation_scene,observer_role:data.observer_role,video_analysis_id:data.video_analysis_id,summary_notes:data.summary_notes||''}); answers.value={...data.observation_data}; await loadVideos(data.child_id,data.video_analysis_id); dialogOpen.value=true }
  catch(reason){ ElMessage.error(messageOf(reason)) }
}
async function viewRecord(row:Observation){ try{ detail.value=(await api.get(`/observations/${row.id}`)).data; detailOpen.value=true }catch(reason){ ElMessage.error(messageOf(reason)) } }
async function save(){
  if(!form.child_id) return ElMessage.warning('请选择儿童档案')
  if(!form.observation_date) return ElMessage.warning('请选择观察日期')
  if(!form.observation_scene) return ElMessage.warning('请选择观察场景')
  if(!form.observer_role) return ElMessage.warning('请选择观察者身份')
  if(!Object.keys(answers.value).length) return ElMessage.warning('请至少填写一个观察项目')
  submitting.value=true
  const payload={...form,observation_data:answers.value,summary_notes:form.summary_notes.trim()||null}
  try { if(editingId.value) await api.put(`/observations/${editingId.value}`,payload); else await api.post('/observations',payload); ElMessage.success(editingId.value?'观察记录已更新':'观察记录已保存'); dialogOpen.value=false; await load() }
  catch(reason){ ElMessage.error(messageOf(reason)) } finally{submitting.value=false}
}
async function removeRecord(row:Observation){
  try { await ElMessageBox.confirm(`确认删除 #${row.id} 行为观察记录吗？此操作无法恢复。`,'删除观察记录',{type:'warning',confirmButtonText:'确认删除',cancelButtonText:'取消'}); await api.delete(`/observations/${row.id}`); ElMessage.success('观察记录已删除'); if(rows.value.length===1&&page.value>1) page.value--; await load() }
  catch(reason:any){ if(reason!=='cancel'&&reason!=='close') ElMessage.error(messageOf(reason)) }
}
function clearAnswer(key:string){ const copy={...answers.value}; delete copy[key]; answers.value=copy }
function formatDate(value:string){ return new Date(value).toLocaleString('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit'}) }
function videoLabel(video:Video){ const frames=video.sampled_frames==null?'':` · ${video.sampled_frames}帧`; return `#${video.id} ${video.original_filename} · ${videoStatus[video.status]||video.status}${frames}` }
function openVideo(id:number){ detailOpen.value=false; void router.push({path:'/analysis',query:{task:String(id)}}) }

onMounted(async()=>{ try{ await Promise.all([loadDefinition(),loadChildren()]); const queryChild=Number(route.query.child); if(Number.isInteger(queryChild)&&queryChild>0){ filterChild.value=queryChild } await load(); const recordId=Number(route.query.record); if(Number.isInteger(recordId)&&recordId>0) await viewRecord({id:recordId} as Observation) }catch(reason){ error.value=messageOf(reason) } })
</script>

<template>
  <div class="page-head"><div><h1>行为观察</h1><p>记录具体日常表现并整理信息；本表不是临床量表，不产生医学风险评分</p></div><el-button type="primary" @click="createRecord">新建观察记录</el-button></div>
  <el-alert v-if="definition" :title="definition.disclaimer" type="warning" show-icon :closable="false" class="notice"/>
  <el-alert v-if="!children.length && !error" title="尚无儿童档案，请先创建档案后再填写观察记录" type="info" show-icon :closable="false" class="notice"><template #default><el-button link type="primary" @click="router.push('/children')">前往儿童档案</el-button></template></el-alert>
  <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="notice"><template #default><el-button link type="primary" @click="load">重新加载</el-button></template></el-alert>
  <section class="panel">
    <div class="toolbar"><el-select v-model="filterChild" clearable filterable placeholder="全部儿童" @change="refresh"><el-option v-for="child in children" :key="child.id" :value="child.id" :label="`${child.child_code} · ${child.nickname}`"/></el-select><el-date-picker v-model="dateRange" type="daterange" value-format="YYYY-MM-DD" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" :disabled-date="(value:Date)=>value.getTime()>Date.now()" @change="refresh"/><el-button @click="refresh">查询</el-button></div>
    <el-table v-loading="loading" :data="rows" stripe><el-table-column prop="id" label="记录" width="80"><template #default="scope">#{{ scope.row.id }}</template></el-table-column><el-table-column label="儿童档案" min-width="190"><template #default="scope"><b>{{ scope.row.child_code }}</b><small>{{ scope.row.child_nickname }}</small></template></el-table-column><el-table-column prop="observation_date" label="观察日期" width="120"/><el-table-column prop="observation_scene" label="观察场景" width="120"/><el-table-column prop="observer_role" label="观察者" width="120"/><el-table-column label="关联视频" min-width="160"><template #default="scope"><template v-if="scope.row.linked_video"><span>{{ scope.row.linked_video.original_filename }}</span><small>{{ videoStatus[scope.row.linked_video.status] }}</small></template><span v-else class="muted">未关联</span></template></el-table-column><el-table-column label="数据完整度" width="120"><template #default="scope">{{ scope.row.data_completeness.recorded_items }}/{{ scope.row.data_completeness.total_items }} 项</template></el-table-column><el-table-column label="创建时间" width="130"><template #default="scope">{{ formatDate(scope.row.created_at) }}</template></el-table-column><el-table-column label="操作" width="180" fixed="right"><template #default="scope"><el-button link type="primary" @click="viewRecord(scope.row)">查看</el-button><el-button link @click="editRecord(scope.row)">编辑</el-button><el-button link type="danger" @click="removeRecord(scope.row)">删除</el-button></template></el-table-column><template #empty><div class="empty"><span>暂无行为观察记录</span><el-button link type="primary" @click="createRecord">创建第一条记录</el-button></div></template></el-table>
    <div class="pagination"><span>共 {{ total }} 条</span><el-pagination v-model:current-page="page" v-model:page-size="pageSize" layout="prev,pager,next,sizes" :page-sizes="[10,20,50]" :total="total" @current-change="load" @size-change="refresh"/></div>
  </section>

  <el-dialog v-model="dialogOpen" :title="editingId?'编辑行为观察记录':'新建行为观察记录'" width="min(920px, 94vw)" destroy-on-close>
    <div class="base-form"><label>儿童档案<el-select v-model="form.child_id" filterable placeholder="请选择" @change="loadVideos(form.child_id)"><el-option v-for="child in children" :key="child.id" :value="child.id" :label="`${child.child_code} · ${child.nickname}`"/></el-select></label><label>观察日期<el-date-picker v-model="form.observation_date" type="date" value-format="YYYY-MM-DD" :disabled-date="(value:Date)=>value.getTime()>Date.now()" style="width:100%"/></label><label>观察场景<el-select v-model="form.observation_scene" placeholder="请选择"><el-option v-for="scene in definition?.scenes" :key="scene" :value="scene"/></el-select></label><label>观察者身份<el-select v-model="form.observer_role" placeholder="请选择"><el-option v-for="role in definition?.observer_roles" :key="role" :value="role"/></el-select></label></div>
    <label class="video-field">可选关联视频分析<el-select v-model="form.video_analysis_id" clearable filterable :disabled="!form.child_id" placeholder="不关联视频也可保存"><el-option v-for="video in videos" :key="video.id" :value="video.id" :label="videoLabel(video)"/></el-select><small>只显示当前儿童的真实视频记录；失败或未完成状态不会产生虚假分析结果。</small></label>
    <div class="questionnaire"><section v-for="dimension in definition?.dimensions" :key="dimension.key"><h3>{{ dimension.label }}</h3><div v-for="question in dimension.items" :key="question.key" class="question"><div><span>{{ question.label }}</span><el-button v-if="answers[question.key]" link @click="clearAnswer(question.key)">清除</el-button></div><el-radio-group v-model="answers[question.key]"><el-radio-button v-for="option in definition?.options" :key="option.value" :value="option.value">{{ option.label }}</el-radio-button></el-radio-group></div></section></div>
    <label class="notes-field">补充说明<el-input v-model="form.summary_notes" type="textarea" :rows="4" maxlength="4000" show-word-limit placeholder="仅记录与本次观察有关的信息，请勿填写不必要的真实身份信息"/></label>
    <template #footer><el-button :disabled="submitting" @click="dialogOpen=false">取消</el-button><el-button type="primary" :loading="submitting" @click="save">保存记录</el-button></template>
  </el-dialog>

  <el-drawer v-model="detailOpen" title="行为观察详情" size="min(760px, 94vw)"><template v-if="detail"><el-alert :title="detail.disclaimer" type="warning" :closable="false"/><div class="detail-title"><div><b>{{ detail.child_code }} · {{ detail.child_nickname }}</b><span>{{ detail.observation_date }} · {{ detail.observation_scene }} · {{ detail.observer_role }}</span></div><el-button @click="editRecord(detail);detailOpen=false">编辑</el-button></div><section class="summary"><h3>辅助观察摘要</h3><p>{{ detail.auxiliary_summary }}</p><div>已记录 {{ detail.data_completeness.recorded_items }}/{{ detail.data_completeness.total_items }} 项 · 无法判断 {{ detail.data_completeness.unable_to_judge_items }} 项 · 未观察 {{ detail.data_completeness.not_observed_items }} 项</div></section><section v-for="group in groupedDetail" :key="group.key" class="detail-group"><h3>{{ group.label }}</h3><div v-for="item in group.items" :key="item.key"><span>{{ item.label }}</span><el-tag effect="plain">{{ item.value_label }}</el-tag></div></section><section class="notes"><h3>观察者补充说明</h3><p>{{ detail.summary_notes||'未填写' }}</p></section><section v-if="detail.linked_video" class="linked"><h3>关联视频分析</h3><div><div><b>#{{ detail.linked_video.id }} {{ detail.linked_video.original_filename }}</b><span>{{ videoStatus[detail.linked_video.status] }}<template v-if="detail.linked_video.sampled_frames!=null"> · 有效分析 {{ detail.linked_video.sampled_frames }} 帧</template></span></div><el-button type="primary" plain @click="openVideo(detail.linked_video.id)">前往视频记录</el-button></div></section></template></el-drawer>
</template>

<style scoped>
.notice{margin-bottom:16px}.toolbar{display:flex;gap:10px;margin-bottom:16px}.toolbar>.el-select{width:230px}.el-table small{display:block;color:#87969b;margin-top:4px}.muted{color:#98a4a8}.empty{padding:34px;display:flex;flex-direction:column;gap:8px}.pagination{display:flex;justify-content:space-between;align-items:center;margin-top:18px;color:#7b898f;font-size:13px}.base-form{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.base-form label,.video-field,.notes-field{display:grid;gap:7px;font-size:13px;font-weight:600}.video-field{margin:16px 0}.video-field small{color:#7c8d92;font-weight:400}.questionnaire{display:grid;gap:12px}.questionnaire section{border:1px solid #e3eaec;border-radius:9px;padding:15px}.questionnaire h3{font-size:15px;color:#2b5e61;margin-bottom:12px}.question{padding:12px 0;border-top:1px dashed #e3e9eb}.question:first-of-type{border-top:0;padding-top:0}.question>div{display:flex;justify-content:space-between;align-items:center;margin-bottom:9px;color:#4c6067;font-size:13px}.question :deep(.el-radio-button__inner){padding:8px 10px;font-size:12px}.notes-field{margin-top:16px}.detail-title{display:flex;justify-content:space-between;align-items:flex-start;margin:18px 0}.detail-title b,.detail-title span{display:block}.detail-title span{font-size:13px;color:#75868b;margin-top:6px}.summary{background:#eef6f5;border-radius:9px;padding:16px}.summary h3,.detail-group h3,.notes h3,.linked h3{font-size:15px}.summary p{line-height:1.8;color:#455c63}.summary div{font-size:12px;color:#718489}.detail-group,.notes,.linked{margin-top:20px}.detail-group>div{display:flex;justify-content:space-between;gap:15px;align-items:center;padding:11px 0;border-bottom:1px solid #edf1f2;font-size:13px}.notes p{white-space:pre-wrap;line-height:1.8;background:#f7f9fa;padding:14px;border-radius:8px;color:#50656b}.linked>div{display:flex;justify-content:space-between;align-items:center;background:#f5f8f9;padding:14px;border-radius:8px}.linked b,.linked span{display:block}.linked span{font-size:12px;color:#7a8a8f;margin-top:5px}@media(max-width:720px){.toolbar{flex-direction:column}.toolbar>.el-select{width:100%}.base-form{grid-template-columns:1fr}.question .el-radio-group{display:grid;grid-template-columns:1fr 1fr}.question :deep(.el-radio-button__inner){width:100%}.pagination,.detail-title,.linked>div{align-items:flex-start;flex-direction:column;gap:10px}}
</style>
