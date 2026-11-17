import type { AuthProvider } from '@/core/auth/authProviders'
import type { Schemas } from '@/core/api/generated'
import type { QueryOf } from '@/core/api/webRequest'

// False on is_service_account leaves out API-key service users (they never
// sign in, so an acknowledgement addressed to one could never be confirmed).
export type UserFilterDto = QueryOf<'/users'>
export type UserSortBy = NonNullable<UserFilterDto['order_by']>
export type UserSortDir = NonNullable<UserFilterDto['order_dir']>
export type UserDirectoryFilterDto = QueryOf<'/users/directory'>

/**
 * Aliased from the generated schema. The backend accepts any string as
 * `auth_provider`, so the requests narrow it to the closed union
 * UserResponse carries.
 */
export type UserCreateRequest = Omit<Schemas['UserCreateRequest'], 'auth_provider'> & {
  auth_provider: AuthProvider
}

export type UserUpdateRequest = Omit<Schemas['UserUpdateRequest'], 'auth_provider'> & {
  auth_provider?: AuthProvider | null
}
