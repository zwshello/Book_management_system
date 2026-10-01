<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getOverview } from '../api/statistics'
import OverviewCards from '../components/OverviewCards.vue'
import OverviewChart from '../components/OverviewChart.vue'
import { errorMessage } from '../utils/errors'
import type { Overview } from '../types/domain'
const overview = ref<Overview | null>(null); const loading = ref(false)
async function load() { loading.value = true; try { overview.value = await getOverview() } catch (error) { ElMessage.error(errorMessage(error)) } finally { loading.value = false } }
onMounted(load)
</script>
<template><div class="page-head"><div><h1>统计分析</h1><p>五项基础概览，数据来自 statistics-service</p></div><el-button @click="load">刷新</el-button></div><div v-loading="loading"><template v-if="overview"><OverviewCards :overview="overview" /><div class="panel"><h3>数量对比</h3><OverviewChart :overview="overview" /></div><p class="muted">可借图书数量按册统计；已借册数包含待确认归还，当前借阅数仅包含 ACTIVE 记录。</p></template></div></template>
