import { apiClient } from './client'
import type { Book, BookStatus, Category, Page, Query } from '../types/domain'
export interface BookInput { title: string; author: string; isbn: string; category: string; publisher: string; published_date: string | null; description: string; status: BookStatus; total_copies?: number }
export interface CategoryInput { name: string; description: string }
export async function listBooks(params: Query): Promise<Page<Book>> { const { data } = await apiClient.get<Page<Book>>('/books', { params }); return data }
export async function getBook(id: string): Promise<Book> { const { data } = await apiClient.get<Book>(`/books/${id}`); return data }
export async function createBook(payload: BookInput): Promise<Book> { const { data } = await apiClient.post<Book>('/books', payload); return data }
export async function updateBook(id: string, payload: Omit<BookInput, 'total_copies'>): Promise<Book> { const { data } = await apiClient.patch<Book>(`/books/${id}`, payload); return data }
export async function adjustStock(id: string, total_copies: number): Promise<Book> { const { data } = await apiClient.post<Book>(`/books/${id}/stock-adjustments`, { total_copies }); return data }
export async function deleteBook(id: string): Promise<void> { await apiClient.delete(`/books/${id}`) }
export async function listCategories(params: Query = {}): Promise<Page<Category>> { const { data } = await apiClient.get<Page<Category>>('/categories', { params }); return data }
export async function allCategories(): Promise<Category[]> {
  const first = await listCategories({ page: 1, page_size: 100 })
  const result = [...first.results]
  for (let page = 2; result.length < first.count; page += 1) {
    const next = await listCategories({ page, page_size: 100 })
    result.push(...next.results)
    if (next.results.length === 0) break
  }
  return result
}
export async function createCategory(payload: CategoryInput): Promise<Category> { const { data } = await apiClient.post<Category>('/categories', payload); return data }
export async function updateCategory(id: string, payload: CategoryInput): Promise<Category> { const { data } = await apiClient.patch<Category>(`/categories/${id}`, payload); return data }
export async function deleteCategory(id: string): Promise<void> { await apiClient.delete(`/categories/${id}`) }
