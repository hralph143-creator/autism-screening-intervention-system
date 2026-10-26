<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import type { UploadFile, UploadFiles, UploadInstance, UploadProps, UploadRawFile, UploadUserFile } from 'element-plus'
import { ElMessage, ElMessageBox, genFileId } from 'element-plus'
import * as echarts from 'echarts'
import { useRoute } from 'vue-router'
import { api, messageOf } from '../api'

interface Child { id:number; child_code:string; nickname:string }
interface Task { id:number; child_id:number; child_code:string; child_nickname:string; original_filename:string; file_size:number; duration_seconds:number; width:number; height:number; source_fps:number; status:string; progress:number; error_message:string|null; retry_count:number; created_at:string; completed_at:string|null }

const children = ref<Child[]>([]); const rows = ref<Task[]>([]); const total = ref(0); const loading = ref(false)
const route = useRoute()
const page = ref(1); const pageSize = ref(10); const filterChild = ref<number|null>(null); const filterStatus = ref('')
const childId = ref<number|null>(null); const consent = ref(false); const selectedFile = ref<File|null>(null)
const uploadRef = ref<UploadInstance>(); const fileList = ref<UploadUserFile[]>([])
const uploading = ref(false); const uploadProgress = ref(0); const model = ref<any>(null); const modelLoading = ref(false)
const detailOpen = ref(false); const detail = ref<any>(null); const resultLoading = ref(false); const chartEl = ref<HTMLDivElement>(); let chart: echarts.ECharts|null = null; let pollTimer:number|undefined

const statusLabel:Record<string,string> = { PENDING:'等待中', RUNNING:'分析中', COMPLETED:'已完成', FAILED:'失败', INTERRUPTED:'已中断' }
const statusType:Record<string,string> = { PENDING:'info', RUNNING:'warning', COMPLETED:'success', FAILED:'danger', INTERRUPTED:'danger' }

async function loadModel() {
  modelLoading.value = true
  try { model.value = (await api.get('/models/status', { timeout: 60_000 })).data }
  catch (error) { model.value = { ready:false, error:messageOf(error) } }
  finally { modelLoading.value = false }
}
async function loadChildren() {
  try { children.value = (await api.get('/children', { params:{ page_size:100 } })).data.items }
  catch (error) { ElMessage.error(messageOf(error)) }
}
async function loadTasks(silent=false) {
  if (!silent) loading.value = true
  try {
    const { data } = await api.get('/video-analyses', { params:{ child_id:filterChild.value || undefined, status:filterStatus.value || undefined, page:page.value, page_size:pageSize.value } })
    rows.value = data.items; total.value = data.total
  } catch (error) { if (!silent) ElMessage.error(messageOf(error)) }
  finally { loading.value = false }
}
function warning(message:string) { ElMessage.warning({ message, grouping:true }) }
function clearSelectedFile() {
  selectedFile.value = null
  fileList.value = []
  uploadRef.value?.clearFiles()
}
function chooseFile(file:UploadFile, files:UploadFiles) {
  const raw = file.raw
  if (!raw || !raw.name.toLowerCase().endsWith('.mp4')) {
    clearSelectedFile()
    warning('请选择扩展名为 .mp4 的视频文件')
    return
  }
  selectedFile.value = raw
  fileList.value = files.slice(-1)
}
function removeFile(_file:UploadFile, files:UploadFiles) {
  fileList.value = files
  selectedFile.value = files.at(-1)?.raw || null
}
const replaceFile:UploadProps['onExceed'] = files => {
  clearSelectedFile()
  const raw = files[0] as UploadRawFile|undefined
  if (!raw) return
  raw.uid = genFileId()
  uploadRef.value?.handleStart(raw)
}
async function submit() {
  if (uploading.value) return
  if (!childId.value) return warning('请选择关联儿童档案')
  const raw = selectedFile.value || fileList.value.at(-1)?.raw
  if (!raw) {
    clearSelectedFile()
    return warning('文件选择状态已失效，请重新选择 MP4 视频')
  }
  if (!raw.name.toLowerCase().endsWith('.mp4')) return warning('请选择扩展名为 .mp4 的视频文件')
  if (!consent.value) return warning('请先确认监护人授权与隐私说明')
  const body = new FormData(); body.append('child_id', String(childId.value)); body.append('consent_confirmed', 'true'); body.append('file', raw, raw.name)
  uploading.value = true; uploadProgress.value = 0
  try {
    const { data } = await api.post('/video-analyses', body, { timeout:180_000, onUploadProgress:event => { if (event.total) uploadProgress.value = Math.round(event.loaded / event.total * 100) } })
    ElMessage.success(`视频已安全保存，任务 #${data.id} 已进入本地分析队列`)
    clearSelectedFile(); consent.value = false; page.value = 1; await loadTasks()
  } catch (error) { ElMessage.error(messageOf(error)) }
  finally { uploading.value = false }
}
async function openResult(row:Task) {
  if (row.status !== 'COMPLETED') return
  detailOpen.value = true; resultLoading.value = true; detail.value = null
  try { detail.value = (await api.get(`/video-analyses/${row.id}/result`)).data; await nextTick(); drawChart() }
  catch (error) { ElMessage.error(messageOf(error)); detailOpen.value = false }
  finally { resultLoading.value = false }
}
function drawChart() {
  if (!chartEl.value || !detail.value) return
  chart?.dispose(); chart = echarts.init(chartEl.value)
  const series = detail.value.result.time_series
  chart.setOption({
    color:['#167c80','#e39b37','#6878c8'], tooltip:{ trigger:'axis' }, legend:{ data:['头部位置变化','上肢运动变化','面部中心变化'] },
    grid:{ left:48,right:24,top:48,bottom:42 }, xAxis:{ type:'category', name:'秒', data:series.map((item:any)=>(item.timestamp_ms/1000).toFixed(1)) },
    yAxis:{ type:'value', name:'归一化位移' }, series:[
      { name:'头部位置变化', type:'line', showSymbol:false, connectNulls:false, data:series.map((item:any)=>item.head_motion) },
      { name:'上肢运动变化', type:'line', showSymbol:false, connectNulls:false, data:series.map((item:any)=>item.upper_limb_motion) },
      { name:'面部中心变化', type:'line', showSymbol:false, connectNulls:false, data:series.map((item:any)=>item.face_center_motion) },
    ]
  })
}
async function retry(row:Task) {
  try { await api.post(`/video-analyses/${row.id}/retry`, {}, { timeout:60_000 }); ElMessage.success('任务已重新进入队列'); await loadTasks() }
  catch (error) { ElMessage.error(messageOf(error)) }
}
async function remove(row:Task) {
  try {
    await ElMessageBox.confirm(`确认删除任务 #${row.id}、原视频和所有分析结果吗？`, '删除分析记录', { type:'warning', confirmButtonText:'确认删除', cancelButtonText:'取消' })
    await api.delete(`/video-analyses/${row.id}`); ElMessage.success('相关文件与记录已删除'); await loadTasks()
  } catch (error:any) { if (error !== 'cancel' && error !== 'close') ElMessage.error(messageOf(error)) }
}
function refreshFilters(){ page.value=1; void loadTasks() }
function formatDate(value:string|null){ return value ? new Date(value).toLocaleString('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}) : '—' }
function percent(value:number){ return `${Math.round(value*100)}%` }
function numberValue(value:number|null){ return value == null ? '数据不足' : value.toFixed(4) }
function frameUrl(name:string){ return `/api/video-analyses/${detail.value.analysis.id}/frames/${encodeURIComponent(name)}` }
function resize(){ chart?.resize() }

onMounted(async()=>{ await Promise.all([loadModel(),loadChildren(),loadTasks()]); const taskId=Number(route.query.task); if(Number.isInteger(taskId)&&taskId>0){ try{ const task=(await api.get(`/video-analyses/${taskId}`)).data; if(task.status==='COMPLETED') await openResult(task); else ElMessage.info(`关联视频任务当前状态：${statusLabel[task.status]||task.status}`) }catch(error){ ElMessage.error(messageOf(error)) } } pollTimer=window.setInterval(()=>{ if(rows.value.some(item=>['PENDING','RUNNING'].includes(item.status))) void loadTasks(true) },1500); window.addEventListener('resize',resize) })
onBeforeUnmount(()=>{ if(pollTimer) clearInterval(pollTimer); window.removeEventListener('resize',resize); chart?.dispose() })
</script>

<template>
  <div class="page-head"><h1>视频分析</h1><el-button :loading="modelLoading" @click="loadModel">检查模型</el-button></div>
  <el-alert v-if="model && !model.ready" type="error" show-icon :closable="false" :title="model.error || '视频分析暂不可用，请重新安装模型'" class="model-alert"/>
  <el-alert v-else-if="model?.ready" type="success" show-icon :closable="false" class="model-alert" title="视频分析可用"/>

  <div class="analysis-grid">
    <section class="panel upload-panel">
      <h2>新建分析</h2><p class="hint">MP4 · 最大 100 MB · 最长 120 秒</p>
      <label>关联儿童档案</label><el-select v-model="childId" filterable placeholder="请选择儿童编号或档案昵称" style="width:100%"><el-option v-for="child in children" :key="child.id" :value="child.id" :label="`${child.child_code} · ${child.nickname}`"/></el-select>
      <el-upload ref="uploadRef" v-model:file-list="fileList" drag action="#" accept="video/mp4,.mp4" :auto-upload="false" :limit="1" :on-change="chooseFile" :on-remove="removeFile" :on-exceed="replaceFile" class="video-upload"><div class="upload-copy"><b>拖放或点击选择 MP4 视频</b></div></el-upload>
      <el-checkbox v-model="consent" class="consent">我确认已获得监护人对本次视频采集、保存和本地分析的明确授权，并已了解隐私用途。</el-checkbox>
      <el-progress v-if="uploading" :percentage="uploadProgress" :stroke-width="8"/>
      <el-button type="primary" size="large" :loading="uploading" :disabled="!model?.ready || uploading" @click="submit">保存并开始本地分析</el-button>
    </section>
  </div>

  <section class="panel history-panel">
    <div class="section-head"><div><h2>分析历史</h2><span>共 {{ total }} 条</span></div><div class="filters"><el-select v-model="filterChild" clearable placeholder="全部儿童" @change="refreshFilters"><el-option v-for="child in children" :key="child.id" :value="child.id" :label="`${child.child_code} · ${child.nickname}`"/></el-select><el-select v-model="filterStatus" clearable placeholder="全部状态" @change="refreshFilters"><el-option v-for="(label,key) in statusLabel" :key="key" :value="key" :label="label"/></el-select></div></div>
    <el-table v-loading="loading" :data="rows" stripe><el-table-column prop="id" label="任务" width="78"><template #default="scope">#{{ scope.row.id }}</template></el-table-column><el-table-column label="儿童档案" min-width="190"><template #default="scope"><b>{{ scope.row.child_code }}</b><small>{{ scope.row.child_nickname }}</small></template></el-table-column><el-table-column prop="original_filename" label="视频" min-width="190" show-overflow-tooltip/><el-table-column label="规格" width="145"><template #default="scope">{{ scope.row.width }}×{{ scope.row.height }}<small>{{ scope.row.duration_seconds.toFixed(1) }} 秒</small></template></el-table-column><el-table-column label="状态" width="150"><template #default="scope"><el-tag :type="statusType[scope.row.status] as any">{{ statusLabel[scope.row.status] }}</el-tag><el-progress v-if="scope.row.status==='RUNNING'" :percentage="scope.row.progress" :show-text="false" :stroke-width="5"/></template></el-table-column><el-table-column label="创建时间" width="145"><template #default="scope">{{ formatDate(scope.row.created_at) }}</template></el-table-column><el-table-column label="操作" width="190" fixed="right"><template #default="scope"><el-button v-if="scope.row.status==='COMPLETED'" link type="primary" @click="openResult(scope.row)">查看结果</el-button><el-tooltip v-if="scope.row.error_message" :content="scope.row.error_message"><el-button link type="danger">原因</el-button></el-tooltip><el-button v-if="['FAILED','INTERRUPTED'].includes(scope.row.status)" link @click="retry(scope.row)">重试</el-button><el-button v-if="!['PENDING','RUNNING'].includes(scope.row.status)" link type="danger" @click="remove(scope.row)">删除</el-button></template></el-table-column><template #empty><div class="empty">暂无视频分析记录</div></template></el-table>
    <div class="pagination"><span>第 {{ page }} 页</span><el-pagination v-model:current-page="page" v-model:page-size="pageSize" layout="prev,pager,next,sizes" :page-sizes="[10,20,50]" :total="total" @current-change="loadTasks()" @size-change="refreshFilters"/></div>
  </section>

  <el-drawer v-model="detailOpen" title="视频分析结果" size="min(920px, 94vw)" @closed="chart?.dispose()"><div v-loading="resultLoading"><template v-if="detail"><el-alert type="warning" :closable="false" :title="detail.result.disclaimer"/>
    <div class="result-meta"><b>{{ detail.analysis.child_code }} · {{ detail.analysis.child_nickname }}</b><span>{{ detail.analysis.original_filename }} · {{ detail.analysis.duration_seconds.toFixed(1) }} 秒</span></div>
    <div class="metric-grid"><article><span>姿态有效帧率</span><b>{{ percent(detail.result.summary.pose_coverage) }}</b><small>{{ detail.result.summary.pose_valid_frames }}/{{ detail.result.summary.sampled_frames }} 帧</small></article><article><span>面部有效帧率</span><b>{{ percent(detail.result.summary.face_coverage) }}</b><small>{{ detail.result.summary.face_valid_frames }}/{{ detail.result.summary.sampled_frames }} 帧</small></article><article><span>数据质量</span><b>{{ detail.result.summary.quality_level }}</b></article><article><span>处理耗时</span><b>{{ detail.result.summary.processing_seconds.toFixed(1) }} 秒</b></article></div>
    <h3>运动变化趋势</h3><div ref="chartEl" class="chart"></div>
    <div class="stats"><div><span>头部位置平均变化</span><b>{{ numberValue(detail.result.motion_statistics.head_location_change.mean) }}</b></div><div><span>上肢平均变化</span><b>{{ numberValue(detail.result.motion_statistics.upper_limb_change.mean) }}</b></div><div><span>面部中心平均变化</span><b>{{ numberValue(detail.result.motion_statistics.face_center_change.mean) }}</b></div></div>
    <template v-if="detail.result.preview_frames.length"><h3>关键结果帧</h3><div class="previews"><figure v-for="frame in detail.result.preview_frames" :key="frame.filename"><img :src="frameUrl(frame.filename)" alt="带检测关键点的视频采样帧"/><figcaption>{{ (frame.timestamp_ms/1000).toFixed(1) }} 秒</figcaption></figure></div></template>
    <el-alert v-for="warning in detail.result.warnings" :key="warning" type="warning" :closable="false" :title="warning" class="result-warning"/>
  </template></div></el-drawer>
</template>

<style scoped>
.model-alert{margin-bottom:18px}.analysis-grid{margin-bottom:18px}.panel h2{font-size:17px;margin-bottom:8px}.hint{color:#718188;font-size:13px}.upload-panel{display:grid;gap:14px}.upload-panel label{font-size:13px;font-weight:600;margin-bottom:-8px}.video-upload{width:100%}.video-upload :deep(.el-upload),.video-upload :deep(.el-upload-dragger){width:100%}.upload-copy{color:#557077}.consent{height:auto;align-items:flex-start;white-space:normal;line-height:1.6}.consent :deep(.el-checkbox__input){margin-top:4px}.history-panel{margin-bottom:28px}.section-head{display:flex;justify-content:space-between;gap:14px;align-items:center;margin-bottom:16px}.section-head>div:first-child{display:flex;align-items:baseline;gap:10px}.section-head h2{margin:0}.section-head span{font-size:12px;color:#89979c}.filters{display:flex;gap:10px}.filters .el-select{width:190px}.el-table small{display:block;color:#89979c;margin-top:4px}.el-table .el-progress{margin-top:7px}.pagination{display:flex;justify-content:space-between;align-items:center;margin-top:18px;color:#7b898f;font-size:13px}.empty{padding:36px}.result-meta{display:flex;justify-content:space-between;gap:16px;margin:20px 0;color:#687a80;font-size:13px}.result-meta b{color:#2c484f}.metric-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.metric-grid article{background:#f3f8f8;border:1px solid #e3eded;border-radius:9px;padding:15px}.metric-grid span,.metric-grid small{display:block;color:#73868b;font-size:12px}.metric-grid b{display:block;font-size:21px;color:#236a6e;margin:9px 0}.chart{height:330px;width:100%}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:16px 0 24px}.stats div{padding:12px;border-left:3px solid #83aaa8;background:#f8fafb}.stats span,.stats b{display:block}.stats span{font-size:12px;color:#78888d}.stats b{margin-top:7px}.previews{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.previews figure{margin:0;border:1px solid #e2e9eb;border-radius:8px;overflow:hidden;background:#f7f9fa}.previews img{display:block;width:100%;aspect-ratio:16/10;object-fit:contain}.previews figcaption{padding:7px;text-align:center;color:#65777c;font-size:12px}.result-warning{margin-top:8px}@media(max-width:900px){.metric-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:680px){.section-head,.filters,.result-meta{align-items:stretch;flex-direction:column}.filters .el-select{width:100%}.metric-grid,.stats,.previews{grid-template-columns:1fr}.pagination{align-items:flex-start;flex-direction:column}}
</style>
