import { apiClient } from './client'
import type { BorrowRecord, Page, Query } from '../types/domain'
export async function myBorrows(params: Query): Promise<Page<BorrowRecord>> { const { data } = await apiClient.get<Page<BorrowRecord>>('/borrows/me', { params }); return data }
export async function allBorrows(params: Query): Promise<Page<BorrowRecord>> { const { data } = await apiClient.get<Page<BorrowRecord>>('/borrows', { params }); return data }
export async function borrowBook(book_id: string, key: string): Promise<BorrowRecord> { const { data } = await apiClient.post<BorrowRecord>('/borrows', { book_id }, { headers: { 'Idempotency-Key': key } }); return data }
export async function returnBook(id: string, key: string): Promise<BorrowRecord> { const { data } = await apiClient.post<BorrowRecord>(`/borrows/${id}/return`, {}, { headers: { 'Idempotency-Key': key } }); return data }
