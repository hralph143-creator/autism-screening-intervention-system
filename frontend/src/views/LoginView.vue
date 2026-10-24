<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, messageOf } from '../api'
import { setAdministrator } from '../session'

const router = useRouter(); const route = useRoute(); const initialized = ref(true); const loading = ref(false)
const login = reactive({ username: '', password: '' })
const setup = reactive({ username: '', password: '', confirm_password: '' })
onMounted(async () => { try { initialized.value = (await api.get('/auth/status')).data.initialized } catch (error) { ElMessage.error(messageOf(error)) } })
async function submit() {
  const payload = initialized.value ? login : setup
  if (!initialized.value && setup.password !== setup.confirm_password) { ElMessage.warning('两次输入的密码不一致'); return }
  loading.value = true
  try {
    const { data } = await api.post(initialized.value ? '/auth/login' : '/auth/initialize', payload)
    setAdministrator(data); ElMessage.success(initialized.value ? '登录成功' : '管理员创建成功')
    await router.replace(String(route.query.redirect || '/'))
  } catch (error) { ElMessage.error(messageOf(error)) } finally { loading.value = false }
}
</script>
<template><div class="login-page"><section class="context"><div class="symbol">观</div><h1>基于深度学习的自闭症<br/>筛查与干预系统</h1><p>面向儿童日常行为观察与家庭互动管理的本地软件基础平台。</p><div class="notice">本系统定位为教学科研与辅助观察工具，不替代专业医生的诊断和治疗意见。</div></section><section class="login-card"><h2>{{ initialized ? '管理员登录' : '初始化管理员' }}</h2><p>{{ initialized ? '请输入本机管理员账号' : '首次使用，请创建管理员账号' }}</p><el-form v-if="initialized" label-position="top" @submit.prevent="submit"><el-form-item label="用户名"><el-input v-model="login.username" maxlength="32" autocomplete="username"/></el-form-item><el-form-item label="密码"><el-input v-model="login.password" type="password" show-password maxlength="128" autocomplete="current-password" @keyup.enter="submit"/></el-form-item></el-form><el-form v-else label-position="top" @submit.prevent="submit"><el-form-item label="管理员用户名"><el-input v-model="setup.username" maxlength="32" autocomplete="username"/><small>3–32 位中文、字母、数字或下划线</small></el-form-item><el-form-item label="管理员密码"><el-input v-model="setup.password" type="password" show-password maxlength="128" autocomplete="new-password"/><small>至少 8 位，并包含大小写字母、数字中的至少两类</small></el-form-item><el-form-item label="确认密码"><el-input v-model="setup.confirm_password" type="password" show-password maxlength="128" autocomplete="new-password" @keyup.enter="submit"/></el-form-item></el-form><el-button type="primary" :loading="loading" class="submit" @click="submit">{{ initialized ? '登录' : '创建管理员并进入系统' }}</el-button><div class="security">登录会话使用 HttpOnly Cookie 保存，密码仅以哈希形式存储。</div></section></div></template>
<style scoped>.login-page{min-height:100vh;display:grid;grid-template-columns:minmax(420px,1fr) 430px;align-items:center;gap:9vw;padding:8vh 10vw;background:#f2f6f5}.context{max-width:620px}.symbol{width:48px;height:48px;display:grid;place-items:center;border-radius:12px;background:#176f73;color:white;font-size:20px;font-weight:bold}.context h1{font-size:39px;line-height:1.35;color:#173f42;margin:24px 0 18px}.context>p{color:#5f7077;font-size:16px;line-height:1.8}.notice{margin-top:28px;border-left:3px solid #c79455;background:#fffaf2;padding:13px 16px;color:#6d5c47;line-height:1.7}.login-card{background:white;border:1px solid #e1e9e8;border-radius:14px;padding:34px;box-shadow:0 15px 48px rgba(29,65,64,.09)}.login-card h2{font-size:24px;margin-bottom:8px}.login-card>p{color:#7a898f;margin-bottom:26px}.login-card small{color:#849197}.submit{width:100%;margin-top:4px}.security{font-size:12px;color:#89969b;line-height:1.6;margin-top:18px}@media(max-width:850px){.login-page{display:block;padding:7vh 20px}.context{display:none}.login-card{max-width:430px;margin:auto}}</style>

