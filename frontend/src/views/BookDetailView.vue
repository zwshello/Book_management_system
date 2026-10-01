<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getBook } from '../api/books'
import { requestBorrow } from '../utils/borrowing'
import { errorMessage } from '../utils/errors'
import type { Book } from '../types/domain'
const route = useRoute(); const router = useRouter()
const book = ref<Book | null>(null); const loading = ref(false); const sending = ref(false)
async function load() { loading.value = true; try { book.value = await getBook(String(route.params.id)) } catch (error) { ElMessage.error(errorMessage(error)) } finally { loading.value = false } }
async function borrow() {
  if (!book.value || sending.value) return
  sending.value = true
  try {
    const result = await requestBorrow(book.value.id)
    ElMessage.success(result.status === 'PENDING' ? '请求已受理，结果待核对；请在我的借阅查看。' : '借阅成功')
    await load()
  } catch (error) { ElMessage.error(`${errorMessage(error)} 如请求超时，请先查看我的借阅，勿更换操作编号重复借书。`) }
  finally { sending.value = false }
}
onMounted(load)
</script>
<template>
  <div class="page-head"><div><h1>图书详情</h1><p>书目资料与当前库存</p></div><el-button @click="router.push('/books')">返回列表</el-button></div>
  <div v-loading="loading" class="panel" v-if="book">
    <h2>{{ book.title }}</h2><p class="muted">{{ book.author }} · {{ book.category_name }}</p>
    <div class="detail-grid"><p><b>ISBN：</b>{{ book.isbn }}</p><p><b>出版社：</b>{{ book.publisher || '未填写' }}</p><p><b>出版日期：</b>{{ book.published_date || '未填写' }}</p><p><b>馆藏总量：</b>{{ book.total_copies }} 册</p><p><b>可借：</b>{{ book.available_copies }} 册</p><p><b>状态：</b>{{ book.status }}</p></div>
    <p>{{ book.description || '暂无简介' }}</p>
    <el-button type="primary" :disabled="book.status !== 'ACTIVE' || book.available_copies < 1" :loading="sending" @click="borrow">借阅此书</el-button>
  </div>
</template>
