// Public barrel; other features import auth only through here (ESLint-enforced).

export { default as LoginView } from './views/LoginView.vue'
export { resolveStartPageRoute } from './utils/postLoginTarget'
