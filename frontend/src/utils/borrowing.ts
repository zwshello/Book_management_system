import axios from 'axios'
import type { BorrowRecord } from '../types/domain'
import { borrowBook, returnBook } from '../api/borrows'

function storageKey(kind: 'borrow' | 'return', id: string): string {
  let userId = 'unknown'
  try {
    const stored: unknown = JSON.parse(sessionStorage.getItem('library_user') ?? 'null')
    if (stored && typeof stored === 'object' && 'id' in stored && typeof stored.id === 'string') userId = stored.id
  } catch { /* The route guard will refresh malformed account state. */ }
  return `library_${kind}_${userId}_${id}`
}
function keyFor(kind: 'borrow' | 'return', id: string): string {
  const key = storageKey(kind, id)
  let value = sessionStorage.getItem(key)
  if (!value) { value = crypto.randomUUID(); sessionStorage.setItem(key, value) }
  return value
}
function clearKey(kind: 'borrow' | 'return', id: string) { sessionStorage.removeItem(storageKey(kind, id)) }

export async function requestBorrow(bookId: string): Promise<BorrowRecord> {
  try {
    const result = await borrowBook(bookId, keyFor('borrow', bookId))
    if (result.status !== 'PENDING') clearKey('borrow', bookId)
    return result
  } catch (error: unknown) {
    // A 409 is a confirmed business conflict; an unavailable response may have committed remotely.
    if (axios.isAxiosError(error) && error.response?.status === 409) clearKey('borrow', bookId)
    throw error
  }
}
export async function requestReturn(recordId: string): Promise<BorrowRecord> {
  try {
    const result = await returnBook(recordId, keyFor('return', recordId))
    if (result.status === 'RETURNED') clearKey('return', recordId)
    return result
  } catch (error: unknown) {
    if (axios.isAxiosError(error) && error.response?.status === 409) clearKey('return', recordId)
    throw error
  }
}
