<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { myBorrows } from '../api/borrows'
import { requestReturn } from '../utils/borrowing'
import { errorMessage } from '../utils/errors'
import type { BorrowRecord } from '../types/domain'
const query = reactive({ status: '', page: 1, page_size: 20 })
const rows = ref<BorrowRecord[]>([]); const count = ref(0); const loading = ref(false); const busy = ref<string | null>(null)
async function load() { loading.value = true; try { const data = await myBorrows({ status: query.status || undefined, page: query.page, page_size: query.page_size }); rows.value = data.results; count.value = data.count } catch (error) { ElMessage.error(errorMessage(error)) } finally { loading.value = false } }
async function giveBack(row: BorrowRecord) {
  busy.value = row.id
  try { const result = await requestReturn(row.id); ElMessage.success(result.status === 'RETURN_PENDING' ? '归还已受理，等待库存确认。' : '归还成功'); await load() }
  catch (error) { ElMessage.error(`${errorMessage(error)} 如结果不明，请刷新记录，勿更换操作编号重复归还。`) }
  finally { busy.value = null }
}
onMounted(load)
</script>
<template>
  <div class="page-head"><div><h1>我的借阅</h1><p>跟踪借阅、到期与归还状态</p></div></div>
  <div class="panel"><div class="toolbar"><el-select v-model="query.status" placeholder="全部状态" clearable @change="query.page=1;load()"><el-option v-for="s in ['PENDING','ACTIVE','OVERDUE','RETURN_PENDING','RETURNED','FAILED']" :key="s" :label="s" :value="s" /></el-select><el-button @click="load">刷新</el-button></div>
    <el-table v-loading="loading" :data="rows" stripe><el-table-column prop="book_title_snapshot" label="图书" min-width="180" /><el-table-column prop="isbn_snapshot" label="ISBN" min-width="145" /><el-table-column prop="display_status" label="状态" width="150" /><el-table-column prop="borrowed_at" label="借出时间" min-width="170" /><el-table-column prop="due_at" label="应还时间" min-width="170" /><el-table-column label="操作" width="110"><template #default="scope"><el-button type="primary" link :loading="busy===scope.row.id" :disabled="scope.row.status!=='ACTIVE'" @click="giveBack(scope.row)">归还</el-button></template></el-table-column></el-table>
    <div class="pager"><el-pagination v-model:current-page="query.page" :page-size="query.page_size" :total="count" layout="total, prev, pager, next" @current-change="load" /></div>
  </div>
</template>
