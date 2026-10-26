<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, messageOf } from '../api'
const loading = ref(true); const error = ref(''); const health = ref<any>(null); const info = ref<any>(null)
async function load(){loading.value=true;error.value='';try{[health.value,info.value]=await Promise.all([api.get('/health'),api.get('/system/info')]).then(v=>v.map(x=>x.data))}catch(e){error.value=messageOf(e)}finally{loading.value=false}}
onMounted(load)
</script>
<template><div class="page-head"><h1>系统设置</h1><el-button :loading="loading" @click="load">重新检查</el-button></div><el-alert v-if="error" :title="error" type="error" show-icon :closable="false"/><div v-else class="panel" v-loading="loading"><el-descriptions :column="1" border><el-descriptions-item label="系统名称">{{ info?.name }}</el-descriptions-item><el-descriptions-item label="后端服务"><el-tag :type="health?.status==='ok'?'success':'danger'">{{ health?.status==='ok'?'运行正常':'不可用' }}</el-tag></el-descriptions-item><el-descriptions-item label="SQLite 数据库"><el-tag :type="health?.database==='connected'?'success':'danger'">{{ health?.database==='connected'?'连接正常':'连接异常' }}</el-tag></el-descriptions-item><el-descriptions-item label="后端框架">{{ info?.backend?.framework }}</el-descriptions-item><el-descriptions-item label="Python 版本">{{ info?.backend?.python }}</el-descriptions-item><el-descriptions-item label="运行模式">{{ info?.environment }}</el-descriptions-item><el-descriptions-item label="当前管理员">{{ info?.administrator }}</el-descriptions-item></el-descriptions></div></template>

