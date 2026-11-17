import type { Schemas } from '@/core/api/generated'

/**
 * The credentials of the OAuth2 password form the login posts. The form's
 * other fields (scope, grant_type, client credentials) are left at their
 * defaults.
 */
export type LoginRequest = Pick<
  Schemas['Body_login_access_token_api_v1_auth_login_access_token_post'],
  'username' | 'password'
>
