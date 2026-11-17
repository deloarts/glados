/**
 * Fixed backend answers for the screenshot tests, typed against the generated
 * web schema so a changed response shape fails `npm run type-check` here
 * rather than as a blank screenshot. Dates are fixed for the same reason.
 */
import type { components } from '../../src/core/api/generated/webSchema'
import { Permission } from '../../src/core/auth/permissions'
import type { MockHandler } from './mockApi'

type Schemas = components['schemas']

export const NOW = '2026-11-02T08:30:00Z'

export const branding: Schemas['PublicBrandingResponse'] = {
  app_name: 'Glados',
  app_description: null,
  company_name: 'Example Manufacturing',
  contact_email: null,
  default_language: 'enGB',
  domain: 'glados.example',
  footer_text: null,
  has_company_logo: false,
  has_favicon: false,
  has_login_background_video: false,
  has_logo: false,
  imprint_url: null,
  maintenance_enabled: false,
  maintenance_message: null,
  privacy_url: null,
  support_url: null,
}

export function user(overrides: Partial<Schemas['UserResponse']> = {}): Schemas['UserResponse'] {
  return {
    id: 1,
    public_id: '00000000-0000-4000-8000-000000000001',
    username: 'avery',
    full_name: 'Avery Example',
    email: 'avery@glados.example',
    auth_provider: 'local',
    permissions: Object.values(Permission).filter((value): value is Extract<typeof value, string> => typeof value === 'string'),
    direct_permissions: [],
    group_ids: [],
    member_ids: [],
    pdm_links: [],
    has_avatar: false,
    is_active: true,
    is_service_account: false,
    is_shared_account: false,
    is_systemuser: false,
    rfid_configured: false,
    totp_enabled: false,
    language: 'enGB',
    date_format: 'iso',
    start_page: 'dashboard',
    theme_preset: 'Aura',
    theme_primary: 'glados',
    theme_surface: 'glados',
    theme_dark_mode: false,
    button_flat_style: false,
    table_gridlines: false,
    table_striped_rows: false,
    created: NOW,
    last_logged_in: NOW,
    ...overrides,
  }
}

const values: Schemas['ValuesResponse'] = {
  date_formats: ['iso', 'dmy_dot', 'dmy_slash', 'mdy_slash', 'd_mon_y'],
  languages: ['enGB', 'deAT'],
  start_pages: ['dashboard', 'todo', 'workspace', 'catalogue', 'procurement', 'production', 'resources', 'tools'],
  supplier_levels: ['A', 'B', 'C'],
  theme_presets: ['Aura', 'Lara', 'Material', 'Nora'],
  theme_primaries: ['glados', 'soul', 'blue'],
  theme_surfaces: ['glados', 'slate'],
  timezones: ['Europe/Vienna'],
}

const capabilities: Schemas['ServerCapabilities'] = {
  addin_scopes: [],
  pdm_addin_scopes: [],
  agent_access_enabled: false,
  agent_token_max_lifetime_days: 30,
  agent_read_scopes: [],
  agent_draft_scopes: [],
  currency: 'EUR',
  default_date_format: 'iso',
  default_language: 'enGB',
  default_timezone: 'Europe/Vienna',
  empty_value_placeholder: '-',
  features: {
    calculations: true,
    checklists: true,
    devices: true,
    eplan_data_portal: false,
    production_planning: true,
    sequences: true,
    todos: true,
    time_tracking: false,
    time_tracking_provider_label: null,
  },
  mail_enabled: true,
  mail_attachment_limit_mb: 10,
  maintenance_enabled: false,
  maintenance_message: null,
  office_launcher_enabled: false,
  office_sharepoint_url: '',
  storage_enabled: true,
  token_max_lifetime_days: 365,
}

const numbering: Schemas['NumberingPolicy'] = {
  allow_headless_projects: false,
  cad_items_read_only: false,
  pdm_enabled: false,
  product_number_pattern: 'P{YY}-{####}',
  project_number_pattern: '{YY}-{###}',
  bought_items: {
    auto: true,
    editable: false,
    example: 'B-000123',
    external_pattern: '',
    source: 'internal',
    web_creation_allowed: true,
  },
  made_items: {
    auto: true,
    editable: false,
    example: 'M-000123',
    external_pattern: '',
    source: 'internal',
    web_creation_allowed: true,
    revision: {
      start: 'A',
      separator: '',
      skip_ambiguous_letters: true,
      only_newest_editable: true,
      predecessor_status_web: 'ask',
      field_policy: [],
    },
  },
}

/** What every screen requests, signed in or not. */
export function baseHandlers(signedIn: Schemas['UserResponse'] | null): MockHandler[] {
  return [
    { path: '/public/branding', body: branding },
    { path: '/public/branding/login-video', status: 404 },
    signedIn
      ? { path: '/web/users/me', body: signedIn }
      : { path: '/web/users/me', status: 401, body: { detail: 'Not authenticated', code: 'AuthenticationError' } },
    { path: '/web/production-schedule/auto-plan/status', body: { running: false, run: null } },
    { path: '/web/host/values', body: values },
    { path: '/web/host/capabilities', body: capabilities },
    { path: '/web/host/numbering', body: numbering },
    { path: '/web/announcements/me', body: { banner: null, pending_acknowledgements: [] } },
    { path: '/web/notifications/', body: { items: [], total: 0, unread_count: 0 } },
    // The live event stream: an empty stream that ends at once. The client
    // reconnects quietly, which keeps the footer's connection state online.
    { path: '/web/live/', body: '' },
  ]
}

const author: Schemas['PublicUserResponse'] = {
  id: 1,
  public_id: '00000000-0000-4000-8000-000000000001',
  username: 'avery',
  full_name: 'Avery Example',
  has_avatar: false,
}

function uuid(n: number): string {
  return `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
}

function articleGroup(id: number, name: string, color: string): Schemas['ArticleGroupResponse'] {
  return {
    id,
    public_id: uuid(1000 + id),
    name,
    description: '',
    label_color: color,
    label_font_color: '#ffffff',
    archived: false,
    sort_order: id,
    created: NOW,
    changed: NOW,
    creator_id: 1,
    creator: author,
    changed_by_id: null,
    changed_by: null,
  }
}

export const articleGroups = [
  articleGroup(1, 'Housings', '#2563eb'),
  articleGroup(2, 'Shafts', '#16a34a'),
  articleGroup(3, 'Brackets', '#d97706'),
]

const MADE_ITEMS: [string, string, string, string | null, number, Schemas['MadeItemCatalogueStatus']][] = [
  ['M-000101', 'A', 'Gearbox housing', 'EN AW-6082', 0, 'active'],
  ['M-000102', 'C', 'Drive shaft 40 mm', '42CrMo4', 1, 'active'],
  ['M-000103', 'B', 'Motor bracket left', 'S235JR', 2, 'active'],
  ['M-000104', 'A', 'Motor bracket right', 'S235JR', 2, 'active'],
  ['M-000105', 'B', 'Bearing cover', 'EN AW-6082', 0, 'inactive'],
  ['M-000106', 'D', 'Spacer ring 12 mm', 'POM-C', 1, 'active'],
  ['M-000107', 'A', 'Sensor mount', null, 2, 'replaced'],
  ['M-000108', 'A', 'Cable duct cover', 'S235JR', 0, 'active'],
]

export const madeItems: Schemas['MadeItemResponse'][] = MADE_ITEMS.map(
  ([part_number, revision, article_name, material, group, status], index) => ({
    id: 101 + index,
    public_id: uuid(101 + index),
    part_number,
    revision,
    article_name,
    material,
    status,
    article_groups: [articleGroups[group]!],
    archived: false,
    created: NOW,
    changed: NOW,
    revision_date: '2026-10-15',
    revision_note: null,
    data_source: 'WEB',
    vault_id: null,
    pdm_file_id: null,
    pdm_file_version: null,
    pdm_synced_at: null,
    pdm_sync_state: null,
    pdm_locked_fields: [],
    mass: 1200 + index * 85,
    base_size: null,
    note: null,
    weblink: null,
    successor_item_id: null,
    creator_id: 1,
    creator: author,
    changed_by_id: null,
    changed_by: null,
    bought_item_id: null,
    bought_item: null,
    source_item_id: null,
    pdm_source_item_id: null,
    source_item: null,
    customer_id: null,
    customer_name: null,
    customer_part_number: null,
    customer_revision: null,
    source_label: '',
    source_sublabel: '',
    processes: [],
    edit_version: 1,
  }),
)

export function page<T>(items: T[]): { items: T[]; total: number; skip: number; limit: number | null } {
  return { items, total: items.length, skip: 0, limit: 50 }
}
