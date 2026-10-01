<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getOverview } from '../api/statistics'
import OverviewCards from '../components/OverviewCards.vue'
import { errorMessage } from '../utils/errors'
import type { Overview } from '../types/domain'
const overview = ref<Overview | null>(null); const router = useRouter()
onMounted(async () => { try { overview.value = await getOverview() } catch (error) { ElMessage.error(errorMessage(error)) } })
</script>
<template><div class="page-head"><div><h1>管理首页</h1><p>当前馆藏与借阅概览</p></div><el-button type="primary" @click="router.push('/admin/statistics')">查看统计分析</el-button></div><OverviewCards v-if="overview" :overview="overview" /><div class="quick-grid"><el-card shadow="hover" @click="router.push('/admin/users')"><h3>用户管理</h3><p class="muted">查看、创建、编辑与归档用户</p></el-card><el-card shadow="hover" @click="router.push('/admin/books')"><h3>图书管理</h3><p class="muted">维护书目与库存</p></el-card><el-card shadow="hover" @click="router.push('/admin/borrows')"><h3>借阅管理</h3><p class="muted">查询全站借阅记录</p></el-card></div></template>
