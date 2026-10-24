<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
const route = useRoute(); const title = computed(() => String(route.meta.title || '功能模块')); const description = computed(() => String(route.meta.description || ''))
</script>
<template><div class="page-head"><div><h1>{{ title }}</h1></div></div><div class="placeholder panel"><div class="placeholder-mark">{{ title.slice(0, 1) }}</div><h2>该功能将在后续开发阶段实现</h2><p>{{ description }}</p><p class="muted">当前页面仅用于确认导航和路由结构有效，不包含模拟数据或不可用操作。</p></div></template>
<style scoped>.placeholder{text-align:center;padding:84px 30px}.placeholder-mark{width:52px;height:52px;margin:0 auto 20px;display:grid;place-items:center;border-radius:13px;background:#e7f2f1;color:#176f73;font-size:20px;font-weight:bold}.placeholder h2{font-size:20px}.placeholder p{color:#687a82;line-height:1.7}.placeholder .muted{font-size:13px;color:#929da1}</style>

