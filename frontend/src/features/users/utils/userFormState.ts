import type { AuthProvider } from '@/core/auth/authProviders'
import type { UserResponse } from '@/core/types/userResponse'

/** The fields of the user dialog, as the form edits them. */
export interface UserFormState {
  username: string
  full_name: string
  email: string
  password: string
  language: string
  date_format: string
  is_active: boolean
  is_shared_account: boolean
  auth_provider: AuthProvider
  member_ids: number[]
  group_ids: number[]
  // The direct grants only; the groups add theirs on top.
  permissions: string[]
  theme_preset: string | null
  theme_primary: string | null
  theme_surface: string | null
  theme_dark_mode: boolean
}

/** A new local account in the tenant's default language, with no theme picked yet. */
export function createEmptyUserForm(defaultLanguage: string): UserFormState {
  return {
    username: '',
    full_name: '',
    email: '',
    password: '',
    language: defaultLanguage,
    date_format: '',
    is_active: true,
    is_shared_account: false,
    auth_provider: 'local',
    member_ids: [],
    group_ids: [],
    permissions: [],
    theme_preset: null,
    theme_primary: null,
    theme_surface: null,
    theme_dark_mode: false,
  }
}

/** An existing account's fields, with an empty password that means unchanged. */
export function userFormFromUser(user: UserResponse): UserFormState {
  return {
    username: user.username,
    full_name: user.full_name,
    email: user.email,
    password: '',
    language: user.language,
    date_format: user.date_format,
    is_active: user.is_active,
    is_shared_account: user.is_shared_account,
    auth_provider: user.auth_provider,
    member_ids: [...user.member_ids],
    group_ids: [...user.group_ids],
    permissions: [...user.direct_permissions],
    theme_preset: user.theme_preset,
    theme_primary: user.theme_primary,
    theme_surface: user.theme_surface,
    theme_dark_mode: user.theme_dark_mode,
  }
}
