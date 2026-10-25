<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import { api, messageOf } from '../api'

interface ChildRecord {
  id: number
  child_code: string
  nickname: string
  birth_month: string | null
  age_text: string
  gender: string | null
  development_notes: string | null
  guardian_notes: string | null
  created_at: string
  updated_at: string
}

const rows = ref<ChildRecord[]>([]); const total = ref(0); const loading = ref(false); const error = ref('')
const router = useRouter()
const query = ref(''); const page = ref(1); const pageSize = ref(10); const sortOrder = ref<'desc'|'asc'>('desc')
const dialogOpen = ref(false); const detailOpen = ref(false); const submitting = ref(false); const editingId = ref<number|null>(null)
const detail = ref<ChildRecord|null>(null); const formRef = ref<FormInstance>()
const emptyForm = () => ({ nickname: '', birth_month: '', gender: '', development_notes: '', guardian_notes: '' })
const form = reactive(emptyForm())
const rules: FormRules = {
  nickname: [{ required: true, message: '请输入档案昵称或代号', trigger: 'blur' }, { max: 50, message: '最多输入 50 个字符', trigger: 'blur' }],
  development_notes: [{ max: 4000, message: '最多输入 4000 个字符', trigger: 'blur' }],
  guardian_notes: [{ max: 2000, message: '最多输入 2000 个字符', trigger: 'blur' }],
}

async function load() {
  loading.value = true; error.value = ''
  try {
    const { data } = await api.get('/children', { params: { q: query.value.trim(), page: page.value, page_size: pageSize.value, sort_order: sortOrder.value } })
    rows.value = data.items; total.value = data.total
  } catch (reason) { error.value = messageOf(reason) } finally { loading.value = false }
}
function search() { page.value = 1; void load() }
function createRecord() { editingId.value = null; Object.assign(form, emptyForm()); dialogOpen.value = true }
async function editRecord(row: ChildRecord) {
  try {
    const { data } = await api.get(`/children/${row.id}`); editingId.value = row.id
    Object.assign(form, { nickname: data.nickname, birth_month: data.birth_month || '', gender: data.gender || '', development_notes: data.development_notes || '', guardian_notes: data.guardian_notes || '' })
    dialogOpen.value = true
  } catch (reason) { ElMessage.error(messageOf(reason)) }
}
async function viewRecord(row: ChildRecord) {
  try { detail.value = (await api.get(`/children/${row.id}`)).data; detailOpen.value = true }
  catch (reason) { ElMessage.error(messageOf(reason)) }
}
async function save() {
  if (!formRef.value || !(await formRef.value.validate().catch(() => false))) return
  submitting.value = true
  const payload = { ...form, birth_month: form.birth_month || null, gender: form.gender || null, development_notes: form.development_notes || null, guardian_notes: form.guardian_notes || null }
  try {
    if (editingId.value) await api.put(`/children/${editingId.value}`, payload)
    else await api.post('/children', payload)
    ElMessage.success(editingId.value ? '档案修改成功' : '档案创建成功'); dialogOpen.value = false; await load()
  } catch (reason) { ElMessage.error(messageOf(reason)) } finally { submitting.value = false }
}
async function removeRecord(row: ChildRecord) {
  try {
    await ElMessageBox.confirm(`确认删除档案“${row.nickname}”（${row.child_code}）吗？删除后无法恢复。`, '删除儿童档案', { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' })
    await api.delete(`/children/${row.id}`); ElMessage.success('档案已删除')
    if (rows.value.length === 1 && page.value > 1) page.value -= 1
    await load()
  } catch (reason: any) { if (reason !== 'cancel' && reason !== 'close') ElMessage.error(messageOf(reason)) }
}
function formatDate(value: string) { return new Date(value).toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }) }
function disableFutureMonth(value: Date) { return value.getTime() > Date.now() }
onMounted(load)
</script>
<template>
  <div class="page-head"><div><h1>儿童档案</h1><p>默认使用系统编号与化名管理，避免录入不必要的身份信息</p></div><el-button type="primary" @click="createRecord">新建档案</el-button></div>
  <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="error-alert"><template #default><el-button link type="primary" @click="load">重新加载</el-button></template></el-alert>
  <div class="panel">
    <div class="toolbar"><el-input v-model="query" placeholder="搜索儿童编号或档案昵称" clearable maxlength="50" @keyup.enter="search" @clear="search"/><el-select v-model="sortOrder" @change="search"><el-option label="按建档时间降序" value="desc"/><el-option label="按建档时间升序" value="asc"/></el-select><el-button @click="search">查询</el-button></div>
    <el-table v-loading="loading" :data="rows" stripe><el-table-column prop="child_code" label="儿童编号" min-width="190"/><el-table-column prop="nickname" label="档案昵称" min-width="150"/><el-table-column prop="age_text" label="年龄" width="130"/><el-table-column label="性别" width="90"><template #default="scope">{{ scope.row.gender || '未填写' }}</template></el-table-column><el-table-column label="建档日期" width="130"><template #default="scope">{{ formatDate(scope.row.created_at) }}</template></el-table-column><el-table-column label="操作" width="245" fixed="right"><template #default="scope"><el-button link type="primary" @click="viewRecord(scope.row)">查看</el-button><el-button link type="primary" @click="router.push({path:'/observations',query:{child:String(scope.row.id)}})">观察记录</el-button><el-button link @click="editRecord(scope.row)">编辑</el-button><el-button link type="danger" @click="removeRecord(scope.row)">删除</el-button></template></el-table-column><template #empty><div class="empty-state"><span>暂无儿童档案</span><el-button link type="primary" @click="createRecord">创建第一份档案</el-button></div></template></el-table>
    <div class="pagination"><span>共 {{ total }} 条</span><el-pagination v-model:current-page="page" v-model:page-size="pageSize" layout="prev, pager, next, sizes" :page-sizes="[10,20,50]" :total="total" @current-change="load" @size-change="search"/></div>
  </div>
<el-dialog v-model="dialogOpen" :title="editingId ? '编辑儿童档案' : '新建儿童档案'" width="620px" destroy-on-close @closed="formRef?.clearValidate()"><el-form ref="formRef" :model="form" :rules="rules" label-position="top"><el-form-item v-if="editingId" label="儿童编号"><el-input :model-value="rows.find(item => item.id === editingId)?.child_code || detail?.child_code" disabled/></el-form-item><el-form-item label="档案昵称或代号" prop="nickname"><el-input v-model="form.nickname" maxlength="50" show-word-limit placeholder="请勿填写不必要的真实身份信息"/></el-form-item><div class="form-row"><el-form-item label="出生年月"><el-date-picker v-model="form.birth_month" type="month" value-format="YYYY-MM" format="YYYY年MM月" :disabled-date="disableFutureMonth" placeholder="可选" style="width:100%"/></el-form-item><el-form-item label="性别"><el-select v-model="form.gender" clearable placeholder="可选" style="width:100%"><el-option label="男" value="男"/><el-option label="女" value="女"/><el-option label="未说明" value="未说明"/></el-select></el-form-item></div><el-form-item label="基本发育观察备注" prop="development_notes"><el-input v-model="form.development_notes" type="textarea" :rows="4" maxlength="4000" show-word-limit/></el-form-item><el-form-item label="监护人备注" prop="guardian_notes"><el-input v-model="form.guardian_notes" type="textarea" :rows="3" maxlength="2000" show-word-limit/></el-form-item></el-form><template #footer><el-button :disabled="submitting" @click="dialogOpen=false">取消</el-button><el-button type="primary" :loading="submitting" @click="save">保存档案</el-button></template></el-dialog>
  <el-drawer v-model="detailOpen" title="档案详情" size="520px"><template v-if="detail"><section class="detail-code"><span>儿童编号</span><b>{{ detail.child_code }}</b></section><el-descriptions :column="1" border><el-descriptions-item label="档案昵称">{{ detail.nickname }}</el-descriptions-item><el-descriptions-item label="出生年月">{{ detail.birth_month || '未填写' }}</el-descriptions-item><el-descriptions-item label="年龄">{{ detail.age_text }}</el-descriptions-item><el-descriptions-item label="性别">{{ detail.gender || '未填写' }}</el-descriptions-item><el-descriptions-item label="建档时间">{{ formatDate(detail.created_at) }}</el-descriptions-item><el-descriptions-item label="最后更新">{{ formatDate(detail.updated_at) }}</el-descriptions-item></el-descriptions><h3>基本发育观察备注</h3><p class="notes">{{ detail.development_notes || '未填写' }}</p><h3>监护人备注</h3><p class="notes">{{ detail.guardian_notes || '未填写' }}</p></template></el-drawer>
</template>
<style scoped>.error-alert{margin-bottom:14px}.toolbar{display:flex;gap:10px;margin-bottom:16px}.toolbar .el-input{width:300px}.toolbar .el-select{width:190px}.pagination{display:flex;justify-content:space-between;align-items:center;margin-top:18px;color:#7b898f;font-size:13px}.empty-state{padding:36px;display:flex;flex-direction:column;gap:8px}.form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px}.detail-code{background:#edf5f4;padding:16px;border-radius:9px;margin-bottom:18px}.detail-code span,.detail-code b{display:block}.detail-code span{font-size:12px;color:#78898e;margin-bottom:6px}.detail-code b{color:#245f62}.notes{white-space:pre-wrap;line-height:1.75;color:#55666d;background:#f7f9fa;padding:14px;border-radius:8px;min-height:48px}@media(max-width:760px){.toolbar{flex-wrap:wrap}.toolbar .el-input,.toolbar .el-select{width:100%}.form-row{grid-template-columns:1fr}.pagination{align-items:flex-start;gap:10px;flex-direction:column}}</style>
