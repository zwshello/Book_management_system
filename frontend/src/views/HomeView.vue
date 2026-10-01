<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { myBorrows } from '../api/borrows'
import { useAuthStore } from '../stores/auth'
import { errorMessage } from '../utils/errors'
import type { BorrowRecord } from '../types/domain'
const auth = useAuthStore()
const router = useRouter()
const activeCount = ref<number | null>(null)
const recent = ref<BorrowRecord[]>([])
onMounted(async () => {
  try {
    const [active, latest] = await Promise.all([myBorrows({ status: 'ACTIVE', page_size: 1 }), myBorrows({ page_size: 5 })])
    activeCount.value = active.count
    recent.value = latest.results
  } catch (error) { ElMessage.error(errorMessage(error)) }
})
</script>
<template>
  <div class="page-head"><div><h1>你好，{{ auth.user?.display_name || auth.user?.username }}</h1><p>从这里开始查询馆藏、管理自己的借阅。</p></div></div>
  <div class="quick-grid">
    <el-card shadow="hover" @click="router.push('/books')"><h3>查找图书</h3><p class="muted">按书名、作者、ISBN、分类和可借状态组合搜索。</p><el-button type="primary" link>浏览馆藏 →</el-button></el-card>
    <el-card shadow="hover" @click="router.push('/my-borrows')"><h3>我的借阅</h3><p class="muted">查看借阅状态、到期时间和归还结果。</p><el-button type="primary" link>查看记录 →</el-button></el-card>
    <el-card shadow="hover" @click="router.push('/profile')"><h3>个人信息</h3><p class="muted">维护邮箱与显示名称。</p><el-button type="primary" link>编辑资料 →</el-button></el-card>
  </div>
  <div class="panel" style="margin-top:20px"><h3>借阅动态</h3><p class="muted">当前借阅：{{ activeCount ?? '—' }} 本</p><el-table :data="recent" size="small"><el-table-column prop="book_title_snapshot" label="图书" min-width="180" /><el-table-column prop="display_status" label="状态" width="140" /><el-table-column prop="due_at" label="应还时间" min-width="175" /></el-table></div>
  <div v-if="auth.isAdmin" class="panel" style="margin-top:20px"><h3>管理员入口</h3><p class="muted">用户、图书、分类、借阅及五项概览统计。</p><el-button @click="router.push('/admin')">进入管理工作台</el-button></div>
</template>
