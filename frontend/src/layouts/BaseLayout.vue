<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'
const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const active = computed(() => route.path)
async function leave() {
  try { await auth.logout() } catch { ElMessage.warning('远程退出未完成，本地登录信息已清除。') }
  await router.replace('/login')
}
</script>
<template>
  <el-container class="app-shell">
    <el-aside width="224px" class="sidebar">
      <div class="brand"><span class="brand-mark">▣</span><div>图书管理系统<small>LIBRARY DESK</small></div></div>
      <el-menu :default-active="active" class="side-menu" @select="(path: string) => router.push(path)">
        <el-menu-item index="/dashboard">首页</el-menu-item>
        <el-menu-item index="/books">图书查询</el-menu-item>
        <el-menu-item index="/my-borrows">我的借阅</el-menu-item>
        <el-menu-item index="/profile">个人信息</el-menu-item>
        <template v-if="auth.isAdmin">
          <div class="menu-label">管理工作台</div>
          <el-menu-item index="/admin">管理首页</el-menu-item>
          <el-menu-item index="/admin/users">用户管理</el-menu-item>
          <el-menu-item index="/admin/books">图书管理</el-menu-item>
          <el-menu-item index="/admin/categories">分类管理</el-menu-item>
          <el-menu-item index="/admin/borrows">借阅管理</el-menu-item>
          <el-menu-item index="/admin/statistics">统计分析</el-menu-item>
        </template>
      </el-menu>
      <div class="sidebar-foot">微服务与云原生技术实践</div>
    </el-aside>
    <el-container>
      <el-header class="topbar"><span>微服务与云原生技术实践 · 课程专业实习</span><div class="top-actions"><el-tag size="small" type="info">{{ auth.user?.role === 'ADMIN' ? '管理员' : '普通用户' }}</el-tag><span>{{ auth.user?.display_name || auth.user?.username }}</span><el-button text @click="leave">退出登录</el-button></div></el-header>
      <el-main class="workspace"><router-view /></el-main>
    </el-container>
  </el-container>
</template>
