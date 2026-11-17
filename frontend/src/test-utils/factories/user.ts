import type { UserResponse } from '@/core/types/userResponse'

/**
 * A complete, active local user with no permissions. The user is not a
 * system user on purpose, because a system user short-circuits
 * usePermissions() and would make every permission gate untestable.
 */
export function makeUserResponse(overrides: Partial<UserResponse> = {}): UserResponse {
  return {
    id: 1,
    public_id: '11111111-1111-1111-1111-111111111111',
    pdm_links: [],
    username: 'tester',
    full_name: 'Tester',
    email: 'tester@example.com',
    created: '2026-01-01T00:00:00Z',
    last_logged_in: null,
    language: 'enGB',
    date_format: 'iso',
    start_page: 'dashboard',
    theme_preset: 'Aura',
    theme_surface: 'glados',
    theme_primary: 'glados',
    theme_dark_mode: false,
    button_flat_style: false,
    table_gridlines: false,
    table_striped_rows: false,
    rfid_configured: false,
    is_active: true,
    is_systemuser: false,
    is_service_account: false,
    is_shared_account: false,
    auth_provider: 'local',
    member_ids: [],
    group_ids: [],
    permissions: [],
    direct_permissions: [],
    totp_enabled: false,
    has_avatar: false,
    ...overrides,
  }
}

/** The default user holding exactly the given permissions. */
export function userWithPermissions(
  permissions: string[],
  overrides: Partial<UserResponse> = {},
): UserResponse {
  return makeUserResponse({ ...overrides, permissions })
}
