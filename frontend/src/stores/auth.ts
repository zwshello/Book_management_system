import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import * as authApi from '../api/auth'
import type { User } from '../types/domain'

function storedUser(): User | null { try { return JSON.parse(sessionStorage.getItem('library_user') ?? 'null') as User | null } catch { return null } }
export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(storedUser())
  const token = ref(sessionStorage.getItem('library_access'))
  const isAdmin = computed(() => user.value?.role === 'ADMIN')
  function clear() { user.value = null; token.value = null; for (const key of ['library_access', 'library_refresh', 'library_user']) sessionStorage.removeItem(key) }
  function setUser(value: User) { user.value = value; sessionStorage.setItem('library_user', JSON.stringify(value)) }
  async function login(username: string, password: string) { const result = await authApi.login(username, password); token.value = result.access; sessionStorage.setItem('library_access', result.access); sessionStorage.setItem('library_refresh', result.refresh); setUser(result.user) }
  async function ensureUser() { if (!token.value) return null; const current = await authApi.currentUser(); setUser(current); return current }
  async function logout() { const refresh = sessionStorage.getItem('library_refresh'); try { if (refresh) await authApi.logout(refresh) } finally { clear() } }
  return { user, token, isAdmin, clear, login, logout, ensureUser, setUser }
})
