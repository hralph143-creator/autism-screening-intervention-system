<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { api, messageOf } from '../api'
import { getRememberedAccounts, setAdministrator } from '../session'

const router = useRouter(); const route = useRoute(); const initialized = ref(true); const loading = ref(false)
const login = reactive({ username: '', password: '' })
const setup = reactive({ username: '', password: '', confirm_password: '' })
const rememberedAccounts = ref<string[]>([])
function accountSuggestions(query: string, done: (items: { value: string }[]) => void) {
  const keyword = query.trim().toLocaleLowerCase()
  done(rememberedAccounts.value.filter(item => !keyword || item.toLocaleLowerCase().includes(keyword)).map(value => ({ value })))
}
onMounted(async () => {
  rememberedAccounts.value = getRememberedAccounts()
  login.username = rememberedAccounts.value[0] || ''
  try { initialized.value = (await api.get('/auth/status')).data.initialized } catch (error) { ElMessage.error(messageOf(error)) }
})
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
<template>
  <div class="login-page">
    <section class="context">
      <div class="symbol">观</div>
      <h1>基于深度学习的自闭症<br/>筛查与干预系统</h1>
      <div class="notice">本系统用于教学科研和行为记录，不作为医疗诊断依据。</div>
    </section>
    <section class="login-card">
      <h2>{{ initialized ? '管理员登录' : '初始化管理员' }}</h2>
      <el-form v-if="initialized" label-position="top" autocomplete="on" @submit.prevent="submit">
        <el-form-item label="用户名">
          <el-autocomplete v-model="login.username" :fetch-suggestions="accountSuggestions" trigger-on-focus clearable name="username" autocomplete="username" maxlength="32" placeholder="输入或选择账号"/>
        </el-form-item>
        <el-form-item label="密码"><el-input v-model="login.password" name="password" type="password" show-password maxlength="128" autocomplete="current-password"/></el-form-item>
        <el-button native-type="submit" type="primary" :loading="loading" class="submit">登录</el-button>
      </el-form>
      <el-form v-else label-position="top" autocomplete="on" @submit.prevent="submit">
        <el-form-item label="管理员用户名"><el-input v-model="setup.username" name="username" maxlength="32" autocomplete="username"/></el-form-item>
        <el-form-item label="管理员密码"><el-input v-model="setup.password" name="password" type="password" show-password maxlength="128" autocomplete="new-password"/></el-form-item>
        <el-form-item label="确认密码"><el-input v-model="setup.confirm_password" name="confirm_password" type="password" show-password maxlength="128" autocomplete="new-password"/></el-form-item>
        <el-button native-type="submit" type="primary" :loading="loading" class="submit">创建管理员并进入系统</el-button>
      </el-form>
    </section>
  </div>
</template>
<style scoped>.login-page{min-height:100vh;display:grid;grid-template-columns:minmax(420px,1fr) 430px;align-items:center;gap:9vw;padding:8vh 10vw;background:#f2f6f5}.context{max-width:620px}.symbol{width:48px;height:48px;display:grid;place-items:center;border-radius:12px;background:#176f73;color:white;font-size:20px;font-weight:bold}.context h1{font-size:39px;line-height:1.35;color:#173f42;margin:24px 0 18px}.notice{margin-top:28px;border-left:3px solid #c79455;background:#fffaf2;padding:13px 16px;color:#6d5c47;line-height:1.7}.login-card{background:white;border:1px solid #e1e9e8;border-radius:14px;padding:34px;box-shadow:0 15px 48px rgba(29,65,64,.09)}.login-card h2{font-size:24px;margin:0 0 26px}.login-card :deep(.el-autocomplete){width:100%}.submit{width:100%;margin-top:4px}@media(max-width:850px){.login-page{display:block;padding:7vh 20px}.context{display:none}.login-card{max-width:430px;margin:auto}}</style>

