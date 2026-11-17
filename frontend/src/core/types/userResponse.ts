import type { Schemas } from '@/core/api/generated'

/**
 * Sourced from the backend's own OpenAPI schema (see
 * core/api/generated/) rather than hand-maintained, so fixtures and callers
 * cannot drift from the fields the backend actually sends. Regenerate with
 * `npm run generate:api-types` whenever the backend's user schema changes;
 * a stale copy here fails the CI drift check.
 */
export type PublicUser = Schemas['PublicUserResponse']

/**
 * The reduced view of a user that every signed-in user may read, what the
 * pickers and name lookups hold. E-mail, permissions, groups, 2FA state and
 * the last login are only in UserResponse, which needs read:settings.
 */
export type UserSummary = Schemas['UserSummaryResponse']

/**
 * `auth_provider`, `language`, `date_format`, `theme_*` and `start_page` are
 * string-literal unions in the schema (matching AUTH_PROVIDERS, DATE_FORMATS
 * in core/utils/dates.ts and AppLocale), so switches on them can be
 * exhaustive. `auth_provider` is admin-only; the backend reverts self-updates
 * of it.
 */
export type UserResponse = Schemas['UserResponse']
