import { apiClient } from './client'
import type { Page, Query, Role, User } from '../types/domain'
export interface UserInput { username: string; email: string; display_name: string; password?: string; role: Role; is_active: boolean }
export async function listUsers(params: Query): Promise<Page<User>> { const { data } = await apiClient.get<Page<User>>('/users', { params }); return data }
export async function createUser(payload: UserInput): Promise<User> { const { data } = await apiClient.post<User>('/users', payload); return data }
export async function updateUser(id: string, payload: Partial<UserInput>): Promise<User> { const { data } = await apiClient.patch<User>(`/users/${id}`, payload); return data }
export async function deleteUser(id: string): Promise<void> { await apiClient.delete(`/users/${id}`) }
