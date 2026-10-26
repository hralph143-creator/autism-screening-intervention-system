<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
const route = useRoute(); const title = computed(() => String(route.meta.title || '功能模块'))
</script>
<template><div class="page-head"><h1>{{ title }}</h1></div><div class="placeholder panel"><div class="placeholder-mark">{{ title.slice(0, 1) }}</div><h2>{{ title }}</h2></div></template>
<style scoped>.placeholder{text-align:center;padding:84px 30px}.placeholder-mark{width:52px;height:52px;margin:0 auto 20px;display:grid;place-items:center;border-radius:13px;background:#e7f2f1;color:#176f73;font-size:20px;font-weight:bold}.placeholder h2{font-size:20px}</style>

