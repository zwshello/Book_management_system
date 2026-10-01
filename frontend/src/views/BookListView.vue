<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { allCategories, listBooks } from '../api/books'
import { useAuthStore } from '../stores/auth'
import { errorMessage } from '../utils/errors'
import type { Book, Category } from '../types/domain'
const router = useRouter(); const auth = useAuthStore()
const query = reactive({ title: '', author: '', isbn: '', category_id: '', status: 'ACTIVE', availability: '', ordering: '-created_at', page: 1, page_size: 20 })
const books = ref<Book[]>([]); const categories = ref<Category[]>([]); const count = ref(0); const loading = ref(false)
async function load() {
  loading.value = true
  try { const result = await listBooks({ title: query.title || undefined, author: query.author || undefined, isbn: query.isbn || undefined, category_id: query.category_id || undefined, status: query.status, availability: query.availability || undefined, ordering: query.ordering, page: query.page, page_size: query.page_size }); books.value = result.results; count.value = result.count }
  catch (error) { ElMessage.error(errorMessage(error)) }
  finally { loading.value = false }
}
async function loadCategories() { try { categories.value = await allCategories() } catch (error) { ElMessage.error(errorMessage(error)) } }
function search() { query.page = 1; void load() }
function reset() { Object.assign(query, { title: '', author: '', isbn: '', category_id: '', status: 'ACTIVE', availability: '', ordering: '-created_at', page: 1 }); void load() }
onMounted(() => { void loadCategories(); void load() })
</script>
<template>
  <div class="page-head"><div><h1>图书查询</h1><p>组合条件搜索馆藏，查看详情并借阅</p></div></div>
  <div class="panel"><div class="toolbar">
    <el-input v-model="query.title" placeholder="书名模糊搜索" clearable @keyup.enter="search" /><el-input v-model="query.author" placeholder="作者模糊搜索" clearable @keyup.enter="search" /><el-input v-model="query.isbn" placeholder="ISBN 精确查询" clearable @keyup.enter="search" />
    <el-select v-model="query.category_id" placeholder="全部分类" clearable><el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" /></el-select>
    <el-select v-if="auth.isAdmin" v-model="query.status" placeholder="状态"><el-option label="在架" value="ACTIVE" /><el-option label="归档" value="ARCHIVED" /></el-select>
    <el-select v-model="query.availability" placeholder="可借状态" clearable><el-option label="可借" value="available" /><el-option label="不可借" value="unavailable" /></el-select>
    <el-select v-model="query.ordering" placeholder="排序"><el-option label="最新录入" value="-created_at" /><el-option label="最早录入" value="created_at" /><el-option label="书名升序" value="title" /><el-option label="书名降序" value="-title" /><el-option label="出版日期由新到旧" value="-published_date" /></el-select>
    <el-button type="primary" @click="search">查询</el-button><el-button @click="reset">重置</el-button>
  </div>
  <el-table v-loading="loading" :data="books" stripe><el-table-column prop="title" label="书名" min-width="200" /><el-table-column prop="author" label="作者" min-width="130" /><el-table-column prop="isbn" label="ISBN" min-width="150" /><el-table-column prop="category_name" label="分类" min-width="110" /><el-table-column prop="available_copies" label="可借册数" width="100" /><el-table-column prop="status" label="状态" width="105" /><el-table-column label="操作" width="90"><template #default="scope"><el-button v-if="scope.row.status==='ACTIVE'" type="primary" link @click="router.push(`/books/${scope.row.id}`)">详情</el-button></template></el-table-column></el-table>
  <div class="pager"><el-pagination v-model:current-page="query.page" :page-size="query.page_size" :total="count" layout="total, prev, pager, next" @current-change="load" /></div>
  </div>
</template>
