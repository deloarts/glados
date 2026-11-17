/**
 * Which credential store answers for a user.
 *
 * 'local', the password hash stored by this application.
 * 'ldap' , a bind against the configured directory, and nothing else. The
 *           stored hash is an unusable sentinel, so these accounts have no
 *           local password to set, change, or fall back to; while the
 *           directory is unreachable they cannot sign in at all.
 *
 * Admin-only: the backend silently reverts this field on a self-update, so a
 * user can never move themselves off the directory.
 */
export const AUTH_PROVIDERS = ['local', 'ldap'] as const

export type AuthProvider = (typeof AUTH_PROVIDERS)[number]
