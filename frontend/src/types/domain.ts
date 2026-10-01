export type Role = 'USER' | 'ADMIN'
export type BookStatus = 'ACTIVE' | 'ARCHIVED'
export type BorrowStatus = 'PENDING' | 'ACTIVE' | 'RETURN_PENDING' | 'RETURNED' | 'FAILED' | 'OVERDUE'
export interface Page<T> { count: number; page: number; page_size: number; results: T[] }
export interface User { id: string; username: string; email: string; display_name: string; role: Role; is_active: boolean; status: 'ACTIVE' | 'DISABLED'; created_at: string; updated_at: string }
export interface Category { id: string; name: string; description: string; created_at: string; updated_at: string }
export interface Book { id: string; title: string; author: string; isbn: string; category: string; category_name: string; publisher: string; published_date: string | null; description: string; total_copies: number; available_copies: number; status: BookStatus; created_at: string; updated_at: string }
export interface BorrowRecord { id: string; user_id: string; book_id: string; username_snapshot: string; book_title_snapshot: string; isbn_snapshot: string; status: Exclude<BorrowStatus, 'OVERDUE'>; display_status: BorrowStatus; is_overdue: boolean; borrowed_at: string | null; due_at: string | null; returned_at: string | null; created_at: string }
export interface Overview { user_total: number; book_total: number; available_book_titles: number; available_copies: number; borrowed_copies: number; current_borrows: number; chart: { labels: string[]; values: number[] } }
export interface ApiErrorBody { code?: string; message?: string; details?: unknown; request_id?: string }
export type Query = Record<string, string | number | boolean | undefined>
