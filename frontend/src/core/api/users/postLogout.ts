import authApi from '@/core/api/auth'

/**
 * Ends the session server-side and clears its httponly cookie. Called
 * from currentUserStore's teardownSession() on every path that ends a
 * session client-side, best-effort: an already-dead session has nothing
 * left to revoke, and a network failure here must never block signing
 * out locally.
 */
export async function postLogout(): Promise<void> {
  await authApi.post('/logout')
}
