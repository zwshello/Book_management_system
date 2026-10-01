<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { updateProfile } from '../api/auth'
import { useAuthStore } from '../stores/auth'
import { errorMessage } from '../utils/errors'
const auth = useAuthStore(); const form = reactive({ email: '', display_name: '' }); const formRef = ref<FormInstance>(); const saving = ref(false)
const rules: FormRules = { email: [{ required: true, message: '请输入邮箱', trigger: 'blur' }, { type: 'email', message: '邮箱格式不正确', trigger: 'blur' }], display_name: [{ max: 100, message: '最多 100 个字符', trigger: 'blur' }] }
onMounted(() => { form.email = auth.user?.email ?? ''; form.display_name = auth.user?.display_name ?? '' })
async function save() { if (!await formRef.value?.validate().catch(() => false)) return; saving.value = true; try { auth.setUser(await updateProfile(form)); ElMessage.success('资料已更新') } catch (error) { ElMessage.error(errorMessage(error)) } finally { saving.value = false } }
</script>
<template><div class="page-head"><div><h1>个人信息</h1><p>查看账户并维护联系信息</p></div></div><div class="panel" style="max-width:620px"><p><b>用户名：</b>{{ auth.user?.username }}</p><p><b>角色：</b>{{ auth.user?.role }}</p><el-form ref="formRef" :model="form" :rules="rules" label-width="100px"><el-form-item label="邮箱" prop="email"><el-input v-model="form.email" maxlength="254" /></el-form-item><el-form-item label="显示名称" prop="display_name"><el-input v-model="form.display_name" maxlength="100" /></el-form-item><el-form-item><el-button type="primary" :loading="saving" @click="save">保存资料</el-button></el-form-item></el-form></div></template>
