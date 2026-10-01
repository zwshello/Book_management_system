<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import { errorMessage } from '../utils/errors'
const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const form = reactive({ username: '', password: '' })
const formRef = ref<FormInstance>()
const loading = ref(false)
const rules: FormRules = { username: [{ required: true, message: '请输入用户名', trigger: 'blur' }], password: [{ required: true, message: '请输入密码', trigger: 'blur' }] }
async function submit() {
  if (!await formRef.value?.validate().catch(() => false)) return
  loading.value = true
  try {
    await auth.login(form.username, form.password)
    ElMessage.success('登录成功')
    const redirect = typeof route.query.redirect === 'string' && route.query.redirect.startsWith('/') ? route.query.redirect : '/dashboard'
    await router.replace(redirect)
  } catch (error) { ElMessage.error(errorMessage(error)) }
  finally { loading.value = false }
}
</script>
<template>
  <div class="login-page"><div class="login-card">
    <h1>欢迎回来</h1><p>登录图书管理系统，继续你的借阅与管理工作。</p>
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @keyup.enter="submit">
      <el-form-item label="用户名" prop="username"><el-input v-model="form.username" autocomplete="username" placeholder="输入用户名" /></el-form-item>
      <el-form-item label="密码" prop="password"><el-input v-model="form.password" type="password" show-password autocomplete="current-password" placeholder="输入密码" /></el-form-item>
      <el-button type="primary" :loading="loading" style="width:100%;margin-top:8px" @click="submit">登录</el-button>
    </el-form>
  </div></div>
</template>
