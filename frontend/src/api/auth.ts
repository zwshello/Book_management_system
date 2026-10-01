import { apiClient } from './client'
import type { User } from '../types/domain'
export interface LoginResult { access: string; refresh: string; user: User }
export async function login(username: string, password: string): Promise<LoginResult> { const { data } = await apiClient.post<LoginResult>('/auth/login', { username, password }); return data }
export async function logout(refresh: string): Promise<void> { await apiClient.post('/auth/logout', { refresh }) }
export async function currentUser(): Promise<User> { const { data } = await apiClient.get<User>('/users/me'); return data }
export async function updateProfile(payload: Pick<User, 'email' | 'display_name'>): Promise<User> { const { data } = await apiClient.patch<User>('/users/me', payload); return data }
