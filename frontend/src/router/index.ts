import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import BaseLayout from '../layouts/BaseLayout.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('../views/LoginView.vue') },
    { path: '/', component: BaseLayout, children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', name: 'dashboard', component: () => import('../views/HomeView.vue') },
      { path: 'books', name: 'books', component: () => import('../views/BookListView.vue') },
      { path: 'books/:id', name: 'book-detail', component: () => import('../views/BookDetailView.vue') },
      { path: 'my-borrows', name: 'my-borrows', component: () => import('../views/MyBorrowsView.vue') },
      { path: 'profile', name: 'profile', component: () => import('../views/ProfileView.vue') },
      { path: 'admin', name: 'admin-dashboard', component: () => import('../views/AdminDashboardView.vue'), meta: { admin: true } },
      { path: 'admin/users', name: 'admin-users', component: () => import('../views/UsersAdminView.vue'), meta: { admin: true } },
      { path: 'admin/books', name: 'admin-books', component: () => import('../views/BooksAdminView.vue'), meta: { admin: true } },
      { path: 'admin/categories', name: 'admin-categories', component: () => import('../views/CategoriesAdminView.vue'), meta: { admin: true } },
      { path: 'admin/borrows', name: 'admin-borrows', component: () => import('../views/BorrowsAdminView.vue'), meta: { admin: true } },
      { path: 'admin/statistics', name: 'admin-statistics', component: () => import('../views/StatisticsView.vue'), meta: { admin: true } },
    ] },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})
router.beforeEach(async (to) => {
  if (to.name === 'login') return true
  const auth = useAuthStore()
  if (!auth.token) return { name: 'login', query: { redirect: to.fullPath } }
  try {
    const user = await auth.ensureUser()
    if (!user) return { name: 'login' }
    if (to.meta.admin && user.role !== 'ADMIN') return { name: 'dashboard' }
  } catch { return { name: 'login', query: { redirect: to.fullPath } } }
  return true
})
export default router
