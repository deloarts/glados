import axios from 'axios'

const API_ROOT = import.meta.env.VITE_API_URL ?? ''

// Auth endpoints live under their own surface-agnostic prefix
// (/api/v1/auth), separate from the /api/v1/web API used elsewhere.
//
// withCredentials: the "trust this device" cookie (httpOnly, path-scoped
// to /api/v1/auth) must ride along on login requests, it is what lets
// the backend skip the TOTP prompt; the login/totp responses also set
// the web session cookie here, and logout (also on this surface) both
// reads and clears it, so this client needs credentials just as much as
// the main web API does (src/core/api/index.ts).
//
// The CSRF header is attached unconditionally too: login/totp don't need
// it (nothing is cookie-authenticated yet), but logout does.
const authApi = axios.create({
  baseURL: `${API_ROOT}/api/v1/auth`,
  withCredentials: true,
})

authApi.defaults.headers.common['X-Requested-With'] = 'glados'

export default authApi
