import axios from 'axios'

import { idleHeaders } from '@/core/session/userActivity'
import { useConnectionStore } from '@/core/stores/connectionStore'

const API_ROOT = import.meta.env.VITE_API_URL ?? ''

// The session lives in an httponly cookie that scripts cannot read (see
// auth_deps.py). withCredentials sends it, also across the dev ports, and
// CSRF_HEADER protects the unsafe methods it authenticates.
const CSRF_HEADER_NAME = 'X-Requested-With'
const CSRF_HEADER_VALUE = 'glados'

const api = axios.create({
  baseURL: `${API_ROOT}/api/v1/web`,
  withCredentials: true,
  paramsSerializer: (params) => {
    const usp = new URLSearchParams()
    for (const [key, value] of Object.entries(params)) {
      if (Array.isArray(value)) {
        for (const v of value) usp.append(key, String(v))
      } else if (value !== undefined && value !== null) {
        usp.append(key, String(value))
      }
    }
    return usp.toString()
  },
})

api.defaults.headers.common[CSRF_HEADER_NAME] = CSRF_HEADER_VALUE

// Every request says how long the user has been idle, so a request the app
// sends on its own does not keep the session alive (see userActivity.ts).
api.interceptors.request.use((config) => {
  for (const [name, value] of Object.entries(idleHeaders())) config.headers.set(name, value)
  return config
})

// A session ending mid-visit sends the user to sign in. The store is
// imported lazily to avoid an import cycle through the router. Login uses
// `authApi`, so bad credentials never land here. Every request also serves
// as a connectivity probe (see connectionStore).
api.interceptors.response.use(
  (response) => {
    useConnectionStore().reportSuccess()
    return response
  },
  async (error) => {
    if (axios.isAxiosError(error)) {
      if (error.response) {
        // The server answered. Even a 500 proves the path to it is up, and
        // an unhappy server is not what the footer's offline state is about.
        useConnectionStore().reportSuccess()
      } else if (!axios.isCancel(error)) {
        // Nothing came back. Cancellations say nothing about the connection.
        useConnectionStore().reportFailure()
      }
    }

    if (axios.isAxiosError(error) && error.response?.status === 401) {
      const { useCurrentUserStore } = await import('@/core/stores/currentUserStore')
      useCurrentUserStore().sessionExpired()
    }

    // Maintenance mode flipped on mid-visit: the domain error's class name is
    // the stable discriminator (see exception_handlers.py), never the prose
    // in `detail`, which is admin-authored and untranslated.
    if (
      axios.isAxiosError(error) &&
      error.response?.status === 503 &&
      error.response.data?.code === 'MaintenanceModeError'
    ) {
      const { useCurrentUserStore } = await import('@/core/stores/currentUserStore')
      useCurrentUserStore().maintenanceLockout()
    }

    return Promise.reject(error)
  },
)

export default api
