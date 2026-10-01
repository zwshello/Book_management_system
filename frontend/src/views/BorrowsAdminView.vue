<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { allBorrows } from '../api/borrows'
import { errorMessage } from '../utils/errors'
import type { BorrowRecord } from '../types/domain'
const query = reactive({ user_id: '', book_id: '', status: '', created_from: '', created_to: '', page: 1, page_size: 20 })
const rows = ref<BorrowRecord[]>([]); const count = ref(0); const loading = ref(false)
async function load() { loading.value = true; try { const data = await allBorrows({ user_id: query.user_id || undefined, book_id: query.book_id || undefined, status: query.status || undefined, created_from: query.created_from || undefined, created_to: query.created_to || undefined, page: query.page, page_size: query.page_size }); rows.value = data.results; count.value = data.count } catch (error) { ElMessage.error(errorMessage(error)) } finally { loading.value = false } }
function search() { query.page = 1; void load() }
onMounted(load)
</script>
<template><div class="page-head"><div><h1>借阅管理</h1><p>按用户、图书、状态和日期查看全部借阅记录</p></div></div><div class="panel"><div class="toolbar"><el-input v-model="query.user_id" placeholder="用户 UUID" clearable @keyup.enter="search" /><el-input v-model="query.book_id" placeholder="图书 UUID" clearable @keyup.enter="search" /><el-select v-model="query.status" placeholder="全部状态" clearable><el-option v-for="s in ['PENDING','ACTIVE','OVERDUE','RETURN_PENDING','RETURNED','FAILED']" :key="s" :label="s" :value="s" /></el-select><el-date-picker v-model="query.created_from" type="date" value-format="YYYY-MM-DD" placeholder="开始日期" /><el-date-picker v-model="query.created_to" type="date" value-format="YYYY-MM-DD" placeholder="结束日期" /><el-button type="primary" @click="search">查询</el-button></div><el-table v-loading="loading" :data="rows" stripe><el-table-column prop="username_snapshot" label="借阅人" min-width="110" /><el-table-column prop="book_title_snapshot" label="图书" min-width="170" /><el-table-column prop="display_status" label="状态" width="150" /><el-table-column prop="borrowed_at" label="借出时间" min-width="170" /><el-table-column prop="due_at" label="应还时间" min-width="170" /><el-table-column prop="returned_at" label="归还时间" min-width="170" /></el-table><div class="pager"><el-pagination v-model:current-page="query.page" :page-size="query.page_size" :total="count" layout="total, prev, pager, next" @current-change="load" /></div></div></template>
